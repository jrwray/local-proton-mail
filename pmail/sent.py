"""Was it sent? Look in All Mail, not the Sent folder.

Proton moves whole conversations: archiving a thread takes your sent message out of Sent and your
unsent draft out of Drafts (both land in Archive). So "in Sent" misses mail that went out, and
"gone from Drafts" doesn't mean it was sent. All Mail keeps everything; a message from you without
the \\Draft flag went out. Read-only: folders are opened read-only and bodies are never fetched.
"""

import datetime as dt
import email
import email.header
import email.utils

from pmail import bridge, config

ALL_MAIL = "All Mail"
SENT = "Sent"


def _dec(raw: bytes | None) -> str:
    if not raw:
        return ""
    return str(email.header.make_header(email.header.decode_header(raw.decode("utf-8", "replace"))))


def status(flags) -> str:
    """'draft' or 'sent' for a message from you, by its IMAP flags."""
    names = {f.decode() if isinstance(f, bytes) else str(f) for f in flags}
    return "draft" if "\\Draft" in names else "sent"


def own_addresses(client) -> set[str]:
    """Every address you send from: the sign-in address plus the senders seen in Sent."""
    login, _ = config.load_credentials()
    addrs = {login.lower()}
    client.select_folder(SENT, readonly=True)
    uids = client.search(["ALL"])
    if uids:
        key = b"BODY[HEADER.FIELDS (FROM)]"
        for data in client.fetch(uids, ["BODY.PEEK[HEADER.FIELDS (FROM)]"]).values():
            for _name, addr in email.utils.getaddresses([_dec(data[key]).split(":", 1)[-1]]):
                if addr:
                    addrs.add(addr.lower())
    return addrs


def find(to: str | None = None, subject: str | None = None, since: dt.date | None = None,
         sender: str | None = None) -> list[dict]:
    """Your messages in All Mail (newest last), each marked sent or draft, plus whether Sent shows it."""
    criteria = []
    if to:
        criteria += ["TO", to]
    if subject:
        criteria += ["SUBJECT", subject]
    if since:
        criteria += ["SINCE", since]
    rows = []
    with bridge.connect() as client:
        senders = [sender] if sender else sorted(own_addresses(client))
        client.select_folder(ALL_MAIL, readonly=True)
        uids = sorted({u for s in senders for u in client.search(["FROM", s] + criteria)})
        if not uids:
            return []
        fields = "BODY.PEEK[HEADER.FIELDS (TO SUBJECT DATE MESSAGE-ID IN-REPLY-TO)]"
        for uid, data in client.fetch(uids, ["FLAGS", "INTERNALDATE", fields]).items():
            msg = email.message_from_bytes(data[fields.replace(".PEEK", "").encode()])
            rows.append({
                "uid": uid,
                "when": data[b"INTERNALDATE"],
                "status": status(data[b"FLAGS"]),
                "to": _dec(msg["To"].encode() if msg["To"] else None),
                "subject": _dec(msg["Subject"].encode() if msg["Subject"] else None),
                "message_id": (msg["Message-ID"] or "").strip(),
                "threaded": bool(msg["In-Reply-To"]),
            })
        client.select_folder(SENT, readonly=True)
        for row in rows:
            row["in_sent_folder"] = bool(row["message_id"]) and bool(
                client.search(["HEADER", "Message-ID", row["message_id"]]))
    rows.sort(key=lambda r: r["when"])
    return rows

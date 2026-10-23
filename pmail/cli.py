"""Command line entry point: python -m pmail <command>"""

import argparse
import getpass

from pmail import ai, bridge, config, settings, sync


def cmd_setup(args: argparse.Namespace) -> int:
    config.check_keychain()
    print("Find these in Proton Mail Bridge: click your account, then 'Mailbox details' (IMAP).")
    username = input("Bridge IMAP username: ").strip()
    password = getpass.getpass("Bridge IMAP password (not your Proton password): ")
    config.save_credentials(username, password)
    print("Saved to this device's keychain. Next: python -m pmail check")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    with bridge.connect() as client:
        total = 0
        print(f"{'Folder':40} Messages")
        for _flags, _delim, name in client.list_folders():
            count = client.folder_status(name, ["MESSAGES"])[b"MESSAGES"]
            total += count
            print(f"{name:40} {count}")
        print(f"\nConnected. {total} messages across all folders (labels count each copy).")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    result = sync.run()
    print(f"Done. {result['added']} new, {result['updated']} changed, {result['removed']} deleted. "
          f"{result['total']} emails in {config.ARCHIVE_DIR}")
    return 0


def cmd_range(args: argparse.Namespace) -> int:
    if args.since is not None:
        settings.save({"since": settings.parse_since(args.since)})
    since = settings.load()["since"]
    print(f"Keeping {'all mail' if since is None else 'emails from ' + since + ' on'}. "
          "The next sync applies it.")
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    try:
        result = ai.run(limit=args.limit)
    except KeyboardInterrupt:
        print("Stopped. Run it again to carry on where it left off.")
        return 1
    except RuntimeError as exc:
        raise SystemExit(str(exc))
    print(f"Done. {result['done']} summarized, {result['remaining']} still to do.")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    from pmail import control
    print(control.start())
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    from pmail import control
    print(control.stop())
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    from pmail import control
    s = control.status()
    print(control.describe(s))
    return 0 if s else 1


def cmd_serve(args: argparse.Namespace) -> int:
    from pmail import server
    server.serve(port=args.port, open_browser=not args.no_browser)
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    from pmail.service import Service
    service = Service(summaries=not args.no_summaries)
    service.start()
    print("Watching for new mail. Press Ctrl+C to stop.")
    try:
        while True:
            service._stop.wait(3600)
    except KeyboardInterrupt:
        service.stop()
    return 0


def cmd_fetch_attachment(args: argparse.Namespace) -> int:
    from pmail import attachments
    path = attachments.fetch(args.id, args.name)
    print(f"Saved to {path}. It came from an email: treat it as untrusted and don't run it.")
    return 0


def cmd_draft(args: argparse.Namespace) -> int:
    import sys
    from pmail import drafts
    if args.body is not None:
        body = args.body
    elif args.body_file:
        with open(args.body_file, encoding="utf-8") as handle:
            body = handle.read()
    else:
        body = sys.stdin.read()
    print(drafts.create(body, to=args.to, subject=args.subject or "", cc=args.cc, reply_to_id=args.reply))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pmail", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup", help="save Bridge credentials to this device's keychain").set_defaults(func=cmd_setup)
    sub.add_parser("check", help="connect to Bridge and list folders").set_defaults(func=cmd_check)
    sub.add_parser("sync", help="download new mail and update folders/flags").set_defaults(func=cmd_sync)
    p = sub.add_parser("range", help="show or set which emails to keep: all, today or YYYY-MM-DD")
    p.add_argument("since", nargs="?")
    p.set_defaults(func=cmd_range)
    p = sub.add_parser("summarize", help="summarize personal conversations with the local AI model (resumable)")
    p.add_argument("--limit", type=int, help="stop after this many conversations")
    p.set_defaults(func=cmd_summarize)
    sub.add_parser("start", help="start the app in the background (live sync + summaries)").set_defaults(func=cmd_start)
    sub.add_parser("stop", help="stop the background app").set_defaults(func=cmd_stop)
    sub.add_parser("status", help="is it running, and what is it doing").set_defaults(func=cmd_status)
    p = sub.add_parser("serve", help="open the local page and keep mail and summaries in sync while it runs")
    p.add_argument("--port", type=int, default=7861)
    p.add_argument("--no-browser", action="store_true")
    p.set_defaults(func=cmd_serve)
    p = sub.add_parser("watch", help="live sync in this terminal, without the page")
    p.add_argument("--no-summaries", action="store_true")
    p.set_defaults(func=cmd_watch)
    p = sub.add_parser("fetch-attachment", help="download one attachment into archive/attachments/<id>/")
    p.add_argument("id", help="email id (from index.jsonl or the email's ID line)")
    p.add_argument("name", help="attachment file name, as listed in the email")
    p.set_defaults(func=cmd_fetch_attachment)
    p = sub.add_parser("draft", help="save a draft to Proton Drafts for you to review (never sends)")
    p.add_argument("--reply", metavar="ID", help="reply in the conversation of this email id")
    p.add_argument("--to", action="append", help="recipient (repeat for more); defaults to the sender when replying")
    p.add_argument("--cc", action="append")
    p.add_argument("--subject")
    p.add_argument("--body", help="draft text (or use --body-file, or pipe it in)")
    p.add_argument("--body-file")
    p.set_defaults(func=cmd_draft)
    args = parser.parse_args(argv)
    return args.func(args)

"""The MCP server: protocol basics, read tools, drafts, and the no-send guarantee."""

import io
import json

from pmail import archive, config, drafts, mcp_server


def _msg(mid, thread, date, subject="Hello", body="Hi there", bulk=False, sender="Sam <sam@example.com>"):
    meta = {"id": mid, "proton_id": f"pm-{mid}", "message_id": f"<{mid}@x>", "date": date,
            "from": [sender], "to": ["Alex <alex@example.com>"], "cc": [], "reply_to": [],
            "subject": subject, "refs": [], "bulk": bulk, "attachments": [], "folders": ["INBOX"],
            "flags": [], "thread": thread, "snippet": body[:50]}
    meta["path"] = archive.new_path(meta)
    archive.write_message(meta, body)
    return meta


def _archive():
    msgs = {m["id"]: m for m in [
        _msg("a1", "a1", "2026-10-01T09:00+00:00", "Dinner Friday?", "Are you free for dinner on Friday?"),
        _msg("a2", "a1", "2026-10-02T09:00+00:00", "Re: Dinner Friday?", "Yes, 7pm works.",
             sender="Alex <alex@example.com>"),
        _msg("b1", "b1", "2026-10-03T09:00+00:00", "Weekly deals", "50% off everything", bulk=True,
             sender="Shop <news@example.org>"),
    ]}
    state = archive.empty_state()
    state["messages"] = msgs
    archive.save_state(state)
    archive.write_json(config.ARCHIVE_DIR / "ai" / "a1.json",
                       {"title": "Friday dinner", "summary": "Sam and Alex set dinner for 7pm Friday.",
                        "category": "personal", "action_items": []})
    archive.write_indexes(msgs)
    return msgs


def _call(name, **arguments):
    reply = mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": name, "arguments": arguments}})
    result = reply["result"]
    return result["isError"], result["content"][0]["text"]


def test_initialize_and_list_tools():
    init = mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                              "params": {"protocolVersion": "2025-06-18", "capabilities": {}}})
    assert init["result"]["protocolVersion"] == "2025-06-18"
    assert "tools" in init["result"]["capabilities"]
    assert mcp_server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    tools = mcp_server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    names = {t["name"] for t in tools}
    assert names == {"search_emails", "read_email", "list_threads", "read_thread", "create_draft"}


def test_no_tool_can_send():
    for name, (_, spec) in mcp_server.TOOLS.items():
        assert "send" not in name
        assert "cannot send" in spec["description"] or spec["annotations"].get("readOnlyHint")


def test_search_skips_bulk_unless_asked():
    _archive()
    _, text = _call("search_emails", query="dinner")
    data = json.loads(text)
    assert [e["id"] for e in data["emails"]] == ["a2", "a1"]  # newest first
    assert data["note"] == mcp_server.UNTRUSTED
    assert json.loads(_call("search_emails")[1])["total"] == 2
    assert json.loads(_call("search_emails", include_bulk=True)[1])["total"] == 3
    assert json.loads(_call("search_emails", sender="alex")[1])["total"] == 1


def test_read_email_and_thread_mark_text_untrusted():
    _archive()
    is_error, text = _call("read_email", id="a1")
    assert not is_error
    assert text.startswith(mcp_server.UNTRUSTED)
    assert "Are you free for dinner" in text
    _, thread = _call("read_thread", thread="a1")
    assert "Sam and Alex set dinner" in thread
    assert thread.index("Are you free") < thread.index("7pm works")


def test_list_threads_has_summaries():
    _archive()
    data = json.loads(_call("list_threads", summarized_only=True)[1])
    assert [t["thread"] for t in data["threads"]] == ["a1"]
    assert data["threads"][0]["title"] == "Friday dinner"


def test_bad_ids_are_tool_errors_not_crashes():
    _archive()
    assert _call("read_email", id="nope")[0] is True
    assert _call("read_thread", thread="nope")[0] is True
    assert _call("read_email", wrong="x")[0] is True


def test_create_draft_goes_through_drafts_module(monkeypatch):
    _archive()
    seen = {}
    monkeypatch.setattr(drafts, "create", lambda body, **kw: seen.update(body=body, **kw) or "Draft saved")
    is_error, text = _call("create_draft", body="Sounds good!", reply_to_id="a2")
    assert (is_error, text) == (False, "Draft saved")
    assert seen["reply_to_id"] == "a2"


def test_empty_draft_is_a_tool_error():
    is_error, text = _call("create_draft", body="   ")
    assert is_error and "empty" in text


def test_serve_speaks_one_json_message_per_line():
    _archive()
    lines = [json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
             json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
             "not json",
             json.dumps({"jsonrpc": "2.0", "id": 2, "method": "nope"})]
    out = io.StringIO()
    mcp_server.serve(io.StringIO("\n".join(lines) + "\n"), out)
    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [r.get("id") for r in replies] == [1, None, 2]
    assert replies[1]["error"]["code"] == -32700
    assert replies[2]["error"]["code"] == -32601


def test_serve_survives_a_message_that_is_not_an_object():
    lines = ["[1, 2]", json.dumps({"jsonrpc": "2.0", "id": 3, "method": "ping"})]
    out = io.StringIO()
    mcp_server.serve(io.StringIO("\n".join(lines) + "\n"), out)
    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    assert replies[0]["error"]["code"] == -32600
    assert replies[1] == {"jsonrpc": "2.0", "id": 3, "result": {}}

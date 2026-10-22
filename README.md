# local-proton-mail

Keeps a local, AI-agent-readable copy of a Proton Mail account, synced through
[Proton Mail Bridge](https://proton.me/mail/bridge). Works on Windows and macOS.

The mail itself is saved in `archive/`, which is gitignored: this repo only ever
holds the tool. Each device builds its own copy from Bridge.

## Why local

Your inbox doesn't need to be handed to another company for AI to be useful with it.

- **No third-party mailbox access.** No OAuth grant, no cloud connector, no
  service holding a copy of your mail. It goes from Proton to your disk through
  Proton's own Bridge, and nowhere else.
- **You choose what an AI sees.** Agents read plain files on your machine, so
  you can point a cloud model (Claude, Hugging Face, other APIs) at one
  conversation instead of a whole account, or use a local model and keep
  everything offline.
- **No lock-in.** Plain text and JSONL that any tool, script or future AI can read.
- **Drafts, never sends.** Agents can prepare replies in your Drafts folder; the
  tool has no code that sends mail, so you press send yourself.
- **Open source.** Read every line that touches your mail.

Note: when you ask a cloud AI about an email, the text you give it is sent to
that provider, just like pasting it into a chat. The difference is that you
decide what goes, per question.

## Set up a device (Windows or macOS)

1. Install [Proton Mail Bridge](https://proton.me/mail/bridge) and sign in.
2. Have Python 3.11+ installed. For free local summaries, install [Ollama](https://ollama.com/download)
   and a model: `ollama pull qwen2.5:7b`.
3. Clone this repo and double-click **`Start.bat`** (Windows) or **`Start.command`** (macOS).
   The first run sets everything up by itself (using [uv](https://docs.astral.sh/uv/) if you have it).
4. The page opens at http://127.0.0.1:7861. Paste the IMAP username and password from
   Bridge (Mailbox details), pick a date range, and leave it running while you work.

While it runs, new INBOX mail arrives within seconds, a full pass every few minutes
picks up moves, deletes and label changes, and personal conversations are summarized
one by one in the background (newsletters, receipts, notifications and other automated mail are skipped; anyone you have written to always counts as personal).

### Commands (for terminals and AI agents)

Run from the repo folder: `pmail.cmd <command>` on Windows, `./pmail.sh <command>` on macOS.
Each sets itself up on first use.

```
pmail start                          # run in the background, no window
pmail status                         # running? what is it doing?
pmail stop
pmail sync                           # one sync pass
pmail summarize [--limit N]          # summarize pending conversations now
pmail range today|all|YYYY-MM-DD     # which emails to keep
pmail fetch-attachment <id> "<name>"
pmail draft --reply <id> --body "..."   # saved to Proton Drafts, never sent
pmail mcp                            # MCP server for Claude and other agents (below)
```

Agents: see `archive/AGENTS.md` for the layout and the safety rules.

### Use with Claude (MCP)

`pmail mcp` is a [Model Context Protocol](https://modelcontextprotocol.io) server, so Claude Desktop,
Claude Code and other MCP clients can use the archive directly. It has five tools:

| Tool | What it does |
| --- | --- |
| `search_emails` | Search by words, sender, dates or folder; newsletters left out unless asked |
| `read_email` | One email's header and text |
| `list_threads` | Conversations with their AI title, summary and action items |
| `read_thread` | A whole conversation in order, summary first |
| `create_draft` | Save a draft in Proton Drafts for you to send. There is no send tool. |

Every result that contains email text starts with a reminder that the text is untrusted. The
server reads the local archive and talks to Bridge only for drafts. It has no dependencies
beyond this repo (`pmail/mcp_server.py`, about 250 lines).

Claude Code:

```
claude mcp add proton-mail -- /path/to/local-proton-mail/pmail.sh mcp      # macOS
claude mcp add proton-mail -- C:\path\to\local-proton-mail\pmail.cmd mcp   # Windows
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "proton-mail": { "command": "/path/to/local-proton-mail/pmail.sh", "args": ["mcp"] }
  }
}
```

## How emails are stripped, and why

AI models need the words, not the presentation. Formatting costs tokens,
adds noise to search and confuses chunking, so every email is reduced to
plain text before it is saved. This is the step before chunking, embedding
or putting mail into a RAG index.

- HTML, styling, layout tables, images and invisible preview padding are removed.
- Links are kept as `text (url)`, minus tracking parameters like `utm_*`.
- Quoted copies of earlier replies are cut, since the thread already has them.
- Signatures (after `-- `) and "Sent with Proton Mail" lines are cut.
- Newsletters and automated mail are marked `Bulk: yes` so later AI steps can skip them.
- Attachments are listed by name, type and size, not saved.

The rules live in `pmail/clean.py` with tests in `tests/test_clean.py`.

## AI summaries

Each personal conversation gets a title, short summary, category, action items and
the people, dates and amounts it mentions, in `archive/ai/<thread>.json` and
`threads.jsonl`. Newsletters, notifications, spam and trash are skipped.

- Runs on your machine with [Ollama](https://ollama.com); nothing leaves the computer.
- The model gets no tools: email text in, fixed JSON out. Instructions hidden in an
  email have nothing to act on.
- On a laptop CPU expect a minute or two per conversation; the backlog is worked
  through newest first and resumes where it left off. Smaller models are faster.

## Security

- Listens on 127.0.0.1 only; rejects other Host headers (DNS rebinding) and any change
  that doesn't come from its own page with an `X-Pmail` header.
- The Bridge password lives in the OS keychain, never in a file.
- No code that can send email exists in this repo; CI fails if any appears, or if
  mail, settings, real addresses or keys are ever committed.
- Your local copy is plain text: use full-disk encryption (BitLocker / FileVault) and
  keep it out of cloud-synced folders (the tool warns if it isn't).

## Status

- [x] Bridge connection, download, stripping, date range
- [x] Agent safety rules and repo guards
- [x] Local AI summaries (Ollama)
- [x] Local page with Start.bat / Start.command
- [x] Live sync while running
- [x] Attachments on demand
- [x] Drafts written by agents (never sent)
- [x] MCP server for Claude and other agents
- [ ] Claude API as an optional summary engine

# Changelog

Notable changes per plugin version (`plugins/<plugin>/.claude-plugin/plugin.json`); unprefixed headings are the
`whatsapp` plugin. Back to [AGENTS.md](./AGENTS.md).

## gmail 0.2.0 — 2026-11-05

- **Replies in a thread:** `gmail-send --reply-to <message id> [--all]` answers in the original's thread
  (`In-Reply-To`, `References`, thread id), to its sender or with `--all` to everyone on it, subject "Re: …",
  with the original **quoted below**, as Gmail does (`--no-quote` to leave it out; the quoted text is never
  printed). One Touch ID scan reads that email and sends; `--dry-run` lists the recipients first
  ([ADR 847f76](./docs/architecture/decisions/2026-11-05-847f76-gmail-replies-read-headers-behind-their-own-scan.md)).
  Run `gmail-send login` once more to allow reading the email you reply to.
- **Your signature** is saved from Gmail at sign-in to `~/.gmail-send/signature.html` (editable;
  `gmail-send signature --refresh` fetches it again) and added to every send, reply and draft, under your text
  and above any quote, as Gmail does; `--no-signature` leaves it out.
- `--html -` reads the HTML version from stdin, so no file is needed.
- New guide: [Set up Gmail for Claude on a Mac](./docs/guides/gmail-setup-with-claude.md), written to hand to Claude:
  plugin, connector and deny rules, the OAuth client with links and console search terms, sign-in, signature, tests,
  troubleshooting.
- New guide: [the connector reads, `gmail-send` sends](./docs/guides/gmail-connector-and-gmail-send.md): how the
  two tools work together, the deny rules on the connector's sending tools, and the setup cost.
- `gmail-send logout` no longer asks for Touch ID: it deletes the sealed sign-in and its key from the Mac.

## gmail 0.1.0 — 2026-11-05

- **New plugin, `gmail-send`** ([ADR d38d84](./docs/architecture/decisions/2026-11-05-d38d84-gmail-send-through-the-gmail-api.md)):
  send mail or save a draft (`--draft`) with local attachments (`--file`), an HTML version (`--html`) and cc
  through the Gmail API, with your own OAuth client. Every send and draft needs your Touch ID: the sign-in is
  stored only encrypted to a Secure Enclave key that needs a scan for every use. Attachments only from
  `~/Downloads`, `~/Desktop`, `~/Documents` and `~/Pictures`. Set up with `/gmail-setup`
  ([plugin README](./plugins/gmail/README.md)).

## 0.10.1 — 2026-11-05

- **Repo renamed to claude-comms** ([ADR 2d0dd3](./docs/architecture/decisions/2026-11-05-2d0dd3-rename-repo-to-claude-comms.md)):
  install as `whatsapp@claude-comms`. An existing install moves over with the
  [runbook](./docs/operations/runbook.md#moving-from-whatsapp-claude-to-claude-comms) steps; pairing, allowlist,
  data and the `com.whatsapp-claude.bridge` service are kept.

## 0.10.0 — 2026-10-30

- **Find chats by contact name, number or part of a name:** `wa-send` and `wa-allow` take a saved contact's name,
  a number (country code optional) or part of a name ("Panda" finds "Panda Po"); one match is used and named,
  several are listed and nothing is done
  ([ADR 7e2c9d](./docs/architecture/decisions/2026-10-30-7e2c9d-chat-discovery-contact-names-and-partial-match.md)).
- **1:1 chats get real names:** chats WhatsApp addresses by LID now take the contact saved under the phone number
  (and the reverse), so `wa`, `wa-allow list` and the Touch ID prompt show "Asha", not digits; a name the person
  chose is shown `~Like this`. Existing digit-named chats are renamed when the bridge connects.
- `wa-send --arm` no longer says a Touch ID prompt is coming when the bridge refuses first.

## 0.9.0 — 2026-10-30

- **Armed sends:** `wa-send --arm <chat> [--for 2h] [--times N] "<pattern>"` asks for your Touch ID now, showing
  the whole pattern; later text sends to that chat that fit it (slots `{num}`, `{id}`, `{url}`, `{text}`) go out
  without a prompt, so a message for when a step finishes isn't lost while you're away
  ([ADR 032c66](./docs/architecture/decisions/2026-10-30-032c66-armed-sends-approve-a-pattern-ahead.md)). Held in
  the bridge's memory only; `wa-send --armed` lists them, `--disarm` drops them.
- `wa-send` shows the bridge's message instead of crashing when a refusal isn't JSON.

## 0.8.0 — 2026-10-28

- **Send to any chat:** a send you approve with Touch ID no longer needs the chat on the allowlist first; once
  sent, the chat is allowlisted on this machine and its last 50 messages are fetched
  ([ADR 16abb6](./docs/architecture/decisions/2026-10-27-16abb6-touch-id-send-adds-the-chat.md)), and synced to
  your other machines through your notification chat.
- **Self-chat stays clean:** `#wa` commands also work in notification chats, and the bridge posts them there
  instead of your self-chat ([ADR fc6f0e](./docs/architecture/decisions/2026-10-27-fc6f0e-commands-through-notification-chats.md)).
- Fixed: `direct on` missed 1:1 chats WhatsApp addresses by LID (`…@lid`), often most of them; it now covers
  every 1:1 chat.

## 0.7.0 — 2026-10-28

- **Touch ID for sends:** the bridge asks for your Touch ID before every send to anyone but you, whoever calls it,
  so sends work from `wa -p` and any session, and the API token alone can no longer send
  ([ADR 17d63a](./docs/architecture/decisions/2026-10-27-17d63a-touch-id-send-approval-and-notification-chats.md)).
- **Notification chats:** `#wa notify <group>` for a group of only you (and at most one other account); Claude's
  messages to it send unattended.
- **`wa-send`:** send from any terminal or `!` command; `install.sh approve-test` checks the prompt.
- Needs `swiftc` (Command Line Tools) to build the helper.

## 0.6.0 — 2026-10-27

- **History on add:** adding a chat (phone, `wa-allow`, `add_chat`) fetches its last 50 messages from your phone
  ([ADR a8ea3b](./docs/architecture/decisions/2026-10-27-a8ea3b-history-on-add-add-chat-and-named-prompts.md)).
- **`add_chat`** in `wa`: "start watching <group>" adds a chat after you approve the prompt.
- Send and `add_chat` prompts **name the chat** next to its JID.

## 0.5.0 — 2026-10-24

- `wa` starts in **auto mode** (the guard now allows it); `wa --manual` for prompts on everything.
- Sends to your own "Message yourself" chat go out without asking; sends to others still ask. Downloads don't ask.
- Files can be sent from `~/Downloads`, `~/Desktop`, `~/Documents`, `~/Pictures` and the outbox (`send_from` in
  `config.json`); hidden folders are always refused
  ([ADR f10233](./docs/architecture/decisions/2026-10-24-f10233-auto-mode-self-sends-and-send-folders.md)).
- Fixed: media downloads failed with HTTP 403 (the upstream bridge stripped the CDN signature from the download
  path). Fixed: `list_chats`, `get_chat`, `list_messages` and other read tools failed output validation under mcp
  1.30; every read tool is now called in tests.

## 0.4.1 — 2026-10-24

- Python dependencies refreshed (mcp 1.30, starlette 1.9, anyio 4.15, urllib3 2.8, certifi 2026.10.23); `mcp` held
  below 2.0 until the server is migrated to its renamed API.

## 0.4.0 — 2026-10-24

- **Cursor support removed** ([ADR 3d143d](./docs/architecture/decisions/2026-10-23-3d143d-drop-cursor-support.md)): it could
  only be read-only, and Claude on Haiku is cheap. The bypass guard blocks WhatsApp tools in Cursor again. Clean up
  an old Cursor install with the [runbook](./docs/operations/runbook.md#removing-an-old-cursor-install) steps.
- Renamed back to **whatsapp-claude**: install as `whatsapp@whatsapp-claude`; service label
  `com.whatsapp-claude.bridge` (`install.sh service` removes `com.whatsapp-agent-bridge.bridge`).

## 0.3.2 — 2026-10-24

- `#wa add me` (also `myself`, `self`) allowlists your own "Message yourself" chat by its phone-number and LID
  JIDs; it has no name to match.
- Reinstalling while the bridge runs no longer leaves the service stopped: `install.sh` stops it before swapping
  the binary, waits for launchd, and retries the start.

## 0.3.1 — 2026-10-24

- Cheap models by default: `wa` uses `haiku`, `wa-cursor --cli` uses `composer-2.5`. Override with `--model` or
  `WA_MODEL` / `WA_CURSOR_MODEL`. Guides cover background one-shot runs (`wa -p`, `wa-cursor --cli -p`).

## 0.3.0 — 2026-10-24

- **Cursor support (read-only)**: `install.sh cursor` adds a WhatsApp workspace and a user-level taint guard;
  `wa-cursor` opens it (app or `--cli`). Reading and triage in Cursor; sends blocked (reply from `wa`); after
  WhatsApp is read in a chat, its shell commands and other tools are blocked. Cursor ignores a hook's "ask" in
  auto-run, so the guard only allows or denies. The Claude guard defers to it inside Cursor ([ADR b283a0](./docs/architecture/decisions/2026-10-23-b283a0-cursor-support-with-taint-guard.md)).

## 0.2.1 — 2026-10-24

- Renamed the repo and plugin source to **whatsapp-agent-bridge** (it serves Claude Code and, next, Cursor). Install
  as `whatsapp@whatsapp-agent-bridge`; the old GitHub URL redirects. The background service label becomes
  `com.whatsapp-agent-bridge.bridge`; `install.sh service` removes the old one.

## 0.2.0 — 2026-10-24

- The allowlist is shared by every machine through your WhatsApp "Message yourself" chat: `#wa add|remove|direct`
  typed on the phone or posted by `wa-allow`; applied once per machine, with a ✅ ⏳ ❓ ❌ reaction; no file sync
  ([ADR f28675](./docs/architecture/decisions/2026-10-23-f28675-allowlist-carried-in-whatsapp-self-chat.md)).
  Reinstall with `/wa-setup` on each machine.

## 0.1.0 — 2026-10-23

- Hardened fork of lharries/whatsapp-mcp: loopback-only, token-authenticated bridge API; outbox-only media
  sends; path sanitising; no message text in logs; current whatsmeow ([ADR de419c](./docs/architecture/decisions/2026-10-23-de419c-fork-and-harden-whatsapp-mcp.md)).
- Chat allowlist gating storage, downloads and sends ([ADR e302a3](./docs/architecture/decisions/2026-10-23-e302a3-allowlist-gates-content-and-sends.md)).
- `wa` session, bypass guard hook, `/wa-setup`, triage skill, `digest` tool, pairing-code login, launchd service
  ([ADR 8f4095](./docs/architecture/decisions/2026-10-23-8f4095-dedicated-session-and-bypass-guard.md)).

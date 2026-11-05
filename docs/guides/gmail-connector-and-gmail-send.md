# Gmail: the connector reads, `gmail-send` sends

Back to [AGENTS.md](../../AGENTS.md). Plugin: [gmail README](../../plugins/gmail/README.md). Decisions:
[ADR d38d84](../architecture/decisions/2026-11-05-d38d84-gmail-send-through-the-gmail-api.md),
[ADR 847f76](../architecture/decisions/2026-11-05-847f76-gmail-replies-read-headers-behind-their-own-scan.md).
Threats: [security model § Gmail](../architecture/security-model.md#gmail).

Email from Claude Code uses two tools, each with one job and its own access control:

| | **Gmail connector** (claude.ai, hosted) | **`gmail-send`** (this repo's `gmail` plugin, on your Mac) |
|---|---|---|
| Job | **read**: search, list, open messages and threads, labels | **send**: new email, draft, reply in a thread |
| Signs in as | your Google account, through claude.ai (`/mcp`) | your Google account, through **your own** OAuth client |
| Can read mail | yes, all of it | only the one email being answered (to thread and quote it) |
| Can send | technically yes; **blocked by deny rules** (below) | yes: the only way mail goes out |
| Approval | none needed to read | **one Touch ID scan per send, draft or reply** (the sign-in is sealed to the Secure Enclave) |
| Attachments | n/a (sending is blocked) | read straight from disk (Downloads, Desktop, Documents, Pictures), byte-for-byte |
| Runs where | Anthropic's servers | this Mac only; nothing to the model but what you pass it |

## How a session uses them together

1. **Context:** the connector finds and reads mail (`search_threads`, `get_thread`, `get_message`). No prompts.
2. **Reply:** take the message id from step 1 and run `gmail-send --reply-to <id> [--all] "<text>"`. One scan:
   it reads that email itself (threading headers and the text to quote, which it never prints) and sends in the
   thread, with your signature, quoting the original. `--dry-run` shows the recipients first.
3. **New email or draft:** `gmail-send <to> -s "<subject>" [--file …] [--html - | --html <file>] [--draft] "<text>"`.
4. **Never** send, reply, forward or draft through the connector: those tools are denied (below), so an attempt
   fails at Claude Code before reaching Gmail.

Why not do everything with one tool:

- **Connector only:** attachments would go through the model as base64 (slow; one wrong character corrupts the
  file silently), threading headers aren't exposed in its normal formats, and nothing asks before a send.
- **`gmail-send` only:** every lookup for context would cost a Touch ID scan, or need a second, unlocked read
  sign-in on disk, which adds nothing over the connector's own access.

## Access controls

**1. Deny rules on the connector's sending tools.** In `~/.claude/settings.json` (your user settings, not this
repo), `permissions.deny` lists:

```json
"deny": [
  "mcp__claude_ai_Gmail__send_message",
  "mcp__claude_ai_Gmail__reply",
  "mcp__claude_ai_Gmail__forward",
  "mcp__claude_ai_Gmail__create_draft",
  "mcp__claude_ai_Gmail__update_draft"
]
```

Claude Code refuses these tools in every session and every permission mode, bypass included. The connector's
reading tools keep working. This closes threat [G8](../architecture/security-model.md#gmail): without it, the
connector sends as you with no approval. Undo by deleting the entries. Deny rules don't affect the Gmail web app or
your phone.

**2. The Touch ID lock on `gmail-send`.** Its Google sign-in exists only encrypted to a Secure Enclave key that
needs your fingerprint for every use; macOS enforces it, so no process can send as you through it without a scan.
One scan per send, draft or reply; none for `setup`, `login`, `status`, `logout` or `--dry-run` of a new email.

**3. What `gmail-send` may read and attach.** Only the email named by `--reply-to`, within that reply's scan;
attachments and `--html` files only from the send folders.

## Setting it up (and what it costs)

- **Connector:** `/mcp` → claude.ai Gmail → sign in. Add the deny rules above.
- **`gmail-send`:** install the `gmail` plugin and follow its [README](../../plugins/gmail/README.md): create an OAuth
  client, `gmail-send setup <file>`, `gmail-send login`.

**The setup cost is real.** `gmail-send` signs in with an OAuth client that **you** create in Google Cloud (about 5
minutes, once per Google account). This repo is public and never ships a client: a company's client in a public repo
would expose that company's app to anyone. Ways to lighten it for a team:

| Option | Each person does | Trade-off |
|---|---|---|
| Everyone creates their own client | the Google Cloud steps, then `setup` + `login` | most setup; nothing shared |
| One team client, shared privately (a private repo or password manager, never this repo) | `gmail-send setup <shared file>` + `login` | the client is shared within the team; each login is still personal and Touch ID-locked |
| An IT-owned client for the organisation | `setup` + `login` | cleanest at scale; needs IT |
| Connector only | `/mcp` | no setup, but no safe attachments and no Touch ID: keep its send tools denied and send nothing |

A Workspace account's own client should use the **Internal** audience (no review, no expiry); a personal account
uses **External**, published to *In production* to avoid the 7-day expiry.

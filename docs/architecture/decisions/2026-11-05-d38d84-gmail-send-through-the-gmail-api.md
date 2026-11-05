# 2026-11-05-d38d84 — Gmail channel: `gmail-send` through the Gmail API, Touch ID before mail to others

- **Status:** accepted
- **Date:** 2026-11-05
- **Deciders:** Utkarsh Upadhyay
- **Scope:** gmail
- **Supersedes / Amends:** —

## Context
The owner wants to send email from Claude Code the way `wa-send` sends WhatsApp, including a local file as an
attachment. A hosted Gmail connector can send, but it takes attachments only as base64 inside the tool call, so the
assistant would have to copy the whole file through its own context: slow, costly, and one wrong character
corrupts the file without anything noticing. Email has an official API, so unlike WhatsApp it needs no linked
device, bridge or long-running process ([ADR 2d0dd3](./2026-11-05-2d0dd3-rename-repo-to-claude-comms.md)).

## Decision
A separate `gmail` plugin with one command, **`gmail-send`**, a standard-library Python script run by `uv`:

- **Send:** builds the message with Python's `email` package, reading attachments from disk, and posts it to the
  Gmail API's upload endpoint for `users.messages.send`. The mail appears in the owner's Sent folder.
- **Sign-in:** the owner's own Google Cloud OAuth client of type *Desktop app*; `gmail-send login` runs the
  installed-app flow (loopback redirect on 127.0.0.1, PKCE, `state`) for the scopes `gmail.send`, `openid` and
  `email` only, so the tool can send but never read mail. The refresh token goes to the macOS **Keychain**
  (written through `security -i` on stdin, never on a command line); the client file and the signed-in address
  are kept in `~/.gmail-send` (0700, files 0600).
- **Approval:** before any send with a recipient other than the signed-in address, the **Gmail for Claude** Touch
  ID helper asks the owner, naming every recipient, the subject, each attachment with its size, and the start of
  the text. Biometrics only, no password field; a decline, a timeout or a missing helper means no send. Mail only
  to yourself sends straight away. The helper is the WhatsApp plugin's 29-line helper copied under the gmail
  plugin, since an installed plugin can't read files outside its own folder.
- **Attachments only from the send folders:** `~/Downloads`, `~/Desktop`, `~/Documents`, `~/Pictures` by default,
  resolved through symlinks, refusing any hidden path component, 25 MB in total.
- `gmail-send` prints what it will send (from, to, cc, subject, attachments with size and SHA-256, the text)
  before asking or sending; `--dry-run` stops there.

## Assumptions
- 1. The owner can create an OAuth client and their Google Workspace lets them sign in to it (unverified until
     the first `gmail-send login`, 2026-11-05).
- 2. `gmail.send` alone is enough: the tool never needs to read, search or draft mail (the hosted connector covers
     reading).
- 3. Touch ID approval is checked in the `gmail-send` process. It stops an assistant from sending to others
     without the owner seeing the message; it is not a boundary against code running as the owner, which can read
     the refresh token from the Keychain or use the hosted connector, which sends without approval.

## Reversal triggers
- Revisit if the Workspace blocks the sign-in (Assumption #1): fall back to the macOS Mail app, or ask IT to
  approve the client.
- Revisit if mail to others must be approved even against code running as the owner (Assumption #3): bind the
  refresh token in the Keychain to a signed helper that asks for Touch ID before releasing it, and disconnect the
  hosted connector's send.

## Consequences
- Attachments arrive byte-for-byte as on disk, and the assistant never handles their content.
- One-time setup per machine: create the OAuth client, `gmail-send setup <client file>`, `gmail-send login`.
- Google may expire the refresh token (7 days for a client in *Testing* status with an external user type);
  `gmail-send login` again. An *Internal* client in the owner's Workspace doesn't expire this way.
- The gmail plugin shares no runtime with WhatsApp: a dropped WhatsApp pairing can't block mail.

## Alternatives considered
- Hosted Gmail connector with base64 attachments: unreliable for anything but tiny files (see Context).
- SMTP with an app password: Workspace admins usually disable app passwords, and it stores a long-lived password.
- macOS Mail app through AppleScript: depends on Mail being configured and running; harder to control.
- Add Gmail to the WhatsApp bridge: couples the channels ([ADR 2d0dd3](./2026-11-05-2d0dd3-rename-repo-to-claude-comms.md)).
- Keychain-bound token from day one: stronger, but more code before the simple path is proven. Rejected under
  Assumption #3 for now.

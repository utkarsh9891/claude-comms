# 2026-11-05-d38d84 — Gmail channel: `gmail-send` through the Gmail API, every send behind Touch ID

- **Status:** amended by 847f76, c41e0b
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

Mail is riskier than WhatsApp: it reaches anyone, carries files, and is hard to take back. The owner's rule is that
**no mail leaves without their Touch ID**, and that the rule must hold against any process on the Mac, not only
against an assistant using the tool as intended.

## Decision
A separate `gmail` plugin with one command, **`gmail-send`**, a standard-library Python script run by `uv`, and a
small Swift helper, **Gmail for Claude**:

- **Send or draft:** builds the message with Python's `email` package, reading attachments from disk, and posts it
  to the Gmail API upload endpoint for `users.messages.send`, or `users.drafts.create` with `--draft` (the owner
  checks and sends a draft from Gmail).
- **Sign-in:** the owner's own Google Cloud OAuth client of type *Desktop app*, never stored in this repo;
  `gmail-send login` runs the installed-app flow (loopback redirect on 127.0.0.1, PKCE, `state`) for the scopes
  `gmail.compose`, `openid` and `email`. `gmail.compose` sends and creates drafts and can't read the inbox;
  `gmail.send` alone can't create drafts.
- **Every send and draft needs Touch ID, enforced by the hardware:** the refresh token is handed to the helper on
  stdin and stored only encrypted (ECDH + AES-GCM) to a **Secure Enclave key** created with
  `.biometryCurrentSet` and `.privateKeyUsage`. Using that key needs a Touch ID scan; no password fallback, and
  enrolling another finger invalidates it. `gmail-send` asks the helper to unlock the token for each send, with a
  prompt naming every recipient ("you" for the owner), the subject, each attachment with its size, the start of
  the text and whether there is an HTML version; the one-hour access token it gets is used once and never stored.
  Mail to yourself asks too.
- **Attachments only from the send folders:** `~/Downloads`, `~/Desktop`, `~/Documents`, `~/Pictures` by default,
  resolved through symlinks, refusing any hidden path component, 25 MB in total; the same for an `--html` file.
- `gmail-send` prints what it will send (from, to, cc, subject, attachments with size and SHA-256, the text)
  before asking; `--dry-run` stops there.
- **Other ways to send as the owner are closed separately:** a hosted Gmail connector's send, reply, forward and
  draft tools are denied in the owner's Claude Code settings (deny rules hold in every permission mode), or the
  connector is disconnected.

## Assumptions
- 1. The owner's Workspace lets their own Internal OAuth client sign in (verified 2026-11-05 with a test send).
- 2. An ad-hoc-built helper can keep a Secure Enclave key that needs Touch ID for every use, without an Apple
     developer signature (verified 2026-11-05: decrypts after a scan; with prompts forbidden it fails with
     "User interaction is required").
- 3. `gmail.compose` is enough: the tool never needs to read or search mail (the hosted connector covers reading).

## Reversal triggers
- Revisit if the Workspace starts blocking the client (Assumption #1): ask IT to allow it, or the macOS Mail app.
- Revisit if macOS stops allowing Secure Enclave keys for unsigned tools (Assumption #2): sign the helper, or keep
  the token in a Keychain item bound to it.
- Revisit if reading mail is wanted (Assumption #3): that brings untrusted text in and needs its own ADR.

## Consequences
- Attachments arrive byte-for-byte as on disk, and the assistant never handles their content.
- No process can send as the owner through this sign-in without a Touch ID scan the owner approves. A process
  running as the owner can still show a misleading prompt by calling the helper itself; the owner reads what they
  approve.
- One-time setup per machine: create the OAuth client, `gmail-send setup <client file>`, `gmail-send login`. The
  sign-in must be repeated after fingerprints change, after `logout`, or if Google revokes it. `logout` needs no
  scan: it deletes the sealed sign-in and its key; revoking at Google is the owner's step on Google's page.
- Every send costs one scan, mail to yourself included.
- The gmail plugin shares no runtime with WhatsApp: a dropped WhatsApp pairing can't block mail.

## Alternatives considered
- Hosted Gmail connector with base64 attachments: unreliable for anything but tiny files (see Context), and sends
  without approval.
- Touch ID checked only inside `gmail-send`, the token in a plain Keychain item: any process running as the owner
  could read the token and send without a prompt. Rejected: fails the owner's rule.
- Keychain item with a biometric access control: needs the data-protection keychain and an app signature with a
  team ID, which an ad-hoc-built helper doesn't have.
- `gmail.send` only: can't create drafts.
- SMTP with an app password: Workspace admins usually disable app passwords, and it stores a long-lived password.
- macOS Mail app through AppleScript: depends on Mail being configured and running; no per-send approval.
- Add Gmail to the WhatsApp bridge: couples the channels ([ADR 2d0dd3](./2026-11-05-2d0dd3-rename-repo-to-claude-comms.md)).

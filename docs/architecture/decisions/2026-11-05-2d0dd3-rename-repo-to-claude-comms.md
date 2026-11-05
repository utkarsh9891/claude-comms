# 2026-11-05-2d0dd3 — Rename the repo to claude-comms; one plugin per channel

- **Status:** accepted
- **Date:** 2026-11-05
- **Deciders:** Utkarsh Upadhyay
- **Scope:** repo
- **Supersedes / Amends:** —

## Context
The repo and its marketplace were named **whatsapp-claude** because WhatsApp was the only channel. An email
channel is next: sending mail with a local file attached, which a hosted Gmail connector can't do without the
assistant copying the file through its own context as base64. Email has an official API, so it needs no
long-running bridge, no linked device and no dedicated session; it shares only the approval model (Touch ID before
a send to someone else) and the command shape of `wa-send`.

## Decision
Rename the GitHub repo, the local checkout and the marketplace to **claude-comms**. Each channel is its own plugin
in this marketplace: `whatsapp` today (installed as `whatsapp@claude-comms`), an email plugin next, with its own
ADR. Channels share the repo's rules and may reuse the Touch ID helper, but not each other's runtime: a channel
never depends on another channel's bridge or session.

What keeps its name, because it is WhatsApp-specific and renaming it would restart the paired service for no gain:
the `whatsapp` plugin and its commands (`wa`, `wa-send`, `wa-allow`, `/wa-setup`), the launchd label
`com.whatsapp-claude.bridge`, and `~/.whatsapp-mcp`.

## Assumptions
- 1. An email channel will be added to this repo (planned 2026-11-05).
- 2. The email channel needs no long-running process and shares no runtime state with the WhatsApp bridge.
- 3. GitHub keeps redirecting `utkarsh9891/whatsapp-claude` to the renamed repo, so existing clones and
     marketplace entries keep working until they are updated.

## Reversal triggers
- Revisit if no second channel lands (Assumption #1): the name can return to whatsapp-claude.
- Revisit if the email channel turns out to need the bridge (Assumption #2): then one plugin may fit better than two.

## Consequences
- Installs change from `whatsapp@whatsapp-claude` to `whatsapp@claude-comms`: each machine removes the old
  marketplace, adds the new one and reinstalls the plugin. Runtime files under `~/.whatsapp-mcp` don't move, and
  pairing, allowlist and data are kept.
- WhatsApp stays independent of email: a dropped WhatsApp pairing can't block a mail send, and the `wa` session's
  guard files are untouched.
- Older ADRs and CHANGELOG entries keep the old name; they record what was true then.

## Alternatives considered
- Keep the name and add email anyway: the name would misdescribe the repo. Rejected under Assumption #1.
- Add email to the WhatsApp bridge and `wa` session: couples two channels' failures and widens a deliberately
  narrow session. Rejected under Assumption #2.
- A separate repo for email: duplicates the CI, doc rules and Touch ID helper for a small send command.
- Also rename the launchd label and `~/.whatsapp-mcp`: needs a service restart and migration on every machine for
  a cosmetic change.

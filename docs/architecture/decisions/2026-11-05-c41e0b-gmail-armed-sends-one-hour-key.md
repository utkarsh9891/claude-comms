# 2026-11-05-c41e0b — Gmail armed sends: approve a pattern with one scan, send matching mail for up to an hour

- **Status:** accepted
- **Date:** 2026-11-05
- **Deciders:** Utkarsh Upadhyay
- **Scope:** gmail
- **Supersedes / Amends:** amends [2026-11-05-d38d84](./2026-11-05-d38d84-gmail-send-through-the-gmail-api.md)

## Context
Every `gmail-send` send needs a Touch ID scan (ADR d38d84). A message meant for when a long step finishes ("build
done", "report ready") is lost if the owner isn't at the Mac. WhatsApp solves this with armed patterns held by its
bridge ([ADR 032c66](./2026-10-30-032c66-armed-sends-approve-a-pattern-ahead.md)); Gmail has no bridge, and the owner
wants no background process and no extra step: one scan to arm, nothing per matching send.

## Decision
- `gmail-send --arm <to> [--cc …] -s "<subject pattern>" [--for 45m] [--times N] "<text pattern>"` asks for **one
  Touch ID scan** whose prompt shows the recipients, both patterns whole, the count, the window, what each slot may
  hold, and "no files, no HTML".
- The scan mints Google's **one-hour access key**, stored with the pattern in `~/.gmail-send/armed.json` (0600,
  under a file lock). **The sealed sign-in never leaves the lock**: only the short-lived key is stored, and Google
  ends it within the hour whatever happens to the file. The window is at most that hour (`--for`, default the
  key's life minus two minutes); longer means arming again.
- A send uses an armed pattern only if it is a **new plain email** (no attachment, no HTML, not a draft, not a reply)
  to **exactly** the armed To and Cc, and its whole subject and text match. Each use counts against `--times`
  (default 1, at most 20); a use is given back if Google refuses the send. Entries are deleted, key included, when
  their uses or window run out. Anything else asks for Touch ID as usual.
- Patterns are WhatsApp's: fixed text plus `{num}`, `{id}`, `{url}`, `{text}`; `{{`/`}}` literal; at most 150
  characters each, no control or text-direction characters, and the two together need some fixed text.
- `gmail-send --armed` lists them (never the key); `gmail-send --disarm [<id>]` drops them with no scan.
- The signature is added to armed mail as to any other (it is the owner's own text, not part of the pattern).

## Assumptions
- 1. Google's access keys for this client live one hour (`expires_in` 3599 s, 2026-11-05).
- 2. The owner accepts that, while a pattern is armed, any process running as the owner could read the stored key
     and send **any** mail as the owner until the key expires (at most an hour), not only mail that fits the
     pattern (owner, 2026-11-05).

## Reversal triggers
- Revisit if a longer window is needed: the only scan-free way is storing the full sign-in, which this ADR rejects.
- Revisit if Assumption #2 stops holding: then armed sends need a separate process that holds the key in memory
  and enforces the pattern, as the WhatsApp bridge does.

## Consequences
- Unattended notifications by email, one scan per hour of arming.
- `armed.json` is a live credential for up to an hour; `--disarm` deletes it at once (Google still honours the key
  until it expires; revoking it would revoke the whole sign-in).

## Alternatives considered
- Store the full sign-in for longer windows (up to 3 h asked for): anything copying it could send as the owner
  indefinitely. Rejected.
- Renew the key with a scan each hour of a longer window: an extra step the owner didn't want.
- A background process holding the key in memory and enforcing the pattern: rejected by the owner (no extra
  process); the trade-off is Assumption #2.

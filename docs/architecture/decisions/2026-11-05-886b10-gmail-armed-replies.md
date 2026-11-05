# 2026-11-05-886b10 — Gmail armed replies: read the email at arming, store the reply's context with the send-only key

- **Status:** accepted
- **Date:** 2026-11-05
- **Deciders:** Utkarsh Upadhyay
- **Scope:** gmail
- **Supersedes / Amends:** amends [2026-11-05-c41e0b](./2026-11-05-c41e0b-gmail-armed-sends-one-hour-key.md)

**Implementation: not built yet.** This ADR is the complete design and test plan, agreed so the build needs no
further discussion. Until it is built, a reply (`--reply-to`) always asks for one Touch ID scan, armed or not.

## Context
Armed sends ([c41e0b](./2026-11-05-c41e0b-gmail-armed-sends-one-hour-key.md)) cover new plain emails only. A reply
can't use them: it must read the email it answers (thread id, `Message-ID`/`References`, recipients for reply-all,
and the text to quote; [ADR 847f76](./2026-11-05-847f76-gmail-replies-read-headers-behind-their-own-scan.md)), and
the armed key is deliberately limited to `gmail.compose`, which can't read mail. The owner wants a reply prepared
now and sent later without a scan (e.g. "reply-all with the result when the job finishes").

Settled while designing armed sends, and binding here:

1. **One Touch ID scan to arm, nothing per matching send.** No background process.
2. **The window is at most one hour** (Google's access-key lifetime); not shortened, not extended. Longer needs
   arming again.
3. **The stored key is send-only** (`gmail.compose`), checked against Google's answer; arming refuses a broader key.
4. **The full sign-in never leaves the Secure Enclave lock**, and is never stored in the clear for a window.
5. **A reply prompt names the email and the rule** ("its sender" / "everyone on it"), not the people: the
   recipients are only known after the email is read (same as one-scan replies, ADR 847f76).
6. **Quote by default, signature by default**, as for every reply; `--no-quote` reads headers only.

## Decision

### Command

```text
gmail-send --arm --reply-to <Gmail message id> [--all] [--no-quote] [--times N] [--for ≤1h] "<text pattern>"
```

- No subject pattern (the subject is the original's "Re: …"), no `--to`/`--cc` (recipients come from the
  original, as for a reply), no files, no HTML, no drafts.
- Text pattern: the armed-send slots (`{num}`, `{id}`, `{url}`, `{text}`, `{{ }}`), at most 150 characters, no
  control or text-direction characters, must have fixed text.
- `--times` 1–20 (default 1); `--for` at most 1 h (default: the key's life minus two minutes).

### Arming (one scan)

1. Validate everything first (id shape `GMAIL_ID`, pattern, times, window, signed in, `gmail.readonly` granted
   unless `--no-quote`); refuse before any scan.
2. Prompt (macOS: "Gmail for Claude is trying to …"):
   `send N replies without asking, within <span>, to email <id>, to its sender|everyone on it[, quoting it];
   text "<pattern>" (<slot meanings>); no files, no HTML`.
3. **One unlock** of the sealed sign-in (`unlock_token`), then **two refreshes from that same refresh token**:
   - a full key, used **once**, in memory, to read the original (`lookup_original`: `format=raw` to quote,
     `format=metadata` with `--no-quote`), then discarded;
   - a key with `scope=gmail.compose`, checked like `access_key(..., scope=...)`, which is the one stored.
4. Compute what the reply needs now, exactly as a live reply would: `reply_recipients(orig, me, all)`,
   `reply_subject(orig.subject)`, `In-Reply-To` = `Message-ID`, `References`, thread id, and (unless
   `--no-quote`) the quote text/HTML and `quote_line` attribution.
5. Store one entry in `armed.json` (0600, under the existing lock), `kind: "reply"`:
   `id, kind, msg_id, all, quote, to, cc, subject, thread, message_id, references, quote_line, quote_text,
   quote_html, text (pattern), left, until, inflight, key`.
6. Print a summary like `--dry-run` (To, Cc, subject, thread, "Quoting: the original (N lines; not shown)"),
   so the session sees who it will go to. The quoted text is never printed.

### Sending (no scan)

`gmail-send --reply-to <id> [--all] [--no-quote] "<text>"` uses an armed reply only when **all** hold:
same `msg_id`, same `--all` and quote choice, no `--to`/`--cc`/`-s`/files/HTML/`--draft`, and the whole text
matches the pattern. Then: take a use (in-flight tracking as for armed sends), build the message from the stored
context with `compose(text, None, signature, stored quote)` and `build_message(..., in_reply_to, references)`,
send it through the multipart upload with the stored thread id and the stored send-only key. On a refusal from
Google, give the use back. Anything else falls through to the normal one-scan reply. `--dry-run` shows the
match without using it.

### Lifetime

Entries end like armed sends: after `--times` uses or at `until`; the entry, its key **and the stored quote** are
deleted then, or by `--disarm`. `--armed` lists reply entries as
`<id>  reply to <msg_id> (sender|all, quoting)  text "<pattern>"  N left, until HH:MM` (never the key or quote).

## Assumptions
- 1. Google issues several access keys from one refresh token in one go, including a narrower one (verified for
     the narrow key on 2026-11-05; the two-key sequence is checked by the first live test below).
- 2. The original doesn't change in a way that matters within the hour (its headers don't; a reply quotes what
     was read at arming).
- 3. The owner accepts that one email's headers and quoted text sit in `armed.json` (0600) for at most the window.

## Reversal triggers
- Revisit if Google refuses two refreshes in a row or the narrowed key (Assumption #1): then arming refuses, as
  armed sends already do for a broader key.
- Revisit if a stored quote on disk is unacceptable (Assumption #3): arm with `--no-quote` only.

## Consequences
- Prepared replies go out unattended, in the thread, quoted, signed, for up to an hour.
- `armed.json` holds, while armed, the send-only key **and** one email's headers and quoted text. Security model
  G10 gains: "an armed reply stores the original's headers and quote for the window; deleted with the entry".
- One more branch in `send()`: replies check armed entries before asking for the scan.

## Build plan

Code (`plugins/gmail/bin/gmailsend.py`, `bin/gmail-send`):

1. `unlock_keys(reason, scopes_list)`: one `unlock_token`, then one refresh per requested scope (`None` = full);
   reuse `access_key`'s scope check. Arming replies uses `[None, COMPOSE_SCOPE]`.
2. `arm_reply(msg_id, reply_all, quote, text_pattern, for_value, times, keys=unlock_keys, get=http_get_json,
   clock, out)`: steps 1–6 above; shares validation and storage with `arm`.
3. `take_armed_reply(msg_id, reply_all, quote, text)`; extend `_settle`/`give_back` (already id-based).
4. In `send()`: when `reply_to` and no `--to/--cc/-s`, files, HTML or draft, try `take_armed_reply` **before**
   the scan; on a match, build from the stored context and skip `lookup_original`.
5. `--armed` prints reply entries; `status` counts them.
6. CLI: `--arm --reply-to …` (positional text only; refuse `-s`, `--to`, `--cc`, `--file`, `--html`, `--draft`).

Docs: README "Armed sends" (+ a reply example), CHANGELOG (gmail 0.4.0), plugin version 0.4.0, security model G10
row and residual risk, module.yaml interface line, the connector guide's one-line note, and this ADR's
"Implementation" line removed.

## Test plan

Unit (`plugins/gmail/tests`, stand-ins for Google and the helper, no network):

- arming refuses before any scan: bad id, bad pattern, `--times` 0/21, `--for` > 1 h, missing read permission
  (unless `--no-quote`), `-s`/`--to`/`--cc`/`--file`/`--html`/`--draft` given;
- one unlock, two refreshes: the full key reads the original, the stored key is the `gmail.compose` one, a broader
  stored key is refused and nothing is stored;
- prompt text: names the email, the rule (sender/everyone), "quoting it", the pattern, slot meanings, "no files,
  no HTML";
- stored entry: `kind: reply`, recipients/subject/thread/headers from the original, quote present (absent with
  `--no-quote`), file 0600, `--armed` shows neither key nor quote;
- a matching reply sends with **no scan**: multipart with the thread id, `In-Reply-To`/`References`, "Re:"
  subject, recipients as computed at arming, signature above the quote, quote byte-identical to what was read;
- anything else asks: different id, different `--all`/quote choice, text not matching, `--to`/`--cc`/`-s`/file/
  HTML/draft present;
- uses and lifetime: `--times` counted; a refused send gives the use back; expiry and `--disarm` delete the entry
  **and its stored quote**; `--dry-run` doesn't use it.

Live (one Touch ID scan in total):

1. `gmail-send --arm --reply-to <id of a test email to yourself> --for 15m "Armed reply {id}"` → one prompt.
2. Check the stored key: `tokeninfo` reports only `gmail.compose`.
3. `gmail-send --reply-to <same id> "Armed reply live-1"` → **no prompt**; Gmail shows it in the same thread,
   quoted, with the signature; `armed.json` is gone afterwards.

## Alternatives considered
- Read the original at send time: needs a key that can read mail on disk for the window. Rejected (decision 3).
- Store the full sign-in for the window: rejected for armed sends (c41e0b), same here.
- A second scan at send time: defeats arming.
- Let `--to`/`--cc` override in armed replies: more combinations to match and test for little use; can be added
  later.

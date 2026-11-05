# 2026-11-05-847f76 — Gmail replies in a thread, quoting the original: read that one email behind its own Touch ID scan

- **Status:** accepted
- **Date:** 2026-11-05
- **Deciders:** Utkarsh Upadhyay
- **Scope:** gmail
- **Supersedes / Amends:** amends [2026-11-05-d38d84](./2026-11-05-d38d84-gmail-send-through-the-gmail-api.md)

## Context
A reply sent with `gmail-send` and a hand-made "Re:" subject landed outside the original thread, for the owner and
for the recipients. Threading needs the original's `Message-ID` (for `In-Reply-To` and `References`) and its Gmail
thread id; a reply-all also needs its From, To and Cc. The owner also wants replies to carry the original quoted
below, as Gmail does, so readers outside Gmail see the history: **always, unless asked not to**. ADR d38d84 assumed
the tool would never read mail (its Assumption #3) and said reading would need its own ADR. The owner wants the
lookup inside `gmail-send`, so the calling session doesn't have to dig headers or text out of another tool, and
agreed that reading mail *for context* stays with a hosted connector, not `gmail-send`.

## Decision
- `gmail-send --reply-to <Gmail message id> [--all] [--no-quote]` reads **only that one email**: the whole message
  (`format=raw`, scope **`gmail.readonly`**) to thread and quote it, or with `--no-quote` its headers only
  (`format=metadata`).
- The read unlocks the sign-in like any send: **its own Touch ID scan**, with a prompt naming the message id and
  saying nothing is sent. Sending (or `--draft`) then asks again, now naming the recipients found, the original's
  subject and sender, and that it is quoted. Two scans per reply: the recipients of a reply-all aren't known until
  the original is read, and the send prompt must name every recipient.
- **Quoting by default**, as Gmail does: "On <date>, <sender> wrote:" and the original's text with `>` in the
  plain version; Gmail's `gmail_quote` markup around the original's HTML (or its escaped text) in the HTML version,
  so Gmail folds it behind "•••". An HTML-only original is quoted as text too.
- **The quoted text is never printed.** It goes into the reply as written; the summary says only that it is
  quoted and how many lines. Other people's text doesn't reach the session that runs `gmail-send`.
- Recipients follow Gmail: Reply-To, else From; a reply to your own email goes to its To; `--all` adds the
  original To and Cc; the owner is left out unless nobody else is on the thread. `--to`/`--cc` replace them; `-s`
  replaces "Re: <subject>".
- The message carries `In-Reply-To` and `References`, and goes up with the thread id (multipart upload).
- Header text reused in a subject or shown in a prompt has line breaks, control and bidi characters removed.
- **The owner's Gmail signature** is added to every send, reply and draft, as Gmail does: under the owner's text,
  above any quote; `--no-signature` leaves it out. It is read from the owner's own send-as settings with the
  login the send scan already unlocked (no extra scan); if it can't be read, the mail goes without it.
- The sign-in holds `gmail.readonly`, **not** `gmail.metadata`: with `gmail.metadata` in a sign-in, Gmail refuses
  full messages even when `gmail.readonly` is also granted. A `gmail.metadata` sign-in (0.2.0) still replies with
  `--no-quote`.

## Assumptions
- 1. Thread id, `References`/`In-Reply-To` and a matching subject are enough for Gmail to thread (Gmail's
     documented rules; verified live 2026-11-05).
- 2. Two scans per reply is acceptable to the owner (2026-11-05).
- 3. Reading mail for context belongs to a hosted connector; `gmail-send` reads only the email being answered
     and the owner's own signature (owner, 2026-11-05).

## Reversal triggers
- Revisit if two scans per reply is too much friction (Assumption #2).
- Revisit if `gmail-send` is asked to read mail beyond the email being answered (Assumption #3): that would bring
  other people's text into sessions and needs its own ADR.

## Consequences
- Sign in once more for `gmail.readonly`; sends, drafts and `--no-quote` replies keep working meanwhile.
- The sign-in can read the owner's mail, but only after a Touch ID scan, and the tool reads only the message named.
- Replies read correctly in any mail app.

## Alternatives considered
- Caller passes the headers and the text to quote: one scan, no new scope, but the caller needs raw headers (a
  hosted connector gives them only with the whole message) and would retype someone else's email, which can change
  words silently. Rejected.
- `gmail.metadata` plus `gmail.readonly`: Gmail then refuses full messages.
- One scan for both read and send: its prompt couldn't name reply-all recipients.
- No quoting: readers outside Gmail lose the history. Rejected by the owner.

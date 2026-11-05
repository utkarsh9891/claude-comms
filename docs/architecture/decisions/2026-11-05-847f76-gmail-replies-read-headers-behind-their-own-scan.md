# 2026-11-05-847f76 — Gmail replies in a thread: read the original's headers, behind their own Touch ID scan

- **Status:** accepted
- **Date:** 2026-11-05
- **Deciders:** Utkarsh Upadhyay
- **Scope:** gmail
- **Supersedes / Amends:** amends [2026-11-05-d38d84](./2026-11-05-d38d84-gmail-send-through-the-gmail-api.md)

## Context
A reply sent with `gmail-send` and a hand-made "Re:" subject landed outside the original thread, for the owner and
for the recipients. Threading needs the original's `Message-ID` (for `In-Reply-To` and `References`) and its Gmail
thread id; a reply-all also needs its From, To and Cc. ADR d38d84 assumed the tool would never read mail
(its Assumption #3) and said reading would need its own ADR. The owner wants the lookup inside `gmail-send`, so the
calling session doesn't have to dig headers out of another tool.

## Decision
- `gmail-send --reply-to <Gmail message id> [--all]` reads **only the original's headers** (`format=metadata`,
  the headers listed in the code) with the scope **`gmail.metadata`**, which can't read bodies or attachments.
- The read unlocks the sign-in like any send: **its own Touch ID scan**, with a prompt naming the message id and
  saying nothing is sent. Sending (or `--draft`) then asks again, now naming the recipients found, the original's
  subject and sender. Two scans per reply: the recipients of a reply-all aren't known until the headers are read,
  and the send prompt must name every recipient.
- Recipients follow Gmail: Reply-To, else From; a reply to your own email goes to its To; `--all` adds the
  original To and Cc; the owner is never a recipient. `--to`/`--cc` replace them; `-s` replaces "Re: <subject>".
- The message carries `In-Reply-To` and `References`, and goes up with the thread id (multipart upload).
- Header text from the original is someone else's: line breaks, control and bidi characters are removed before it
  is reused in a subject or shown in a prompt.

## Assumptions
- 1. Headers only are enough to thread and to reply-all (verified against Gmail's threading rules: thread id,
     `References`/`In-Reply-To`, matching subject).
- 2. Two scans per reply is acceptable to the owner (stated 2026-11-05 when choosing the lookup inside the tool).

## Reversal triggers
- Revisit if two scans per reply is too much friction (Assumption #2): the caller can pass the headers instead,
  and only the send scan remains.
- Revisit if bodies are ever wanted (quoting the original): that reads untrusted text and needs its own ADR.

## Consequences
- Existing sign-ins lack `gmail.metadata`: `gmail-send login` once more; plain sends keep working meanwhile.
- The sign-in can now list who wrote to the owner and about what, but only after a Touch ID scan.
- Header text from other people reaches the tool's output (the summary), which an assistant reads; it is cleaned,
  and nothing in it is acted on.

## Alternatives considered
- Caller passes `--in-reply-to`, `--references`, `--thread` and recipients: one scan, no new scope, but the caller
  needs the raw headers, which a hosted connector only gives with the whole message. Rejected under Assumption #2.
- `gmail.readonly`: reads bodies; more than replies need.
- One scan for both read and send: its prompt couldn't name reply-all recipients.

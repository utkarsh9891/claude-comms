# Architecture Decision Records

Back to [AGENTS.md](../../../AGENTS.md).

ADRs record **significant, hard-to-reverse** decisions and the forces behind them, so a later reader (human or
agent) knows *why* this repo is the way it is and *when* a decision should be reopened.

## Rules

- **One decision per ADR**, written from [`adr-template.md`](./adr-template.md).
- **Ids are collision-proof, not sequential:** `YYYY-MM-DD-<hash>-<slug>.md`, the UTC authoring date plus six
  random hex characters (`openssl rand -hex 3`) plus a short slug. Never pick a "next number".
- **ADR before code.** A change that needs an ADR commits the ADR before the code that implements it, in the
  same PR ([documentation mandate](../../contributing/documentation-mandate.md)).
- **A merged ADR is `accepted`** — the reviewed merge is the acceptance. `proposed` only on a draft PR.
- **Immutable once on `main`.** Edit freely while the PR is open; after merge, change a decision only with a new
  ADR that supersedes or amends it, and update the old one's `Status` line to point at it.
- **Scope** names the module the decision governs: `bridge`, `server`, `plugin` (WhatsApp), `gmail`, or `repo`
  (cross-cutting or governance).
- Enforced by [`scripts/check-docs.py`](../../../scripts/check-docs.py): filename shape, required header lines,
  no `proposed` on `main`, every ADR linked from this index.

## Index

| ADR | Decision | Scope | Status |
|---|---|---|---|
| [2026-10-23-de419c](./2026-10-23-de419c-fork-and-harden-whatsapp-mcp.md) | Build on a hardened fork of lharries/whatsapp-mcp (whatsmeow) | repo | accepted |
| [2026-10-23-e302a3](./2026-10-23-e302a3-allowlist-gates-content-and-sends.md) | The bridge stores content and allows sends only for allowlisted chats | bridge | amended by f28675, a8ea3b, 16abb6 |
| [2026-10-23-8f4095](./2026-10-23-8f4095-dedicated-session-and-bypass-guard.md) | WhatsApp tools only in a dedicated `wa` session, plus a hook that blocks them in bypass mode | plugin | amended by f10233 |
| [2026-10-23-aa4dba](./2026-10-23-aa4dba-public-repo-pr-only-merge-commits.md) | Public repo; `main` changes only by reviewed PR with merge commits | repo | accepted |
| [2026-10-23-f28675](./2026-10-23-f28675-allowlist-carried-in-whatsapp-self-chat.md) | The allowlist travels through WhatsApp's "Message yourself" chat | bridge | amended by fc6f0e |
| [2026-10-23-b283a0](./2026-10-23-b283a0-cursor-support-with-taint-guard.md) | Cursor support: a dedicated workspace, read-only, with a taint guard | plugin | superseded by 3d143d |
| [2026-10-23-3d143d](./2026-10-23-3d143d-drop-cursor-support.md) | Drop Cursor support; Claude Code only | plugin | accepted |
| [2026-10-24-f10233](./2026-10-24-f10233-auto-mode-self-sends-and-send-folders.md) | Auto mode, free sends to yourself, and sending from everyday folders | plugin | amended by a8ea3b, 17d63a |
| [2026-10-27-a8ea3b](./2026-10-27-a8ea3b-history-on-add-add-chat-and-named-prompts.md) | Fetch history when a chat is added, add chats from `wa`, and name the chat in prompts | bridge | amended by 17d63a |
| [2026-10-27-17d63a](./2026-10-27-17d63a-touch-id-send-approval-and-notification-chats.md) | The bridge asks for Touch ID before sending to others; notification chats send unattended | bridge | amended by 16abb6, 032c66 |
| [2026-10-27-16abb6](./2026-10-27-16abb6-touch-id-send-adds-the-chat.md) | A send you approve with Touch ID may go to any chat, and adds it to the allowlist | bridge | accepted |
| [2026-10-27-fc6f0e](./2026-10-27-fc6f0e-commands-through-notification-chats.md) | `#wa` commands also travel through notification chats, keeping the self-chat clean | bridge | accepted |
| [2026-10-30-032c66](./2026-10-30-032c66-armed-sends-approve-a-pattern-ahead.md) | Armed sends: approve a message pattern with Touch ID ahead of time | bridge | accepted |
| [2026-10-30-7e2c9d](./2026-10-30-7e2c9d-chat-discovery-contact-names-and-partial-match.md) | Find chats by contact name, number or part of a name | bridge | accepted |
| [2026-11-05-2d0dd3](./2026-11-05-2d0dd3-rename-repo-to-claude-comms.md) | Rename the repo to claude-comms; one plugin per channel | repo | accepted |
| [2026-11-05-d38d84](./2026-11-05-d38d84-gmail-send-through-the-gmail-api.md) | Gmail channel: `gmail-send` through the Gmail API, every send behind Touch ID | gmail | amended by 847f76 |
| [2026-11-05-847f76](./2026-11-05-847f76-gmail-replies-read-headers-behind-their-own-scan.md) | Gmail replies in a thread: read the original's headers, behind their own Touch ID scan | gmail | accepted |

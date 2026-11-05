# AGENTS.md — the map of everything

**Every document in this repository is reachable by following links from this page.** If you don't know where
something lives, the answer is here or one hop away. [`CLAUDE.md`](./CLAUDE.md), [`CURSOR.md`](./CURSOR.md)
and every other agent or IDE entry point point here. Reachability is enforced in CI by
[`scripts/check-docs.py`](./scripts/check-docs.py).

**claude-comms** holds Claude Code plugins for messaging channels, one plugin per channel
([ADR 2d0dd3](./docs/architecture/decisions/2026-11-05-2d0dd3-rename-repo-to-claude-comms.md)). Two today:

- the **gmail** plugin installs `gmail-send`, which sends mail (or saves a draft) with local attachments through
  the Gmail API, every send behind the owner's Touch ID ([plugin README](./plugins/gmail/README.md));
- the **whatsapp** plugin lets you read, triage and reply to WhatsApp from Claude Code. A local **bridge**
links your WhatsApp account as a linked device and stores the chats you allowlist; an **MCP server** exposes them
as tools; a **Claude Code plugin** packages both behind a dedicated session and a guard that keeps the tools out
of permission-bypass mode. Message text is untrusted input from other people, and the whole design follows from
that.

## Master index

- **Read me first**
  - [`README.md`](./README.md) — what it is, install, use, at a glance
  - [Architecture overview](./docs/architecture/overview.md) — components, data flow, where each file lives
  - [Security model](./docs/architecture/security-model.md) — threats, the layers that stop them, and the tests
    that prove each layer
- **The rules (read before changing anything)** — [`docs/contributing/`](./docs/contributing/README.md)
  - [Documentation mandate](./docs/contributing/documentation-mandate.md) — doc-first, ADR before code, every
    change updates its docs in the same PR
  - [Branching and merging](./docs/contributing/branching-and-merging.md) — PR-only `main`, merge commits,
    required checks, worktrees
  - [Commit conventions](./docs/contributing/commit-conventions.md)
  - [Testing](./docs/contributing/testing.md) — what each CI job runs and how to run it locally
  - [Always-apply agent principles](./agent/principles/README.md) — the standing instructions every agent loads
  - [`CONTRIBUTING.md`](./CONTRIBUTING.md) — the short version for outside contributors
- **Decisions** — [ADR index](./docs/architecture/decisions/README.md) ([template](./docs/architecture/decisions/adr-template.md))
- **The code** — every module declares itself in a `module.yaml`; read that first

  | Module | Path | Manifest | What it is |
  |---|---|---|---|
  | `plugin` | [`plugins/whatsapp/`](./plugins/whatsapp/README.md) | [`module.yaml`](./plugins/whatsapp/module.yaml) | Claude Code plugin: guard hook, `/wa-setup`, triage skill, `wa` and `wa-allow` launchers, installer |
  | `bridge` | [`plugins/whatsapp/bridge/`](./plugins/whatsapp/bridge/README.md) | [`module.yaml`](./plugins/whatsapp/bridge/module.yaml) | Go service: WhatsApp linked device, allowlist, local send API |
  | `server` | [`plugins/whatsapp/server/`](./plugins/whatsapp/server/README.md) | [`module.yaml`](./plugins/whatsapp/server/module.yaml) | Python MCP server: read tools, `digest`, send tools via the bridge |
  | `gmail` | [`plugins/gmail/`](./plugins/gmail/README.md) | [`module.yaml`](./plugins/gmail/module.yaml) | Claude Code plugin: `gmail-send`, the Gmail for Claude Touch ID lock, `/gmail-setup`, installer |

- **Using it**
  - [Set up Gmail for Claude on a Mac](./docs/guides/gmail-setup-with-claude.md) — the whole setup, written to hand to
    Claude: plugin, connector and deny rules, the OAuth client step by step, sign-in, signature, test
  - [Gmail: the connector reads, `gmail-send` sends](./docs/guides/gmail-connector-and-gmail-send.md) — how the two
    tools work together, their access controls (deny rules, Touch ID) and the setup cost
  - [Gmail: `gmail-send`](./plugins/gmail/README.md) — set up, send, drafts, replies, attachments, the Touch ID lock
  - [Claude Code guide](./docs/guides/claude-code.md) — the `wa` session, what it allows and asks
  - [Allowlist guide](./docs/guides/allowlist.md) — choosing which chats are captured and which can be replied to,
    and [finding a chat](./docs/guides/allowlist.md#finding-a-chat) by name, number or part of a name
- **Operating it** — [Runbook](./docs/operations/runbook.md): install, pair, re-pair, service, logs,
  several machines, uninstall, troubleshooting
- **Governance**
  - [`SECURITY.md`](./SECURITY.md) — private vulnerability reporting
  - [`.github/CODEOWNERS`](./.github/CODEOWNERS) — guard files that always need owner review
  - [`CHANGELOG.md`](./CHANGELOG.md) — notable changes per plugin version
  - Upstream licence: [`plugins/whatsapp/LICENSE.upstream`](./plugins/whatsapp/LICENSE.upstream) (MIT, lharries/whatsapp-mcp)

## How to find things

| You want to… | Go to |
|---|---|
| Change what the bridge stores or sends | [bridge module.yaml](./plugins/whatsapp/bridge/module.yaml), then [security model](./docs/architecture/security-model.md) |
| Add or change an MCP tool | [server module.yaml](./plugins/whatsapp/server/module.yaml), then the [triage skill](./plugins/whatsapp/skills/whatsapp-triage/SKILL.md) |
| Touch a guard file (`hooks/`, `wa/settings.json`, `bin/wa`, `bridge/config.go`, `bridge/selfcmd.go`, `bridge/approve.go`, `bridge/armed.go`, `approve/`, `bin/install.sh`) | [security model](./docs/architecture/security-model.md) and [principle: never weaken a guard](./agent/principles/never-weaken-a-guard.mdc) |
| Make a design choice someone could later want to reverse | write an ADR first: [decisions](./docs/architecture/decisions/README.md) |
| Change how a chat is found by name or number (`wa-send`, `wa-allow`) | [`bin/walookup.py`](./plugins/whatsapp/bin/walookup.py), [ADR 7e2c9d](./docs/architecture/decisions/2026-10-30-7e2c9d-chat-discovery-contact-names-and-partial-match.md), [finding a chat](./docs/guides/allowlist.md#finding-a-chat) |
| Change armed sends (approve a pattern ahead) | [`bridge/armed.go`](./plugins/whatsapp/bridge/armed.go), [ADR 032c66](./docs/architecture/decisions/2026-10-30-032c66-armed-sends-approve-a-pattern-ahead.md) |
| Change how mail is sent, approved or attached (`plugins/gmail/`) | [gmail module.yaml](./plugins/gmail/module.yaml), then [security model § Gmail](./docs/architecture/security-model.md#gmail) |
| Fix a machine that stopped receiving messages | [runbook § troubleshooting](./docs/operations/runbook.md#troubleshooting) |

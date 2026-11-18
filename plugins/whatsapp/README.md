# plugin — Claude Code packaging

Manifest: [`module.yaml`](./module.yaml) · Back to [AGENTS.md](../../AGENTS.md) ·
Decision: [ADR 2026-10-23-8f4095](../../docs/architecture/decisions/2026-10-23-8f4095-dedicated-session-and-bypass-guard.md)

| Path | What it is |
|---|---|
| [`hooks/bypass-guard.sh`](./hooks/bypass-guard.sh) | `PreToolUse` hook on `mcp__.*whatsapp__.*`: allows only `default`, `acceptEdits`, `plan`, `auto`; sends to yourself and downloads go through; sends to others go through to the bridge's Touch ID check (ask here with an older bridge); `add_chat` asks, naming the chat; fails closed. Test: [`hooks/test-bypass-guard.sh`](./hooks/test-bypass-guard.sh) |
| [`wa/settings.json`](./wa/settings.json) | permissions of the `wa` session: starts in auto mode, bypass disabled, reads allowed |
| [`bin/wa`](./bin/wa) | launches the WhatsApp-only Claude session ([guide](../../docs/guides/claude-code.md)) |
| [`bin/wa-allow`](./bin/wa-allow) | allowlist CLI, incl. notification chats ([guide](../../docs/guides/allowlist.md)) |
| [`bin/wa-send`](./bin/wa-send) | send from any terminal through the bridge's checks, or arm a pattern to send later unattended ([guide](../../docs/guides/claude-code.md#sending-from-any-terminal)) |
| [`bin/walookup.py`](./bin/walookup.py) | finds a chat by name, number or part of a name, for `wa-send` and `wa-allow` ([guide](../../docs/guides/allowlist.md#finding-a-chat)) |
| [`approve/wa-approve.swift`](./approve/wa-approve.swift) | the Touch ID helper, installed as **WhatsApp for Claude**, that the bridge runs before a send to others ([ADR 17d63a](../../docs/architecture/decisions/2026-10-27-17d63a-touch-id-send-approval-and-notification-chats.md)) |
| [`bin/install.sh`](./bin/install.sh) | `install`, `pair [phone]`, `service`, `status`, `approve-test`, `uninstall` ([runbook](../../docs/operations/runbook.md)) |
| [`commands/wa-setup.md`](./commands/wa-setup.md) | `/wa-setup [phone]`: install, pair and start the service from Claude Code; on a fresh Mac it checks WhatsApp Web is reachable and asks first ([ADR 51b64d](../../docs/architecture/decisions/2026-11-18-51b64d-bridge-setup-is-opt-in-per-machine.md)) |
| [`skills/whatsapp-triage/SKILL.md`](./skills/whatsapp-triage/SKILL.md) | how the assistant reads (digest first), and replies (draft, confirm target, approve) |
| [`bridge/`](./bridge/README.md), [`server/`](./server/README.md) | the two runtime modules |

Changing any guard file: read the [security model](../../docs/architecture/security-model.md) first.

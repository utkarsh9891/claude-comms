---
description: Install (after asking whether this Mac needs it) or repair WhatsApp for Claude Code on this machine (build, pair, background service)
argument-hint: "[phone number with country code, for code pairing]"
---

Set up WhatsApp on this machine with the plugin's installer at `${CLAUDE_PLUGIN_ROOT}/bin/install.sh`.

1. Run `${CLAUDE_PLUGIN_ROOT}/bin/install.sh status` and show the result.
2. **If it shows `app: not installed`, ask before installing anything**
   ([ADR 51b64d](../../../docs/architecture/decisions/2026-11-18-51b64d-bridge-setup-is-opt-in-per-machine.md)):
   - Check whether WhatsApp Web is reachable: `curl -s -o /dev/null -w '%{http_code}' --max-time 10
     https://web.whatsapp.com/`. A `200` means reachable. A `403`, any other error code, or a timeout means a
     network filter is probably blocking it, and the bridge won't connect from this network.
   - Ask the user whether this Mac needs the WhatsApp bridge. Say what it installs (a background service, this
     Mac as a linked device on their WhatsApp, a local store of the chats they allowlist) and include the
     reachability result.
   - If the answer is no, install nothing, pair nothing and start nothing. Say that nothing was changed, suggest
     `claude plugin uninstall whatsapp@claude-comms`, and stop.
3. If the app is not installed (and the user said yes), or the plugin version is newer, run
   `${CLAUDE_PLUGIN_ROOT}/bin/install.sh install`. If it reports missing tools, stop and tell the user the exact
   `brew install` line.
4. If not paired: run `${CLAUDE_PLUGIN_ROOT}/bin/install.sh pair $ARGUMENTS` in the background, read its output
   until it prints `PAIRING CODE:` (or says a QR opened), and show the user the code and the phone steps
   immediately: WhatsApp → Settings → Linked devices → Link a device → "Link with phone number instead".
   Then wait for it to finish and report whether pairing succeeded.
5. Run `install.sh status` again and report it. If it shows `approval: Touch ID`, run
   `${CLAUDE_PLUGIN_ROOT}/bin/install.sh approve-test` after telling the user a Touch ID prompt is coming (nothing
   is sent), and report the result.
6. Tell the user the next steps:
   - `wa-allow list` to see chats; capture one with `#wa add <group name>` in the WhatsApp "Message yourself" chat
     (or `wa-allow add "<group name>"`); it applies on every machine. Nothing is stored until then.
   - start WhatsApp sessions with `wa` in a new terminal; WhatsApp tools are blocked in bypass-permissions mode.
   - sends to others ask for Touch ID; `wa-send` sends from any terminal; `#wa notify <group>` makes a group of
     only them (and at most one other account) a notification chat for unattended messages.

Never print the contents of `~/.whatsapp-mcp/token`, and never read `messages.db` in this session.

# 2026-11-18-51b64d — Setting up a Mac asks before installing the WhatsApp bridge

- **Status:** accepted
- **Date:** 2026-11-18
- **Deciders:** Utkarsh Upadhyay
- **Scope:** plugin
- **Supersedes / Amends:** —

## Context
When Claude set up claude-comms on a Mac (`/wa-setup`, or the runbook's "Set up or upgrade another Mac" recipe),
it built the bridge, paired it, started a `KeepAlive` service and added a `wa-send` section to `~/.claude/CLAUDE.md`,
all without asking whether that Mac needed WhatsApp at all. Not every Mac does: the marketplace also carries the
`gmail` plugin, and some Macs sit on managed networks whose web filter blocks WhatsApp Web. On such a Mac the
bridge's websocket handshake gets an HTTP 403 instead of 101, so the service retries every 30 seconds forever,
every send fails with "bridge not reachable", and the paired session, the message store and the CLAUDE.md
instruction all point at a channel that cannot work. The owner hit exactly this and had to remove the bridge by
hand.

## Decision
1. **Every setup Claude runs asks first, on a fresh install.** Before building anything, `/wa-setup` and the "Set
   up another Mac" recipe:
   - check whether WhatsApp Web is reachable from this Mac (`curl` to `https://web.whatsapp.com/`; a 403 or a
     filter page means blocked) and report the result, and
   - ask the user whether this Mac needs the WhatsApp bridge, saying what it installs (a background service, a
     linked device, a local store of allowlisted chats) and, if WhatsApp Web is blocked, that it won't connect.
2. **Only a yes configures the bridge**: build, pair, start the service, Touch ID check, notification chats,
   allowlist and the `wa-send` section in `~/.claude/CLAUDE.md`.
3. **A no changes nothing on the Mac.** Claude says so, suggests `claude plugin uninstall whatsapp@claude-comms` if
   the plugin is installed, and carries on with any other setup asked for (such as `gmail`).
4. **An existing install isn't asked again.** When the app is already installed, `/wa-setup` repairs or upgrades it
   as before.
5. `bin/install.sh` is unchanged. Running it by hand is already an explicit choice.

## Assumptions
- 1. Some Macs that use claude-comms don't need WhatsApp, or can't reach WhatsApp Web (true on 2026-11-18 for a
     web-filtered work network).
- 2. Setup on a new Mac is run by Claude from `/wa-setup` or the runbook recipe, so a question there reaches the
     user before anything is installed.
- 3. A plain HTTPS request to `web.whatsapp.com` is blocked or allowed the same way as the bridge's websocket.

## Reversal triggers
- Setup moves into a non-interactive installer or bootstrap script: the question and the check move there.
- The reachability check gives wrong answers (passes where the websocket is blocked, or the reverse): drop it and
  keep only the question.

## Consequences
- One extra question on a fresh setup, carrying the reachability result, which is new information even for a
  user who typed `/wa-setup`.
- A blocked network is caught before a service is installed that can never connect.
- A "no" leaves no service, launchers, data or CLAUDE.md instruction behind.

## Alternatives considered
- Prompt inside `install.sh`: it's a guard file, a prompt would hang when Claude runs it, and a person running it
  by hand has already chosen. Rejected under Assumption #2.
- Skip the bridge automatically when WhatsApp Web is blocked: a laptop changes networks, and whether the bridge is
  wanted is the user's call. The check informs the question but doesn't decide it.
- Split WhatsApp and Gmail into separate marketplaces: more to maintain, and it doesn't help a Mac that adds this
  marketplace for WhatsApp but is on a blocked network.

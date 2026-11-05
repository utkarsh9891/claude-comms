# claude-comms

Claude Code plugins for your messaging channels, one plugin per channel
([ADR 2d0dd3](./docs/architecture/decisions/2026-11-05-2d0dd3-rename-repo-to-claude-comms.md)).

**Gmail** (`gmail` plugin): `gmail-send` sends mail or saves a draft with local attachments through the Gmail API,
every send behind your Touch ID; your own OAuth client, never one from this repo. See the
[gmail plugin README](./plugins/gmail/README.md).

**WhatsApp** (`whatsapp` plugin): read, triage and reply to WhatsApp from Claude Code, safely: only the chats you allowlist, in a dedicated
session, with a hard block on permission-bypass mode.

**Start at [`AGENTS.md`](./AGENTS.md)**, the map of every document in this repo.

> **Unofficial client.** It links your account as a WhatsApp linked device through
> [whatsmeow](https://github.com/tulir/whatsmeow), a hardened fork of
> [lharries/whatsapp-mcp](https://github.com/lharries/whatsapp-mcp). That is against WhatsApp's terms and carries
> a small risk of the number being restricted. Messages from allowlisted chats are stored unencrypted in
> `~/.whatsapp-mcp`, and text the assistant reads goes to the model provider. Check your organisation's policy
> before capturing work chats with personal data.

## Install

Prereqs (macOS): `brew install go uv`.

```text
/plugin marketplace add utkarsh9891/claude-comms
/plugin install whatsapp@claude-comms
/wa-setup 91XXXXXXXXXX          # your number with country code → an 8-character pairing code
```

## Use

```bash
wa-allow list panda              # find a chat: part of a name, a contact's name, or a number
wa-allow add "Field Ops North"   # start capturing a chat
wa                               # the WhatsApp Claude session
wa-send "Claude pings" "done"    # from any terminal: notification chats and yourself need no prompt
wa-send Panda "on my way"        # anyone else: Touch ID shows the chat and text first
wa-send --arm Asha "Build {id} is green: {url}"   # approve now, send later while you're away
```

Sends to anyone but you wait for your Touch ID. Chats are found by contact name, number or part of a name
([finding a chat](./docs/guides/allowlist.md#finding-a-chat)); a message you'll want sent when a step finishes can
be armed ahead of time ([sending later](./docs/guides/claude-code.md#sending-later-while-youre-away)).

More: [Claude Code guide](./docs/guides/claude-code.md) · [allowlist](./docs/guides/allowlist.md) ·
[runbook](./docs/operations/runbook.md) · [security model](./docs/architecture/security-model.md) ·
[contributing](./CONTRIBUTING.md)

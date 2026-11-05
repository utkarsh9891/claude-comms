---
description: Install or repair gmail-send on this machine (Touch ID lock, command, Google sign-in)
argument-hint: "[path to the client_secret….json downloaded from Google Cloud]"
---

Set up gmail-send with the plugin's installer at `${CLAUDE_PLUGIN_ROOT}/bin/install.sh`.

1. Run `${CLAUDE_PLUGIN_ROOT}/bin/install.sh status` and show the result.
2. If the app is missing or older than the plugin, run `${CLAUDE_PLUGIN_ROOT}/bin/install.sh install`. If it
   reports a missing tool, stop and tell the user the exact `brew install` or `xcode-select --install` line.
3. If `client:` says none: if `$ARGUMENTS` names a file, run `gmail-send setup "$ARGUMENTS"`; otherwise look for
   the newest `~/Downloads/client_secret_*.json`, show its path and ask the user to confirm it before running
   `gmail-send setup <path>`. If there is none, walk the user through creating one with the steps in
   `${CLAUDE_PLUGIN_ROOT}/README.md` ("Create your OAuth client") and stop.
4. If `signed in:` says no: tell the user a Google sign-in page is about to open and to allow sending email and
   managing drafts and reading email (used only to reply to one), then run
   `gmail-send login` in the background and wait for it to finish; report the account.
5. Tell the user a Touch ID prompt is coming (nothing is sent or unlocked), run
   `${CLAUDE_PLUGIN_ROOT}/bin/install.sh approve-test`, and report the result.
6. Run `install.sh status` again and report it, then the usage:
   `gmail-send <to> -s "<subject>" [--cc <addr>] [--html <file>] --file <path> [--draft] "<text>"`, and replies
   `gmail-send --reply-to <message id> [--all] [--no-quote] [--draft] "<text>"` (one scan; quotes the original);
   `me` is your
   own address; every send and draft asks for Touch ID; attachments come only from ~/Downloads, ~/Desktop,
   ~/Documents and ~/Pictures.
7. If a hosted Gmail connector is connected, tell the user it can still send without Touch ID and offer to deny
   its send, reply, forward and draft tools in `~/.claude/settings.json`; change the settings only if they agree.

Never print the client secret or the contents of `token.sealed` or `key.se`. After `setup` succeeds, tell the user
the downloaded `client_secret_….json` can be deleted.

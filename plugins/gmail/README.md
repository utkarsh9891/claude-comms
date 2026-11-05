# gmail — send email with attachments from any terminal

Manifest: [`module.yaml`](./module.yaml) · Back to [AGENTS.md](../../AGENTS.md) ·
Decision: [ADR d38d84](../../docs/architecture/decisions/2026-11-05-d38d84-gmail-send-through-the-gmail-api.md) ·
Security: [Gmail threats](../../docs/architecture/security-model.md#gmail) ·
With the connector: [the connector reads, `gmail-send` sends](../../docs/guides/gmail-connector-and-gmail-send.md)

`gmail-send` sends mail as you through the Gmail API, reading attachments straight from disk, so a file arrives
byte-for-byte as it is. It sends, saves drafts and replies in a thread, quoting the original; it reads only the
email you're answering (read other mail for context with a Gmail connector). **Every send and every draft, to
anyone including yourself, needs your Touch ID**: the Google sign-in is stored only locked to it, so nothing on
the Mac can send as you without a scan.

```bash
gmail-send me -s "Test" --file ~/Downloads/report.pdf "Does this open?"     # to yourself
gmail-send a@example.com,b@example.com --cc c@example.com -s "Oct report" \
  --file ~/Downloads/report.pdf "Hi both, the October report is attached."
gmail-send a@example.com -s "Oct report" --file ~/Downloads/report.pdf --draft "…"  # to Gmail Drafts; send it from Gmail
gmail-send me -s "Formatted" --html ~/Documents/body.html "plain-text version"  # HTML with a text fallback
echo "<p>Hi</p>" | gmail-send me -s "Formatted" --html - "plain-text version"   # HTML from stdin: no file needed
echo "body from a pipe" | gmail-send me -s "Piped" -
gmail-send --reply-to 1a1ab97a1a956b87 --all "Thanks, noted."                 # reply-all in the thread, original quoted (one scan)
gmail-send --reply-to 1a1ab97a1a956b87 --no-quote "Short and sweet."          # without the quoted original
gmail-send --reply-to 1a1ab97a1a956b87 --file ~/Downloads/v2.pdf --draft "v2 attached"  # reply to the sender, as a draft
gmail-send a@example.com -s "Check" --file ~/Desktop/x.pdf --dry-run "…"     # show what would be sent; send nothing
```

`gmail-send` prints the from, to, cc, subject, each attachment with its size and SHA-256, and the text (for a
new email before asking; for a reply once the original is read). It writes no email content to disk. The Touch ID prompt ("Gmail for Claude is trying to send an email to …", or "save a draft email to …")
names every recipient ("you" for yourself), the subject, each attachment and the start of the text. Declining, a
120 s timeout or a missing helper sends nothing.

**Replies** (`--reply-to <Gmail message id>`, the id from the Gmail URL or the connector) stay in the original
thread: `In-Reply-To`, `References` and the thread id are set from the original, which `gmail-send` reads within
the reply's **one** Touch ID scan. The original is **quoted below your text**, as Gmail does ("On … wrote:", folded behind
"•••" in Gmail), unless `--no-quote`; the quoted text is never printed, only counted. It answers Reply-To or the sender (your own
email: its To); `--all` adds everyone on the original except you; the subject is "Re: <original>". `--to`, `--cc`
and `-s` replace those. The prompt names the email and "its sender" or "everyone on it"; `--dry-run` lists the
names first
([ADR 847f76](../../docs/architecture/decisions/2026-11-05-847f76-gmail-replies-read-headers-behind-their-own-scan.md)).

**Armed sends** let mail go out later without a scan, for messages you want sent when a step finishes:

```bash
gmail-send --arm me -s "Build {id} done" --times 3 --for 45m "Details: {url}"   # one Touch ID scan now
gmail-send me -s "Build PR-42 done" "Details: https://ci.example.com/42"          # later: no scan, it matches
gmail-send --armed                                                                # what's armed; --disarm [<id>]
```

One scan approves up to `--times` emails (default 1, at most 20) to exactly those recipients whose whole subject
and text fit the patterns, within `--for` (default and at most 1 hour: Google's key lifetime). Slots: `{num}`,
`{id}` (ticket, PR, branch, SHA), `{url}` (one https link), `{text}` (a line up to 100 characters); `{{ }}` are
literal braces. Files, HTML, drafts and replies always ask. While armed, the one-hour key sits in
`~/.gmail-send/armed.json` (0600) ([ADR c41e0b](../../docs/architecture/decisions/2026-11-05-c41e0b-gmail-armed-sends-one-hour-key.md)).

**Your signature** lives in `~/.gmail-send/signature.html`: saved from Gmail when you sign in, editable, and
added under your text (above any quote) on every send, reply and draft, as Gmail does; `--no-signature` leaves it
out. `gmail-send signature` shows it; `gmail-send signature --refresh` fetches Gmail's again (one scan).

**Attachments** (and an `--html` file) come only from `~/Downloads`, `~/Desktop`, `~/Documents` and
`~/Pictures`, after resolving symlinks, never from a hidden file or folder, 25 MB in total. Copy a file into one of
those first. To change the folders, set `"send_from": [...]` in `~/.gmail-send/config.json`.

## Set up (once per Mac)

The full walkthrough, written to hand to Claude Code, is
[Set up Gmail for Claude on a Mac](../../docs/guides/gmail-setup-with-claude.md). In short:

Prereqs: `brew install uv`, and the Command Line Tools for `swiftc` (`xcode-select --install`).

1. **Install the plugin** and run `/gmail-setup` in Claude Code (or `bin/install.sh` without Claude). This builds
   the Touch ID helper into `~/.gmail-send/app` and links `~/.local/bin/gmail-send`.
2. **Create your OAuth client** (below) and run `gmail-send setup ~/Downloads/client_secret_….json`. The file is
   copied to `~/.gmail-send/client.json` (0600); delete the download afterwards.
3. **Sign in:** `gmail-send login` opens Google in your browser; allow sending email, managing drafts and
   reading email (used only to reply to one). If replies say to sign in again, your sign-in predates this. The
   lasting sign-in is stored only encrypted to a Secure Enclave key that needs your Touch ID for every use.
4. **Check:** `gmail-send me -s "Test" --file ~/Downloads/<some file> "hello"` (one Touch ID prompt).
5. **Close other ways to send:** if a hosted Gmail connector is connected, deny its send, reply, forward and
   draft tools in `~/.claude/settings.json` (`permissions.deny`; the exact list is in the
   [connector guide](../../docs/guides/gmail-connector-and-gmail-send.md#access-controls)), or disconnect it;
   otherwise it sends without Touch ID ([G8](../../docs/architecture/security-model.md#gmail)).

### Create your OAuth client

Each person uses their own client; this repo never contains one. In the [Google Cloud console](https://console.cloud.google.com),
signed in with the account you'll send from:

1. Create a project (any name). A Workspace account creates it inside its organisation.
2. **APIs & Services → Library → Gmail API → Enable.**
3. **Google Auth Platform → Get started:** an app name, your email for support and contact. **Audience:**
   - a **Workspace** account (your company's Google): **Internal**. No review, no warning, no expiry.
   - a **personal Gmail** account: **External**, add yourself as a test user, then **Publish app** (*In
     production*) so the sign-in doesn't expire after 7 days. Google shows an "unverified app" warning at sign-in;
     it's your own app.
4. **Clients → Create client → Desktop app → Create → Download JSON.**

If the sign-in page says **access blocked**, your Workspace doesn't allow apps it hasn't approved; ask your
admin to allow this client, or use the hosted Gmail connector for text-only mail.

## Commands

| Command | What it does |
|---|---|
| `gmail-send <to> -s <subject> [--cc …] [--file …]… [--html <file>] [--draft] [--dry-run] [--no-signature] [text… \| -]` | send (or save a draft); `me` is your address; addresses are plain and comma-separated |
| `gmail-send --reply-to <id> [--all] [--no-quote] [--to …] [--cc …] [-s …] [--file …]… [--html …] [--draft] [--dry-run] [text…]` | reply in the original's thread, quoting it (one scan) |
| `gmail-send --arm <to> [--cc …] -s <subject pattern> [--for 45m] [--times N] <text pattern>` | approve matching emails ahead, one scan, at most an hour |
| `gmail-send --armed` / `--disarm [<id>]` | list armed patterns / drop one or all (no scan) |
| `gmail-send setup <client_secret….json>` | store your Desktop-app client (rejects other client types) |
| `gmail-send login` | Google sign-in in the browser (send, drafts; read an email only to reply to it); locks the sign-in to Touch ID |
| `gmail-send status` | client, signed-in account, Touch ID helper, send folders |
| `gmail-send logout` | delete the sign-in from this Mac (no scan); remove the app's access at Google on [your account's connections page](https://myaccount.google.com/connections) |
| `gmail-send signature [--refresh]` | show the saved signature, or fetch Gmail's again (one scan) |
| `bin/install.sh [install\|status\|approve-test\|uninstall]` | build and link; show state; one test prompt; remove the app |

Run `gmail-send login` again if a send says your sign-in **expired or was revoked**, or after you add or remove a
fingerprint (the lock is tied to the enrolled fingers).

## Files

| Path | What it is |
|---|---|
| [`bin/gmail-send`](./bin/gmail-send) | the command (argument parsing) |
| [`bin/gmailsend.py`](./bin/gmailsend.py) | sign-in, the lock (through the helper), send folders, message building, send |
| [`approve/gmail-approve.swift`](./approve/gmail-approve.swift) | the lock, installed as **Gmail for Claude**: seals the sign-in to a Touch ID-only Secure Enclave key and unlocks it per send |
| [`bin/install.sh`](./bin/install.sh) | build, link, status, approve-test, uninstall |
| [`commands/gmail-setup.md`](./commands/gmail-setup.md) | `/gmail-setup [client file]`: install, store the client, sign in, test Touch ID |
| [`tests/`](./tests/test_gmailsend.py) | send folders, message round trip, the lock (with a stand-in helper), sign-in through the real loopback server, the command |

On this machine, not in the repo: `~/.gmail-send/client.json`, `config.json`, `signature.html`, `armed.json` (only
while armed), `token.sealed` and `key.se`
(0600, folder 0700; the last two useless without your Touch ID on this Mac), and the built `~/.gmail-send/app/`.

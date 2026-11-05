# Testing

Back to [contributing](./README.md). Every CI job is a required check on `main`.

| CI job | Runs | Locally |
|---|---|---|
| `bridge` | gofmt, `go vet`, `go test`, build | `cd plugins/whatsapp/bridge && gofmt -l . && go vet ./... && go test ./...` |
| `server` | digest tests and a call to **every read tool** through FastMCP (output validated against its declared type), on a fixture written by the bridge's own `MessageStore`; the chat lookup (`bin/walookup.py`, `wa-allow list`, `wa-send`) on contacts and a LID map written by whatsmeow's own store; MCP server lists its tools | `cd plugins/whatsapp/server && uv run --with pytest python -m pytest tests -q` |
| `plugin` | gmail: `gmail-send` tests (send folders, message round trip, the Touch ID lock with a stand-in helper, sign-in through the real loopback server, the command) — `cd plugins/gmail && uv run --no-project --with pytest python -m pytest tests -q`; WhatsApp: manifest checks, shellcheck, guard test (45 cases: modes incl. `auto`, sends to self vs others with and without the Touch ID bridge, downloads, `add_chat`, chat names in prompts, Cursor input) | `plugins/whatsapp/hooks/test-bypass-guard.sh` |
| `docs` | documentation gate | `python3 scripts/check-docs.py` |

**Fixtures match the writer.** Test databases are produced by the bridge's real writer
(`bridge/fixture_test.go`), never hand-built, so the tests read exactly what production writes.

**Guard changes need a live check too.** After changing a guard or upgrading Claude Code, rerun the live checks
listed in the [security model](../architecture/security-model.md) "Proven by" column with `claude -p` against a
fixture `WA_HOME`.

#!/bin/bash
# whatsapp-claude: build, pair, run as a login service.
#
#   install.sh             build the bridge, its Touch ID helper and the MCP server into ~/.whatsapp-mcp, write
#                          configs, link `wa`, `wa-allow` and `wa-send`
#   install.sh pair [phone] link this machine to WhatsApp (pairing code if phone given, else QR), then start the service
#   install.sh service     (re)start the background bridge (launchd)
#   install.sh status      show what is installed and running
#   install.sh approve-test show one Touch ID prompt from the running bridge; nothing is sent
#   install.sh uninstall   stop the service and remove launchers (keeps ~/.whatsapp-mcp data)
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WA_HOME="${WA_HOME:-$HOME/.whatsapp-mcp}"
APP="$WA_HOME/app"
BIN_DIR="$HOME/.local/bin"
LABEL="com.whatsapp-claude.bridge"
OLD_LABEL="com.whatsapp-agent-bridge.bridge"   # 0.2.1–0.3.2 name; removed on service (re)start
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

say() { printf '%s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

need() {
  local missing=()
  for t in go uv jq claude; do command -v "$t" >/dev/null || missing+=("$t"); done
  [ ${#missing[@]} -eq 0 ] || die "missing: ${missing[*]} (brew install ${missing[*]/claude/})"
  xcrun --find swiftc >/dev/null 2>&1 || die "missing: swiftc (xcode-select --install)"
}

# Command Line Tools can ship an SDK newer than their compilers ("this SDK is not supported by the compiler", or a
# link error in the Go bridge's cgo step); then try each installed macOS SDK, newest first, and remember the one
# that worked in FALLBACK_SDK so the bridge builds against it too. Sources and behaviour are unchanged (threat T4).
FALLBACK_SDK=""
build_helper() {
  local out="$1" src="$PLUGIN_ROOT/approve/wa-approve.swift" sdk log dev
  log="$(mktemp)"
  if xcrun swiftc -O -o "$out" "$src" 2>"$log"; then rm -f "$log"; return 0; fi
  dev="$(xcode-select -p)"
  while IFS= read -r sdk; do
    if xcrun swiftc -O -sdk "$sdk" -o "$out" "$src" 2>>"$log"; then
      FALLBACK_SDK="$sdk"
      say "built the Touch ID helper against $(basename "$sdk") (the default SDK doesn't match this compiler)"
      rm -f "$log"
      return 0
    fi
  done < <(find "$dev/SDKs" "$dev/Platforms/MacOSX.platform/Developer/SDKs" -maxdepth 1 -name 'MacOSX[0-9]*.sdk' 2>/dev/null | sort -rV)
  cat "$log" >&2
  rm -f "$log"
  die "couldn't build the Touch ID helper with any installed SDK (update the Command Line Tools)"
}

do_install() {
  need
  mkdir -p "$WA_HOME" "$BIN_DIR" && chmod 700 "$WA_HOME"
  local was_running=false
  service_loaded && was_running=true

  rm -rf "$APP.new"
  say "building Touch ID helper…"
  build_helper "$APP.new/WhatsApp for Claude"
  say "building bridge…"
  if [ -n "$FALLBACK_SDK" ]; then
    (cd "$PLUGIN_ROOT/bridge" && SDKROOT="$FALLBACK_SDK" go build -o "$APP.new/whatsapp-bridge" .)
  else
    (cd "$PLUGIN_ROOT/bridge" && go build -o "$APP.new/whatsapp-bridge" .)
  fi
  say "installing MCP server…"
  cp -R "$PLUGIN_ROOT/server" "$APP.new/server"
  rm -rf "$APP.new/server/.venv" "$APP.new/server/tests"
  (cd "$APP.new/server" && uv sync --quiet --no-dev)
  cp "$PLUGIN_ROOT/bin/wa" "$PLUGIN_ROOT/bin/wa-allow" "$PLUGIN_ROOT/bin/wa-send" "$PLUGIN_ROOT/bin/walookup.py" "$APP.new/"
  # stop the bridge before swapping the binary it runs from
  $was_running && stop_service
  rm -rf "$APP" && mv "$APP.new" "$APP"

  [ -f "$WA_HOME/config.json" ] || printf '{\n  "allow_chats": [],\n  "allow_direct_chats": false,\n  "port": 8080\n}\n' > "$WA_HOME/config.json"
  chmod 600 "$WA_HOME/config.json"
  cp "$PLUGIN_ROOT/wa/settings.json" "$WA_HOME/settings.json"
  jq -n --arg uv "$(command -v uv)" --arg dir "$APP/server" --arg home "$WA_HOME" \
    '{mcpServers: {whatsapp: {command: $uv, args: ["--directory", $dir, "run", "--quiet", "main.py"], env: {WA_HOME: $home}}}}' \
    > "$WA_HOME/mcp.json"

  ln -sf "$APP/wa" "$BIN_DIR/wa"
  ln -sf "$APP/wa-allow" "$BIN_DIR/wa-allow"
  ln -sf "$APP/wa-send" "$BIN_DIR/wa-send"
  case ":$PATH:" in *":$BIN_DIR:"*) ;; *) say "note: add $BIN_DIR to PATH (echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc)";; esac

  if $was_running; then do_service; fi
  say "installed to $APP"
  [ -f "$WA_HOME/whatsapp.db" ] || say "next: install.sh pair [phone-with-country-code]"
}

paired() {
  [ -f "$WA_HOME/whatsapp.db" ] && [ -n "$(sqlite3 "file:$WA_HOME/whatsapp.db?mode=ro" 'select jid from whatsmeow_device limit 1' 2>/dev/null)" ]
}

do_pair() {
  [ -x "$APP/whatsapp-bridge" ] || die "run install.sh first"
  paired && { say "already paired"; do_service; return; }
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  local log="$WA_HOME/pair.log" args=()
  [ -n "${1:-}" ] && args=(-pair-phone "${1//[^0-9]/}")
  rm -f "$WA_HOME/pair-code.txt" "$WA_HOME/qr.png"
  : > "$log" && chmod 600 "$log"
  WA_HOME="$WA_HOME" "$APP/whatsapp-bridge" "${args[@]}" >"$log" 2>&1 &
  local pid=$!
  trap 'kill $pid 2>/dev/null || true' EXIT

  for _ in $(seq 1 30); do
    [ -s "$WA_HOME/pair-code.txt" ] || [ -s "$WA_HOME/qr.png" ] && break
    kill -0 $pid 2>/dev/null || { cat "$log" >&2; die "bridge exited"; }
    sleep 1
  done
  if [ -s "$WA_HOME/pair-code.txt" ]; then
    say "PAIRING CODE: $(cat "$WA_HOME/pair-code.txt")"
    say "phone: WhatsApp → Settings → Linked devices → Link a device → 'Link with phone number instead'"
  elif [ -s "$WA_HOME/qr.png" ]; then
    open "$WA_HOME/qr.png"
    say "scan the QR that just opened (phone: WhatsApp → Settings → Linked devices → Link a device)"
  else
    die "no pairing code or QR after 30s; see $log"
  fi

  say "waiting up to 3 minutes for the phone…"
  for _ in $(seq 1 180); do
    grep -q "Connected to WhatsApp!" "$log" && break
    kill -0 $pid 2>/dev/null || { tail -5 "$log" >&2; die "bridge exited before pairing"; }
    sleep 1
  done
  grep -q "Connected to WhatsApp!" "$log" || die "timed out; run install.sh pair again"
  kill $pid 2>/dev/null; wait $pid 2>/dev/null || true
  trap - EXIT
  rm -f "$log"
  say "paired"
  do_service
}

do_service() {
  paired || die "not paired yet: install.sh pair [phone]"
  mkdir -p "$(dirname "$PLIST")"
  cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$APP/whatsapp-bridge</string></array>
  <key>EnvironmentVariables</key><dict><key>WA_HOME</key><string>$WA_HOME</string></dict>
  <key>WorkingDirectory</key><string>$WA_HOME</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>$WA_HOME/bridge.log</string>
  <key>StandardErrorPath</key><string>$WA_HOME/bridge.log</string>
</dict></plist>
PLIST
  touch "$WA_HOME/bridge.log" && chmod 600 "$WA_HOME/bridge.log"
  launchctl bootout "gui/$(id -u)/$OLD_LABEL" 2>/dev/null || true
  rm -f "$HOME/Library/LaunchAgents/$OLD_LABEL.plist"
  stop_service
  # bootstrap can fail briefly right after a bootout (exit 5); retry
  local i
  for i in 1 2 3 4 5; do
    launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null && break
    [ "$i" = 5 ] && die "could not start the bridge service (launchctl bootstrap failed)"
    sleep 2
  done
  service_loaded || die "bridge service did not start"
  say "bridge service running (log: $WA_HOME/bridge.log)"
}

service_loaded() { launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; }

# stop_service unloads the bridge and waits until launchd has really let it go.
stop_service() {
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  local i
  for i in $(seq 1 20); do
    service_loaded || return 0
    sleep 0.5
  done
  die "bridge service did not stop"
}

do_status() {
  say "data dir:  $WA_HOME $( [ -d "$WA_HOME" ] && echo ok || echo MISSING)"
  say "app:       $( [ -x "$APP/whatsapp-bridge" ] && echo installed || echo 'not installed')"
  say "paired:    $(paired && echo yes || echo no)"
  if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
    say "service:   $(launchctl print "gui/$(id -u)/$LABEL" | awk '/state =/{print $3; exit}')"
  else
    say "service:   not loaded"
  fi
  say "allowlist: $(jq -r '"\(.allow_chats | length) chats, direct=\(.allow_direct_chats)"' "$WA_HOME/config.json" 2>/dev/null || echo none)"
  say "approval:  $( [ -x "$APP/WhatsApp for Claude" ] && echo 'Touch ID (install.sh approve-test to try it)' || echo 'none: sends to others ask in Claude')"
  say "notify:    $(jq -r '.notify_chats // [] | length' "$WA_HOME/config.json" 2>/dev/null || echo 0) notification chats"
  say "launcher:  $(command -v wa || echo "not on PATH ($BIN_DIR)")"
  say "last log:  $(tail -1 "$WA_HOME/bridge.log" 2>/dev/null || echo -)"
}

do_approve_test() {
  service_loaded || die "bridge not running: install.sh service"
  say "a Touch ID prompt should appear now; nothing will be sent"
  curl -sS -X POST "http://127.0.0.1:$(jq -r '.port // 8080' "$WA_HOME/config.json")/api/approve-test" \
    -H "Authorization: Bearer $(cat "$WA_HOME/token")" -H "Content-Type: application/json" -d '{}' | jq -r .message
}

do_uninstall() {
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  launchctl bootout "gui/$(id -u)/$OLD_LABEL" 2>/dev/null || true
  rm -f "$PLIST" "$HOME/Library/LaunchAgents/$OLD_LABEL.plist" "$BIN_DIR/wa" "$BIN_DIR/wa-allow" "$BIN_DIR/wa-send"
  rm -rf "$APP"
  say "removed service and launchers; data kept in $WA_HOME (delete it to unlink fully, and remove the device in WhatsApp → Linked devices)"
}

case "${1:-install}" in
  install) do_install ;;
  pair) shift; do_pair "${1:-}" ;;
  service) do_service ;;
  status) do_status ;;
  approve-test) do_approve_test ;;
  uninstall) do_uninstall ;;
  *) sed -n '2,11p' "$0"; exit 1 ;;
esac

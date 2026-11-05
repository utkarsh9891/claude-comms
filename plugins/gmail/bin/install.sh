#!/bin/bash
# gmail plugin: build the Touch ID helper and install gmail-send. ADR 2026-11-05-d38d84.
#   install.sh [install]    build into ~/.gmail-send/app and link ~/.local/bin/gmail-send
#   install.sh status       what is installed, and gmail-send status
#   install.sh approve-test show one Touch ID prompt; nothing is sent
#   install.sh uninstall    remove the app and the link (keeps the sign-in: gmail-send logout removes it)
set -euo pipefail

GMAIL_HOME="${GMAIL_SEND_HOME:-$HOME/.gmail-send}"
APP="$GMAIL_HOME/app"
BIN_DIR="$HOME/.local/bin"
PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

say() { printf '%s\n' "$*"; }
die() { printf 'install.sh: %s\n' "$*" >&2; exit 1; }

# Command Line Tools can ship an SDK newer than their compiler; then try each installed SDK, newest first.
build_helper() {
  local out="$1" src="$PLUGIN_ROOT/approve/gmail-approve.swift" sdk log dev
  log="$(mktemp)"
  if xcrun swiftc -O -o "$out" "$src" 2>"$log"; then rm -f "$log"; return 0; fi
  dev="$(xcode-select -p)"
  while IFS= read -r sdk; do
    if xcrun swiftc -O -sdk "$sdk" -o "$out" "$src" 2>>"$log"; then
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
  command -v uv >/dev/null 2>&1 || die "missing: uv (brew install uv)"
  xcrun --find swiftc >/dev/null 2>&1 || die "missing: swiftc (xcode-select --install)"
  mkdir -p "$GMAIL_HOME"
  chmod 700 "$GMAIL_HOME"
  rm -rf "$APP.new"
  mkdir -p "$APP.new"
  build_helper "$APP.new/Gmail for Claude"
  cp "$PLUGIN_ROOT/bin/gmail-send" "$PLUGIN_ROOT/bin/gmailsend.py" "$APP.new/"
  chmod 755 "$APP.new/gmail-send"
  cp "$PLUGIN_ROOT/.claude-plugin/plugin.json" "$APP.new/plugin.json"
  rm -rf "$APP"
  mv "$APP.new" "$APP"
  mkdir -p "$BIN_DIR"
  ln -sf "$APP/gmail-send" "$BIN_DIR/gmail-send"
  say "installed: $APP (version $(jq -r .version "$APP/plugin.json" 2>/dev/null || echo '?'))"
  case ":$PATH:" in *":$BIN_DIR:"*) ;; *) say "note: add $BIN_DIR to PATH (echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc)" ;; esac
}

do_status() {
  if [ -x "$APP/gmail-send" ]; then
    say "app:       $APP (version $(jq -r .version "$APP/plugin.json" 2>/dev/null || echo '?'); plugin $(jq -r .version "$PLUGIN_ROOT/.claude-plugin/plugin.json"))"
    "$APP/gmail-send" status
  else
    say "app:       not installed (install.sh install)"
  fi
}

do_approve_test() {
  [ -x "$APP/Gmail for Claude" ] || die "helper not installed (install.sh install)"
  if "$APP/Gmail for Claude" test "test Touch ID for gmail-send (nothing is sent or unlocked)"; then say "approved"; else say "not approved (exit $?)"; fi
}

do_uninstall() {
  rm -rf "$APP"
  [ -L "$BIN_DIR/gmail-send" ] && rm -f "$BIN_DIR/gmail-send"
  say "removed $APP and the gmail-send link; sign-in and client kept (gmail-send logout, then rm -r $GMAIL_HOME)"
}

case "${1:-install}" in
  install) do_install ;;
  status) do_status ;;
  approve-test) do_approve_test ;;
  uninstall) do_uninstall ;;
  *) die "usage: install.sh [install|status|approve-test|uninstall]" ;;
esac

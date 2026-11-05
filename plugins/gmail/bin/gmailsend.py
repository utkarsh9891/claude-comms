"""gmail-send: send mail with local attachments through the Gmail API. ADR 2026-11-05-d38d84.

The logic behind the `gmail-send` command, kept importable for the tests. Standard library only.
Sign-in: the owner's own Desktop-app OAuth client, scopes gmail.compose + openid + email. The refresh token is
kept only encrypted to a Secure Enclave key that needs the owner's Touch ID for every use (the Gmail for Claude
helper), so every send and every draft, to anyone, needs a scan.
"""
import base64
import email.policy
import hashlib
import http.server
import json
import mimetypes
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

HOME = Path(os.environ.get("GMAIL_SEND_HOME") or Path.home() / ".gmail-send")
# gmail.compose sends and creates drafts (gmail.send alone cannot); neither reads the inbox
SCOPES = ("https://www.googleapis.com/auth/gmail.compose", "openid", "email")
COMPOSE_SCOPE = SCOPES[0]
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
SEND_URL = "https://gmail.googleapis.com/upload/gmail/v1/users/me/messages/send?uploadType=media"
DRAFT_URL = "https://gmail.googleapis.com/upload/gmail/v1/users/me/drafts?uploadType=media"
MAX_ATTACH = 25 * 1024 * 1024
DEFAULT_SEND_FROM = ("~/Downloads", "~/Desktop", "~/Documents", "~/Pictures")
APPROVE_TIMEOUT = 120  # seconds the Touch ID prompt waits before gmail-send gives up
ADDRESS = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")


class Refused(Exception):
    """A refusal shown to the user as `gmail-send: <message>`; nothing was sent."""


# ---------- files under ~/.gmail-send (0700 dir, 0600 files)


def approver_path():
    return HOME / "app" / "Gmail for Claude"


def ensure_home():
    HOME.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(HOME, 0o700)


def write_private(path, obj):
    ensure_home()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, indent=2)
    os.chmod(path, 0o600)


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as e:
        raise Refused(f"{path}: unreadable ({e})")


def load_config():
    return read_json(HOME / "config.json")


def load_client():
    c = read_json(HOME / "client.json")
    if not c.get("client_id"):
        raise Refused("no OAuth client yet: run `gmail-send setup <client_secret….json>` (see the gmail plugin README)")
    return c


def setup(client_file):
    """Store the Desktop-app client downloaded from Google Cloud (its JSON has an `installed` key)."""
    raw = read_json(Path(client_file).expanduser())
    c = raw.get("installed")
    if not c or not c.get("client_id"):
        kind = ", ".join(raw) or "empty"
        raise Refused(f"{client_file}: not a Desktop-app OAuth client (found: {kind}); create one of type 'Desktop app'")
    write_private(HOME / "client.json", {"client_id": c["client_id"], "client_secret": c.get("client_secret", "")})
    return c["client_id"]


# ---------- the lock: the refresh token is sealed to a Touch ID-only Secure Enclave key by the helper


def helper():
    h = approver_path()
    if not os.access(h, os.X_OK):
        raise Refused("the Touch ID helper isn't installed: run /gmail-setup (gmail-send never works without it)")
    return str(h)


def seal_token(token, run=subprocess.run):
    """Hand the refresh token to the helper on stdin; it is stored only encrypted. No prompt."""
    ensure_home()
    r = run([helper(), "seal", str(HOME)], input=token.encode(), capture_output=True)
    if r.returncode != 0:
        raise Refused("couldn't lock the sign-in to Touch ID: " + r.stderr.decode(errors="replace").strip())


def unlock_token(reason, run=subprocess.run):
    """Touch ID showing `reason`, then the refresh token. Nothing can read it without the scan."""
    try:
        r = run([helper(), "open", str(HOME), reason], capture_output=True, timeout=APPROVE_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise Refused("not approved (timed out); nothing was sent") from None
    if r.returncode == 3:
        raise Refused("not signed in (or the sign-in was reset): run `gmail-send login`")
    if r.returncode == 2:
        raise Refused("Touch ID isn't available on this Mac; nothing was sent")
    if r.returncode != 0:
        raise Refused("not approved (declined, timed out, or fingerprints changed since sign-in: then "
                      "`gmail-send login`); nothing was sent")
    return r.stdout.decode()


def forget_token():
    for name in ("token.sealed", "key.se"):
        (HOME / name).unlink(missing_ok=True)


def signed_in():
    return (HOME / "token.sealed").exists() and (HOME / "key.se").exists()


# ---------- HTTP


def http_json(url, data, headers, opener=urllib.request.urlopen):
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with opener(req, timeout=60) as r:
            body = r.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        try:
            j = json.loads(detail)
            err = j.get("error")
            detail = j.get("error_description") or (err.get("message") if isinstance(err, dict) else err) or detail
        except ValueError:
            pass
        raise Refused(f"Google said HTTP {e.code}: {str(detail)[:300]}") from None
    except urllib.error.URLError as e:
        raise Refused(f"can't reach Google: {e.reason}") from None


def form(d):
    return urllib.parse.urlencode(d).encode()


FORM = {"Content-Type": "application/x-www-form-urlencoded"}


# ---------- sign-in: installed-app flow, loopback redirect, PKCE, state


def b64url(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def id_token_email(id_token):
    """The email claim of an ID token received directly from Google's token endpoint over TLS."""
    try:
        payload = id_token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError):
        raise Refused("Google returned an unreadable ID token") from None
    if not claims.get("email") or claims.get("email_verified") is False:
        raise Refused("Google didn't return a verified email address")
    return claims["email"].lower()


def wait_for_redirect(server, deadline):
    """Serve the loopback redirect until Google sends a code or an error, or the deadline passes."""
    got = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
            if "code" in q or "error" in q:
                got.update(q)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"gmail-send: sign-in received. You can close this tab.")

        def log_message(self, *a):
            pass

    server.RequestHandlerClass = Handler
    server.timeout = 1
    while not got and time.monotonic() < deadline:
        server.handle_request()
    return got


def login(open_browser=webbrowser.open, post=http_json, store=seal_token, wait=600):
    client = load_client()
    helper()  # fail before the browser if the lock can't be used
    verifier = b64url(secrets.token_bytes(32))
    state = secrets.token_urlsafe(24)
    server = http.server.HTTPServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
    redirect = f"http://127.0.0.1:{server.server_port}"
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": client["client_id"], "redirect_uri": redirect, "response_type": "code",
        "scope": " ".join(SCOPES), "state": state, "access_type": "offline", "prompt": "consent",
        "code_challenge": b64url(hashlib.sha256(verifier.encode()).digest()), "code_challenge_method": "S256",
    })
    print("Opening Google sign-in in your browser. If nothing opens, visit:\n" + url, file=sys.stderr, flush=True)
    open_browser(url)
    try:
        got = wait_for_redirect(server, time.monotonic() + wait)
    finally:
        server.server_close()
    if not got:
        raise Refused(f"no sign-in within {wait // 60} minutes")
    if "error" in got:
        raise Refused(f"Google refused the sign-in: {got['error']}")
    if not secrets.compare_digest(got.get("state", ""), state):
        raise Refused("sign-in reply didn't match this request (state); ignored")
    tok = post(TOKEN_URL, form({
        "code": got["code"], "client_id": client["client_id"], "client_secret": client.get("client_secret", ""),
        "redirect_uri": redirect, "grant_type": "authorization_code", "code_verifier": verifier,
    }), FORM)
    if COMPOSE_SCOPE not in tok.get("scope", "").split():
        raise Refused("the email permission wasn't granted; run `gmail-send login` and tick it")
    if not tok.get("refresh_token"):
        raise Refused("Google issued no lasting sign-in (refresh token); run `gmail-send login` again")
    account = id_token_email(tok.get("id_token", ""))
    store(tok["refresh_token"])
    cfg = load_config()
    cfg["account"] = account
    write_private(HOME / "config.json", cfg)
    return account


def access_token(reason, post=http_json, unlock=unlock_token):
    """One Touch ID scan (showing `reason`) unlocks the refresh token, exchanged here for a one-hour access token
    that is used once and never stored."""
    client = load_client()
    refresh = unlock(reason)
    try:
        tok = post(TOKEN_URL, form({"client_id": client["client_id"], "client_secret": client.get("client_secret", ""),
                                    "refresh_token": refresh, "grant_type": "refresh_token"}), FORM)
    except Refused as e:
        if "invalid_grant" in str(e) or "expired or revoked" in str(e).lower():
            raise Refused("your Google sign-in expired or was revoked: run `gmail-send login`") from None
        raise
    return tok["access_token"]


def logout(post=http_json, unlock=unlock_token):
    """Revoke at Google (one Touch ID scan; declining still signs out here) and delete the sealed sign-in."""
    cfg = load_config()
    account = cfg.pop("account", None)
    if not account and not signed_in():
        return None
    if signed_in():
        try:
            post(REVOKE_URL, form({"token": unlock("sign out of gmail-send and revoke its Google access")}), FORM)
        except Refused:
            pass  # deleting it here is what matters; revoke later at myaccount.google.com/permissions
    forget_token()
    write_private(HOME / "config.json", cfg)
    return account or "(unknown account)"


# ---------- what may be sent


def parse_recipients(values, me):
    out = []
    for v in values:
        for a in v.split(","):
            a = a.strip()
            if not a:
                continue
            if a.lower() in ("me", "myself", "self"):
                if not me:
                    raise Refused("`me` needs a sign-in: run `gmail-send login`")
                a = me
            if not ADDRESS.match(a):
                raise Refused(f"not a plain email address: {a!r}")
            if a.lower() not in (x.lower() for x in out):
                out.append(a)
    return out


def send_from_roots(cfg):
    return [Path(p).expanduser().resolve() for p in cfg.get("send_from", DEFAULT_SEND_FROM)]


def sendable(path, roots):
    """The resolved file, if it sits inside a send folder with no hidden component; else refuse."""
    p = Path(path).expanduser()
    try:
        real = p.resolve(strict=True)
    except (FileNotFoundError, RuntimeError):
        raise Refused(f"{path}: no such file") from None
    if not real.is_file():
        raise Refused(f"{path}: not a regular file")
    for root in roots:
        if real.is_relative_to(root):
            if any(part.startswith(".") for part in real.relative_to(root).parts):
                raise Refused(f"{path}: hidden files and folders are never attached")
            return real
    folders = ", ".join(str(r).replace(str(Path.home()), "~") for r in roots)
    raise Refused(f"{path}: attachments come only from {folders}; copy the file there first")


def load_attachments(paths, roots):
    out, total = [], 0
    for p in paths:
        real = sendable(p, roots)
        data = real.read_bytes()
        total += len(data)
        if total > MAX_ATTACH:
            raise Refused(f"attachments total {human(total)}, over Gmail's 25 MB")
        out.append((real.name, data))
    return out


def human(n):
    for unit in ("bytes", "KB", "MB"):
        if n < 1024 or unit == "MB":
            return f"{n} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024


def clean(text, limit):
    t = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f​-‏‪-‮⁦-⁩]", " ", text)).strip()
    return t if len(t) <= limit else t[: limit - 1] + "…"


def build_message(me, to, cc, subject, text, attachments, html=None):
    msg = EmailMessage()
    msg["From"] = me
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=me.split("@", 1)[1])
    msg.set_content(text or "")
    if html:
        msg.add_alternative(html, subtype="html")
    for name, data in attachments:
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        main, sub = ctype.split("/", 1)
        msg.add_attachment(data, maintype=main, subtype=sub, filename=name)
    return msg.as_bytes(policy=email.policy.SMTP)


def approval_reason(recipients, subject, attachments, text, html=None, me=None, draft=False):
    """What macOS shows after "Gmail for Claude is trying to …"."""
    who = ", ".join("you" if me and r.lower() == me.lower() else r for r in recipients)
    verb = "save a draft email to " if draft else "send an email to "
    parts = [verb + who, f'subject "{clean(subject, 80)}"']
    if attachments:
        parts.append("attaching " + ", ".join(f"{clean(n, 60)} ({human(len(d))})" for n, d in attachments))
    if text:
        parts.append(f'text "{clean(text, 150)}"')
    if html:
        parts.append(f"with an HTML version ({human(len(html.encode()))})")
    return "; ".join(parts)


def summary(me, to, cc, subject, attachments, text, html):
    lines = [f"From:     {me}", f"To:       {', '.join(to)}"]
    if cc:
        lines.append(f"Cc:       {', '.join(cc)}")
    lines.append(f"Subject:  {subject}")
    for name, data in attachments:
        lines.append(f"Attach:   {name}  {human(len(data))}  sha256 {hashlib.sha256(data).hexdigest()}")
    if html:
        lines.append(f"HTML:     {human(len(html.encode()))} (sent with the text below as its plain version)")
    lines.append("Text:")
    lines += ["  " + line for line in (text or "(empty)").splitlines()] or ["  (empty)"]
    return "\n".join(lines)


def send(to_values, cc_values, subject, text, files, html_file=None, dry_run=False, draft=False,
         post_raw=None, token=access_token, out=print):
    cfg = load_config()
    me = cfg.get("account")
    if not me:
        raise Refused("not signed in: run `gmail-send login`")
    to = parse_recipients(to_values, me)
    cc = [a for a in parse_recipients(cc_values, me) if a.lower() not in (t.lower() for t in to)]
    if not to:
        raise Refused("no recipient")
    if not subject.strip():
        raise Refused("a subject is required (-s)")
    roots = send_from_roots(cfg)
    attachments = load_attachments(files, roots)
    html = sendable(html_file, roots).read_text() if html_file else None
    out(summary(me, to, cc, subject, attachments, text, html))
    raw = build_message(me, to, cc, subject, text, attachments, html)
    if dry_run:
        out("Dry run: nothing sent or saved.")
        return None
    poster = post_raw or http_json
    reason = approval_reason(to + cc, subject, attachments, text, html, me=me, draft=draft)
    out("Asking for Touch ID…")
    bearer = token(reason)  # the scan that unlocks the sign-in is the approval; declining raises Refused
    headers = {"Authorization": f"Bearer {bearer}", "Content-Type": "message/rfc822"}
    if draft:
        res = poster(DRAFT_URL, raw, headers)
        out(f"Draft saved: {res.get('id')}. Check and send it from Gmail Drafts: "
            f"https://mail.google.com/mail/?authuser={urllib.parse.quote(me)}#drafts")
        return res
    res = poster(SEND_URL, raw, headers)
    out(f"Sent: message {res.get('id')} ({', '.join(res.get('labelIds') or [])})")
    return res


def status():
    cfg, lines = load_config(), []
    client = read_json(HOME / "client.json")
    lines.append(f"client:    {'…' + client['client_id'][-40:] if client.get('client_id') else 'none (gmail-send setup <file>)'}")
    account = cfg.get("account")
    lines.append(f"signed in: {account + ' (locked to Touch ID)' if account and signed_in() else 'no (gmail-send login)'}")
    lines.append(f"approval:  {'Touch ID on every send and draft' if os.access(approver_path(), os.X_OK) else 'helper missing: nothing can be sent (/gmail-setup)'}")
    lines.append("send from: " + ", ".join(cfg.get("send_from", DEFAULT_SEND_FROM)))
    return "\n".join(lines)

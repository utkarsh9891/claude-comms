"""Tests for gmail-send (ADR 2026-11-05-d38d84). Google, the Keychain and Touch ID are stand-ins; the MIME
message, the send-folder rules and the loopback sign-in server are the real code."""
import base64
import email
import email.message
import email.policy
import hashlib
import json
import os
import stat
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bin"))
import gmailsend as g  # noqa: E402

ME = "owner@example.com"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests never reach Google: real HTTP fails the test (the loopback sign-in server is allowed), and the
    default Gmail lookup behaves as if the signature can't be read."""
    real = urllib.request.urlopen

    def guarded(req, *a, **k):
        url = getattr(req, "full_url", req)
        if not str(url).startswith("http://127.0.0.1:"):
            raise AssertionError(f"test tried to reach the network: {url}")
        return real(req, *a, **k)

    def offline(url, headers):
        raise g.Refused("no network in tests")

    monkeypatch.setattr(urllib.request, "urlopen", guarded)
    monkeypatch.setattr(g, "http_get_json", offline)


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "gmail-home"
    monkeypatch.setattr(g, "HOME", h)
    return h


@pytest.fixture
def send_dir(tmp_path, home):
    d = tmp_path / "Downloads"
    d.mkdir()
    g.write_private(home / "config.json", {"account": ME, "send_from": [str(d)]})
    g.write_private(home / "client.json", {"client_id": "cid.apps.googleusercontent.com", "client_secret": "s"})
    return d


def id_token(claims):
    enc = lambda o: base64.urlsafe_b64encode(json.dumps(o).encode()).rstrip(b"=").decode()  # noqa: E731
    return f"{enc({'alg': 'none'})}.{enc(claims)}.sig"


# ---------- recipients


def test_recipients_split_dedupe_and_me():
    assert g.parse_recipients(["a@x.com, B@x.com", "a@X.com", "me"], ME) == ["a@x.com", "B@x.com", ME]


@pytest.mark.parametrize("bad", ["Name <a@x.com>", "a@x", "a b@x.com", "a@x.com\nBcc: c@y.com"])
def test_recipients_refuse_anything_but_plain_addresses(bad):
    with pytest.raises(g.Refused):
        g.parse_recipients([bad], ME)


def test_me_needs_a_sign_in():
    with pytest.raises(g.Refused, match="sign-in"):
        g.parse_recipients(["me"], None)


def test_prompt_calls_your_own_address_you_case_insensitively():
    r = g.approval_reason(["OWNER@example.com", "x@y.com"], "s", [], "", me=ME)
    assert r.startswith("send an email to you, x@y.com;")


# ---------- send folders (exfiltration guard)


def test_sendable_inside_folder(send_dir):
    f = send_dir / "report.pdf"
    f.write_bytes(b"%PDF")
    assert g.sendable(f, [send_dir.resolve()]) == f.resolve()


def test_sendable_refuses_outside(tmp_path, send_dir):
    f = tmp_path / "secret.txt"
    f.write_text("x")
    with pytest.raises(g.Refused, match="only from"):
        g.sendable(f, [send_dir.resolve()])


def test_sendable_refuses_dot_dot_escape(tmp_path, send_dir):
    (tmp_path / "secret.txt").write_text("x")
    with pytest.raises(g.Refused, match="only from"):
        g.sendable(send_dir / ".." / "secret.txt", [send_dir.resolve()])


def test_sendable_refuses_symlink_escape(tmp_path, send_dir):
    target = tmp_path / "id_rsa"
    target.write_text("key")
    (send_dir / "innocent.pdf").symlink_to(target)
    with pytest.raises(g.Refused, match="only from"):
        g.sendable(send_dir / "innocent.pdf", [send_dir.resolve()])


def test_sendable_refuses_hidden_components(send_dir):
    (send_dir / ".ssh").mkdir()
    (send_dir / ".ssh" / "id_rsa").write_text("key")
    (send_dir / ".env").write_text("k=v")
    for p in (send_dir / ".ssh" / "id_rsa", send_dir / ".env"):
        with pytest.raises(g.Refused, match="hidden"):
            g.sendable(p, [send_dir.resolve()])


def test_sendable_refuses_missing_and_directories(send_dir):
    with pytest.raises(g.Refused, match="no such file"):
        g.sendable(send_dir / "nope.pdf", [send_dir.resolve()])
    (send_dir / "folder").mkdir()
    with pytest.raises(g.Refused, match="regular file"):
        g.sendable(send_dir / "folder", [send_dir.resolve()])


def test_attachments_over_25_mb_refused(send_dir, monkeypatch):
    monkeypatch.setattr(g, "MAX_ATTACH", 10)
    (send_dir / "a.bin").write_bytes(b"x" * 6)
    (send_dir / "b.bin").write_bytes(b"x" * 6)
    with pytest.raises(g.Refused, match="25 MB"):
        g.load_attachments([send_dir / "a.bin", send_dir / "b.bin"], [send_dir.resolve()])


# ---------- the message


def test_message_round_trips_attachment_bytes_exactly():
    data = os.urandom(70_000)
    raw = g.build_message(ME, ["a@x.com"], ["c@x.com"], "Report – Oct", "Hi\nthere", [("r.pdf", data)],
                          html="<b>Hi</b>")
    assert raw.split(b"\r\n\r\n", 1)[0].count(b"\n") == raw.split(b"\r\n\r\n", 1)[0].count(b"\r\n")  # CRLF headers
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    assert msg["Bcc"] is None
    assert msg["To"] == "a@x.com" and msg["Cc"] == "c@x.com" and msg["Subject"] == "Report – Oct"
    assert msg.get_body(("plain",)).get_content().replace("\r\n", "\n").strip() == "Hi\nthere"
    assert "<b>Hi</b>" in msg.get_body(("html",)).get_content()
    (att,) = list(msg.iter_attachments())
    assert att.get_filename() == "r.pdf" and att.get_content_type() == "application/pdf"
    assert hashlib.sha256(att.get_content()).digest() == hashlib.sha256(data).digest()


def test_subject_newline_cannot_inject_headers():
    with pytest.raises(ValueError):
        g.build_message(ME, ["a@x.com"], [], "x\nBcc: evil@y.com", "", [])


# ---------- approval


def test_reason_names_recipients_subject_files_and_cleans_text():
    r = g.approval_reason(["a@x.com", "b@x.com"], "Q‮Report", [("r.pdf", b"x" * 2048)], "line1\n\x1b[31mline2" + "z" * 300)
    assert r.startswith("send an email to a@x.com, b@x.com; subject \"Q Report\"; attaching r.pdf (2.0 KB)")
    assert "\x1b" not in r and "‮" not in r and "line1 [31mline2" in r and r.endswith("…\"")


def fake_helper(tmp_path, open_code=0, token="1//refresh"):
    """A stand-in for the Secure Enclave helper: seal stores stdin, open prints it after logging the reason."""
    h = g.approver_path()
    h.parent.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "helper.log"
    h.write_text(f"""#!/bin/sh
printf '%s|%s\\n' "$1" "$3" >> '{log}'
case "$1" in
  seal) cat > "$2/token.sealed"; : > "$2/key.se" ;;
  open) [ -f "$2/token.sealed" ] || exit 3; [ {open_code} -eq 0 ] && cat "$2/token.sealed"; exit {open_code} ;;
esac
""")
    h.chmod(h.stat().st_mode | stat.S_IEXEC)
    return log


def test_seal_then_unlock_round_trip_passes_reason_as_one_argument(tmp_path, home):
    log = fake_helper(tmp_path)
    g.seal_token("1//secret-refresh")
    assert g.signed_in()
    assert g.unlock_token('send an email to a@x.com; subject "$(rm -rf ~)"') == "1//secret-refresh"
    assert log.read_text().splitlines() == ["seal|", 'open|send an email to a@x.com; subject "$(rm -rf ~)"']


def test_token_goes_to_the_helper_on_stdin_never_argv(home, tmp_path):
    fake_helper(tmp_path)
    seen = []

    def run(args, **kw):
        seen.append((args, kw.get("input")))
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    g.seal_token("1//0gSecret", run=run)
    (args, stdin), = seen
    assert args[1:] == ["seal", str(home)] and "1//0gSecret" not in " ".join(args) and stdin == b"1//0gSecret"


@pytest.mark.parametrize("code,msg", [(1, "not approved"), (2, "isn't available"), (3, "not signed in")])
def test_unlock_decline_unavailable_and_missing_refuse(tmp_path, home, code, msg):
    fake_helper(tmp_path, open_code=code)
    g.seal_token("1//r")
    if code == 3:
        g.forget_token()
    with pytest.raises(g.Refused, match=msg):
        g.unlock_token("x")


def test_unlock_timeout_refuses(tmp_path, home, monkeypatch):
    fake_helper(tmp_path)

    def run(*a, **k):
        raise subprocess.TimeoutExpired("helper", 1)

    with pytest.raises(g.Refused, match="timed out"):
        g.unlock_token("x", run=run)


def test_nothing_works_without_the_helper(home):
    for call in (lambda: g.unlock_token("x"), lambda: g.seal_token("t")):
        with pytest.raises(g.Refused, match="helper isn't installed"):
            call()


# ---------- send flow


class Calls:
    def __init__(self):
        self.reasons, self.posted = [], []

    def token(self, reason):
        self.reasons.append(reason)
        return "tok"

    def post(self, url, data, headers):
        self.posted.append((url, data, headers))
        return {"id": "m1", "labelIds": ["SENT"]}


def test_send_to_self_still_needs_touch_id(send_dir):
    (send_dir / "r.pdf").write_bytes(b"%PDF-1.4")
    c, out = Calls(), []
    g.send(["me"], [], "s", "t", [send_dir / "r.pdf"], post_raw=c.post, token=c.token, out=out.append)
    assert c.reasons == ['send an email to you; subject "s"; attaching r.pdf (8 bytes); text "t"']
    url, raw, headers = c.posted[0]
    assert url == g.SEND_URL and headers == {"Authorization": "Bearer tok", "Content-Type": "message/rfc822"}
    assert hashlib.sha256(b"%PDF-1.4").hexdigest() in out[0]


def test_send_to_others_names_every_recipient(send_dir):
    c = Calls()
    g.send(["me"], ["x@y.com"], "s", "t", [], post_raw=c.post, token=c.token, out=lambda *_: None)
    assert c.reasons[0].startswith("send an email to you, x@y.com;") and len(c.posted) == 1


def test_declined_approval_sends_nothing(send_dir):
    def decline(reason):
        raise g.Refused("not approved")

    c = Calls()
    with pytest.raises(g.Refused):
        g.send(["x@y.com"], [], "s", "t", [], post_raw=c.post, token=decline, out=lambda *_: None)
    assert c.posted == []


def test_draft_needs_touch_id_and_goes_to_drafts(send_dir):
    (send_dir / "r.pdf").write_bytes(b"%PDF")
    c, out = Calls(), []
    g.send(["x@y.com"], ["z@y.com"], "s", "t", [send_dir / "r.pdf"], draft=True, post_raw=c.post, token=c.token, out=out.append)
    assert c.reasons[0].startswith("save a draft email to x@y.com, z@y.com;")
    assert [u for u, _, _ in c.posted] == [g.DRAFT_URL] and "Gmail Drafts" in out[-1]


def test_dry_run_sends_nothing_and_asks_nothing(send_dir):
    c = Calls()
    g.send(["x@y.com"], [], "s", "t", [], dry_run=True, post_raw=c.post, token=c.token, out=lambda *_: None)
    assert c.posted == [] and c.reasons == []


def test_html_file_obeys_send_folders(tmp_path, send_dir):
    (tmp_path / "body.html").write_text("<p>x</p>")
    with pytest.raises(g.Refused, match="only from"):
        g.send(["me"], [], "s", "t", [], html_file=tmp_path / "body.html", dry_run=True, out=lambda *_: None)


def test_send_requires_sign_in_and_subject(home, send_dir):
    with pytest.raises(g.Refused, match="subject"):
        g.send(["me"], [], "  ", "t", [], dry_run=True, out=lambda *_: None)
    g.write_private(home / "config.json", {})
    with pytest.raises(g.Refused, match="not signed in"):
        g.send(["a@x.com"], [], "s", "t", [], dry_run=True, out=lambda *_: None)


# ---------- setup, tokens


def test_setup_accepts_only_desktop_clients_and_stores_privately(tmp_path, home):
    web = tmp_path / "web.json"
    web.write_text(json.dumps({"web": {"client_id": "x"}}))
    with pytest.raises(g.Refused, match="Desktop"):
        g.setup(web)
    desktop = tmp_path / "desktop.json"
    desktop.write_text(json.dumps({"installed": {"client_id": "cid", "client_secret": "sec", "project_id": "p"}}))
    g.setup(desktop)
    stored = home / "client.json"
    assert json.loads(stored.read_text()) == {"client_id": "cid", "client_secret": "sec"}
    assert stat.S_IMODE(stored.stat().st_mode) == 0o600 and stat.S_IMODE(home.stat().st_mode) == 0o700


def test_access_token_unlocks_once_with_the_reason(send_dir):
    seen = []
    post = lambda url, data, headers: seen.append(dict(urllib.parse.parse_qsl(data.decode()))) or {"access_token": "a1"}  # noqa: E731
    assert g.access_token("why", post=post, unlock=lambda r: f"refresh-for:{r}") == "a1"
    assert seen[0]["refresh_token"] == "refresh-for:why" and seen[0]["grant_type"] == "refresh_token"


def test_expired_sign_in_says_log_in_again(send_dir):
    def post(*a):
        raise g.Refused("Google said HTTP 400: Token has been expired or revoked.")

    with pytest.raises(g.Refused, match="gmail-send login"):
        g.access_token("why", post=post, unlock=lambda r: "1//r")


def test_logout_deletes_without_a_scan(tmp_path, send_dir, home):
    log = fake_helper(tmp_path)
    g.seal_token("1//r")
    assert g.logout() == ME
    assert not g.signed_in() and not (home / "key.se").exists()
    assert "account" not in json.loads((home / "config.json").read_text())
    assert "open|" not in log.read_text()  # the helper was never asked to unlock: no Touch ID
    assert g.logout() is None


def test_id_token_email_requires_verified():
    assert g.id_token_email(id_token({"email": "Owner@Example.com", "email_verified": True})) == ME
    with pytest.raises(g.Refused):
        g.id_token_email(id_token({"email": ME, "email_verified": False}))


# ---------- sign-in through the real loopback server


def browser_that_returns(params_for):
    """A stand-in browser: reads the auth URL and calls the loopback redirect like Google would."""
    seen = {}

    def open_browser(url):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        seen.update(q)

        def hit():
            urllib.request.urlopen(q["redirect_uri"] + "/favicon.ico", timeout=5).read()
            urllib.request.urlopen(q["redirect_uri"] + "/?" + urllib.parse.urlencode(params_for(q)), timeout=5).read()

        threading.Thread(target=hit, daemon=True).start()

    return open_browser, seen


def token_endpoint(scope=g.COMPOSE_SCOPE + " openid", refresh="1//refresh"):
    calls = []

    def post(url, data, headers):
        calls.append(dict(urllib.parse.parse_qsl(data.decode())))
        tok = {"access_token": "a", "scope": scope, "id_token": id_token({"email": ME, "email_verified": True})}
        if refresh:
            tok["refresh_token"] = refresh
        return tok

    return post, calls


def test_login_full_flow(tmp_path, send_dir, home):
    fake_helper(tmp_path)
    browser, seen = browser_that_returns(lambda q: {"code": "c1", "state": q["state"]})
    post, calls = token_endpoint()
    stored = {}
    assert g.login(open_browser=browser, post=post, store=lambda t: stored.update({ME: t}), wait=20) == ME
    assert seen["redirect_uri"].startswith("http://127.0.0.1:") and seen["code_challenge_method"] == "S256"
    assert seen["scope"] == " ".join(g.SCOPES) and seen["access_type"] == "offline"
    (ex,) = calls
    assert ex["code"] == "c1" and ex["grant_type"] == "authorization_code"
    assert base64.urlsafe_b64encode(hashlib.sha256(ex["code_verifier"].encode()).digest()).rstrip(b"=").decode() == seen["code_challenge"]
    assert stored == {ME: "1//refresh"} and json.loads((home / "config.json").read_text())["account"] == ME


def test_login_rejects_wrong_state(tmp_path, send_dir):
    fake_helper(tmp_path)
    browser, _ = browser_that_returns(lambda q: {"code": "c1", "state": "forged"})
    post, calls = token_endpoint()
    with pytest.raises(g.Refused, match="state"):
        g.login(open_browser=browser, post=post, store=lambda *a: None, wait=20)
    assert calls == []


def test_login_reports_google_refusal(tmp_path, send_dir):
    fake_helper(tmp_path)
    browser, _ = browser_that_returns(lambda q: {"error": "access_denied", "state": q["state"]})
    with pytest.raises(g.Refused, match="access_denied"):
        g.login(open_browser=browser, post=lambda *a: pytest.fail("posted"), store=lambda *a: None, wait=20)


@pytest.mark.parametrize("scope,refresh,msg", [
    ("openid email", "1//r", "email permission"),
    ("https://www.googleapis.com/auth/gmail.send openid", "1//r", "email permission"),
    (g.COMPOSE_SCOPE, None, "lasting"),
])
def test_login_needs_send_scope_and_refresh_token(tmp_path, send_dir, scope, refresh, msg):
    fake_helper(tmp_path)
    browser, _ = browser_that_returns(lambda q: {"code": "c", "state": q["state"]})
    post, _ = token_endpoint(scope=scope, refresh=refresh)
    with pytest.raises(g.Refused, match=msg):
        g.login(open_browser=browser, post=post, store=lambda *a: pytest.fail("stored"), wait=20)


# ---------- the command


def test_cli_dry_run_end_to_end(tmp_path, send_dir, home):
    (send_dir / "r.pdf").write_bytes(b"%PDF")
    env = dict(os.environ, GMAIL_SEND_HOME=str(home))
    script = Path(g.__file__).with_name("gmail-send")
    r = subprocess.run([sys.executable, str(script), "me", "-s", "Hi", "--file", str(send_dir / "r.pdf"), "--dry-run", "hello"],
                       capture_output=True, text=True, env=env, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "To:       owner@example.com" in r.stdout and "Dry run: nothing sent or saved." in r.stdout
    r = subprocess.run([sys.executable, str(script), "me", "-s", "Hi", "--file", "/etc/hosts", "--dry-run"],
                       capture_output=True, text=True, env=env, cwd=tmp_path)
    assert r.returncode == 1 and "attachments come only from" in r.stderr
    r = subprocess.run([sys.executable, str(script), "me", "-s", "Hi", "--dry-run", "-"], input="from stdin\n",
                       capture_output=True, text=True, env=env, cwd=tmp_path)
    assert r.returncode == 0 and "  from stdin" in r.stdout


# ---------- replies in a thread


ORIG_ID = "1a1ab97a1a956b87"


ORIG_TEXT = "Please review the October numbers.\n\nThanks,\nBoss"
ORIG_HTML = "<div>Please review the <b>October</b> numbers.</div><div>Thanks,<br>Boss</div>"


def original(text=ORIG_TEXT, html=ORIG_HTML, **over):
    """Gmail's answer for both formats: metadata headers, or the raw message built by Python's own writer."""
    headers = {"Message-ID": "<orig@mail.example.com>", "References": "<root@x>", "Subject": "Oct report",
               "From": "Boss <boss@example.com>", "To": f"{ME}, peer@example.com", "Cc": "lead@example.com",
               "Date": "Thu, 05 Nov 2026 11:56:07 +0000"}
    headers.update(over)
    meta = {"id": ORIG_ID, "threadId": "t123",
            "payload": {"headers": [{"name": k, "value": v} for k, v in headers.items() if v is not None]}}
    if any("\n" in str(v) for v in headers.values() if v):
        return meta  # only the metadata API can hand back a header like that
    msg = email.message.EmailMessage()
    for k, v in headers.items():
        if v is not None:
            msg[k] = v
    if text is not None:
        msg.set_content(text)
    if html is not None:
        if text is None:
            msg.set_content(html, subtype="html")
        else:
            msg.add_alternative(html, subtype="html")
    return {**meta, "raw": base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip("=")}


def reply_env(home, scopes=(g.COMPOSE_SCOPE, g.READ_SCOPE)):
    cfg = json.loads((home / "config.json").read_text())
    cfg["scopes"] = list(scopes)
    g.write_private(home / "config.json", cfg)


def getter(msg, seen, signature=""):
    def get(url, headers):
        seen.append(url)
        return {"signature": signature} if "/settings/sendAs/" in url else msg
    return get


def test_reply_all_is_one_scan_that_reads_then_sends(send_dir, home):
    reply_env(home)
    c, seen, out = Calls(), [], []
    g.send([], [], None, "Thanks", [], reply_to=ORIG_ID, reply_all=True, post_raw=c.post,
           get=getter(original(), seen), token=c.token, out=out.append)
    assert c.reasons == ['send a reply to email 1a1ab97a1a956b87, to everyone on it, quoting it; text "Thanks"']
    assert seen == [g.RAW_URL.format(id=ORIG_ID)]  # read once; no signature lookup during sends
    url, body, headers = c.posted[0]
    assert url == g.SEND_URL.replace("uploadType=media", "uploadType=multipart")
    assert headers["Content-Type"].startswith("multipart/related; boundary=") and b'{"threadId": "t123"}' in body
    msg = sent_message(c)
    assert msg["In-Reply-To"] == "<orig@mail.example.com>" and msg["References"] == "<root@x> <orig@mail.example.com>"
    assert msg["Subject"] == "Re: Oct report" and msg["To"] == "boss@example.com, peer@example.com"
    assert msg["Cc"] == "lead@example.com" and ME not in msg["To"] + msg["Cc"]
    assert any('Reply to: "Oct report" from boss@example.com' in line for line in out)
    assert "review the October" not in "\n".join(out)  # someone else's text is never printed


def test_reply_to_sender_and_named_recipients_in_the_prompt(send_dir, home):
    reply_env(home)
    c = Calls()
    g.send([], [], None, "ok", [], reply_to=ORIG_ID, post_raw=c.post, get=getter(original(), []), token=c.token,
           out=lambda *_: None)
    assert c.reasons[0].startswith("send a reply to email 1a1ab97a1a956b87, to its sender, quoting it")
    c = Calls()
    g.send(["x@example.com"], ["y@example.com"], None, "ok", [], reply_to=ORIG_ID, quote=False, post_raw=c.post,
           get=getter(original(), []), token=c.token, out=lambda *_: None)
    assert c.reasons[0].startswith("send a reply to email 1a1ab97a1a956b87, to x@example.com, cc y@example.com;")


def test_draft_reply_carries_thread_in_message(send_dir, home):
    reply_env(home)
    c = Calls()
    g.send([], [], None, "t", [], reply_to=ORIG_ID, draft=True, post_raw=c.post, get=getter(original(), []),
           token=c.token, out=lambda *_: None)
    url, body, _ = c.posted[0]
    assert url == g.DRAFT_URL.replace("uploadType=media", "uploadType=multipart")
    assert b'{"message": {"threadId": "t123"}}' in body and c.reasons[0].startswith("save a draft reply to email")


def test_dry_run_reply_reads_once_and_sends_nothing(send_dir, home):
    reply_env(home)
    c, out = Calls(), []
    g.send([], [], None, "t", [], reply_to=ORIG_ID, reply_all=True, dry_run=True, post_raw=c.post,
           get=getter(original(), []), token=c.token, out=out.append)
    assert c.reasons == ["read one email (1a1ab97a1a956b87) to preview a reply; nothing is sent"] and c.posted == []
    assert any("To:       boss@example.com, peer@example.com" in line for line in out)


def test_reply_refusals(send_dir, home):
    c = Calls()
    with pytest.raises(g.Refused, match="login` again"):  # signed in before replies existed
        g.send([], [], None, "t", [], reply_to=ORIG_ID, token=c.token, out=lambda *_: None)
    reply_env(home, scopes=(g.COMPOSE_SCOPE, g.METADATA_SCOPE))  # a 0.2.0 sign-in: headers only
    with pytest.raises(g.Refused, match="or --no-quote"):
        g.send([], [], None, "t", [], reply_to=ORIG_ID, token=c.token, out=lambda *_: None)
    reply_env(home)
    with pytest.raises(g.Refused, match="not a Gmail message id"):
        g.send([], [], None, "t", [], reply_to="../../drafts", token=c.token, out=lambda *_: None)
    with pytest.raises(g.Refused, match="needs --reply-to"):
        g.send(["a@example.com"], [], "s", "t", [], reply_all=True, token=c.token, out=lambda *_: None)
    with pytest.raises(g.Refused, match="no Message-ID"):
        g.send([], [], None, "t", [], reply_to=ORIG_ID, quote=False, get=getter(original(**{"Message-ID": None}), []),
               token=c.token, out=lambda *_: None)
    assert c.posted == [] and len(c.reasons) == 1  # only the last one got as far as the scan


def test_original_subject_cannot_inject_headers(send_dir, home):
    reply_env(home)
    c = Calls()
    g.send([], [], None, "t", [], reply_to=ORIG_ID, quote=False, post_raw=c.post,
           get=getter(original(Subject="hi\u202e\nBcc: evil@x"), []), token=c.token, out=lambda *_: None)
    msg = sent_message(c)
    assert msg["Bcc"] is None and "\u202e" not in msg["Subject"] and msg["Subject"].startswith("Re: hi")


def test_cli_reply_parsing_puts_positionals_in_text(tmp_path, send_dir, home):
    import importlib.machinery, importlib.util
    script = Path(g.__file__).with_name("gmail-send")
    loader = importlib.machinery.SourceFileLoader("gmail_send_cli", str(script))
    cli = importlib.util.module_from_spec(importlib.util.spec_from_loader("gmail_send_cli", loader))
    loader.exec_module(cli)
    a = cli.send_args(["--reply-to", ORIG_ID, "--all", "Thanks", "both", "--draft"])
    assert (a.reply_to, a.all, a.text, a.to, a.draft) == (ORIG_ID, True, ["Thanks", "both"], [], True)
    a = cli.send_args(["x@example.com", "-s", "S", "hello"])
    assert (a.to, a.text) == ("x@example.com", ["hello"])


# ---------- quoting the original


def sent_message(c):
    raw = c.posted[0][1].split(b"Content-Type: message/rfc822\r\n\r\n", 1)[1].rsplit(b"\r\n--gmail-send-", 1)[0]
    return email.message_from_bytes(raw, policy=email.policy.default)


def test_reply_quotes_the_original_like_gmail(send_dir, home):
    reply_env(home)
    c = Calls()
    g.send([], [], None, "Looks good.", [], reply_to=ORIG_ID, post_raw=c.post, get=getter(original(), []),
           token=c.token, out=lambda *_: None)
    msg = sent_message(c)
    text = msg.get_body(("plain",)).get_content().replace("\r\n", "\n")
    assert text.startswith("Looks good.\n\nOn Thu, 5 Nov 2026 at ") and ", Boss <boss@example.com> wrote:\n" in text
    assert "> Please review the October numbers.\n>\n> Thanks,\n> Boss" in text
    html = msg.get_body(("html",)).get_content()
    assert html.startswith('<div dir="ltr">Looks good.</div><br><div class="gmail_quote">')
    assert 'class="gmail_quote" style="margin:0px 0px 0px 0.8ex' in html and ORIG_HTML in html
    assert "Boss &lt;boss@example.com&gt; wrote:" in html


def test_no_quote_reads_headers_only_and_sends_just_your_text(send_dir, home):
    reply_env(home, scopes=(g.COMPOSE_SCOPE, g.METADATA_SCOPE))  # works with a headers-only sign-in
    c, seen = Calls(), []
    g.send([], [], None, "Just this.", [], reply_to=ORIG_ID, quote=False, post_raw=c.post,
           get=getter(original(), seen), token=c.token, out=lambda *_: None)
    assert seen[0].startswith(g.META_URL.format(id=ORIG_ID))
    msg = sent_message(c)
    assert msg.get_body(("plain",)).get_content().strip() == "Just this." and msg.get_body(("html",)) is None
    assert ", quoting it" not in c.reasons[0]


def test_quote_keeps_your_html_and_quotes_a_text_only_original(tmp_path, send_dir, home):
    reply_env(home)
    (send_dir / "body.html").write_text("<p>Mine <i>styled</i></p>")
    c = Calls()
    g.send([], [], None, "Mine styled", [], html_file=send_dir / "body.html", reply_to=ORIG_ID, post_raw=c.post,
           get=getter(original(html=None, text="a < b & c"), []), token=c.token, out=lambda *_: None)
    html = sent_message(c).get_body(("html",)).get_content()
    assert html.startswith("<p>Mine <i>styled</i></p><br><div class=\"gmail_quote\">") and "a &lt; b &amp; c" in html


def test_html_only_original_is_quoted_as_text_too(send_dir, home):
    reply_env(home)
    c = Calls()
    g.send([], [], None, "ok", [], reply_to=ORIG_ID, post_raw=c.post,
           get=getter(original(text=None, html="<p>Hi<br>there</p><script>x()</script>"), []), token=c.token,
           out=lambda *_: None)
    text = sent_message(c).get_body(("plain",)).get_content()
    assert "> Hi\r\n> there" in text and "x()" not in text


# ---------- signature (saved file)


def test_signature_from_the_file_goes_under_your_text_and_above_the_quote(send_dir, home):
    reply_env(home)
    g.save_signature("<b>Utkarsh</b><br>Platform")
    c, out = Calls(), []
    g.send([], [], None, "Looks good.", [], reply_to=ORIG_ID, post_raw=c.post, get=getter(original(), []),
           token=c.token, out=out.append)
    msg = sent_message(c)
    text = msg.get_body(("plain",)).get_content().replace("\r\n", "\n")
    assert text.index("Looks good.") < text.index("-- \nUtkarsh\nPlatform") < text.index("wrote:")
    html = msg.get_body(("html",)).get_content()
    assert html.index("Looks good.") < html.index('class="gmail_signature"') < html.index('class="gmail_quote"')
    assert any("Signature: from" in line for line in out)


def test_plain_send_uses_the_file_without_any_lookup(send_dir, home):
    g.save_signature("Utkarsh")
    assert stat.S_IMODE(g.signature_path().stat().st_mode) == 0o600
    c, seen = Calls(), []
    g.send(["me"], [], "s", "Hi", [], post_raw=c.post, get=getter({}, seen), token=c.token, out=lambda *_: None)
    msg = email.message_from_bytes(c.posted[0][1], policy=email.policy.default)
    assert msg.get_body(("plain",)).get_content().replace("\r\n", "\n").strip() == "Hi\n\n-- \nUtkarsh"
    assert 'class="gmail_signature"' in msg.get_body(("html",)).get_content() and seen == []


def test_no_signature_flag_empty_or_missing_file_leave_the_body_alone(send_dir, home):
    for setup_sig, kwargs in (("Utkarsh", {"signature": False}), ("", {}), (None, {})):
        if setup_sig is None:
            g.signature_path().unlink(missing_ok=True)
        else:
            g.save_signature(setup_sig)
        c = Calls()
        g.send(["me"], [], "s", "Hi", [], post_raw=c.post, token=c.token, out=lambda *_: None, **kwargs)
        msg = email.message_from_bytes(c.posted[0][1], policy=email.policy.default)
        assert msg.get_body(("plain",)).get_content().strip() == "Hi" and msg.get_body(("html",)) is None


def test_login_saves_the_signature_without_a_scan(tmp_path, send_dir, home):
    log = fake_helper(tmp_path)
    browser, _ = browser_that_returns(lambda q: {"code": "c1", "state": q["state"]})
    post, _ = token_endpoint(scope=g.COMPOSE_SCOPE + " " + g.READ_SCOPE)
    seen = []
    g.login(open_browser=browser, post=post, wait=20, get=getter({}, seen, signature="<i>U</i>"))
    assert g.load_signature() == "<i>U</i>" and seen == [g.SENDAS_URL.format(email=urllib.parse.quote(ME))]
    assert "open|" not in log.read_text()


def test_refresh_signature_is_one_scan(send_dir, home):
    c = Calls()
    assert g.refresh_signature(get=getter({}, [], signature="New"), token=c.token) == "New"
    assert g.load_signature() == "New" and c.reasons == ["read your Gmail signature to save it for gmail-send; nothing is sent"]


# ---------- HTML from stdin


def test_html_from_stdin_needs_no_file(tmp_path, send_dir, home):
    env = dict(os.environ, GMAIL_SEND_HOME=str(home))
    script = Path(g.__file__).with_name("gmail-send")
    r = subprocess.run([sys.executable, str(script), "me", "-s", "Hi", "--html", "-", "--dry-run", "plain text"],
                       input="<p>from stdin</p>", capture_output=True, text=True, env=env, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "HTML:     17 bytes" in r.stdout and "  plain text" in r.stdout
    r = subprocess.run([sys.executable, str(script), "me", "-s", "Hi", "--html", "-", "--dry-run", "-"],
                       input="x", capture_output=True, text=True, env=env, cwd=tmp_path)
    assert r.returncode == 1 and "not both" in r.stderr

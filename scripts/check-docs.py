#!/usr/bin/env python3
"""Documentation gate (CI job `docs`). See docs/contributing/documentation-mandate.md.

Checks: every module has module.yaml + README.md; every relative markdown link resolves; every tracked .md is
reachable from AGENTS.md; ADR filenames and headers are valid, none is `proposed`, and each is in the ADR index;
CLAUDE.md and CURSOR.md point at AGENTS.md; no OAuth client file is tracked.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULES = ["plugins/whatsapp", "plugins/whatsapp/bridge", "plugins/whatsapp/server", "plugins/gmail"]
ADR_DIR = ROOT / "docs/architecture/decisions"
ADR_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-[0-9a-f]{6}-[a-z0-9-]+\.md$")
ADR_HEADERS = ["Status", "Date", "Deciders", "Scope", "Supersedes / Amends"]
SCOPES = {"bridge", "server", "plugin", "gmail", "repo"}
# Files GitHub or tools read directly, not part of the doc graph
UNREACHABLE_OK = {".github/pull_request_template.md"}
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")

errors = []


def tracked_md():
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "*.md", "*.mdc"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return sorted(p for p in out.split() if (ROOT / p).exists())


def links(path):
    text = (ROOT / path).read_text()
    text = re.sub(r"```.*?```", "", text, flags=re.S)  # ignore code blocks
    for target in LINK.findall(text):
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue
        yield target.split("#")[0]


def resolve(src, target):
    return ((ROOT / src).parent / target).resolve()


files = tracked_md()

for m in MODULES:
    for f in ("module.yaml", "README.md"):
        if not (ROOT / m / f).exists():
            errors.append(f"{m}: missing {f}")

for f in files:
    for t in links(f):
        if not resolve(f, t).exists():
            errors.append(f"{f}: broken link -> {t}")

seen, queue = set(), ["AGENTS.md"]
while queue:
    cur = queue.pop()
    if cur in seen:
        continue
    seen.add(cur)
    for t in links(cur):
        p = resolve(cur, t)
        if p.is_dir():
            p = p / "README.md"
        if p.exists() and p.suffix in (".md", ".mdc"):
            queue.append(str(p.relative_to(ROOT)))
for f in files:
    if f not in seen and f not in UNREACHABLE_OK:
        errors.append(f"{f}: not reachable from AGENTS.md")

index = (ADR_DIR / "README.md").read_text()
for adr in sorted(ADR_DIR.glob("*.md")):
    if adr.name in ("README.md", "adr-template.md"):
        continue
    if not ADR_NAME.match(adr.name):
        errors.append(f"{adr.name}: ADR filename must be YYYY-MM-DD-<6 hex>-<slug>.md")
    text = adr.read_text()
    for h in ADR_HEADERS:
        if not re.search(rf"^- \*\*{re.escape(h)}:\*\* \S", text, re.M):
            errors.append(f"{adr.name}: missing header '{h}'")
    status = re.search(r"^- \*\*Status:\*\* (\S+)", text, re.M)
    if status and status.group(1) == "proposed":
        errors.append(f"{adr.name}: status 'proposed' cannot merge (a merged ADR is accepted)")
    scope = re.search(r"^- \*\*Scope:\*\* (\S+)", text, re.M)
    if scope and scope.group(1) not in SCOPES:
        errors.append(f"{adr.name}: scope must be one of {sorted(SCOPES)}")
    if f"({'./' + adr.name})" not in index:
        errors.append(f"{adr.name}: not listed in decisions/README.md")

# Security model G7: no OAuth client (personal config) in this public repo
tracked = subprocess.run(["git", "ls-files", "-c", "--", "*client_secret*.json"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout.split()
for f in tracked:
    errors.append(f"{f}: an OAuth client must never be committed (security model G7)")

for entry in ("CLAUDE.md", "CURSOR.md"):
    if "AGENTS.md" not in (ROOT / entry).read_text():
        errors.append(f"{entry}: must point at AGENTS.md")

if errors:
    print("\n".join(f"docs: {e}" for e in errors))
    sys.exit(1)
print(f"docs: ok ({len(files)} documents, {len(MODULES)} modules, all reachable from AGENTS.md)")

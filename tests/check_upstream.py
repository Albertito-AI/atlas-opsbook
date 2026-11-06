"""Integration check for a fetched upstream checkout, including its full Git tree."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pstack

repo = Path(".opsbook/upstream")
ref = pstack.LOCK["commit"]
tree = pstack.verify(repo, pstack.LOCK)
files = set(pstack.git(repo, "ls-tree", "-r", "--name-only", ref, "pstack").splitlines())
groups = (("skills","skill"),("playbooks","playbook"),("agents","agent"),("automations","automation"))
for group, kind in groups:
    for value in pstack.LOCK[group]:
        name = "pstack/" + pstack.source_path(kind,value)
        if name not in files:
            raise SystemExit("Missing pinned file: " + name)
if set(pstack.LOCK["skills"]) != {p.split("/")[2] for p in files if p.startswith("pstack/skills/") and p.endswith("/SKILL.md")}:
    raise SystemExit("Skill catalogue incomplete")
print("Verified upstream tree",tree,"and all indexed workflow entry points.")

"""Read original pstack workflows from a pinned, verified upstream Git tree."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent
LOCK = json.loads((ROOT / "upstream.lock.json").read_text(encoding="utf-8"))


def git(directory, *args):
    return subprocess.run(["git", "-C", str(directory), *args], check=True,
                          stdout=subprocess.PIPE, text=True).stdout


def verify(directory, lock):
    actual = git(directory, "rev-parse", lock["commit"] + ":pstack").strip()
    if actual != lock["pstack_tree"]:
        raise ValueError("Upstream tree differs from the lock.")
    return actual


def fetch(destination):
    if destination.exists():
        return verify(destination, LOCK)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination.parent) as tmp:
        staging = Path(tmp) / "source"
        staging.mkdir()
        git(staging, "init", "--quiet")
        git(staging, "remote", "add", "origin", LOCK["repository"] + ".git")
        git(staging, "sparse-checkout", "init", "--cone")
        git(staging, "sparse-checkout", "set", "pstack", "harness/pstack", ".claude-plugin")
        git(staging, "fetch", "--depth=1", "--filter=blob:none", "origin", LOCK["commit"])
        git(staging, "checkout", "--quiet", "--detach", "FETCH_HEAD")
        tree = verify(staging, LOCK)
        if destination.exists():
            return verify(destination, LOCK)
        staging.rename(destination)
    return tree


def source_path(kind, name):
    groups = {"skill": "skills", "playbook": "playbooks", "agent": "agents", "automation": "automations"}
    if name not in LOCK[groups[kind]]:
        raise ValueError("Unknown upstream entry. Run list to see verified names.")
    return {"skill": f"skills/{name}/SKILL.md", "playbook": f"skills/poteto-mode/playbooks/{name}.md",
            "agent": f"agents/{name}", "automation": f"automations/{name}/FOR_AGENTS.md"}[kind]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, default=Path(".opsbook/upstream"))
    sp = p.add_subparsers(dest="cmd", required=True)
    for cmd in ("list", "fetch", "verify"):
        sp.add_parser(cmd)
    show = sp.add_parser("show")
    show.add_argument("kind", choices=["skill", "playbook", "agent", "automation"])
    show.add_argument("name")
    args = p.parse_args()
    try:
        if args.cmd == "list":
            print(json.dumps(LOCK, indent=2))
        elif args.cmd == "fetch":
            print(fetch(args.source))
        else:
            tree = verify(args.source, LOCK)
            if args.cmd == "verify":
                print(tree)
            else:
                path = source_path(args.kind, args.name)
                print(git(args.source, "show", LOCK["commit"] + ":pstack/" + path), end="")
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

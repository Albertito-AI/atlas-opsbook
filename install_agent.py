"""Connect the manual to an agent's normal project entry point."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
START = "<!-- atlas-opsbook:start -->"
END = "<!-- atlas-opsbook:end -->"
INSTRUCTIONS = """At task intake, identify the project facts (such as task and artefact). Run
`python .opsbook/bin/opsbook.py brief '<context JSON>'` from the repository root.
Read the matching procedures and follow them within the owner's existing authority.
If pstack is installed, use its usual router and playbook for the engineering work.

After a significant failure, correction or repeated success, retain a sanitised
case with observable evidence, the expected checks and a nearby counterexample.
Use `record` for cases, then write a conditional rule with `propose`, or use
`learn CASE CHECK "instruction"` to infer its conditions from practice cases.
Use independently labelled exam cases. Run `evaluate ID` and inspect every
new error. Use `promote ID` only within project policy. Read `manual` for the
current text. At task completion use `verify CONTEXT --checks TRUSTED_FILE`
for executable checks. Use `gate` only for externally verified check names.
Never infer permission from an observation or a learned rule. If the manual
causes harm, use `history` then `rollback REVISION "reason"` and retain the case."""
BLOCK = START + "\n## Project operations manual\n\n" + INSTRUCTIONS + "\n" + END


def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(data)
    except FileExistsError:
        if path.read_bytes() != data:
            raise ValueError(f"Existing file differs: {path}. Review it before upgrading.")


def install(root, host):
    root = root.resolve(strict=True)
    bin_dir = root / ".opsbook/bin"
    dest = {"codex": "AGENTS.md", "cursor": ".cursor/rules/atlas-opsbook.mdc",
            "claude": ".claude/rules/atlas-opsbook.md"}[host]
    path = root / dest
    paths = [bin_dir / "opsbook.py", root / ".opsbook/manual.db", root / ".opsbook/.gitignore", path,
             bin_dir / "examples/cases.json", bin_dir / "examples/overbroad.json"]
    for item in paths:
        if item.resolve() != item:
            raise ValueError(f"Use ordinary project paths (symlink found): {item}")
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    prefix = "---\ndescription: Read and revise the project operations manual\nalwaysApply: true\n---\n\n" if host == "cursor" else ""
    if (START in text or END in text) and BLOCK not in text:
        raise ValueError(f"Existing managed instructions were edited: {path}. Review before installing.")
    if host != "codex" and text and text != prefix + BLOCK + "\n":
        raise ValueError(f"An existing rule uses {path}. Review it before installing.")
    write_new(bin_dir / "opsbook.py", (ROOT / "opsbook.py").read_bytes())
    for name in ("cases.json", "overbroad.json"):
        write_new(bin_dir / "examples" / name, (ROOT / "examples" / name).read_bytes())
    write_new(root / ".opsbook/.gitignore", b"manual.db*\nupstream/\n")
    subprocess.run([sys.executable, str(bin_dir / "opsbook.py"), "init"], cwd=root, check=True)
    if BLOCK not in text:
        if host == "codex" and path.exists():
            with path.open("a", encoding="utf-8") as output:
                output.write("\n\n" + BLOCK + "\n")
        else:
            write_new(path, (prefix + BLOCK + "\n").encode())
    print("Installed project instructions in", path)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("host", choices=["cursor", "codex", "claude"])
    p.add_argument("project", type=Path)
    args = p.parse_args()
    try:
        install(args.project, args.host)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        p.exit(2, str(error) + "\n")

"""Exercise the manual against two real zip imports in isolated Python processes."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FACTS = '{"task":"ship","artefact":"package","os":"freebsd"}'


def run(tmp, *args, expected=0):
    result = subprocess.run([sys.executable, str(ROOT / "opsbook.py"), *args], cwd=tmp,
                            capture_output=True, text=True)
    if result.returncode != expected:
        raise RuntimeError(f"{args} returned {result.returncode}: {result.stderr}")
    return json.loads(result.stdout)


def main():
    with tempfile.TemporaryDirectory() as scratch:
        tmp = Path(scratch)
        package = tmp / "widget.zip"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("widget.txt", "mispackaged module")
        command = [sys.executable, "-I", "-c",
                   "import sys; sys.path.insert(0, 'widget.zip'); import atlas_fixture_widget"]
        checks = tmp / "checks.json"
        checks.write_text(json.dumps({"install-clean": command}), encoding="utf-8")
        run(tmp, "init")
        run(tmp, "record", str(ROOT / "examples/cases.json"))
        before = run(tmp, "verify", FACTS, "--checks", str(checks))
        proposal = run(tmp, "learn", "missing-wheel", "install-clean",
                       "Check that the published archive imports in an isolated Python process.")
        run(tmp, "promote", proposal["proposal"])
        broken = run(tmp, "verify", FACTS, "--checks", str(checks), expected=1)
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("atlas_fixture_widget.py", "value = 1\n")
        repaired = run(tmp, "verify", FACTS, "--checks", str(checks))
        print(json.dumps({"before_learning": before, "broken_artifact": broken, "repaired_artifact": repaired}, indent=2))


if __name__ == "__main__":
    main()

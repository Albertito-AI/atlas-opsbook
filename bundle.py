"""Build a distributable ZIP containing Opsbook and the locked original pstack sources."""
from pathlib import Path
import subprocess
import sys
import zipfile
import pstack

root = Path(__file__).resolve().parent
upstream = root / ".opsbook/upstream"
ref = pstack.LOCK["commit"]


def files(repo, revision, *paths):
    raw = subprocess.check_output(["git", "-C", str(repo), "ls-tree", "-rz", "--name-only", revision, "--", *paths])
    return [p.decode() for p in raw.split(b"\0") if p]


def write(z, name, data):
    entry = zipfile.ZipInfo("atlas-opsbook/" + name, (2026, 11, 6, 0, 0, 0))
    entry.compress_type = zipfile.ZIP_DEFLATED
    z.writestr(entry, data)


if __name__ == "__main__":
    pstack.verify(upstream, pstack.LOCK)
    upstream_paths = files(upstream, ref, "pstack", "harness/pstack")
    with zipfile.ZipFile(sys.argv[1], "x") as z:
        for name in files(root, "HEAD"):
            write(z, name, subprocess.check_output(["git", "-C", str(root), "show", "HEAD:" + name]))
        for name in upstream_paths:
            data = subprocess.check_output(["git", "-C", str(upstream), "show", ref + ":" + name])
            write(z, "original/" + name, data)
    print("Bundled original distribution:",len(upstream_paths),"files.")

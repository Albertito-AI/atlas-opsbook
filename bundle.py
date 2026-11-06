"""Package the tracked Opsbook and upstream files, preserving their Git modes."""
from pathlib import Path
import subprocess
import sys
import zipfile

import pstack
from archive_audit import verify_archive

ROOT = Path(__file__).resolve().parent
UPSTREAM = ROOT / ".opsbook/upstream"


def entries(repo, revision, *paths):
    raw = subprocess.check_output(["git", "-C", str(repo), "ls-tree", "-rz", revision, "--", *paths])
    for record in raw.split(b"\0"):
        if record:
            meta, path = record.split(b"\t",1)
            mode, kind, oid = meta.split()
            if kind != b"blob":
                raise ValueError("Unsupported Git entry: " + path.decode())
            yield path.decode(), int(mode,8), oid.decode()


def add_tree(z, repo, ref, prefix, *paths):
    count = 0
    for name, mode, oid in entries(repo, ref, *paths):
        data = subprocess.check_output(["git", "-C", str(repo), "cat-file","blob",oid])
        entry = zipfile.ZipInfo("atlas-opsbook/" + prefix + name,(2026,11,6,0,0,0))
        entry.create_system = 3
        entry.external_attr = mode << 16
        entry.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(entry, data)
        count += 1
    return count


if __name__ == "__main__":
    pstack.verify(UPSTREAM, pstack.LOCK)
    output = Path(sys.argv[1])
    with zipfile.ZipFile(output, "x") as z:
        add_tree(z, ROOT, "HEAD", "")
        count = add_tree(z, UPSTREAM, pstack.LOCK["commit"], "original/", "pstack", "harness/pstack")
    verify_archive(output, "atlas-opsbook/original/pstack/", pstack.LOCK["pstack_tree"])
    adapter = pstack.git(UPSTREAM,"rev-parse",pstack.LOCK["commit"]+":harness/pstack").strip()
    verify_archive(output, "atlas-opsbook/original/harness/pstack/", adapter)
    print("Verified both complete original Git trees inside the archive;",count,"upstream files.")

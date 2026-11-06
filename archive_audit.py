"""Reconstruct the Git tree of an archived directory, including executable bits."""
import argparse
import hashlib
from pathlib import Path
import stat
import sys
import zipfile


def git_hash(kind, data):
    return hashlib.sha1(kind + b" " + str(len(data)).encode() + b"\0" + data).digest()


def tree_id(node):
    records = []
    for name, value in node.items():
        raw = name.encode("utf-8")
        if isinstance(value,dict):
            records.append((raw+b"/", b"40000 "+raw+b"\0"+tree_id(value)))
        else:
            mode, oid = value
            records.append((raw, mode+b" "+raw+b"\0"+oid))
    return git_hash(b"tree", b"".join(record for _,record in sorted(records)))


def verify_archive(path, prefix, expected):
    tree = {}
    with zipfile.ZipFile(path) as z:
        for entry in z.infolist():
            if not entry.filename.startswith(prefix) or entry.is_dir():
                continue
            parts = entry.filename[len(prefix):].split("/")
            if any(part in ("", ".", "..") for part in parts):
                raise ValueError("Invalid archive path.")
            parent = tree
            for part in parts[:-1]:
                parent = parent.setdefault(part, {})
                if not isinstance(parent, dict):
                    raise ValueError("Archive path collision.")
            if parts[-1] in parent:
                raise ValueError("Duplicate archive path.")
            perms = entry.external_attr >> 16
            mode = b"120000" if stat.S_ISLNK(perms) else b"100755" if perms & 0o100 else b"100644"
            parent[parts[-1]] = (mode, git_hash(b"blob", z.read(entry)))
    actual = tree_id(tree).hex()
    if not tree or actual != expected:
        raise ValueError(f"Tree mismatch in {prefix}: expected {expected}, got {actual}")
    return actual


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zipfile", type=Path)
    parser.add_argument("prefix")
    parser.add_argument("expected")
    args=parser.parse_args()
    try:
        print(verify_archive(args.zipfile, args.prefix, args.expected))
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        sys.exit(str(error))

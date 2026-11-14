"""Verify listed files' exact bytes. Integrity is not authorship or authenticity."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

SCHEMA = "atlas.artifact.integrity.v1"
MAX_FILES = 1000
MAX_BYTES = 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
CHUNK = 64 * 1024


def _platform():
    if (os.name != "posix" or os.open not in os.supports_dir_fd
            or not all(hasattr(os, flag) for flag in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK"))):
        raise ValueError("secure descriptor-relative verification requires POSIX support")


def _entries(manifest, max_files, max_bytes):
    if type(max_files) is not int or max_files < 1 or type(max_bytes) is not int or max_bytes < 0:
        raise ValueError("limits must be integers: max_files >= 1 and max_bytes >= 0")
    if (type(manifest) is not dict or set(manifest) != {"schema", "entries"}
            or manifest["schema"] != SCHEMA or type(manifest["entries"]) is not list):
        raise ValueError("expected schema atlas.artifact.integrity.v1 and entries list")
    entries = manifest["entries"]
    if not 1 <= len(entries) <= max_files:
        raise ValueError("manifest must contain between 1 and max_files entries")
    seen, total, validated = set(), 0, []
    for entry in entries:
        if type(entry) is not dict or set(entry) != {"path", "bytes", "sha256"}:
            raise ValueError("each entry requires exactly path, bytes and sha256")
        name = entry["path"]
        if (type(name) is not str or not name or len(name) > 4096
                or any(ord(c) < 32 or ord(c) == 127 for c in name)
                or "\\" in name or ":" in name
                or any(part in ("", ".", "..") for part in name.split("/"))
                or len(name.split("/")) > 64):
            raise ValueError("path must be a bounded canonical relative POSIX path")
        if name.casefold() in seen:
            raise ValueError("duplicate or case-colliding path: " + name)
        seen.add(name.casefold())
        size, digest = entry["bytes"], entry["sha256"]
        if type(size) is not int or size < 0:
            raise ValueError("bytes must be a non-negative integer")
        if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("sha256 must contain 64 lowercase hexadecimal characters")
        total += size
        if total > max_bytes:
            raise ValueError("declared byte total exceeds max_bytes")
        validated.append(dict(entry))
    return validated


def _directory(parts, start):
    """Open each component without following symlinks, retaining an anchored fd."""
    fd = os.dup(start)
    try:
        for part in parts:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _root_fd(root):
    path = Path(root).absolute()
    if ".." in path.parts:
        raise ValueError("root must not contain parent traversal")
    start = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        return _directory(path.parts[1:], start)
    finally:
        os.close(start)


def _fingerprint(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _check_file(root_fd, entry, remaining):
    result = {"path": entry["path"], "ok": False, "bytes_read": 0,
              "expected_bytes": entry["bytes"], "expected_sha256": entry["sha256"]}
    try:
        if entry["bytes"] > remaining:
            raise ValueError("aggregate read budget exhausted")
        parts = entry["path"].split("/")
        parent = _directory(parts[:-1], root_fd)
        try:
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        finally:
            os.close(parent)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("artifact must be a regular file")
            result["actual_bytes"] = before.st_size
            if before.st_size != entry["bytes"]:
                raise ValueError("byte count mismatch")
            digest = hashlib.sha256()
            while result["bytes_read"] < entry["bytes"]:
                chunk = os.read(fd, min(CHUNK, entry["bytes"] - result["bytes_read"]))
                if not chunk:
                    raise ValueError("file truncated while reading")
                digest.update(chunk)
                result["bytes_read"] += len(chunk)
            extra = os.read(fd, 1)
            result["bytes_read"] += len(extra)
            if extra:
                raise ValueError("extra data beyond declared byte count")
            after = os.fstat(fd)
            if _fingerprint(before) != _fingerprint(after):
                raise ValueError("file changed while reading")
            result["actual_sha256"] = digest.hexdigest()
            if result["actual_sha256"] != entry["sha256"]:
                raise ValueError("SHA256 mismatch")
            result["ok"] = True
        finally:
            os.close(fd)
    except (OSError, ValueError) as error:
        result["error"] = str(error)
    return result


def verify_manifest(root, manifest, *, max_files=MAX_FILES, max_bytes=MAX_BYTES):
    """Return structured per-file results; malformed manifests/roots raise errors.

    Only listed files are checked. No writes, extraction, execution or network.
    All path components, including the root's ancestors, reject symlinks.
    """
    entries = _entries(manifest, max_files, max_bytes)
    _platform()
    fd = _root_fd(root)
    try:
        results, remaining = [], max_bytes
        for entry in entries:
            result = _check_file(fd, entry, remaining)
            remaining -= result["bytes_read"]
            results.append(result)
    finally:
        os.close(fd)
    return {"schema": SCHEMA, "ok": all(r["ok"] for r in results),
            "checked": len(results), "bytes_read": sum(r["bytes_read"] for r in results),
            "results": results}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key: " + key)
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check")
    check.add_argument("--root", required=True, type=Path)
    check.add_argument("--manifest", required=True, type=Path)
    check.add_argument("--max-files", type=int, default=MAX_FILES)
    check.add_argument("--max-bytes", type=int, default=MAX_BYTES)
    args = parser.parse_args(argv)
    try:
        _platform()
        fd = os.open(args.manifest, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError("manifest must be a regular file")
            raw = bytearray()
            while len(raw) <= MAX_MANIFEST_BYTES:
                chunk = os.read(fd, min(CHUNK, MAX_MANIFEST_BYTES + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
        finally:
            os.close(fd)
        if len(raw) > MAX_MANIFEST_BYTES:
            raise ValueError("manifest exceeds 1 MiB")
        manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
        report = verify_manifest(args.root, manifest, max_files=args.max_files, max_bytes=args.max_bytes)
    except (OSError, ValueError, RecursionError) as error:
        report = {"schema": SCHEMA, "ok": False, "error": str(error)}
    print(json.dumps(report, sort_keys=True))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())

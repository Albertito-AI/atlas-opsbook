#!/usr/bin/env python3
"""Build and verify bounded, offline incident timelines. Python 3.9+."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

SCHEMA = "atlas.incident.timeline.v1"
MAX_BYTES = 16 * 1024 * 1024
MAX_RECORDS = 100000
MAX_RECEIPT = 128 * 1024 * 1024
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", re.ASCII)


def local_root(root):
    root = Path(root).absolute()
    path = Path(root.anchor)
    for part in root.parts[1:]:
        path /= part
        if path.is_symlink():
            raise ValueError("Root must not contain symlinks")
    if not root.is_dir():
        raise ValueError("Root must be an existing directory")
    return root.resolve()


def local_path(root, name):
    if (not isinstance(name, str) or not name or len(name.encode("utf-8")) > 256
            or any(c in name for c in ("\\", ":", "\x00"))
            or PurePosixPath(name).is_absolute()
            or any(p in ("", ".", "..") for p in name.split("/"))):
        raise ValueError("Expected a relative POSIX path without traversal, at most 256 UTF-8 bytes")
    path = root
    for part in name.split("/"):
        path /= part
        if path.is_symlink():
            raise ValueError("Symlinks are not accepted: " + name)
    return path


def read_bounded(path, limit):
    if not path.is_file():
        raise ValueError("Expected a regular file: " + str(path))
    try:
        with path.open("rb") as handle:
            raw = handle.read(limit + 1)
    except OSError as error:
        raise ValueError("Cannot read %s: %s" % (path, error)) from error
    if len(raw) > limit:
        raise ValueError("Byte limit exceeded: " + str(path))
    return raw


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field: " + key)
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError("Invalid JSON constant: " + value)


def parse_json(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=invalid_constant)


def utc_timestamp(value):
    if value is None:
        return None
    if not isinstance(value, str) or not TIMESTAMP.fullmatch(value) or value.endswith("-00:00"):
        raise ValueError("Time needs an explicit known UTC offset and seconds (up to six fractional digits)")
    # Keep the declared contract stable even if a runtime accepts ISO 24:00.
    if int(value[11:13]) > 23 or int(value[14:16]) > 59 or int(value[17:19]) > 59:
        raise ValueError("Invalid clock time")
    if value[-1] != "Z" and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        raise ValueError("Invalid UTC offset")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    except (ValueError, OverflowError) as error:
        raise ValueError("Invalid timestamp: " + value) from error


def build_timeline(root, inputs, max_bytes=1048576, max_records=10000):
    root = local_root(root)
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BYTES:
        raise ValueError("max_bytes must be an integer from 1 to 16777216")
    if type(max_records) is not int or not 1 <= max_records <= MAX_RECORDS:
        raise ValueError("max_records must be an integer from 1 to 100000")
    if not isinstance(inputs, (list, tuple)) or not 1 <= len(inputs) <= 256:
        raise ValueError("Provide 1 to 256 explicit input paths")
    paths = [(name, local_path(root, name)) for name in inputs]
    if len(set(inputs)) != len(inputs):
        raise ValueError("Duplicate input path")
    manifests, dated, undated = [], [], []
    total_bytes, total_records = 0, 0
    for name, path in sorted(paths):
        raw = read_bounded(path, max_bytes - total_bytes)
        total_bytes += len(raw)
        lines = raw.split(b"\n")
        if lines[-1] == b"":
            lines.pop()
        for number, line in enumerate(lines, 1):
            total_records += 1
            if total_records > max_records:
                raise ValueError("Record limit exceeded")
            try:
                row = parse_json(line)
                if (not isinstance(row, dict) or "message" not in row
                        or not set(row) <= {"source", "message", "time"}):
                    raise ValueError("Expected message and optional source/time fields only")
                source, message = row.get("source", name), row["message"]
                if not all(isinstance(v, str) and v.strip() for v in (source, message)):
                    raise ValueError("Source and message must be nonempty strings")
                source.encode("utf-8")
                message.encode("utf-8")
                event = {"source": source, "message": message, "time": utc_timestamp(row.get("time")),
                         "input": name, "line": number}
            except (ValueError, UnicodeError, RecursionError) as error:
                raise ValueError("%s:%d: %s" % (name, number, error)) from error
            (undated if event["time"] is None else dated).append(event)
        manifests.append({"path": name, "sha256": hashlib.sha256(raw).hexdigest(),
                          "bytes": len(raw), "records": len(lines)})
    tie = lambda event: (event["source"], event["message"], event["input"], event["line"])
    dated.sort(key=lambda event: (event["time"],) + tie(event))
    undated.sort(key=tie)
    return {"schema": SCHEMA, "inputs": manifests,
            "limits": {"max_bytes": max_bytes, "max_records": max_records},
            "dated": dated, "undated": undated, "total_bytes": total_bytes,
            "total_records": total_records,
            "coverage": {"start": dated[0]["time"] if dated else None,
                         "end": dated[-1]["time"] if dated else None}}


def verify_timeline(receipt, root):
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
        raise ValueError("Unsupported incident timeline")
    try:
        entries = receipt["inputs"]
        if not isinstance(entries, list) or not 1 <= len(entries) <= 256:
            raise ValueError("Invalid input manifest")
        current = build_timeline(root, [entry["path"] for entry in entries],
                                 receipt["limits"]["max_bytes"], receipt["limits"]["max_records"])
        matches = (json.dumps(receipt, sort_keys=True, allow_nan=False)
                   == json.dumps(current, sort_keys=True, allow_nan=False))
    except (KeyError, TypeError) as error:
        raise ValueError("Malformed timeline receipt") from error
    if not matches:
        raise ValueError("Timeline differs from its current inputs; rebuild and review the changes")
    return {"valid": True, "records": current["total_records"], "inputs": len(entries)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--root", default=".")
    build.add_argument("--input", action="append", required=True)
    build.add_argument("--out", required=True)
    build.add_argument("--max-bytes", type=int, default=1048576)
    build.add_argument("--max-records", type=int, default=10000)
    check = commands.add_parser("check")
    check.add_argument("--root", default=".")
    check.add_argument("--receipt", required=True)
    args = parser.parse_args(argv)
    try:
        root = local_root(args.root)
        if args.command == "check":
            result = verify_timeline(parse_json(read_bounded(local_path(root, args.receipt), MAX_RECEIPT)), root)
        else:
            receipt = build_timeline(root, args.input, args.max_bytes, args.max_records)
            output = local_path(root, args.out)
            payload = (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            if len(payload) > MAX_RECEIPT:
                raise ValueError("Receipt exceeds 128 MiB limit")
            with output.open("xb") as handle:
                handle.write(payload)
            result = {"output": args.out, "records": receipt["total_records"], "inputs": len(receipt["inputs"])}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, UnicodeError, RecursionError) as error:
        print("incident-timeline: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

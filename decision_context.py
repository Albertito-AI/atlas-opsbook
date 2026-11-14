#!/usr/bin/env python3
"""Select declared current decisions and verify the resulting context. Python 3.9+."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys

CATALOGUE = "atlas.decision.catalogue.v1"
BUNDLE = "atlas.decision.context.v1"
STATUSES = {"accepted", "proposed", "deprecated", "rejected", "unspecified"}
LIMIT = 4 * 1024 * 1024
# JSON escaping and catalogue metadata enlarge a pack beyond its source text.
BUNDLE_LIMIT = 16 * LIMIT


def digest(value):
    return hashlib.sha256(value).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError("Non-JSON numeric constant: " + value)


def parse_json(raw, label):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                          parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ValueError("Invalid UTF-8 JSON in %s: %s" % (label, error)) from error


def safe_path(root, name):
    if (not isinstance(name, str) or not name or "\\" in name
            or ":" in name or any(p in ("", ".", "..") for p in name.split("/"))
            or PurePosixPath(name).is_absolute()):
        raise ValueError("Expected a relative POSIX path without traversal: %r" % name)
    path = root
    for part in name.split("/"):
        path = path / part
        if path.is_symlink():
            raise ValueError("Symlinks are not accepted: " + name)
    return path


def read_bytes(path, limit=LIMIT):
    try:
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("Expected a regular file: " + str(path))
        with path.open("rb") as handle:
            raw = handle.read(limit + 1)
    except OSError as error:
        raise ValueError("Cannot read %s: %s" % (path, error)) from error
    if len(raw) > limit:
        raise ValueError("File exceeds %d-byte limit: %s" % (limit, path))
    return raw


def strings(value, label, allow_empty=False):
    if (not isinstance(value, list) or (not value and not allow_empty)
            or any(not isinstance(x, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", x)
                   for x in value) or len(set(value)) != len(value)):
        raise ValueError("Invalid " + label)
    return sorted(value)


def read_catalogue(root, manifest):
    manifest = Path(manifest)
    if manifest.is_absolute():
        try:
            name = manifest.relative_to(root).as_posix()
        except ValueError as error:
            raise ValueError("Catalogue must be inside root") from error
    else:
        name = manifest.as_posix()
    raw = read_bytes(safe_path(root, name))
    obj = parse_json(raw, "catalogue")
    if not isinstance(obj, dict) or set(obj) != {"schema", "decisions"} or obj["schema"] != CATALOGUE:
        raise ValueError("Unsupported catalogue schema or fields")
    rows = obj["decisions"]
    if not isinstance(rows, list) or not rows or len(rows) > 2000:
        raise ValueError("Catalogue requires 1 to 2000 explicit decisions")
    records, paths = {}, set()
    total = 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "path", "status", "scopes", "supersedes"}:
            raise ValueError("Each decision needs exactly id, path, status, scopes, supersedes")
        identifier = strings([row["id"]], "decision identifier")[0]
        source_path = safe_path(root, row["path"])
        if identifier in records or row["path"] in paths:
            raise ValueError("Duplicate identifier or source path: " + identifier)
        if not isinstance(row["status"], str) or row["status"] not in STATUSES:
            raise ValueError("Explicit known status required: " + identifier)
        scopes = strings(row["scopes"], "scopes")
        supersedes = strings(row["supersedes"], "supersedes", allow_empty=True)
        source = read_bytes(source_path)
        total += len(source)
        if total > 32 * LIMIT:
            raise ValueError("Declared sources exceed 128 MiB limit")
        try:
            text = source.decode("utf-8")
        except UnicodeError as error:
            raise ValueError("Decision source must be UTF-8: " + identifier) from error
        records[identifier] = dict(row, scopes=scopes, supersedes=supersedes,
                                   sha256=digest(source), text=text, bytes=len(source))
        paths.add(row["path"])
    for row in records.values():
        for predecessor in row["supersedes"]:
            if predecessor not in records or predecessor == row["id"]:
                raise ValueError("Missing or self supersession target: " + predecessor)
    # Iterative topological resolution avoids recursion-depth failure on long histories.
    ancestors, pending = {}, set(records)
    while pending:
        ready = sorted(key for key in pending if all(p in ancestors for p in records[key]["supersedes"]))
        if not ready:
            raise ValueError("Supersession cycle: " + ", ".join(sorted(pending)))
        for key in ready:
            parents = records[key]["supersedes"]
            ancestors[key] = set(parents).union(*(ancestors[p] for p in parents))
            pending.remove(key)
    accepted = {k for k, r in records.items() if r["status"] == "accepted"}
    replaced = set().union(*(ancestors[k] for k in accepted))
    active = accepted - replaced
    successors = {}
    for key in sorted(active):
        for predecessor in ancestors[key]:
            successors.setdefault(predecessor, []).append(key)
    for key, choices in sorted(successors.items()):
        if len(choices) > 1:
            raise ValueError("Competing accepted successors of %s: %s" % (key, ", ".join(choices)))
    canonical = [{k: r[k] for k in ("id", "path", "status", "scopes", "supersedes")}
                 for _, r in sorted(records.items())]
    return name, raw, records, replaced, active, digest(encoded(canonical)), total


def build_context(root, manifest, scopes, max_bytes=24000):
    root = Path(root).absolute()
    scopes = strings(scopes, "requested scopes")
    if type(max_bytes) is not int or not 1 <= max_bytes <= LIMIT:
        raise ValueError("max_bytes must be an integer between 1 and 4194304")
    name, raw, records, replaced, active, catalogue_digest, total = read_catalogue(root, manifest)
    selected, omitted, ready = [], [], True
    for key, row in sorted(records.items()):
        relevant = "global" in row["scopes"] or bool(set(scopes).intersection(row["scopes"]))
        if relevant and row["status"] == "unspecified":
            ready = False
            reason = "status: unspecified"
            if key in replaced:
                reason += "; superseded by an accepted descendant"
        elif key in replaced:
            reason = "superseded by an accepted descendant"
        elif not relevant:
            reason = "outside requested scopes"
        elif key in active:
            selected.append(row)
            continue
        else:
            reason = "status: " + row["status"]
        omitted.append({"id": key, "path": row["path"], "reason": reason})
    size = sum(r["bytes"] for r in selected)
    if size > max_bytes:
        raise ValueError("Selected source text exceeds byte budget (%d > %d); narrow scope or review the catalogue" % (size, max_bytes))
    bundle = {"schema": BUNDLE, "manifest": {"path": name, "sha256": digest(raw)},
              "scopes": scopes, "max_bytes": max_bytes, "ready": ready,
              "selected": selected, "omitted": omitted, "selected_bytes": size,
              "total_source_bytes": total, "source_count": len(records),
              "catalogue_digest": catalogue_digest}
    bundle["bundle_digest"] = digest(encoded(bundle))
    return bundle


def check_context(bundle, root):
    if not isinstance(bundle, dict) or bundle.get("schema") != BUNDLE:
        raise ValueError("Unsupported context bundle")
    unsigned = {k: v for k, v in bundle.items() if k != "bundle_digest"}
    try:
        actual_digest = digest(encoded(unsigned))
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ValueError("Malformed context bundle") from error
    if bundle.get("bundle_digest") != actual_digest:
        raise ValueError("Context bundle digest mismatch")
    try:
        current = build_context(root, Path(bundle["manifest"]["path"]), bundle["scopes"], bundle["max_bytes"])
    except (KeyError, TypeError) as error:
        raise ValueError("Malformed context bundle") from error
    # Only selected source bytes are freshness claims. The total is a historical metric.
    ignore = {"bundle_digest", "total_source_bytes"}
    if (set(bundle) != set(current)
            or type(bundle["total_source_bytes"]) is not int
            or not 0 <= bundle["total_source_bytes"] <= 32 * LIMIT
            or encoded({k: v for k, v in bundle.items() if k not in ignore})
            != encoded({k: v for k, v in current.items() if k not in ignore})):
        raise ValueError("Context is stale or inconsistent; rebuild against the current catalogue and selected sources")
    if not current["ready"]:
        raise ValueError("Unspecified decisions require review before this context is ready")
    return {"valid": True, "selected": len(current["selected"]), "scope": current["scopes"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--root", type=Path, default=Path("."))
    build.add_argument("--manifest", type=Path, required=True)
    build.add_argument("--scope", action="append", required=True)
    build.add_argument("--max-bytes", type=int, default=24000)
    build.add_argument("--out", type=Path, required=True)
    check = commands.add_parser("check")
    check.add_argument("--root", type=Path, default=Path("."))
    check.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            result = check_context(parse_json(read_bytes(args.bundle, BUNDLE_LIMIT),
                                              "context bundle"), args.root)
            print(json.dumps(result, sort_keys=True))
            return 0
        result = build_context(args.root, args.manifest, args.scope, args.max_bytes)
        root = args.root.absolute()
        protected = {safe_path(root, result["manifest"]["path"]).resolve()}
        protected.update(safe_path(root, r["path"]).resolve() for r in result["selected"] + result["omitted"])
        if (args.out.resolve() in protected or args.out.is_symlink()
                or (args.out.exists() and any(args.out.samefile(path) for path in protected))):
            raise ValueError("Output must not replace the catalogue, a decision source or a symlink")
        if args.out.exists() and not args.out.is_file():
            raise ValueError("Output must be a regular file: " + str(args.out))
        payload = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if len(payload) > BUNDLE_LIMIT:
            raise ValueError("Serialized context exceeds 64 MiB bundle limit")
        args.out.write_bytes(payload)
        print(json.dumps({"ready": result["ready"], "selected": len(result["selected"]),
                          "selected_bytes": result["selected_bytes"], "output": str(args.out)}))
        return 0 if result["ready"] else 2
    except (ValueError, OSError, UnicodeError) as error:
        print("decision-context: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

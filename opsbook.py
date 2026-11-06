#!/usr/bin/env python3
"""Project-local, replay-tested operations manuals. Requires Python 3.9+."""
import argparse
import hashlib
import itertools
import json
import subprocess
from pathlib import Path
import re
import sqlite3
import sys
import tempfile


def fail(message):
    raise ValueError(message)


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value):
        fail("Use a lowercase identifier of up to 64 characters.")
    return value


def line(value, limit=600):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or not value.isprintable():
        fail("Expected a non-empty single line of text (maximum %d characters)." % limit)
    return value.strip()


def context(value):
    if not isinstance(value, dict) or not 1 <= len(value) <= 16:
        fail("A context needs 1 to 16 categorical fields.")
    return {identifier(k): line(v, 80) for k, v in value.items()}


def action_list(value):
    if not isinstance(value, list) or len(value) > 64:
        fail("Expected a list of up to 64 check identifiers.")
    return sorted({identifier(a) for a in value})


def initial():
    return {"schema": 1, "cases": {}, "drafts": {}, "versions": [
        {"number": 0, "reason": "Initial manual", "rules": []}]}


def add_case(s, raw):
    if not isinstance(raw, dict) or set(raw) != {"id", "set", "context", "expected", "evidence"}:
        fail("Each case needs id, set, context, expected and evidence.")
    sample = {"id": identifier(raw["id"]), "context": context(raw["context"]),
              "expected": action_list(raw["expected"]), "evidence": line(raw["evidence"]), "set": raw["set"]}
    if sample["set"] not in ("practice", "exam"):
        fail("Set must be practice or exam.")
    old = s["cases"].get(sample["id"])
    if old == sample:
        return
    if old or any(c["context"] == sample["context"] for c in s["cases"].values()):
        fail("Case identifiers and contexts must be distinct. Exact reimports are safe.")
    s["cases"][sample["id"]] = sample


def matches(guard, facts):
    return all(facts.get(k) == v for k, v in guard.items())


def predict(rules, facts):
    return {r["check"] for r in rules if matches(r["when"], facts)}


def trial(s, rules):
    old = s["versions"][-1]["rules"]
    report = {}
    for split in ("practice", "exam"):
        rows = []
        for c in sorted(s["cases"].values(), key=lambda c: c["id"]):
            if c["set"] != split:
                continue
            truth = set(c["expected"])
            before, after = predict(old, c["context"]), predict(rules, c["context"])
            old_errors, new_errors = before ^ truth, after ^ truth
            rows.append({"id": c["id"], "before": sorted(before), "after": sorted(after),
                         "expected": c["expected"], "fixed": sorted(old_errors - new_errors),
                         "introduced": sorted(new_errors - old_errors)})
        report[split] = {"cases": len(rows),
                         "correct_before": sum(r["before"] == r["expected"] for r in rows),
                         "correct_after": sum(r["after"] == r["expected"] for r in rows),
                         "rows": rows}
    report["eligible"] = all(
        any(r["fixed"] for r in report[split]["rows"])
        and not any(r["introduced"] for r in report[split]["rows"])
        and any(not r["fixed"] and r["expected"] == r["after"] for r in report[split]["rows"])
        for split in ("practice", "exam"))
    return report


def draft(s, raw):
    required = {"id", "when", "check", "instruction", "basis"}
    if not isinstance(raw, dict) or not required <= raw.keys() or raw.keys() - required - {"replaces"}:
        fail("A rule needs id, when, check, instruction and basis, with optional replaces.")
    basis = identifier(raw["basis"])
    sample = s["cases"].get(basis)
    rule = {"id": identifier(raw["id"]), "when": context(raw["when"]), "check": identifier(raw["check"]),
            "instruction": line(raw["instruction"]), "basis": basis}
    if not sample or sample["set"] != "practice" or not matches(rule["when"], sample["context"]):
        fail("Cite a matching practice case as the basis for the instruction.")
    if rule["check"] not in sample["expected"]:
        fail("The cited practice case must require this check.")
    replaces = raw.get("replaces")
    latest = s["versions"][-1]
    ids = {r["id"] for r in latest["rules"]}
    if replaces is not None and identifier(replaces) not in ids:
        fail("The instruction being replaced must exist in the current manual.")
    if rule["id"] in ids and rule["id"] != replaces:
        fail("Use replaces to revise an active instruction.")
    d = {"base": latest["number"], "rule": rule, "replaces": replaces,
         "case_digest": hashlib.sha256(encode(s["cases"]).encode()).hexdigest()}
    key = hashlib.sha256(encode(d).encode()).hexdigest()[:24]
    s["drafts"][key] = d
    return {"proposal": key, **d}


def learn(s, basis, check, instruction):
    sample = s["cases"].get(basis)
    if not sample or sample["set"] != "practice" or check not in sample["expected"]:
        fail("Choose an observed practice case and one of its expected checks.")
    old = s["versions"][-1]["rules"]
    if check in predict(old, sample["context"]):
        fail("This check is already prescribed for this case.")
    practice = [c for c in s["cases"].values() if c["set"] == "practice"]
    fields = sorted(sample["context"])
    # Prefer more corrected training cases, then fewer predicates, then lexical order.
    best = None
    for width in range(1, min(3, len(fields)) + 1):
        for keys in itertools.combinations(fields, width):
            guard = {k: sample["context"][k] for k in keys}
            covered = [c for c in practice if matches(guard, c["context"])]
            if any(check not in c["expected"] for c in covered):
                continue
            gain = sum(check not in predict(old, c["context"]) for c in covered)
            rank = (-gain, width, keys)
            if best is None or rank < best[0]:
                best = (rank, guard)
    if best is None:
        fail("No supported guard fits the practice cases. Gather better context.")
    rule_id = "rule-" + hashlib.sha256(encode([check, best[1]]).encode()).hexdigest()[:12]
    return draft(s, {"id": rule_id, "when": best[1], "check": check,
                     "instruction": instruction, "basis": basis})


def assess(s, key, promote=False):
    d = s["drafts"].get(key)
    if not d:
        fail("Unknown proposal.")
    latest = s["versions"][-1]
    if promote and latest.get("proposal") == key:
        return latest
    if d["base"] != latest["number"] or d["case_digest"] != hashlib.sha256(encode(s["cases"]).encode()).hexdigest():
        fail("The manual or case set changed. Submit a fresh proposal against the current state.")
    rules = [r for r in latest["rules"] if r["id"] != d["replaces"]] + [d["rule"]]
    report = trial(s, rules)
    if not promote:
        return report
    if not report["eligible"]:
        fail("Promotion refused. Both sets need a repair and a correct unchanged control, with zero new errors.")
    version = {"number": latest["number"] + 1, "reason": "Passed replay", "proposal": key,
               "rules": rules, "report": report, "case_digest": d["case_digest"]}
    s["versions"].append(version)
    return version


def render(s):
    version = s["versions"][-1]
    lines = ["# Project operations manual", "", "Revision %d" % version["number"], "",
             "Use the following instructions when the recorded conditions apply.", ""]
    for r in version["rules"]:
        lines.extend(["## " + r["check"], "", r["instruction"], "",
                      "Applies when " + ", ".join(f"{k} = {v}" for k,v in sorted(r["when"].items())) + ".",
                      "Practice evidence (" + r["basis"] + "): " + s["cases"][r["basis"]]["evidence"], ""])
    if not version["rules"]:
        lines.append("No project instructions have passed replay yet.")
    return "\n".join(lines)


def run_checks(rules, command_file):
    """Run operator-supplied argument vectors. Learned text never becomes a command."""
    commands = read_json(command_file)
    if not isinstance(commands, dict):
        fail("Expected a JSON object of trusted check commands.")
    checks = sorted({r["check"] for r in rules})
    for name in checks:
        argv = commands.get(name)
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
            fail("Missing or invalid trusted command for " + name)
    rows = []
    for name in checks:
        try:
            result = subprocess.run(commands[name], stdin=subprocess.DEVNULL, stdout=sys.stderr,
                                    stderr=sys.stderr, timeout=60, check=False)
            rows.append({"check": name, "exit": result.returncode})
        except (OSError, subprocess.TimeoutExpired) as exc:
            rows.append({"check": name, "error": str(exc)})
    return {"checks": rows, "pass": all(r.get("exit") == 0 for r in rows)}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dispatch(s, a):
    cmd = a.cmd
    if cmd == "init":
        return {"revision": s["versions"][-1]["number"]}
    if cmd == "record":
        samples = read_json(a.file)
        if not isinstance(samples, list) or not samples:
            fail("Provide a non-empty JSON array of cases.")
        for sample in samples:
            add_case(s, sample)
        return {"cases": len(s["cases"])}
    if cmd == "learn":
        return learn(s, a.case, identifier(a.check), a.instruction)
    if cmd == "propose":
        return draft(s, read_json(a.file))
    if cmd in ("evaluate", "promote"):
        return assess(s, a.proposal, cmd == "promote")
    if cmd == "manual":
        return render(s)
    if cmd == "revision":
        if not 0 <= a.number < len(s["versions"]):
            fail("Unknown manual revision.")
        return s["versions"][a.number]
    if cmd == "history":
        return [{k: v for k, v in version.items() if k not in ("rules", "report")} for version in s["versions"]]
    if cmd == "rollback":
        if not 0 <= a.to < len(s["versions"]) - 1:
            fail("Choose an earlier revision.")
        latest = s["versions"][-1]
        if latest.get("restored") == a.to and latest["reason"] == a.reason:
            return latest
        v = {"number": len(s["versions"]), "restored": a.to, "rules": s["versions"][a.to]["rules"],
             "reason": line(a.reason)}
        s["versions"].append(v)
        return v
    facts = context(json.loads(a.context))
    rules = [r for r in s["versions"][-1]["rules"] if matches(r["when"], facts)]
    if cmd in ("brief", "verify"):
        return {"revision": s["versions"][-1]["number"], "instructions": rules}
    supplied = action_list(a.done)
    missing = sorted({r["check"] for r in rules} - set(supplied))
    return {"revision": s["versions"][-1]["number"], "missing": missing, "pass": not missing}


def transact(path, args):
    exists = path.is_file()
    if not exists and args.cmd != "init":
        fail("Initialise the project with init first.")
    if not exists:
        path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as con:
        con.execute("BEGIN IMMEDIATE")
        if args.cmd == "init":
            con.execute("CREATE TABLE IF NOT EXISTS book (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL)")
            con.execute("INSERT OR IGNORE INTO book VALUES(1, ?)", (encode(initial()),))
        row = con.execute("SELECT data FROM book WHERE id=1").fetchone()
        if not row:
            fail("Missing manual state.")
        state = json.loads(row[0])
        if state.get("schema") != 1:
            fail("Unsupported manual schema.")
        result = dispatch(state, args)
        if args.cmd in {"record", "learn", "propose", "promote", "rollback"}:
            con.execute("UPDATE book SET data=? WHERE id=1", (encode(state),))
        return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=Path(".opsbook/manual.db"), help="project-specific SQLite file")
    sub = p.add_subparsers(dest="cmd", required=True)
    for cmd in ("init", "manual", "history", "demo"):
        sub.add_parser(cmd)
    sub.add_parser("revision").add_argument("number", type=int)
    for cmd in ("record", "propose"):
        sub.add_parser(cmd).add_argument("file")
    learn_p = sub.add_parser("learn")
    for name in ("case", "check", "instruction"):
        learn_p.add_argument(name)
    for cmd in ("evaluate", "promote"):
        sub.add_parser(cmd).add_argument("proposal")
    for cmd in ("brief", "gate", "verify"):
        cp = sub.add_parser(cmd)
        cp.add_argument("context", help="JSON object of project facts")
        if cmd == "verify":
            cp.add_argument("--checks", required=True, help="reviewed local JSON command map")
        if cmd == "gate":
            cp.add_argument("--done", nargs="*", default=[], help="externally verified completed checks")
    rp = sub.add_parser("rollback")
    rp.add_argument("to", type=int)
    rp.add_argument("reason")
    return p


def demonstration():
    root = Path(__file__).resolve().parent / "examples"
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "manual.db"
        def run(*argv):
            return transact(db, parser().parse_args(argv))
        run("init")
        run("record", str(root / "cases.json"))
        wide = run("propose", str(root / "overbroad.json"))["proposal"]
        rejected = run("evaluate", wide)
        learned = run("learn", "missing-wheel", "install-clean", "Install the built package in a clean environment and import it.")["proposal"]
        accepted = run("evaluate", learned)
        run("promote", learned)
        manual = run("manual")
        facts = '{"task":"ship","artefact":"package","os":"freebsd"}'
        gate = run("gate", facts)
        passed = run("gate", facts, "--done", "install-clean")
        rolled = run("rollback", "0", "Demonstrate recovery")
        return {"rejected": rejected, "accepted": accepted, "manual": manual,
                "missing_check": gate, "completed_check": passed, "rollback_revision": rolled["number"],
                "after_rollback": run("brief", facts)}


def main():
    args = parser().parse_args()
    try:
        result = demonstration() if args.cmd == "demo" else transact(args.db, args)
        if args.cmd == "verify":
            # End the SQLite transaction before starting external processes.
            revision = result["revision"]
            result = dict(run_checks(result["instructions"], args.checks), revision=revision)
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(result if isinstance(result, str) else json.dumps(result, indent=2, ensure_ascii=False))
    if args.cmd in ("gate", "verify") and not result["pass"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

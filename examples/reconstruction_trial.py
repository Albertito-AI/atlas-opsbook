#!/usr/bin/env python3
"""Original offline reconstruction lesson, with finite evidence and visible limits.

Copyright 2026 Albert Tan Sin Hon. Licensed under MIT.
"""

import copy
import hashlib
import json
from pathlib import Path
import re

SCHEMA = "atlas.reconstruction.trial.v1"
MAX_BYTES = 256
ASCII_WHITESPACE = b" \t\n\r\v\f"
DISCOVERY = (
    b"  ALPHA\tBETA ", "Straße".encode("utf-8"), "İ".encode("utf-8"),
    "\u00a0ALPHA\u00a0".encode("utf-8"), b"\r\nMixed\vWords\f", b"",
)
HELD_OUT = (
    b"A", b"Z", b"a", b"\tA\n B\r", b"one\r\ntwo", b"a\t\tb",
    b"a  b", b"ABC123!", "éÉ ß  İı Ω".encode("utf-8"),
    "\u2003A\u2003".encode("utf-8"), "A\u00a0B".encode("utf-8"),
    "CAFÉ".encode("utf-8"), "ΣΟΣ".encode("utf-8"),
    "e\u0301 É".encode("utf-8"), b"\x00", b"\xff", b"\xe2\x82",
    b" \x00 ", b"\t\r\n\v\f ", b"a" * 256, b"a" * 257,
    b" " * 256, b" " * 257, ("é" * 128).encode("utf-8"),
    ("é" * 129).encode("utf-8"), b"\xff" * 257, b"\xff\x00",
    b"a\x00", b"\xc0\xaf", b"\xed\xa0\x80", b"A\x7fB",
    b"\t" + b"A" * 254 + b"\n",
)
HYPOTHESES = ("unicode_casefold", "unicode_lower", "ascii_only")


def _reply(text="", error=""):
    return {"stdout": "" if error else text + "\n",
            "stderr": error + "\n" if error else "", "exit_code": 2 if error else 0}


def reference(raw):
    """Owned teaching oracle: decode first, then apply explicit string rules."""
    if type(raw) is not bytes:
        raise ValueError("Input must be bytes")
    if len(raw) > MAX_BYTES:
        return _reply(error="too-long")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _reply(error="invalid-utf8")
    if "\x00" in text:
        return _reply(error="nul-byte")
    text = re.sub(r"[ \t\n\r\v\f]+", " ", text.strip(" \t\n\r\v\f"))
    text = text.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                                       "abcdefghijklmnopqrstuvwxyz"))
    return _reply(text) if text else _reply(error="empty")


def candidate(raw):
    """Original reconstruction: a byte state machine, preserving UTF-8 bytes."""
    if type(raw) is not bytes:
        raise ValueError("Input must be bytes")
    if len(raw) > MAX_BYTES:
        return _reply(error="too-long")
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return _reply(error="invalid-utf8")
    if 0 in raw:
        return _reply(error="nul-byte")
    output = bytearray()
    separator = False
    for byte in raw:
        if byte in ASCII_WHITESPACE:
            separator = bool(output)
            continue
        if separator:
            output.append(32)
            separator = False
        output.append(byte + 32 if 65 <= byte <= 90 else byte)
    return _reply(output.decode("utf-8")) if output else _reply(error="empty")


def hypothesis(name, raw):
    """Competing normalisation rules; admission errors are outside this comparison."""
    if name not in HYPOTHESES:
        raise ValueError("Unknown hypothesis")
    if name == "ascii_only":
        return candidate(raw)
    admitted = reference(raw)
    if admitted["exit_code"]:
        return admitted
    text = raw.decode("utf-8")
    if name == "unicode_casefold":
        normalized = " ".join(text.split()).casefold()
    else:
        normalized = re.sub(r"[ \t\n\r\v\f]+", " ",
                            text.strip(" \t\n\r\v\f")).lower()
    return _reply(normalized) if normalized else _reply(error="empty")


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _evidence_digest(receipt):
    return _digest({key: value for key, value in receipt.items() if key != "evidence_digest"})


def _observe(raw):
    original, reconstructed = reference(raw), candidate(raw)
    return {"input_hex": raw.hex(), "input_bytes": len(raw),
            "reference": original, "candidate": reconstructed,
            "match": original == reconstructed}


def build_receipt():
    if set(DISCOVERY).intersection(HELD_OUT):
        raise ValueError("Discovery and held-out probes must be disjoint")
    hypotheses = []
    for name in HYPOTHESES:
        matches = sum(hypothesis(name, raw) == reference(raw) for raw in DISCOVERY)
        hypotheses.append({"name": name, "matches": matches,
                           "probes": len(DISCOVERY), "consistent": matches == len(DISCOVERY)})
    survivors = [item["name"] for item in hypotheses if item["consistent"]]
    if len(survivors) != 1:
        raise ValueError("Discovery has not distinguished one hypothesis")
    discovery = [_observe(raw) for raw in DISCOVERY]
    held_out = [_observe(raw) for raw in HELD_OUT]
    receipt = {
        "schema": SCHEMA, "obligation_id": "toy.normalisation.function.v1",
        "obligation_version": 1,
        "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "observation_boundary": "in-process function calls to an owned local fixture",
        "maximum_input_bytes": MAX_BYTES, "hypotheses": hypotheses,
        "selected_hypothesis": survivors[0], "discovery": discovery, "held_out": held_out,
        "status": "verified" if all(item["match"] for item in discovery + held_out) else "failed",
        "limitations": [
            "Finite probes establish these observations, not universal equivalence or original source recovery.",
            "The oracle is visible in this teaching file; the exercise does not claim a blind evaluation.",
            "Results are function-level; exit_code is a response field, not an observed process exit.",
            "The normalisation algorithms differ, but both use Python UTF-8 decoding and a shared reply formatter.",
        ],
    }
    receipt["evidence_digest"] = _evidence_digest(receipt)
    return receipt


def verify_receipt(receipt):
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
        raise ValueError("Unsupported reconstruction receipt")
    try:
        digest = _evidence_digest(receipt)
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ValueError("Malformed reconstruction receipt") from error
    if receipt.get("evidence_digest") != digest:
        raise ValueError("Evidence digest mismatch")
    current = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if receipt.get("implementation_sha256") != current:
        raise ValueError("Stale evidence: implementation digest changed")
    expected = build_receipt()
    if _canonical(receipt) != _canonical(expected):
        raise ValueError("Evidence does not match the current fixture replay")
    if receipt["status"] != "verified":
        raise ValueError("Reconstruction has unresolved mismatches")
    return {"valid": True, "discovery_cases": len(receipt["discovery"]),
            "held_out_cases": len(receipt["held_out"])}


def _expect_rejection(receipt):
    try:
        verify_receipt(receipt)
    except ValueError as error:
        return {"detected": True, "reason": str(error)}
    raise AssertionError("A deliberate evidence defect was not detected")


def run_trial():
    receipt = build_receipt()
    verification = verify_receipt(receipt)
    stale = copy.deepcopy(receipt)
    stale["implementation_sha256"] = "0" * 64
    stale["evidence_digest"] = _evidence_digest(stale)
    tampered = copy.deepcopy(receipt)
    tampered["held_out"][0]["candidate"]["stdout"] = "invented observation\n"
    tampered["evidence_digest"] = _evidence_digest(tampered)
    differences = [index for index, raw in enumerate(HELD_OUT)
                   if hypothesis("unicode_casefold", raw) != reference(raw)]
    if not differences:
        raise AssertionError("Held-out probes failed to detect the wrong Unicode rule")
    return {"receipt": receipt, "verification": verification,
            "negative_controls": {
                "stale_evidence": _expect_rejection(stale),
                "tampered_evidence": _expect_rejection(tampered),
                "faulty_unicode_candidate": {"detected": True,
                                             "mismatching_held_out_indices": differences},
            }}


if __name__ == "__main__":
    print(json.dumps(run_trial(), ensure_ascii=False, sort_keys=True, indent=2))

"""Independent checks of the owned, offline reconstruction teaching contract.

Copyright 2026 Albert Tan Sin Hon. Licensed under MIT.
"""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "examples" / "reconstruction_trial.py"
SPEC = importlib.util.spec_from_file_location("atlas_reconstruction_trial", SCRIPT)
trial = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trial)


def resign(receipt):
    """Apply the documented receipt encoding, independently of module helpers."""
    payload = {key: value for key, value in receipt.items() if key != "evidence_digest"}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    receipt["evidence_digest"] = hashlib.sha256(raw).hexdigest()
    return receipt


class ReconstructionTrialTests(unittest.TestCase):
    def assert_observation(self, raw, stdout="", stderr="", exit_code=0):
        expected = {"stdout": stdout, "stderr": stderr, "exit_code": exit_code}
        for implementation in (trial.reference, trial.candidate):
            with self.subTest(implementation=implementation.__name__, raw=raw):
                result = implementation(raw)
                self.assertEqual(result, expected)
                self.assertIs(type(result["exit_code"]), int)

    def test_ascii_whitespace_and_case_contract(self):
        self.assert_observation(b" \tALPHA\n\r\v\f BETA \t", "alpha beta\n")
        self.assert_observation(b"A  B\t\tC", "a b c\n")
        self.assert_observation(b"A\x7fB", "a\x7fb\n")
        self.assert_observation(b"123!?", "123!?\n")

    def test_unicode_case_and_non_ascii_spaces_are_preserved(self):
        self.assert_observation("  İ ß É Ω  ".encode(), "İ ß É Ω\n")
        self.assert_observation("\u00a0A\u00a0B\u00a0".encode(), "\u00a0a\u00a0b\u00a0\n")
        self.assert_observation("\u2003A\u2003".encode(), "\u2003a\u2003\n")
        self.assert_observation("\u00a0".encode(), "\u00a0\n")
        self.assert_observation("E\u0301".encode(), "e\u0301\n")

    def test_limit_counts_encoded_bytes_and_precedes_normalisation(self):
        self.assert_observation(b"A" * 256, "a" * 256 + "\n")
        self.assert_observation(b"A" * 257, stderr="too-long\n", exit_code=2)
        self.assert_observation(("é" * 128).encode(), "é" * 128 + "\n")
        self.assert_observation(("é" * 129).encode(), stderr="too-long\n", exit_code=2)
        self.assert_observation(b" " * 256, stderr="empty\n", exit_code=2)
        self.assert_observation(b" " * 257, stderr="too-long\n", exit_code=2)

    def test_error_precedence_and_empty_input(self):
        for raw, error in (
            (b"\xff\x00" + b" " * 255, "too-long\n"),
            (b"\xff\x00", "invalid-utf8\n"),
            (b" \x00\t", "nul-byte\n"),
            (b"", "empty\n"),
            (b" \t\n\r\v\f", "empty\n"),
        ):
            self.assert_observation(raw, stderr=error, exit_code=2)

    def test_malformed_utf8_is_never_replaced_or_ignored(self):
        for raw in (b"\xff", b"\xc0\xaf", b"\xe2\x82", b"\xed\xa0\x80", b"ok\x80"):
            self.assert_observation(raw, stderr="invalid-utf8\n", exit_code=2)

    def test_non_byte_inputs_are_rejected(self):
        for raw in (None, "A", bytearray(b"A"), [65], 65):
            for implementation in (trial.reference, trial.candidate):
                with self.subTest(raw=raw, implementation=implementation.__name__):
                    with self.assertRaises(ValueError):
                        implementation(raw)

    def test_discovery_distinguishes_the_three_competing_rules(self):
        receipt = trial.build_receipt()
        hypotheses = receipt["hypotheses"]
        self.assertEqual({row["name"] for row in hypotheses},
                         {"unicode_casefold", "unicode_lower", "ascii_only"})
        self.assertEqual([row["name"] for row in hypotheses if row["consistent"]],
                         ["ascii_only"])
        self.assertEqual(receipt["selected_hypothesis"], "ascii_only")
        for row in hypotheses:
            self.assertEqual(row["probes"], len(receipt["discovery"]))
            self.assertEqual(row["consistent"], row["matches"] == row["probes"])
        with self.assertRaises(ValueError):
            trial.hypothesis("unregistered", b"A")

    def test_held_out_inputs_are_disjoint_and_include_admission_boundaries(self):
        receipt = trial.build_receipt()
        discovery = {row["input_hex"] for row in receipt["discovery"]}
        held_out = {row["input_hex"] for row in receipt["held_out"]}
        self.assertFalse(discovery & held_out)
        self.assertTrue({(b"a" * 256).hex(), (b"a" * 257).hex(), b"\xff".hex(),
                         b"\x00".hex(), "A\u00a0B".encode().hex()} <= held_out)
        for row in receipt["discovery"] + receipt["held_out"]:
            self.assertEqual(row["input_bytes"], len(bytes.fromhex(row["input_hex"])))
            self.assertIs(row["match"], True)
            self.assertEqual(row["reference"], row["candidate"])

    def test_receipt_is_deterministic_and_bound_to_complete_source_bytes(self):
        first = trial.build_receipt()
        self.assertEqual(first, trial.build_receipt())
        self.assertEqual(first["schema"], "atlas.reconstruction.trial.v1")
        self.assertEqual(first["implementation_sha256"], hashlib.sha256(SCRIPT.read_bytes()).hexdigest())
        self.assertEqual(first["evidence_digest"], resign(copy.deepcopy(first))["evidence_digest"])
        result = trial.verify_receipt(first)
        self.assertIs(result["valid"], True)
        self.assertEqual(result["held_out_cases"], len(first["held_out"]))
        self.assertEqual(result["discovery_cases"], len(first["discovery"]))

    def test_digest_tampering_and_missing_schema_are_rejected(self):
        receipt = trial.build_receipt()
        receipt["held_out"][0]["candidate"]["stdout"] = "invented\n"
        with self.assertRaisesRegex(ValueError, "digest"):
            trial.verify_receipt(receipt)
        for malformed in (None, [], {}, {"schema": "another.schema"}):
            with self.subTest(malformed=malformed):
                with self.assertRaises(ValueError):
                    trial.verify_receipt(malformed)

    def test_recomputed_checksum_cannot_hide_a_stale_implementation(self):
        receipt = trial.build_receipt()
        receipt["implementation_sha256"] = "0" * 64
        resign(receipt)
        with self.assertRaisesRegex(ValueError, "Stale"):
            trial.verify_receipt(receipt)

    def test_self_consistent_wrong_or_reclassified_observations_fail_replay(self):
        receipt = trial.build_receipt()
        wrong = copy.deepcopy(receipt)
        wrong["held_out"][0]["reference"]["stdout"] = "invented\n"
        wrong["held_out"][0]["candidate"]["stdout"] = "invented\n"
        wrong["held_out"][0]["match"] = True
        shifted = copy.deepcopy(receipt)
        shifted["discovery"].append(shifted["held_out"].pop())
        boolean_exit = copy.deepcopy(receipt)
        boolean_exit["held_out"][0]["candidate"]["exit_code"] = False
        for altered in (wrong, shifted, boolean_exit):
            with self.subTest(altered=altered is shifted):
                with self.assertRaisesRegex(ValueError, "replay"):
                    trial.verify_receipt(resign(altered))

    def test_negative_controls_reject_staleness_tampering_and_unicode_rules(self):
        result = trial.run_trial()
        controls = result["negative_controls"]
        self.assertEqual(set(controls), {"stale_evidence", "tampered_evidence",
                                         "faulty_unicode_candidate"})
        self.assertTrue(all(row["detected"] is True for row in controls.values()))
        indices = controls["faulty_unicode_candidate"]["mismatching_held_out_indices"]
        inputs = {bytes.fromhex(result["receipt"]["held_out"][i]["input_hex"]) for i in indices}
        expected = {text.encode() for text in ("éÉ ß  İı Ω", "\u2003A\u2003", "A\u00a0B",
                                               "CAFÉ", "ΣΟΣ", "e\u0301 É")}
        self.assertEqual(inputs, expected)

    def test_cli_runs_offline_from_an_empty_directory_and_emits_verified_json(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(SCRIPT)], cwd=directory,
                                    capture_output=True, text=True, encoding="utf-8", timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            payload = json.loads(result.stdout)
            self.assertIs(payload["verification"]["valid"], True)
            self.assertIs(trial.verify_receipt(payload["receipt"])["valid"], True)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()

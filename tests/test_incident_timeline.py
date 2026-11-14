"""Independent behavioural checks for local incident evidence timelines.

Copyright 2026 Albert Tan Sin Hon. Licensed under MIT.
"""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from incident_timeline import build_timeline, verify_timeline


class IncidentTimelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.script = Path(__file__).resolve().parents[1] / "incident_timeline.py"

    def write(self, name, records):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n"
                                for record in records), encoding="utf-8")
        return name

    def build(self, inputs=None, **limits):
        return build_timeline(self.root, inputs or ["events.jsonl"], **limits)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(self.script), *args],
                              capture_output=True, text=True)

    def test_shuffled_events_and_input_order_produce_stable_chronology(self):
        self.write("z.jsonl", [
            {"message": "recovered", "time": "2026-06-19T12:02:00Z"},
            {"message": "failed", "time": "2026-06-19T12:00:00Z"},
        ])
        self.write("a.jsonl", [
            {"message": "retry", "time": "2026-06-19T12:01:00Z"},
        ])
        first = self.build(["z.jsonl", "a.jsonl"])
        second = self.build(["a.jsonl", "z.jsonl"])
        self.assertEqual(first, second)
        self.assertEqual([event["message"] for event in first["dated"]],
                         ["failed", "retry", "recovered"])
        self.assertEqual([item["path"] for item in first["inputs"]],
                         ["a.jsonl", "z.jsonl"])
        self.assertEqual(first["coverage"], {
            "start": "2026-06-19T12:00:00.000000Z",
            "end": "2026-06-19T12:02:00.000000Z",
        })

    def test_offsets_and_fractional_seconds_normalize_without_losing_precision(self):
        self.write("events.jsonl", [
            {"source": "z", "message": "equal", "time": "2026-06-19T08:30:00.1-03:30"},
            {"source": "a", "message": "equal", "time": "2026-06-19T17:45:00.100000+05:45"},
            {"source": "b", "message": "later", "time": "2026-06-19T12:00:00.100001Z"},
        ])
        events = self.build()["dated"]
        self.assertEqual([event["source"] for event in events], ["a", "z", "b"])
        self.assertEqual([event["time"] for event in events], [
            "2026-06-19T12:00:00.100000Z",
            "2026-06-19T12:00:00.100000Z",
            "2026-06-19T12:00:00.100001Z",
        ])

    def test_duplicate_events_are_preserved_with_original_line_numbers(self):
        event = {"source": "worker", "message": "retry", "time": "2026-06-19T12:00:00Z"}
        self.write("events.jsonl", [event, event])
        result = self.build()
        self.assertEqual(len(result["dated"]), 2)
        self.assertEqual([row["line"] for row in result["dated"]], [1, 2])
        self.assertEqual([row["input"] for row in result["dated"]],
                         ["events.jsonl", "events.jsonl"])
        self.assertEqual(result["inputs"][0]["records"], 2)

    def test_missing_or_null_time_remains_separate_and_source_defaults_to_path(self):
        self.write("events.jsonl", [
            {"message": "unknown time"},
            {"message": "explicitly undated", "time": None, "source": "service"},
            {"message": "dated", "time": "2026-06-19T12:00:00Z"},
        ])
        result = self.build()
        self.assertEqual(len(result["dated"]), 1)
        self.assertEqual(len(result["undated"]), 2)
        self.assertTrue(all(row["time"] is None for row in result["undated"]))
        self.assertEqual(result["undated"][0]["source"], "events.jsonl")
        self.assertEqual(result["undated"][0]["line"], 1)

    def test_input_receipt_hashes_exact_utf8_bytes_and_counts_records(self):
        self.write("events.jsonl", [{"message": "茶"}, {"message": "recovered"}])
        raw = (self.root / "events.jsonl").read_bytes()
        result = self.build()
        self.assertEqual(result["schema"], "atlas.incident.timeline.v1")
        self.assertEqual(result["inputs"], [{
            "path": "events.jsonl", "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw), "records": 2,
        }])
        self.assertEqual(result["total_bytes"], len(raw))
        self.assertEqual(result["total_records"], 2)
        self.assertEqual(verify_timeline(result, self.root),
                         {"valid": True, "records": 2, "inputs": 1})

    def test_empty_files_have_no_events_or_invented_coverage(self):
        (self.root / "events.jsonl").write_bytes(b"")
        result = self.build()
        self.assertEqual(result["dated"], [])
        self.assertEqual(result["undated"], [])
        self.assertEqual(result["total_bytes"], 0)
        self.assertEqual(result["total_records"], 0)
        self.assertEqual(result["coverage"], {"start": None, "end": None})
        self.assertEqual(verify_timeline(result, self.root),
                         {"valid": True, "records": 0, "inputs": 1})

    def test_byte_limit_is_aggregate_and_exact_boundary_succeeds(self):
        self.write("a.jsonl", [{"message": "茶"}])
        self.write("b.jsonl", [{"message": "b"}])
        size = sum((self.root / name).stat().st_size for name in ["a.jsonl", "b.jsonl"])
        result = self.build(["a.jsonl", "b.jsonl"], max_bytes=size)
        self.assertEqual(sum(item["bytes"] for item in result["inputs"]), size)
        with self.assertRaises(ValueError):
            self.build(["a.jsonl", "b.jsonl"], max_bytes=size - 1)

    def test_record_limit_counts_dated_and_undated_across_files(self):
        self.write("a.jsonl", [{"message": "one"}, {"message": "two"}])
        self.write("b.jsonl", [{"message": "three", "time": "2026-06-19T12:00:00Z"}])
        result = self.build(["b.jsonl", "a.jsonl"], max_records=3)
        self.assertEqual(len(result["dated"]) + len(result["undated"]), 3)
        with self.assertRaises(ValueError):
            self.build(["a.jsonl", "b.jsonl"], max_records=2)

    def test_limits_reject_invalid_types_and_unbounded_values(self):
        self.write("events.jsonl", [{"message": "one"}])
        for name, values in [("max_bytes", [0, -1, True, 1.5, "10", 16 * 1024 * 1024 + 1]),
                             ("max_records", [0, -1, True, 1.5, "10", 100001])]:
            for value in values:
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    self.build(**{name: value})

    def test_unknown_fields_and_invalid_record_shapes_fail_explicitly(self):
        invalid = [[], None, "event", {}, {"message": ""}, {"message": 123},
                   {"message": "event", "extra": "ignored?"},
                   {"message": "event", "source": 123},
                   {"message": "event", "source": None},
                   {"message": "event", "time": 123}]
        for row in invalid:
            with self.subTest(row=row):
                self.write("events.jsonl", [row])
                with self.assertRaises(ValueError):
                    self.build()

    def test_duplicate_json_keys_are_rejected(self):
        (self.root / "events.jsonl").write_text(
            '{"message":"first","message":"replacement"}\n', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.build()

    def test_malformed_json_invalid_utf8_and_blank_lines_are_rejected(self):
        for raw in [b'{broken}\n', b'{"message":"\xff"}\n',
                    b'\n', b'{"message":"one"}\n\n']:
            with self.subTest(raw=raw):
                (self.root / "events.jsonl").write_bytes(raw)
                with self.assertRaises(ValueError):
                    self.build()

    def test_invalid_or_ambiguous_timestamps_are_not_silently_undated(self):
        invalid = ["2026-06-19T12:00:00", "2026-06-19", "2026-06-19 12:00:00Z",
                   "2026-02-30T12:00:00Z", "2026-06-19T24:00:00Z",
                   "2026-06-19T12:00:60Z", "2026-06-19T12:00:00-00:00",
                   "2026-06-19T12:00:00+24:00", "2026-06-19T12:00:00+00:60",
                   "2026-06-19T12:00:00.1234567Z", "2026-06-19T12:00:00z", ""]
        for value in invalid:
            with self.subTest(time=value):
                self.write("events.jsonl", [{"message": "event", "time": value}])
                with self.assertRaises(ValueError):
                    self.build()

    def test_input_paths_cannot_escape_or_alias_root(self):
        self.write("events.jsonl", [{"message": "one"}])
        paths = [str(self.root / "events.jsonl"), "../events.jsonl", "./events.jsonl",
                 "a/../events.jsonl", "a//events.jsonl", "a\\events.jsonl",
                 "a:events.jsonl", "events.jsonl/", "a" * 257, ""]
        for name in paths:
            with self.subTest(name=name), self.assertRaises(ValueError):
                build_timeline(self.root, [name])

    def test_file_directory_and_root_symlinks_are_rejected(self):
        self.write("real/events.jsonl", [{"message": "one"}])
        (self.root / "linked.jsonl").symlink_to(self.root / "real/events.jsonl")
        (self.root / "linked-dir").symlink_to(self.root / "real", target_is_directory=True)
        for name in ["linked.jsonl", "linked-dir/events.jsonl"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.build([name])
        with self.assertRaises(ValueError):
            build_timeline(self.root / "linked-dir", ["events.jsonl"])

    def test_nonregular_inputs_and_duplicate_or_missing_input_list_are_rejected(self):
        self.write("events.jsonl", [{"message": "one"}])
        (self.root / "directory").mkdir()
        os.mkfifo(self.root / "pipe")
        for inputs in [["directory"], ["pipe"], ["missing.jsonl"], [],
                       ["events.jsonl", "events.jsonl"]]:
            with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                build_timeline(self.root, inputs)
        too_many = [self.write("batch/{:03d}.jsonl".format(index), []) for index in range(257)]
        with self.assertRaises(ValueError):
            build_timeline(self.root, too_many)

    def test_source_edit_or_deletion_invalidates_saved_receipt(self):
        self.write("events.jsonl", [{"message": "original"}])
        receipt = self.build()
        self.write("events.jsonl", [{"message": "modified"}])
        with self.assertRaises(ValueError):
            verify_timeline(receipt, self.root)
        (self.root / "events.jsonl").unlink()
        with self.assertRaises(ValueError):
            verify_timeline(receipt, self.root)

    def test_whitespace_only_source_drift_is_detected(self):
        self.write("events.jsonl", [{"message": "original"}])
        receipt = self.build()
        (self.root / "events.jsonl").write_text('{"message": "original"}  \n', encoding="utf-8")
        with self.assertRaises(ValueError):
            verify_timeline(receipt, self.root)

    def test_modified_events_and_source_metadata_fail_verification(self):
        self.write("events.jsonl", [{"message": "original", "time": "2026-06-19T12:00:00Z"}])
        original = self.build()
        changed_text = copy.deepcopy(original)
        changed_text["dated"][0]["message"] = "invented"
        changed_hash = copy.deepcopy(original)
        changed_hash["inputs"][0]["sha256"] = "0" * 64
        changed_count = copy.deepcopy(original)
        changed_count["inputs"][0]["records"] = 99
        changed_order = copy.deepcopy(original)
        changed_order["dated"] = []
        changed_boolean_line = copy.deepcopy(original)
        changed_boolean_line["dated"][0]["line"] = True
        changed_float_line = copy.deepcopy(original)
        changed_float_line["dated"][0]["line"] = 1.0
        changed_boolean_count = copy.deepcopy(original)
        changed_boolean_count["total_records"] = True
        for receipt in [changed_text, changed_hash, changed_count, changed_order,
                        changed_boolean_line, changed_float_line, changed_boolean_count]:
            with self.subTest(receipt=receipt), self.assertRaises(ValueError):
                verify_timeline(receipt, self.root)

    def test_malformed_receipts_are_rejected(self):
        self.write("events.jsonl", [{"message": "one"}])
        original = self.build()
        extra = copy.deepcopy(original)
        extra["ignored"] = True
        unsupported = dict(original, schema="unrecognized")
        for receipt in [None, [], {}, extra, unsupported]:
            with self.subTest(receipt=receipt), self.assertRaises(ValueError):
                verify_timeline(receipt, self.root)

    def test_cli_build_and_check_round_trip(self):
        self.write("events.jsonl", [{"message": "one"}])
        built = self.cli("build", "--root", str(self.root), "--input", "events.jsonl",
                         "--out", "receipt.json")
        self.assertEqual(built.returncode, 0, built.stderr)
        receipt = json.loads((self.root / "receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt, self.build())
        checked = self.cli("check", "--root", str(self.root), "--receipt", "receipt.json")
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_cli_never_overwrites_an_input_or_existing_output(self):
        self.write("events.jsonl", [{"message": "one"}])
        (self.root / "existing.json").write_bytes(b"keep this receipt")
        for output in ["events.jsonl", "existing.json"]:
            path = self.root / output
            original = path.read_bytes()
            result = self.cli("build", "--root", str(self.root), "--input", "events.jsonl",
                              "--out", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(path.read_bytes(), original)

    def test_cli_rejects_unsafe_or_symlink_output_paths(self):
        self.write("events.jsonl", [{"message": "one"}])
        (self.root / "alias.json").symlink_to(self.root / "events.jsonl")
        (self.root / "linked-dir").symlink_to(self.root, target_is_directory=True)
        for output in ["../outside.json", str(self.root / "absolute.json"),
                       "alias.json", "linked-dir/receipt.json"]:
            with self.subTest(output=output):
                result = self.cli("build", "--root", str(self.root), "--input", "events.jsonl",
                                  "--out", output)
                self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "receipt.json").exists())

    def test_cli_failure_does_not_write_partial_receipt(self):
        self.write("events.jsonl", [{"message": "one"}, {"message": "two"}])
        result = self.cli("build", "--root", str(self.root), "--input", "events.jsonl",
                          "--max-records", "1", "--out", "receipt.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(result.stderr.strip())
        self.assertFalse((self.root / "receipt.json").exists())

    def test_cli_check_reports_changed_evidence(self):
        self.write("events.jsonl", [{"message": "one"}])
        (self.root / "receipt.json").write_text(json.dumps(self.build()), encoding="utf-8")
        self.write("events.jsonl", [{"message": "two"}])
        result = self.cli("check", "--root", str(self.root), "--receipt", "receipt.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(result.stderr.strip())


if __name__ == "__main__":
    unittest.main()

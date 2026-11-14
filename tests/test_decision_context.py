"""Behavioural and adversarial checks for bounded decision context.

The fixtures represent explicitly declared decisions, not inferred meaning.
Copyright 2026 Albert Tan Sin Hon. Licensed under MIT.
"""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from decision_context import build_context, check_context


class DecisionContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / "decisions.json"

    def decision(self, number, *, status="accepted", scopes=None,
                 supersedes=None, text=None):
        identifier = "ADR-{:04d}".format(number)
        path = "docs/adr/{:04d}-decision.md".format(number)
        source = self.root / path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(text if text is not None else "# {}\n\nDecision {}.\n".format(identifier, number),
                          encoding="utf-8")
        return {"id": identifier, "path": path, "status": status,
                "scopes": ["billing"] if scopes is None else scopes,
                "supersedes": [] if supersedes is None else supersedes}

    def catalogue(self, records):
        self.manifest.write_text(json.dumps({
            "schema": "atlas.decision.catalogue.v1", "decisions": records,
        }, indent=2), encoding="utf-8")

    def build(self, records=None, *, scopes=None, max_bytes=24000):
        if records is not None:
            self.catalogue(records)
        return build_context(self.root, self.manifest,
                             ["billing"] if scopes is None else scopes,
                             max_bytes=max_bytes)

    def selected_ids(self, bundle):
        return [record["id"] for record in bundle["selected"]]

    def test_large_history_selects_current_scoped_and_global_decisions(self):
        records = [self.decision(1),
                   self.decision(2, supersedes=["ADR-0001"]),
                   self.decision(3, scopes=["global"])]
        records += [self.decision(n, scopes=["warehouse"], status="deprecated")
                    for n in range(4, 151)]
        result = self.build(records)
        self.assertTrue(result["ready"])
        self.assertEqual(set(self.selected_ids(result)), {"ADR-0002", "ADR-0003"})
        self.assertEqual(result["source_count"], 150)
        self.assertEqual(len(result["omitted"]), 148)
        self.assertEqual(result["selected_bytes"], sum(
            len(record["text"].encode("utf-8")) for record in result["selected"]))
        self.assertLess(result["selected_bytes"], result["total_source_bytes"])
        self.assertEqual(check_context(result, self.root),
                         {"valid": True, "selected": 2, "scope": ["billing"]})

    def test_proposed_successor_does_not_overrule_accepted_decision(self):
        result = self.build([self.decision(1), self.decision(
            2, status="proposed", supersedes=["ADR-0001"])])
        self.assertEqual(self.selected_ids(result), ["ADR-0001"])
        self.assertTrue(result["ready"])

    def test_transitive_accepted_successor_suppresses_ancestor(self):
        result = self.build([
            self.decision(1),
            self.decision(2, status="proposed", supersedes=["ADR-0001"]),
            self.decision(3, supersedes=["ADR-0002"]),
        ])
        self.assertEqual(self.selected_ids(result), ["ADR-0003"])

    def test_unspecified_scoped_status_is_visible_and_not_ready(self):
        result = self.build([self.decision(1, status="unspecified")])
        self.assertEqual(result["selected"], [])
        self.assertFalse(result["ready"])
        self.assertEqual(result["omitted"][0]["id"], "ADR-0001")
        self.assertIn("unspecified", result["omitted"][0]["reason"].lower())

    def test_unspecified_outside_requested_scope_does_not_block(self):
        result = self.build([self.decision(1), self.decision(
            2, status="unspecified", scopes=["warehouse"])])
        self.assertTrue(result["ready"])
        self.assertEqual(self.selected_ids(result), ["ADR-0001"])

    def test_superseded_scoped_unspecified_status_still_requires_review(self):
        result = self.build([
            self.decision(1, status="unspecified"),
            self.decision(2, supersedes=["ADR-0001"]),
        ])
        self.assertEqual(self.selected_ids(result), ["ADR-0002"])
        self.assertFalse(result["ready"])
        self.assertIn("unspecified", result["omitted"][0]["reason"].lower())

    def test_duplicate_identifiers_are_rejected(self):
        records = [self.decision(1), self.decision(2)]
        records[1]["id"] = records[0]["id"]
        with self.assertRaises(ValueError):
            self.build(records)

    def test_duplicate_source_paths_are_rejected(self):
        records = [self.decision(1), self.decision(2)]
        records[1]["path"] = records[0]["path"]
        with self.assertRaises(ValueError):
            self.build(records)

    def test_non_string_source_paths_raise_validation_errors(self):
        record = self.decision(1)
        for path in [None, [], {}, 17, True]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.build([dict(record, path=path)])

    def test_missing_target_and_self_supersession_are_rejected(self):
        for target in ["ADR-9999", "ADR-0001"]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.build([self.decision(1, supersedes=[target])])

    def test_cycles_are_rejected_even_outside_requested_scope(self):
        records = [self.decision(1), self.decision(
            2, scopes=["warehouse"], supersedes=["ADR-0003"]),
            self.decision(3, scopes=["warehouse"], supersedes=["ADR-0002"])]
        with self.assertRaises(ValueError):
            self.build(records)

    def test_competing_terminal_accepted_successors_are_not_date_ranked(self):
        records = [self.decision(1),
                   self.decision(2, supersedes=["ADR-0001"]),
                   self.decision(3, supersedes=["ADR-0001"])]
        with self.assertRaises(ValueError):
            self.build(records)

    def test_linear_accepted_successors_are_unambiguous(self):
        result = self.build([
            self.decision(1), self.decision(2, supersedes=["ADR-0001"]),
            self.decision(3, supersedes=["ADR-0002"]),
        ])
        self.assertEqual(self.selected_ids(result), ["ADR-0003"])

    def test_supersession_replaces_all_predecessor_scopes(self):
        result = self.build([
            self.decision(1, scopes=["global"]),
            self.decision(2, scopes=["warehouse"], supersedes=["ADR-0001"]),
        ])
        self.assertEqual(result["selected"], [])
        self.assertTrue(result["ready"])
        self.assertIn("superseded", result["omitted"][0]["reason"])

    def test_duplicate_catalogue_keys_are_rejected(self):
        self.catalogue([self.decision(1)])
        raw = self.manifest.read_text(encoding="utf-8")
        self.manifest.write_text(raw.replace(
            '"status": "accepted"', '"status": "proposed", "status": "accepted"'),
            encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            self.build()

    def test_catalogue_requires_utf8_and_json_numeric_constants(self):
        self.catalogue([self.decision(1)])
        raw = self.manifest.read_text(encoding="utf-8")
        cases = [raw.encode("utf-16"), raw.replace('"accepted"', "NaN").encode("utf-8")]
        for data in cases:
            with self.subTest(data=data[:30]), self.assertRaises(ValueError):
                self.manifest.write_bytes(data)
                self.build()

    def test_unknown_and_missing_status_are_never_assumed_accepted(self):
        for state in ["active", "ACCEPTED", None]:
            with self.subTest(status=state):
                record = self.decision(1)
                if state is None:
                    del record["status"]
                else:
                    record["status"] = state
                with self.assertRaises(ValueError):
                    self.build([record])

    def test_unsafe_absolute_and_parent_paths_are_rejected(self):
        record = self.decision(1)
        for path in [str(self.root / record["path"]), "../outside.md",
                     "docs/adr/../0001-decision.md"]:
            with self.subTest(path=path):
                changed = dict(record, path=path)
                with self.assertRaises(ValueError):
                    self.build([changed])

    def test_file_and_directory_symlinks_are_rejected(self):
        record = self.decision(1)
        target = self.root / record["path"]
        (self.root / "linked.md").symlink_to(target)
        (self.root / "linked-dir").symlink_to(target.parent, target_is_directory=True)
        for path in ["linked.md", "linked-dir/0001-decision.md"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.build([dict(record, path=path)])

    def test_selected_source_edit_and_deletion_invalidate_saved_context(self):
        record = self.decision(1)
        original = self.build([record])
        path = self.root / record["path"]
        path.write_text("# A different decision\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            check_context(original, self.root)
        path.unlink()
        with self.assertRaises(ValueError):
            check_context(original, self.root)

    def test_catalogue_byte_change_requires_rebuild_even_when_json_equivalent(self):
        original = self.build([self.decision(1)])
        self.manifest.write_text(self.manifest.read_text(encoding="utf-8") + "\n",
                                 encoding="utf-8")
        with self.assertRaises(ValueError):
            check_context(original, self.root)

    def test_context_text_and_selection_tampering_are_rejected(self):
        original = self.build([self.decision(1)])
        changed_text = copy.deepcopy(original)
        changed_text["selected"][0]["text"] = "Invented replacement instruction."
        changed_selection = copy.deepcopy(original)
        changed_selection["selected"] = []
        changed_readiness = copy.deepcopy(original)
        changed_readiness["ready"] = False
        for changed in [changed_text, changed_selection, changed_readiness]:
            with self.subTest(change=changed), self.assertRaises(ValueError):
                check_context(changed, self.root)

    def test_non_json_bundle_values_raise_validation_errors(self):
        bundle = self.build([self.decision(1)])
        bundle["scopes"] = {"billing"}
        with self.assertRaises(ValueError):
            check_context(bundle, self.root)

    def test_unselected_source_edit_does_not_invalidate_selected_context(self):
        records = [self.decision(1), self.decision(2, scopes=["warehouse"])]
        original = self.build(records)
        (self.root / records[1]["path"]).write_text(
            "A longer, changed decision in another domain.\n", encoding="utf-8")
        self.assertEqual(check_context(original, self.root),
                         {"valid": True, "selected": 1, "scope": ["billing"]})

    def test_byte_budget_counts_utf8_and_never_truncates(self):
        text = "# 茶\n\nUse the existing store.\n"
        record = self.decision(1, text=text)
        byte_count = len(text.encode("utf-8"))
        exact = self.build([record], max_bytes=byte_count)
        self.assertEqual(exact["selected_bytes"], byte_count)
        self.assertEqual(exact["selected"][0]["text"], text)
        with self.assertRaises(ValueError):
            self.build(max_bytes=byte_count - 1)

    def test_selected_order_and_scope_order_are_deterministic(self):
        records = [self.decision(3, scopes=["warehouse"]), self.decision(1),
                   self.decision(2, scopes=["global"])]
        first = self.build(records, scopes=["warehouse", "billing"])
        second = self.build(list(reversed(records)), scopes=["billing", "warehouse"])
        self.assertEqual(first["selected"], second["selected"])
        self.assertEqual(first["scopes"], ["billing", "warehouse"])
        self.assertEqual(second["scopes"], ["billing", "warehouse"])

    def test_cli_build_check_and_unresolved_status_exit_codes(self):
        script = Path(__file__).resolve().parents[1] / "decision_context.py"
        self.catalogue([self.decision(1)])
        output = self.root / "context.json"
        command = [sys.executable, str(script), "build", "--root", str(self.root),
                   "--manifest", str(self.manifest), "--scope", "billing",
                   "--out", str(output)]
        built = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(built.returncode, 0, built.stderr)
        self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["ready"])
        checked = subprocess.run(
            [sys.executable, str(script), "check", "--root", str(self.root),
             "--bundle", str(output)], capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.catalogue([self.decision(1, status="unspecified")])
        output.unlink()
        unresolved = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(unresolved.returncode, 2, unresolved.stderr)
        self.assertFalse(json.loads(output.read_text(encoding="utf-8"))["ready"])

    def test_cli_output_cannot_overwrite_a_source_through_a_hard_link(self):
        script = Path(__file__).resolve().parents[1] / "decision_context.py"
        record = self.decision(1)
        self.catalogue([record])
        source = self.root / record["path"]
        original = source.read_bytes()
        output = self.root / "context.json"
        os.link(source, output)
        built = subprocess.run(
            [sys.executable, str(script), "build", "--root", str(self.root),
             "--manifest", str(self.manifest), "--scope", "billing",
             "--out", str(output)], capture_output=True, text=True)
        self.assertEqual(source.read_bytes(), original,
                         "Writing a context must never mutate a declared source")
        self.assertEqual(built.returncode, 2, built.stderr)

    def test_cli_can_check_its_own_output_within_allowed_source_budget(self):
        script = Path(__file__).resolve().parents[1] / "decision_context.py"
        source_text = "# Decision\n" + "\n" * 2_100_000
        self.catalogue([self.decision(1, text=source_text)])
        output = self.root / "context.json"
        built = subprocess.run(
            [sys.executable, str(script), "build", "--root", str(self.root),
             "--manifest", str(self.manifest), "--scope", "billing",
             "--max-bytes", str(len(source_text.encode("utf-8"))),
             "--out", str(output)], capture_output=True, text=True)
        self.assertEqual(built.returncode, 0, built.stderr)
        checked = subprocess.run(
            [sys.executable, str(script), "check", "--root", str(self.root),
             "--bundle", str(output)], capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_cli_rejects_duplicate_bundle_keys(self):
        script = Path(__file__).resolve().parents[1] / "decision_context.py"
        bundle = self.build([self.decision(1)])
        output = self.root / "context.json"
        raw = json.dumps(bundle)
        output.write_text(raw.replace('"ready": true', '"ready": false, "ready": true'),
                          encoding="utf-8")
        checked = subprocess.run(
            [sys.executable, str(script), "check", "--root", str(self.root),
             "--bundle", str(output)], capture_output=True, text=True)
        self.assertEqual(checked.returncode, 2, checked.stderr)
        self.assertIn("Duplicate JSON key", checked.stderr)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "Named pipes are unavailable")
    def test_cli_rejects_named_pipe_source_without_blocking(self):
        script = Path(__file__).resolve().parents[1] / "decision_context.py"
        record = self.decision(1)
        source = self.root / record["path"]
        source.unlink()
        os.mkfifo(source)
        self.catalogue([record])
        built = subprocess.run(
            [sys.executable, str(script), "build", "--root", str(self.root),
             "--manifest", str(self.manifest), "--scope", "billing",
             "--out", str(self.root / "context.json")],
            capture_output=True, text=True, timeout=5)
        self.assertEqual(built.returncode, 2, built.stderr)
        self.assertIn("regular file", built.stderr)


if __name__ == "__main__":
    unittest.main()

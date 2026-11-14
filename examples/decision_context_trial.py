#!/usr/bin/env python3
"""Exercise original synthetic decisions without accessing a real repository.

Copyright 2026 Albert Tan Sin Hon. Licensed under MIT.
"""

import copy
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from decision_context import build_context, check_context


def expect_rejection(action):
    try:
        action()
    except ValueError as error:
        return {"detected": True, "reason": str(error)}
    raise AssertionError("A deliberately invalid case was accepted")


def run_trial():
    with tempfile.TemporaryDirectory(prefix="atlas-decision-trial-") as directory:
        root = Path(directory)
        manifest = root / "decisions.json"
        records = []

        def decision(number, title, text, status="accepted", scopes=None, supersedes=None):
            path = "docs/adr/%04d.md" % number
            source = root / path
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("# " + title + "\n\n" + text + "\n", encoding="utf-8")
            records.append({"id": "ADR-%04d" % number, "path": path, "status": status,
                            "scopes": ["billing"] if scopes is None else scopes,
                            "supersedes": [] if supersedes is None else supersedes})

        def save_catalogue(rows):
            manifest.write_text(json.dumps({"schema": "atlas.decision.catalogue.v1",
                                            "decisions": rows}, indent=2) + "\n",
                                encoding="utf-8")

        decision(1, "Synthetic execution receipts",
                 "Record input hashes with every reproducible demonstration.", scopes=["global"])
        decision(2, "Synthetic invoice draft storage",
                 "The example initially stores invoice drafts in one local JSON file.")
        decision(3, "Synthetic invoice draft transactions",
                 "Use a local SQLite transaction for each draft update in this example.",
                 supersedes=["ADR-0002"])
        decision(4, "Synthetic remote draft proposal",
                 "A remote draft service is a proposal awaiting human review.",
                 status="proposed", supersedes=["ADR-0003"])
        decision(5, "Synthetic warehouse note",
                 "This imported note has no declared acceptance decision.",
                 status="unspecified", scopes=["warehouse"])
        for number in range(6, 151):
            decision(number, "Archived synthetic experiment %d" % number,
                     "This obsolete warehouse experiment is retained as historical evidence.",
                     status="deprecated", scopes=["warehouse"])
        save_catalogue(records)

        bundle = build_context(root, manifest, ["billing"])
        selected_ids = [row["id"] for row in bundle["selected"]]
        if selected_ids != ["ADR-0001", "ADR-0003"] or not bundle["ready"]:
            raise AssertionError("The declared current and global decisions were not selected")
        positive = check_context(bundle, root)

        source = root / records[2]["path"]
        original_source = source.read_bytes()
        source.write_bytes(original_source + b"\nDeliberate source drift.\n")
        drift = expect_rejection(lambda: check_context(bundle, root))
        source.write_bytes(original_source)

        original_manifest = manifest.read_bytes()
        manifest.write_bytes(original_manifest + b"\n")
        catalogue_drift = expect_rejection(lambda: check_context(bundle, root))
        manifest.write_bytes(original_manifest)

        changed = copy.deepcopy(bundle)
        changed["selected"][0]["text"] = "An invented decision inserted after the build."
        tampering = expect_rejection(lambda: check_context(changed, root))
        budget = expect_rejection(lambda: build_context(
            root, manifest, ["billing"], max_bytes=bundle["selected_bytes"] - 1))

        unresolved_records = copy.deepcopy(records)
        unresolved_records[4]["scopes"] = ["billing"]
        save_catalogue(unresolved_records)
        unresolved_bundle = build_context(root, manifest, ["billing"])
        if unresolved_bundle["ready"]:
            raise AssertionError("A scoped unspecified decision was silently accepted")
        unspecified = expect_rejection(lambda: check_context(unresolved_bundle, root))

        cyclic_records = copy.deepcopy(records)
        cyclic_records[9]["supersedes"] = ["ADR-0011"]
        cyclic_records[10]["supersedes"] = ["ADR-0010"]
        save_catalogue(cyclic_records)
        cycle = expect_rejection(lambda: build_context(root, manifest, ["billing"]))

        return {"schema": "atlas.decision.trial.v1", "fixture": "original synthetic decisions",
                "source_count": bundle["source_count"], "selected_ids": selected_ids,
                "selected_bytes": bundle["selected_bytes"],
                "total_source_bytes": bundle["total_source_bytes"],
                "omitted_count": len(bundle["omitted"]), "positive_check": positive,
                "negative_checks": {"selected_source_drift": drift,
                                    "catalogue_byte_drift": catalogue_drift,
                                    "bundle_tampering": tampering, "budget_overflow": budget,
                                    "unspecified_status": unspecified, "out_of_scope_cycle": cycle}}


if __name__ == "__main__":
    print(json.dumps(run_trial(), indent=2, sort_keys=True))

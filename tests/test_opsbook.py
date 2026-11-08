import concurrent.futures
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import install_agent
import opsbook as b
import pstack

ROOT = Path(b.__file__).parent
CASES = json.loads((ROOT / "examples/cases.json").read_text())
WIDE = json.loads((ROOT / "examples/overbroad.json").read_text())


class Manual(unittest.TestCase):
    def setUp(self):
        self.s = b.initial()
        for c in CASES:
            b.add_case(self.s, c)

    def learn(self):
        return b.learn(self.s, "missing-wheel", "install-clean", "Import the built package.")["proposal"]

    def test_learns_conjunction(self):
        key = self.learn()
        self.assertEqual(self.s["drafts"][key]["rule"]["when"], {"artefact":"package","task":"ship"})
        report = b.assess(self.s, key)
        self.assertTrue(report["eligible"])
        self.assertEqual((report["exam"]["correct_before"], report["exam"]["correct_after"]), (2,4))

    def test_generalisation_fails_on_control(self):
        key = b.draft(self.s, WIDE)["proposal"]
        report = b.assess(self.s, key)
        self.assertFalse(report["eligible"])
        self.assertEqual(next(r for r in report["exam"]["rows"] if r["id"] == "release-notes")["introduced"], ["install-clean"])
        with self.assertRaises(ValueError):
            b.assess(self.s, key, True)

    def test_no_exam_and_no_control(self):
        for split in ("practice", "exam"):
            s = b.initial()
            for c in CASES:
                if c["set"] != split or c["expected"]:
                    b.add_case(s,c)
            key = b.draft(s, WIDE)["proposal"]
            self.assertFalse(b.assess(s, key)["eligible"])
        del self.s["cases"]["macos-wheel"]
        self.s["cases"] = {k:v for k,v in self.s["cases"].items() if v["set"] == "practice"}
        self.assertFalse(b.assess(self.s, self.learn())["eligible"])

    def test_learning_does_not_read_exam_labels(self):
        first = self.s["drafts"][self.learn()]["rule"]
        for c in self.s["cases"].values():
            if c["set"] == "exam":
                c["expected"] = ["another-check"]
        second = self.s["drafts"][self.learn()]["rule"]
        self.assertEqual(first, second)
        self.assertFalse(b.assess(self.s,self.learn())["eligible"])

    def test_changed_cases_invalidate_proposal(self):
        key = self.learn()
        b.add_case(self.s, dict(CASES[0], id="more", context={"new":"context"}))
        with self.assertRaisesRegex(ValueError, "changed"):
            b.assess(self.s, key, True)

    def test_cannot_train_on_exam_or_duplicate_context(self):
        with self.assertRaises(ValueError):
            b.learn(self.s,"bsd-wheel","install-clean","Import it.")
        for changes in ({"id":"renamed"}, {"expected":[]}, {"context":[]}, {"set":"test"}):
            with self.assertRaises(ValueError):
                b.add_case(self.s,dict(CASES[0], **changes))
        b.add_case(self.s,CASES[0])
        self.assertEqual(len(self.s["cases"]),8)

    def test_promotion_idempotence_and_stale_proposal(self):
        wide = b.draft(self.s,WIDE)["proposal"]
        key = self.learn()
        self.assertEqual(b.assess(self.s,key,True), b.assess(self.s,key,True))
        with self.assertRaises(ValueError):
            b.assess(self.s,wide,True)

    def test_rollback_history_and_rule_replacement(self):
        b.assess(self.s,self.learn(),True)
        active = self.s["versions"][-1]["rules"][0]["id"]
        key = b.draft(self.s,dict(WIDE,replaces=active))["proposal"]
        self.assertFalse(b.assess(self.s,key)["eligible"])
        a = b.parser().parse_args(["rollback","0","bad instruction"])
        self.assertEqual(b.dispatch(self.s,a),b.dispatch(self.s,a))
        self.assertEqual(len(self.s["versions"]),3)
        self.assertIn("No project",b.render(self.s))

    def test_per_check_regression_can_hide_inside_an_existing_error(self):
        s = b.initial()
        b.add_case(s,dict(CASES[0], expected=["x","y"]))
        report = b.trial(s,[{"when":{"task":"ship"},"check":"x"},{"when":{"task":"ship"},"check":"z"}])
        row = report["practice"]["rows"][0]
        self.assertEqual((row["fixed"], row["introduced"]), (["x"],["z"]))

    def test_demo(self):
        d = b.demonstration()
        self.assertFalse(d["missing_check"]["pass"])
        self.assertTrue(d["completed_check"]["pass"])
        self.assertFalse(d["after_rollback"]["instructions"])


class Integration(unittest.TestCase):
    def test_transactions_close_connections_and_preserve_commits(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "manual.db"
            for argv in (["init"], ["record", str(ROOT / "examples/cases.json")]):
                connection = sqlite3.connect(db)
                try:
                    with patch("opsbook.sqlite3.connect", return_value=connection):
                        b.transact(db, b.parser().parse_args(argv))
                    with self.assertRaises(sqlite3.ProgrammingError):
                        connection.execute("SELECT 1")
                finally:
                    connection.close()
            connection = sqlite3.connect(db)
            try:
                state = json.loads(connection.execute("SELECT data FROM book WHERE id=1").fetchone()[0])
                self.assertEqual(len(state["cases"]), len(CASES))
            finally:
                connection.close()

    def test_transactions_close_connections_on_validation_and_database_errors(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "manual.db"
            b.transact(db, b.parser().parse_args(["init"]))
            invalid = Path(d) / "cases.json"
            invalid.write_text(json.dumps([CASES[0], {"id": "invalid"}]))
            empty = Path(d) / "empty.db"
            empty.touch()
            for path, argv, error in (
                (db, ["record", str(invalid)], ValueError),
                (empty, ["history"], sqlite3.OperationalError),
            ):
                with self.subTest(command=argv[0]):
                    connection = sqlite3.connect(path)
                    try:
                        with patch("opsbook.sqlite3.connect", return_value=connection):
                            with self.assertRaises(error):
                                b.transact(path, b.parser().parse_args(argv))
                        with self.assertRaises(sqlite3.ProgrammingError):
                            connection.execute("SELECT 1")
                    finally:
                        connection.close()
            connection = sqlite3.connect(db)
            try:
                state = json.loads(connection.execute("SELECT data FROM book WHERE id=1").fetchone()[0])
                self.assertEqual(state["cases"], {})
            finally:
                connection.close()

    def test_installs_each_host_and_preserves_codex_file(self):
        for host in ("codex","cursor","claude"):
            with tempfile.TemporaryDirectory() as d:
                path=Path(d)
                (path/"AGENTS.md").write_text("Existing policy\n")
                install_agent.install(path,host)
                install_agent.install(path,host)
                content=(path/"AGENTS.md").read_text()
                self.assertTrue(content.startswith("Existing policy\n"))
                self.assertEqual(content.count(install_agent.BLOCK),int(host=="codex"))
                r=subprocess.run([sys.executable,".opsbook/bin/opsbook.py","demo"],cwd=d,capture_output=True)
                self.assertEqual(r.returncode,0)

    def test_installer_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            (path / "target").write_text("prior")
            (path / "AGENTS.md").symlink_to(path/"target")
            with self.assertRaises(ValueError):
                install_agent.install(path,"codex")
            self.assertEqual((path/"target").read_text(),"prior")

    def test_import_is_atomic_and_cli_exits(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/"state"
            def run(*argv):
                return subprocess.run([sys.executable,str(ROOT/"opsbook.py"),"--db",str(db),*argv],
                                      text=True,capture_output=True)
            self.assertEqual(run("history").returncode,2)
            self.assertEqual(run("init").returncode,0)
            bad=Path(d)/"cases.json"
            bad.write_text(json.dumps([CASES[0],{"id":"invalid"}]))
            self.assertEqual(run("record",str(bad)).returncode,2)
            self.assertEqual(run("learn","missing-wheel","install-clean","Test it").returncode,2)
            run("record",str(ROOT/"examples/cases.json"))
            key=json.loads(run("learn","missing-wheel","install-clean","Test it").stdout)["proposal"]
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                results=list(pool.map(lambda _: run("promote",key).returncode, range(3)))
            self.assertEqual(results,[0]*3)
            self.assertEqual(len(json.loads(run("history").stdout)),2)
            self.assertEqual(run("gate",json.dumps(CASES[0]["context"])).returncode,1)

    def test_actual_broken_and_fixed_archives(self):
        r=subprocess.run([sys.executable,str(ROOT/"examples/package_trial.py")],capture_output=True,text=True,check=True)
        actual=json.loads(r.stdout)
        self.assertEqual(actual["before_learning"]["checks"],[])
        self.assertEqual(actual["broken_artifact"]["checks"][0]["exit"],1)
        self.assertEqual(actual["repaired_artifact"]["checks"][0]["exit"],0)

    def test_upstream_catalogue(self):
        self.assertEqual(len(pstack.LOCK["skills"]),len(set(pstack.LOCK["skills"])))
        self.assertIn("reflect",pstack.LOCK["skills"])
        self.assertEqual(pstack.source_path("playbook","babysit"),"skills/poteto-mode/playbooks/babysit.md")
        with self.assertRaises(ValueError):
            pstack.source_path("skill","../LICENSE")

    def test_executable_checks_are_explicit_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"checks.json"
            p.write_text('{"inspect":"echo bogus"}')
            with self.assertRaises(ValueError):
                b.run_checks([{"check":"inspect"}],p)
            p.write_text(json.dumps({"inspect":["missing-opsbook-executable-fixture"]}))
            self.assertFalse(b.run_checks([{"check":"inspect"}],p)["pass"])


if __name__ == "__main__":
    unittest.main()

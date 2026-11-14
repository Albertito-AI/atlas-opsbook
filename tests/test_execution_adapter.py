"""Performed local durability tests; no production or distributed-service claim."""
import copy
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapter_host_fixture import DurableHost
from execution_adapter import AdapterError, ExecutionAdapter
from execution_queue import Queue, QueueError


def crash_worker(database, host_path, clock):
    queue = Queue(database, clock=lambda: tuple(clock))
    host = DurableHost(host_path)
    def work(ticket, hold):
        host.apply(hold, quiescent=False)
        os._exit(23)
    ExecutionAdapter(queue, host).run_once("worker", work, lease_ms=1000)


class ExecutionAdapterTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.now = [1000000, 10000, "boot-1"]
        self.queue = Queue(self.root / "queue.sqlite3", clock=lambda: tuple(self.now))
        self.queue.init()
        self.host = DurableHost(self.root / "host.json")
        self.adapter = ExecutionAdapter(self.queue, self.host)
        self.add()

    def add(self, name="one", effectful=True, max_attempts=3, deadline=2000000):
        ticket = self.queue.enqueue(name, job_key="job-" + name, resource_key="resource-" + name,
            outer_revision="stable-claim-1", outer_deadline_ms=deadline, effectful=effectful,
            max_attempts=max_attempts,
            payload={"authority": {"claim_token": "token-" + name, "source_revision": "source-1"},
                     "task": "synthetic retained-file observation"})
        self.host.register(ticket)
        return ticket

    def advance(self, ms):
        self.now[0] += ms
        self.now[1] += ms

    def work(self, ticket, hold):
        current = self.queue.get(ticket["dispatch_id"])
        self.assertTrue(current["effect_started"])
        self.assertEqual(self.host.read(ticket)["hold"], hold)
        return self.host.apply(hold)

    def held(self):
        return self.host.pending_holds()["holds"][0]

    def restart(self):
        return ExecutionAdapter(Queue(self.queue.path, clock=lambda: tuple(self.now)), DurableHost(self.host.path))

    def test_success_autonomously_resolves_and_next_job_runs(self):
        self.add("two")
        first = self.adapter.run_once("worker", self.work)
        second = self.adapter.run_once("worker", self.work)
        self.assertEqual(first["status"], "resolved")
        self.assertEqual(second["status"], "resolved")
        self.assertEqual(len(self.host.state()["effects"]), 2)
        self.assertEqual(self.host.pending_holds()["holds"], [])
        self.assertEqual(self.adapter.run_once("worker", self.work)["status"], "idle")

    def test_read_only_worker_has_local_receipt_without_effect_claim(self):
        self.host.mutate(lambda state: state["claims"].clear())
        self.queue.claim("discard")
        self.queue.fail("one", "discard", 1, "not this test", retry=False)
        self.add("read", effectful=False)
        result = self.adapter.run_once("worker", lambda ticket, hold: {"read": True, "hold_is_none": hold is None})
        self.assertEqual(result["status"], "completed_read_only")
        self.assertEqual(self.host.state()["effects"], [])

    def test_preexisting_operator_stop_prevents_worker(self):
        self.host.mutate(lambda state: state.update(operator_stop=True))
        with patch.object(self, "work") as work:
            for _ in range(5):
                self.assertEqual(self.adapter.run_once("worker", work)["status"], "blocked")
        work.assert_not_called()
        self.assertTrue(self.host.state()["operator_stop"])
        self.assertEqual(self.queue.get("one")["attempts"], 0)
        self.assertEqual(self.queue.get("one")["state"], "ready")

    def test_preexisting_other_stop_does_not_consume_attempts(self):
        self.host.mutate(lambda state: state.update(other_stops=["protected-other-job"]))
        with patch.object(self, "work") as work:
            for _ in range(5):
                self.assertEqual(self.adapter.run_once("worker", work)["status"], "blocked")
            work.assert_not_called()
        self.assertEqual(self.queue.get("one")["attempts"], 0)
        self.assertEqual(self.queue.get("one")["state"], "ready")

    def test_atomic_hold_creation_rejects_changed_assignment(self):
        original = self.host.acquire_hold
        def changed(binding, snapshot):
            self.host.mutate(lambda state: state["claims"]["job-one"].update(claim_token="changed"))
            original(binding, snapshot)
        with patch.object(self.host, "acquire_hold", side_effect=changed), patch.object(self, "work") as work:
            with self.assertRaises(AdapterError):
                self.adapter.run_once("worker", work)
            work.assert_not_called()
        self.assertEqual(self.host.pending_holds()["holds"], [])

    def test_authority_changed_after_hold_prevents_effect(self):
        original = self.host.acquire_hold
        def changed(binding, snapshot):
            original(binding, snapshot)
            self.host.mutate(lambda state: state["claims"]["job-one"].update(source_revision="source-2"))
        with patch.object(self.host, "acquire_hold", side_effect=changed), patch.object(self, "work") as work:
            with self.assertRaises(AdapterError):
                self.adapter.run_once("worker", work)
            work.assert_not_called()
        self.assertFalse(self.queue.get("one")["effect_started"])
        self.assertEqual(len(self.host.pending_holds()["holds"]), 1)

    def test_lost_hold_acknowledgement_is_recovered_without_blind_execution(self):
        self.host.fail_acquire_after_commit = True
        with patch.object(self, "work") as work, self.assertRaises(RuntimeError):
            self.adapter.run_once("worker", work)
        work.assert_not_called()
        self.assertEqual(self.restart().run_once("worker", self.work)["status"], "blocked")
        hold = self.held()
        self.host.confirm_not_applied(hold)
        self.assertEqual(self.restart().recover()[0]["decision"], "not_applied")
        self.assertEqual(self.restart().run_once("worker", self.work)["status"], "resolved")
        self.assertEqual(len(self.host.state()["effects"]), 1)

    def test_local_begin_failure_preserves_canonical_hold(self):
        with patch.object(self.queue, "begin_effect", side_effect=QueueError("Synthetic local write failure")):
            with self.assertRaises(QueueError):
                self.adapter.run_once("worker", self.work)
        self.assertEqual(len(self.host.pending_holds()["holds"]), 1)
        self.assertEqual(self.host.state()["effects"], [])

    def test_process_death_after_applied_effect_recovers_without_second_effect(self):
        context = multiprocessing.get_context("spawn")
        child = context.Process(target=crash_worker, args=(str(self.queue.path), str(self.host.path), self.now))
        child.start()
        child.join(20)
        if child.is_alive():
            child.kill()
            child.join()
            self.fail("Synthetic crash worker hung")
        self.assertEqual(child.exitcode, 23)
        self.advance(1001)
        recovered = self.restart().recover()
        self.assertEqual(recovered[0]["decision"], "applied")
        self.assertEqual(self.queue.get("one")["state"], "succeeded")
        self.assertEqual(len(self.host.state()["effects"]), 1)
        self.assertEqual(self.restart().run_once("worker", self.work)["status"], "idle")

    def test_worker_exception_and_control_flow_interruptions_preserve_uncertainty(self):
        for exception in (RuntimeError("lost response"), SystemExit(4), KeyboardInterrupt()):
            with self.subTest(exception=type(exception).__name__):
                name = "case-" + type(exception).__name__
                if name != "case-RuntimeError":
                    self.add(name)
                def work(ticket, hold):
                    self.host.apply(hold)
                    raise exception
                with self.assertRaises(type(exception)):
                    self.adapter.run_once("worker", work)
                self.assertEqual(len(self.host.pending_holds()["holds"]), 1)
                self.assertEqual(self.restart().recover()[0]["decision"], "applied")
        self.assertEqual(len(self.host.state()["effects"]), 3)

    def test_failed_canonical_ack_after_local_success_replays_receipt_only(self):
        self.host.fail_resolve_before_commit = True
        with self.assertRaises(RuntimeError):
            self.adapter.run_once("worker", self.work)
        self.assertEqual(self.queue.get("one")["state"], "succeeded")
        self.assertEqual(self.restart().recover()[0]["decision"], "applied")
        self.assertEqual(len(self.host.state()["effects"]), 1)

    def test_lost_resolution_response_uses_matching_terminal_readback(self):
        self.host.fail_resolve_after_commit = True
        result = self.adapter.run_once("worker", self.work)
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(len(self.host.state()["resolutions"]), 1)
        self.assertEqual(self.restart().recover(), [])

    def test_operator_and_other_stop_survive_own_resolution(self):
        def work(ticket, hold):
            result = self.work(ticket, hold)
            self.host.mutate(lambda state: state.update(operator_stop=True, other_stops=["operator-other-job"]))
            return result
        self.assertEqual(self.adapter.run_once("worker", work)["status"], "resolved")
        state = self.host.state()
        self.assertTrue(state["operator_stop"])
        self.assertEqual(state["other_stops"], ["operator-other-job"])
        self.assertEqual(state["holds"], {})

    def test_late_callback_reconciles_after_both_deadlines(self):
        def work(ticket, hold):
            result = self.work(ticket, hold)
            self.advance(1100000)
            return result
        result = self.adapter.run_once("worker", work, lease_ms=1000)
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(self.queue.get("one")["state"], "succeeded")
        self.assertEqual(len(self.host.state()["effects"]), 1)

    def test_incomplete_enumeration_and_host_read_fail_closed(self):
        self.host.incomplete = True
        with patch.object(self, "work") as work, self.assertRaises(AdapterError):
            self.adapter.run_once("worker", work)
        work.assert_not_called()
        self.assertEqual(self.queue.get("one")["attempts"], 0)
        self.host.incomplete = False
        with patch.object(self.host, "read", side_effect=OSError("unavailable")):
            with self.assertRaises(OSError):
                self.adapter.run_once("worker", self.work)
        self.assertEqual(self.host.state()["effects"], [])

    def test_wrong_action_or_fence_observation_cannot_clear_hold(self):
        observe = self.host.observe
        def corrupt(hold, result):
            outcome = observe(hold, result)
            outcome["binding"]["fence"] += 1
            return outcome
        with patch.object(self.host, "observe", side_effect=corrupt), self.assertRaises(AdapterError):
            self.adapter.run_once("worker", self.work)
        self.assertEqual(self.queue.get("one")["state"], "uncertain")
        self.assertEqual(len(self.host.pending_holds()["holds"]), 1)

    def test_unquiescent_absence_never_retries(self):
        def work(ticket, hold):
            return {"synthetic_worker_still_active": True}
        first = self.adapter.run_once("worker", work, lease_ms=1000)
        self.assertEqual(first["status"], "blocked")
        self.advance(1001)
        with patch.object(self, "work") as next_worker:
            self.assertEqual(self.restart().run_once("worker", next_worker)["status"], "blocked")
            next_worker.assert_not_called()
        self.assertEqual(self.queue.get("one")["attempts"], 1)

    def test_not_applied_after_budget_exhaustion_resolves_hold_without_retry(self):
        self.host.fail_acquire_after_commit = True
        with self.assertRaises(RuntimeError):
            self.adapter.run_once("worker", self.work, lease_ms=1000)
        hold = self.held()
        self.host.confirm_not_applied(hold)
        self.advance(1100000)
        result = self.restart().recover()[0]
        self.assertEqual(result["decision"], "not_applied")
        self.assertEqual(self.queue.get("one")["state"], "dead")
        self.assertEqual(self.host.state()["holds"], {})

    def test_invalid_result_after_effect_does_not_report_success(self):
        def work(ticket, hold):
            self.work(ticket, hold)
            return {"invalid": object()}
        with self.assertRaises(AdapterError):
            self.adapter.run_once("worker", work)
        self.assertEqual(self.queue.get("one")["state"], "uncertain")
        self.assertEqual(self.restart().recover()[0]["decision"], "applied")

    def test_missing_canonical_hold_with_uncertainty_fails_closed(self):
        def work(ticket, hold):
            self.work(ticket, hold)
            raise RuntimeError("lost")
        with self.assertRaises(RuntimeError):
            self.adapter.run_once("worker", work)
        self.host.mutate(lambda state: state["holds"].clear())
        with self.assertRaisesRegex(AdapterError, "no canonical pending hold"):
            self.restart().recover()

    def test_reenqueue_success_does_not_repeat_effect(self):
        self.adapter.run_once("worker", self.work)
        ticket = self.queue.get("one")
        self.queue.enqueue("one", **{key: ticket[key] for key in (
            "job_key", "resource_key", "outer_revision", "outer_deadline_ms", "payload", "effectful", "max_attempts")})
        self.assertEqual(self.restart().run_once("worker", self.work)["status"], "idle")
        self.assertEqual(len(self.host.state()["effects"]), 1)


if __name__ == "__main__":
    unittest.main()

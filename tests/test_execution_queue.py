"""Independent lifecycle and real-process contention tests for the local queue."""
import multiprocessing
import os
from pathlib import Path
import queue as queue_module
import tempfile
import unittest

from execution_queue import Queue, QueueError


def claim_contender(database, clock_value, barrier, results, owner):
    """A separate process opens its own connection and competes for one claim."""
    try:
        worker = Queue(database, clock=lambda: tuple(clock_value))
        barrier.wait(timeout=20)
        results.put({"row": worker.claim(owner, lease_ms=1000)})
    except BaseException as error:
        results.put({"error": type(error).__name__ + ": " + str(error)})


def crash_inside_transaction(database, clock_value, signal):
    """Fault injection at the actual transaction boundary, without normal cleanup."""
    worker = Queue(database, clock=lambda: tuple(clock_value))
    with worker._transaction() as connection:
        connection.execute("UPDATE tickets SET error='uncommitted crash mutation' WHERE dispatch_id='one'")
        connection.execute("UPDATE queue_meta SET next_fence=next_fence+1000 WHERE id=1")
        signal.send("writes performed without commit")
        os._exit(23)


class ExecutionQueueTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "execution.sqlite3"
        self.now = [1000000, 10000, "epoch-1"]
        self.queue = Queue(self.path, clock=lambda: tuple(self.now))
        self.queue.init()

    def advance(self, milliseconds):
        self.now[0] += milliseconds
        self.now[1] += milliseconds

    def arguments(self, identifier, **changes):
        values = dict(job_key="job-" + identifier, resource_key="resource-" + identifier,
                      outer_revision="revision-1", outer_deadline_ms=2000000,
                      payload={"action": "inspect", "expected_ref": "abc123"},
                      effectful=False, max_attempts=3)
        values.update(changes)
        return values

    def enqueue(self, identifier="one", **changes):
        return self.queue.enqueue(identifier, **self.arguments(identifier, **changes))

    def claim(self, owner="worker-1", lease_ms=1000):
        row = self.queue.claim(owner, lease_ms=lease_ms)
        self.assertIsNotNone(row)
        return row

    def token(self, row):
        return row["dispatch_id"], row["owner"], row["fence"]

    def compete(self, workers=8):
        context = multiprocessing.get_context("spawn")
        barrier = context.Barrier(workers + 1)
        results = context.Queue()
        processes = [context.Process(target=claim_contender,
                     args=(str(self.path), tuple(self.now), barrier, results, "worker-" + str(i)))
                     for i in range(workers)]
        try:
            for process in processes:
                process.start()
            barrier.wait(timeout=20)
            responses = []
            for _ in processes:
                try:
                    responses.append(results.get(timeout=20))
                except queue_module.Empty:
                    self.fail("A contender failed to return a result")
            for process in processes:
                process.join(timeout=5)
                self.assertEqual(process.exitcode, 0, "Contender did not exit cleanly")
            self.assertFalse([item for item in responses if "error" in item], responses)
            return [item["row"] for item in responses if item["row"] is not None]
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
            results.close()
            results.join_thread()

    def test_identical_enqueue_is_idempotent_even_after_claim(self):
        arguments = self.arguments("one", payload={"b": 2, "a": 1})
        first = self.queue.enqueue("one", **arguments)
        again = self.queue.enqueue("one", **dict(arguments, payload={"a": 1, "b": 2}))
        self.assertEqual(first, again)
        claimed = self.claim()
        self.assertEqual(self.queue.enqueue("one", **arguments), claimed)
        self.assertEqual(self.queue.get("one")["attempts"], 1)

    def test_enqueue_rejects_conflicting_immutable_fields_and_duplicate_job(self):
        original = self.enqueue()
        changes = [{"payload": {"action": "write"}}, {"resource_key": "different"},
                   {"job_key": "different"}, {"outer_revision": "revision-2"},
                   {"outer_deadline_ms": 2000001}, {"effectful": True}, {"max_attempts": 2}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(QueueError):
                self.enqueue(**change)
        with self.assertRaises(QueueError):
            self.enqueue("different", job_key="job-one")
        self.assertEqual(self.queue.get("one"), original)

    def test_eight_processes_cannot_claim_the_same_dispatch(self):
        self.enqueue()
        claims = self.compete()
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["dispatch_id"], "one")
        self.assertEqual(self.queue.get("one")["attempts"], 1)
        self.assertEqual(self.queue.get("one")["owner"], claims[0]["owner"])

    def test_eight_processes_obey_six_active_claim_limit(self):
        for number in range(8):
            self.enqueue("job" + str(number))
        claims = self.compete()
        self.assertEqual(len(claims), 6)
        self.assertEqual(len({row["dispatch_id"] for row in claims}), 6)
        self.assertEqual(len({row["fence"] for row in claims}), 6)
        self.assertIsNone(self.queue.claim("ninth-worker", lease_ms=1000))
        states = [self.queue.get("job" + str(number))["state"] for number in range(8)]
        self.assertEqual(states.count("leased"), 6)
        self.assertEqual(states.count("ready"), 2)

    def test_eight_processes_obey_single_effectful_writer_limit(self):
        for number in range(8):
            self.enqueue("writer" + str(number), effectful=True)
        claims = self.compete()
        self.assertEqual(len(claims), 1)
        self.assertTrue(claims[0]["effectful"])
        self.assertIsNone(self.queue.claim("another-writer", lease_ms=1000))

    def test_shared_resource_is_exclusive_and_released_after_completion(self):
        self.enqueue("one", resource_key="shared")
        self.enqueue("two", resource_key="shared")
        first = self.claim()
        self.assertIsNone(self.queue.claim("worker-2", lease_ms=1000))
        self.queue.complete(*self.token(first), {"result": "inspected"})
        second = self.claim("worker-2")
        self.assertNotEqual(first["dispatch_id"], second["dispatch_id"])

    def test_expired_pre_effect_attempt_is_reclaimed_with_monotonic_fence(self):
        self.enqueue(effectful=True)
        first = self.claim()
        self.advance(1000)
        recovered = self.queue.reap()
        self.assertTrue(recovered)
        self.assertEqual(self.queue.get("one")["state"], "ready")
        second = self.claim("worker-2")
        self.assertGreater(second["fence"], first["fence"])
        self.assertEqual(second["attempts"], 2)
        self.assertFalse(second["effect_started"])
        for operation in [lambda: self.queue.heartbeat(*self.token(first)),
                          lambda: self.queue.begin_effect(*self.token(first)),
                          lambda: self.queue.complete(*self.token(first), {"result": "stale"}),
                          lambda: self.queue.fail(*self.token(first), "stale")]:
            with self.assertRaises(QueueError):
                operation()
        self.queue.complete(*self.token(second), {"result": "current"})
        self.assertEqual(self.queue.get("one")["state"], "succeeded")

    def test_retries_exhaust_attempt_cap_without_external_effect(self):
        self.enqueue(max_attempts=2)
        fences = []
        for number in range(2):
            row = self.claim("worker-" + str(number))
            fences.append(row["fence"])
            self.assertEqual(row["attempts"], number + 1)
            self.advance(1000)
            self.queue.reap()
        self.assertEqual(self.queue.get("one")["state"], "dead")
        self.assertGreater(fences[1], fences[0])
        self.assertIsNone(self.queue.claim("final-worker", lease_ms=1000))

    def test_owner_and_fence_are_both_required_for_live_mutations(self):
        self.enqueue(effectful=True)
        row = self.claim()
        for owner, fence in [("intruder", row["fence"]), (row["owner"], row["fence"] + 1)]:
            for operation in [lambda: self.queue.heartbeat("one", owner, fence),
                              lambda: self.queue.begin_effect("one", owner, fence),
                              lambda: self.queue.complete("one", owner, fence, {"result": "x"}),
                              lambda: self.queue.fail("one", owner, fence, "x")]:
                with self.assertRaises(QueueError):
                    operation()
        self.assertEqual(self.queue.get("one"), row)

    def test_heartbeat_renews_live_lease_but_cannot_revive_expiry(self):
        self.enqueue()
        row = self.claim()
        self.advance(500)
        renewed = self.queue.heartbeat(*self.token(row), lease_ms=1000)
        self.assertGreater(renewed["lease_until_ms"], row["lease_until_ms"])
        self.assertEqual(renewed["fence"], row["fence"])
        self.advance(1000)
        with self.assertRaises(QueueError):
            self.queue.heartbeat(*self.token(renewed), lease_ms=1000)

    def test_expired_outer_deadline_cannot_be_extended_by_heartbeat(self):
        self.enqueue(outer_deadline_ms=self.now[0] + 1000)
        row = self.claim(lease_ms=10000)
        self.advance(1000)
        with self.assertRaises(QueueError):
            self.queue.heartbeat(*self.token(row), lease_ms=10000)
        self.queue.reap()
        self.assertEqual(self.queue.get("one")["state"], "dead")
        self.assertIsNone(self.queue.claim("worker-2"))

    def test_expiry_after_effect_is_uncertain_and_never_automatically_retried(self):
        self.enqueue(effectful=True)
        first = self.claim()
        self.queue.begin_effect(*self.token(first))
        self.advance(1000)
        self.queue.reap()
        uncertain = self.queue.get("one")
        self.assertEqual(uncertain["state"], "uncertain")
        self.enqueue("other-writer", effectful=True)
        for _ in range(3):
            self.advance(1000)
            self.queue.reap()
            self.assertIsNone(self.queue.claim("replacement"))
        self.assertEqual(self.queue.get("one")["attempts"], 1)
        self.assertEqual(self.queue.get("one")["fence"], uncertain["fence"])

    def test_uncertain_effect_holds_resource_and_capacity_until_reconciled(self):
        self.enqueue("writer", effectful=True, resource_key="shared")
        writer = self.claim()
        self.queue.begin_effect(*self.token(writer))
        for number in range(5):
            self.enqueue("reader" + str(number))
            self.claim("reader-" + str(number), lease_ms=10000)
        self.advance(1000)
        self.queue.reap()
        self.enqueue("extra")
        self.assertIsNone(self.queue.claim("extra-worker"))
        self.queue.reconcile("writer", expected_fence=writer["fence"], decision="applied",
                             evidence={"receipt": "confirmed"}, quiescent=True)
        self.assertEqual(self.claim("extra-worker")["dispatch_id"], "extra")

    def test_uncertain_resource_blocks_a_read_only_job_on_the_same_target(self):
        self.enqueue("writer", effectful=True, resource_key="shared")
        writer = self.claim()
        self.queue.begin_effect(*self.token(writer))
        self.advance(1000)
        self.queue.reap()
        self.enqueue("reader", resource_key="shared")
        self.assertIsNone(self.queue.claim("reader-worker"))

    def test_failure_after_effect_is_uncertain_even_when_retry_requested(self):
        self.enqueue(effectful=True)
        row = self.claim()
        self.queue.begin_effect(*self.token(row))
        failed = self.queue.fail(*self.token(row), "response lost", retry=True)
        self.assertEqual(failed["state"], "uncertain")
        self.assertIsNone(self.queue.claim("worker-2"))

    def test_reconciliation_requires_uncertainty_evidence_and_explicit_quiescence(self):
        self.enqueue(effectful=True)
        with self.assertRaises(QueueError):
            self.queue.reconcile("one", expected_fence=1, decision="applied",
                                 evidence={"receipt": "x"}, quiescent=True)
        row = self.claim()
        self.queue.begin_effect(*self.token(row))
        self.queue.fail(*self.token(row), "ambiguous response")
        for changes in [{"evidence": {}}, {"evidence": []}, {"quiescent": False},
                        {"quiescent": 1}, {"decision": "retry"},
                        *[{"expected_fence": value} for value in [True, 0, -1, 1.0, "1", None]]]:
            args = dict(expected_fence=row["fence"], decision="applied",
                        evidence={"receipt": "confirmed"}, quiescent=True)
            args.update(changes)
            with self.subTest(change=changes), self.assertRaises(QueueError):
                self.queue.reconcile("one", **args)
        self.assertEqual(self.queue.get("one")["state"], "uncertain")

    def test_applied_reconciliation_is_terminal_and_preserves_audit_evidence(self):
        self.enqueue(effectful=True)
        row = self.claim()
        self.queue.begin_effect(*self.token(row))
        self.queue.fail(*self.token(row), "lost response")
        result = self.queue.reconcile("one", expected_fence=row["fence"], decision="applied",
                                      evidence={"receipt": "observed-123"}, quiescent=True)
        self.assertEqual(result["state"], "succeeded")
        self.assertIn("observed-123", str(self.queue.events("one")))
        self.assertIsNone(self.queue.claim("worker-2"))
        with self.assertRaises(QueueError):
            self.queue.reconcile("one", expected_fence=row["fence"], decision="not_applied",
                                 evidence={"receipt": "contradiction"}, quiescent=True)

    def test_not_applied_reconciliation_allows_only_a_fresh_fenced_attempt(self):
        self.enqueue(effectful=True)
        old = self.claim()
        self.queue.begin_effect(*self.token(old))
        self.queue.fail(*self.token(old), "ambiguous response")
        result = self.queue.reconcile("one", expected_fence=old["fence"], decision="not_applied",
                                      evidence={"inspection": "effect absent"}, quiescent=True)
        self.assertEqual(result["state"], "ready")
        new = self.claim("worker-2")
        self.assertGreater(new["fence"], old["fence"])
        self.assertFalse(new["effect_started"])
        with self.assertRaises(QueueError):
            self.queue.complete(*self.token(old), {"result": "stale"})

    def test_reconciliation_cannot_bypass_attempt_limit(self):
        self.enqueue(effectful=True, max_attempts=1)
        row = self.claim()
        self.queue.begin_effect(*self.token(row))
        self.queue.fail(*self.token(row), "ambiguous response")
        result = self.queue.reconcile("one", expected_fence=row["fence"], decision="not_applied",
                                      evidence={"inspection": "absent"}, quiescent=True)
        self.assertEqual(result["state"], "dead")
        self.assertIsNone(self.queue.claim("worker-2"))

    def test_outer_deadline_does_not_release_uncertainty_without_reconciliation(self):
        self.enqueue(effectful=True, outer_deadline_ms=self.now[0] + 1000)
        row = self.claim()
        self.queue.begin_effect(*self.token(row))
        self.advance(1000)
        self.queue.reap()
        self.assertEqual(self.queue.get("one")["state"], "uncertain")
        result = self.queue.reconcile("one", expected_fence=row["fence"], decision="not_applied",
                                      evidence={"inspection": "absent"}, quiescent=True)
        self.assertEqual(result["state"], "dead")

    def test_delayed_reconciliation_cannot_settle_a_later_uncertain_attempt(self):
        self.enqueue(effectful=True)
        first = self.claim("worker-1")
        self.queue.begin_effect(*self.token(first))
        self.queue.fail(*self.token(first), "first response unavailable")
        self.queue.reconcile("one", expected_fence=first["fence"], decision="not_applied",
                             evidence={"inspection": "first effect absent"}, quiescent=True)

        second = self.claim("worker-2")
        self.assertGreater(second["fence"], first["fence"])
        self.queue.begin_effect(*self.token(second))
        self.queue.fail(*self.token(second), "second response unavailable")
        uncertain = self.queue.get("one")
        events = self.queue.events("one")
        self.assertEqual(uncertain["attempts"], 2)
        self.assertEqual(uncertain["state"], "uncertain")

        for decision in ["applied", "not_applied"]:
            with self.subTest(stale_decision=decision):
                with self.assertRaises(QueueError):
                    self.queue.reconcile("one", expected_fence=first["fence"], decision=decision,
                                         evidence={"inspection": "delayed first-attempt evidence"}, quiescent=True)
                self.assertEqual(self.queue.get("one"), uncertain)
                self.assertEqual(self.queue.events("one"), events)

        result = self.queue.reconcile("one", expected_fence=second["fence"], decision="applied",
                                      evidence={"receipt": "second effect confirmed"}, quiescent=True)
        self.assertEqual(result["state"], "succeeded")
        self.assertEqual(result["fence"], second["fence"])

    def test_reconciliation_requires_an_explicit_attempt_fence(self):
        self.enqueue(effectful=True)
        row = self.claim()
        self.queue.begin_effect(*self.token(row))
        self.queue.fail(*self.token(row), "uncertain")
        with self.assertRaises(TypeError):
            self.queue.reconcile("one", decision="applied", evidence={"receipt": "unscoped"}, quiescent=True)
        self.assertEqual(self.queue.get("one")["state"], "uncertain")

    def test_retry_backoff_is_enforced_by_claim(self):
        self.enqueue()
        first = self.claim()
        self.queue.fail(*self.token(first), "temporary", retry=True, delay_ms=500)
        self.assertIsNone(self.queue.claim("too-early"))
        self.advance(499)
        self.assertIsNone(self.queue.claim("still-too-early"))
        self.advance(1)
        self.assertGreater(self.claim("ready-now")["fence"], first["fence"])

    def test_completion_is_terminal_and_receipt_is_durable(self):
        self.enqueue()
        row = self.claim()
        receipt = {"result": "passed", "evidence": ["local-fixture"]}
        self.queue.complete(*self.token(row), receipt)
        reopened = Queue(self.path, clock=lambda: tuple(self.now))
        self.assertEqual(reopened.get("one")["state"], "succeeded")
        self.assertEqual(reopened.get("one")["receipt"], receipt)
        with self.assertRaises(QueueError):
            reopened.complete(*self.token(row), receipt)
        self.assertIsNone(reopened.claim("again"))

    def test_global_fence_survives_reopen_and_increases_across_jobs(self):
        self.enqueue("one")
        first = self.claim()
        self.queue.complete(*self.token(first), {"result": "complete"})
        self.enqueue("two")
        reopened = Queue(self.path, clock=lambda: tuple(self.now))
        second = reopened.claim("worker-2", lease_ms=1000)
        self.assertGreater(second["fence"], first["fence"])

    def test_failure_without_retry_is_terminal_before_any_effect(self):
        self.enqueue()
        row = self.claim()
        result = self.queue.fail(*self.token(row), "permanent failure", retry=False)
        self.assertEqual(result["state"], "dead")
        self.assertIsNone(self.queue.claim("retry-worker"))

    def test_read_only_ticket_cannot_mark_an_external_effect(self):
        self.enqueue()
        row = self.claim()
        with self.assertRaises(QueueError):
            self.queue.begin_effect(*self.token(row))

    def test_backward_clock_is_rejected_without_mutating_ticket(self):
        self.enqueue()
        before = self.queue.get("one")
        for field in (0, 1):
            self.now[field] -= 1
            with self.subTest(clock_component=field), self.assertRaises(QueueError):
                self.queue.claim("worker-1")
            self.now[field] += 1
            self.assertEqual(self.queue.get("one"), before)

    def test_lease_expiry_uses_elapsed_clock_separately_from_outer_utc_deadline(self):
        self.enqueue()
        row = self.claim()
        self.now[0] += 500000
        self.assertEqual(self.queue.get("one")["state"], "leased")
        renewed = self.queue.heartbeat(*self.token(row), lease_ms=1000)
        self.now[1] += 1000
        with self.assertRaises(QueueError):
            self.queue.complete(*self.token(renewed), {"result": "late"})

    def test_new_clock_epoch_recovers_pre_effect_and_quarantines_post_effect(self):
        self.enqueue("reader")
        reader = self.claim("reader-worker")
        self.enqueue("writer", effectful=True)
        writer = self.claim("writer-worker")
        self.queue.begin_effect(*self.token(writer))
        self.now = [1000001, 0, "epoch-2"]
        recovered = self.queue.reap()
        self.assertEqual({row["dispatch_id"] for row in recovered}, {"reader", "writer"})
        self.assertEqual(self.queue.get("reader")["state"], "ready")
        self.assertEqual(self.queue.get("writer")["state"], "uncertain")
        with self.assertRaises(QueueError):
            self.queue.complete(*self.token(reader), {"result": "old epoch"})

    def test_process_crash_rolls_back_ticket_and_fence_mutations(self):
        before = self.enqueue()
        context = multiprocessing.get_context("spawn")
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(target=crash_inside_transaction,
                                  args=(str(self.path), tuple(self.now), sender))
        try:
            process.start()
            sender.close()
            self.assertTrue(receiver.poll(20), "Child did not reach the uncommitted write")
            self.assertEqual(receiver.recv(), "writes performed without commit")
            process.join(timeout=10)
            self.assertEqual(process.exitcode, 23)
            reopened = Queue(self.path, clock=lambda: tuple(self.now))
            self.assertEqual(reopened.get("one"), before)
            first = reopened.claim("after-crash", lease_ms=1000)
            self.assertEqual(first["fence"], 1)
            self.assertEqual(first["attempts"], 1)
        finally:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
            receiver.close()
            sender.close()

    def test_invalid_enqueue_fields_fail_without_a_ticket(self):
        changes = [{"job_key": ""}, {"resource_key": ""}, {"outer_revision": ""},
                   {"payload": []}, {"payload": {"value": float("nan")}},
                   {"effectful": 1}, {"max_attempts": 0}, {"max_attempts": True},
                   {"outer_deadline_ms": True}]
        for number, change in enumerate(changes):
            identifier = "invalid" + str(number)
            with self.subTest(change=change), self.assertRaises(QueueError):
                self.enqueue(identifier, **change)
        self.assertIsNone(self.queue.claim("nothing-to-claim"))

    def test_invalid_dispatch_identifiers_are_rejected(self):
        for identifier in ["", "含义", "x" * 10000, None, 12]:
            with self.subTest(identifier=identifier), self.assertRaises(QueueError):
                self.queue.enqueue(identifier, **self.arguments("valid"))


if __name__ == "__main__":
    unittest.main()

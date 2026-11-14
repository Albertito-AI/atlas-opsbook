#!/usr/bin/env python3
"""Exercise local worker contention and uncertain-effect recovery with synthetic jobs."""
import argparse
import multiprocessing
from pathlib import Path
import queue
import sys
import tempfile
import time
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from execution_queue import Queue, QueueError


class Clock:
    def __init__(self):
        self.utc = 100000
        self.elapsed = 1000

    def __call__(self):
        return self.utc, self.elapsed, "fixture-boot"

    def advance(self, milliseconds):
        self.utc += milliseconds
        self.elapsed += milliseconds


def contender(path, number, start, ready, results):
    """Each child opens its own connection; it never performs a job's payload."""
    try:
        local = Queue(Path(path))
        ready.put(number)
        if not start.wait(30):
            raise RuntimeError("Start barrier timed out")
        claim = local.claim("worker-%02d" % number, lease_ms=60000)
        results.put({"worker": number, "claim": claim})
    except Exception as error:
        results.put({"worker": number, "error": repr(error)})
        raise


def contention_trial(root, contenders):
    if type(contenders) is not int or not 1 <= contenders <= 50:
        raise ValueError("contenders must be between 1 and 50")
    path = root / "contention.sqlite"
    local = Queue(path)
    local.init()
    deadline = int(time.time() * 1000) + 180000
    for number in range(contenders):
        local.enqueue("dispatch-%02d" % number, job_key="job-%02d" % number,
                      resource_key="fixture-%02d" % number,
                      outer_revision="synthetic-reviewed-source-v1",
                      outer_deadline_ms=deadline,
                      payload={"operation": "read synthetic evidence", "case": number})
    context = multiprocessing.get_context("spawn")
    start, ready, results = context.Event(), context.Queue(), context.Queue()
    workers = [context.Process(target=contender,
                               args=(str(path), number, start, ready, results))
               for number in range(contenders)]
    limit = time.monotonic() + 55
    outcomes = []
    try:
        for worker in workers:
            worker.start()
        for _ in workers:
            ready.get(timeout=max(0.01, limit - time.monotonic()))
        start.set()
        for _ in workers:
            outcomes.append(results.get(timeout=max(0.01, limit - time.monotonic())))
        for worker in workers:
            worker.join(timeout=max(0.01, limit - time.monotonic()))
        if any(worker.is_alive() or worker.exitcode != 0 for worker in workers):
            raise AssertionError("A contender did not finish successfully")
        if any("error" in result for result in outcomes):
            raise AssertionError("A contender reported an error")
    except queue.Empty as error:
        raise AssertionError("Bounded worker test timed out") from error
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
        for worker in workers:
            if worker.pid is not None:
                worker.join(timeout=1)
        for channel in (ready, results):
            channel.close()
            channel.join_thread()
    winners = [result["claim"] for result in outcomes if result["claim"] is not None]
    if len(winners) != min(6, contenders):
        raise AssertionError("The six-worker capacity contract was violated")
    if len({row["dispatch_id"] for row in winners}) != len(winners):
        raise AssertionError("A ticket was claimed twice")
    if len({row["fence"] for row in winners}) != len(winners):
        raise AssertionError("Claim fences were reused")
    return {"processes": contenders, "claims": len(winners),
            "without_claim": contenders - len(winners), "duplicate_claims": 0,
            "external_actions": 0}


def recovery_trial(root):
    clock = Clock()
    local = Queue(root / "recovery.sqlite", clock=clock)
    local.init()
    local.enqueue("write-fixture", job_key="fixture-job", resource_key="fixture-resource",
                  outer_revision="synthetic-reviewed-source-v1",
                  outer_deadline_ms=clock.utc + 10000,
                  payload={"operation": "simulate a write boundary"}, effectful=True,
                  max_attempts=2)
    first = local.claim("first-worker", lease_ms=10)
    local.begin_effect(first["dispatch_id"], "first-worker", first["fence"])
    # No external call is made. Advance the clock to model a lost worker.
    clock.advance(11)
    local.reap()
    if local.get("write-fixture")["state"] != "uncertain" or local.claim("replacement") is not None:
        raise AssertionError("An uncertain external effect was automatically retried")
    local.reconcile("write-fixture", expected_fence=first["fence"],
                    decision="not_applied", quiescent=True,
                    evidence={"source": "owned local fixture", "observed_effects": 0,
                              "old_attempt": "stopped before any external call"})
    second = local.claim("replacement", lease_ms=100)
    if second is None or second["fence"] <= first["fence"]:
        raise AssertionError("Reclaim did not issue a newer fence")
    try:
        local.complete("write-fixture", "first-worker", first["fence"], {"outcome": "late"})
    except QueueError:
        fenced = True
    else:
        raise AssertionError("The obsolete worker completed a reclaimed ticket")
    local.begin_effect("write-fixture", "replacement", second["fence"])
    final = local.complete("write-fixture", "replacement", second["fence"],
                           {"outcome": "synthetic fixture completed", "external_actions": 0})
    if final["state"] != "succeeded":
        raise AssertionError("Reviewed recovery did not complete")
    return {"uncertain_not_retried": True, "obsolete_worker_fenced": fenced,
            "reconciled_state": final["state"], "attempts": final["attempts"],
            "external_actions": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contenders", type=int, default=12)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        result = {"schema": "atlas.execution.queue.trial.v1",
                  "contention": contention_trial(root, args.contenders),
                  "recovery": recovery_trial(root),
                  "scope": "Synthetic local processes sharing one database; no agents or external writes launched."}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

"""Trusted synchronous host adapter for bounded local execution tickets.

No daemon, network client, payload execution or production coordinator binding.
Copyright 2026 Albert Tan Sin Hon. Licensed under MIT. Python 3.9+.
"""
import copy
import hashlib
import json

from execution_queue import MAX_JSON_BYTES, QueueError


class AdapterError(QueueError):
    pass


def _json(value, label):
    if type(value) is not dict or not value:
        raise AdapterError(label + " must be a nonempty JSON object")
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False)
        if json.loads(raw) != value or len(raw.encode("utf-8")) > MAX_JSON_BYTES:
            raise ValueError()
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise AdapterError("Invalid or oversized " + label) from error
    return raw


def _text(value):
    return isinstance(value, str) and 0 < len(value) <= 200 and value.isprintable()


def digest(value):
    return hashlib.sha256(_json(value, "binding or outcome").encode("utf-8")).hexdigest()


class ExecutionAdapter:
    """Invoke trusted callbacks, with canonical authority outside the local queue.

    The injected host implements read, pending_holds, acquire_hold, observe and
    resolve. See docs/EXECUTION_ADAPTER.md for their authoritative contracts.
    Worker callbacks are supplied by the operator, never selected from payload.
    """

    def __init__(self, queue, host):
        self.queue = queue
        self.host = host

    def _binding(self, ticket):
        authority = ticket["payload"].get("authority")
        if (type(authority) is not dict or set(authority) != {"claim_token", "source_revision"}
                or not all(_text(value) for value in authority.values())):
            raise AdapterError("Ticket requires bounded claim_token and source_revision authority")
        owner = ticket["owner"]
        if owner is None:
            claims = [event for event in self.queue.events(ticket["dispatch_id"])
                      if event["event"] == "claimed" and event["fence"] == ticket["fence"]]
            if len(claims) != 1:
                raise AdapterError("Cannot recover the exact claimed worker")
            owner = claims[0]["details"]["owner"]
        return {"dispatch_id": ticket["dispatch_id"], "job_key": ticket["job_key"],
                "resource_key": ticket["resource_key"], "outer_revision": ticket["outer_revision"],
                "outer_deadline_ms": ticket["outer_deadline_ms"], "owner": owner,
                "fence": ticket["fence"], "effectful": ticket["effectful"],
                "claim_token": authority["claim_token"], "source_revision": authority["source_revision"],
                "payload_sha256": digest(ticket["payload"])}

    @staticmethod
    def _hold(hold, binding=None):
        if (type(hold) is not dict or set(hold) != {"action_id", "binding"}
                or not _text(hold["action_id"]) or type(hold["binding"]) is not dict):
            raise AdapterError("Invalid canonical action hold")
        _json(hold, "canonical action hold")
        if binding is not None and hold["binding"] != binding:
            raise AdapterError("Canonical hold does not bind the exact local attempt")
        return hold

    def _snapshot(self, ticket):
        snapshot = self.host.read(ticket)
        if (type(snapshot) is not dict or not _text(snapshot.get("version"))
                or type(snapshot.get("operator_stop")) is not bool
                or type(snapshot.get("other_stops")) is not list
                or not all(_text(item) for item in snapshot["other_stops"])
                or not {"claim", "hold", "resolution"} <= set(snapshot)):
            raise AdapterError("Incomplete canonical authority snapshot")
        return snapshot

    @staticmethod
    def _authority(snapshot, binding, own_hold=None):
        expected = {key: value for key, value in binding.items()
                    if key not in {"dispatch_id", "fence", "payload_sha256"}}
        if snapshot["claim"] != expected:
            raise AdapterError("Canonical assignment changed or is not active")
        if snapshot["operator_stop"] or snapshot["other_stops"]:
            raise AdapterError("Canonical admission is stopped")
        if snapshot["resolution"] is not None:
            raise AdapterError("Canonical action already has a terminal resolution")
        if snapshot["hold"] != own_hold:
            raise AdapterError("Canonical hold conflicts with this attempt")

    def _pending(self):
        pending = self.host.pending_holds()
        if (type(pending) is not dict or pending.get("complete") is not True
                or type(pending.get("holds")) is not list
                or type(pending.get("operator_stop")) is not bool
                or type(pending.get("other_stops")) is not list
                or not all(_text(item) for item in pending["other_stops"])):
            raise AdapterError("Canonical hold enumeration is incomplete")
        holds = [self._hold(hold) for hold in pending["holds"]]
        if len({hold["action_id"] for hold in holds}) != len(holds):
            raise AdapterError("Duplicate canonical action hold")
        if len({hold["binding"].get("dispatch_id") for hold in holds}) != len(holds):
            raise AdapterError("Duplicate canonical dispatch hold")
        return {"holds": holds, "operator_stop": pending["operator_stop"],
                "other_stops": pending["other_stops"]}

    @staticmethod
    def _outcome(value, hold):
        if (type(value) is not dict
                or set(value) != {"action_id", "binding", "decision", "quiescent", "evidence"}
                or value["action_id"] != hold["action_id"] or value["binding"] != hold["binding"]
                or value["decision"] not in {"applied", "not_applied", "unknown"}
                or type(value["quiescent"]) is not bool):
            raise AdapterError("Outcome is not bound to the exact canonical action")
        _json(value["evidence"], "observed outcome evidence")
        _json(value, "observed outcome")
        return value

    @staticmethod
    def _resolved(snapshot, hold, outcome):
        expected = {"action_id": hold["action_id"], "binding": hold["binding"],
                    "outcome": outcome, "outcome_sha256": digest(outcome)}
        return snapshot["resolution"] == expected and snapshot["hold"] is None

    def _resolve_host(self, ticket, hold, outcome):
        snapshot = self._snapshot(ticket)
        if self._resolved(snapshot, hold, outcome):
            return
        if snapshot["hold"] != hold:
            raise AdapterError("Missing exact hold and matching terminal resolution")
        try:
            # This is a distinct trusted coordinator operation, not local proof.
            # Its CAS records the outcome and removes only this action's hold.
            self.host.resolve(hold, outcome, snapshot)
        except Exception:
            # One readback handles a lost response without blindly retrying a write.
            if self._resolved(self._snapshot(ticket), hold, outcome):
                return
            raise
        if not self._resolved(self._snapshot(ticket), hold, outcome):
            raise AdapterError("Canonical action resolution was not read back")

    def _finish(self, hold, outcome, result=None):
        ticket = self.queue.get(hold["binding"]["dispatch_id"])
        self._hold(hold, self._binding(ticket))
        if outcome["decision"] == "unknown" or not outcome["quiescent"]:
            return {"status": "blocked", "action_id": hold["action_id"],
                    "reason": "Outcome or old-worker quiescence is unresolved"}
        receipt = {"adapter": "trusted-host-v1", "hold": hold, "outcome": outcome}
        if result is not None:
            receipt["worker_result"] = result
        _json(receipt, "adapter receipt")
        if ticket["state"] == "succeeded":
            previous = ticket["receipt"]
            if (type(previous) is not dict or previous.get("adapter") != "trusted-host-v1"
                    or previous.get("hold") != hold or outcome["decision"] != "applied"):
                raise AdapterError("Completed local attempt contradicts observed outcome")
            persisted = self._outcome(previous.get("outcome"), hold)
            if persisted["decision"] != "applied" or not persisted["quiescent"]:
                raise AdapterError("Completed receipt lacks its exact observed outcome")
            # Fresh observation confirms applicability; hand off original exact proof.
            outcome = persisted
        else:
            if ticket["state"] == "leased":
                owner, fence = ticket["owner"], ticket["fence"]
                try:
                    if outcome["decision"] == "applied" and ticket["effect_started"]:
                        self.queue.complete(ticket["dispatch_id"], owner, fence, receipt)
                    else:
                        self.queue.fail(ticket["dispatch_id"], owner, fence,
                                        "Trusted observation established not applied", retry=True)
                except QueueError:
                    # An expired lease revokes new work, not evidence reconciliation.
                    self.queue.reap()
                ticket = self.queue.get(ticket["dispatch_id"])
            if ticket["state"] == "uncertain":
                self.queue.reconcile(ticket["dispatch_id"], expected_fence=hold["binding"]["fence"],
                                     decision=outcome["decision"], evidence=receipt, quiescent=True)
            elif ticket["state"] in {"ready", "dead"}:
                if outcome["decision"] != "not_applied" or ticket["effect_started"]:
                    raise AdapterError("Local history cannot support the observed action")
            elif ticket["state"] != "succeeded":
                raise AdapterError("Local attempt could not be reconciled")
        ticket = self.queue.get(ticket["dispatch_id"])
        self._resolve_host(ticket, hold, outcome)
        return {"status": "resolved", "action_id": hold["action_id"],
                "decision": outcome["decision"], "ticket": ticket}

    def recover(self):
        """Observe and reconcile pending holds; never invoke a worker callback."""
        self.queue.reap()
        holds = self._pending()["holds"]
        by_dispatch = {hold["binding"].get("dispatch_id"): hold for hold in holds}
        for ticket in self.queue.uncertain():
            if ticket["dispatch_id"] not in by_dispatch:
                raise AdapterError("Local uncertain effect has no canonical pending hold")
        results = []
        for hold in holds:
            try:
                ticket = self.queue.get(hold["binding"].get("dispatch_id"))
            except QueueError as error:
                if str(error) != "Unknown dispatch ID":
                    raise
                results.append({"status": "blocked", "action_id": hold["action_id"],
                                "reason": "Hold belongs to another local queue or missing history"})
                continue
            self._hold(hold, self._binding(ticket))
            result = ticket["receipt"].get("worker_result") if ticket["state"] == "succeeded" else None
            outcome = self._outcome(self.host.observe(hold, result), hold)
            results.append(self._finish(hold, outcome, result))
        return results

    def run_once(self, owner, worker, *, lease_ms=30_000):
        """Execute at most one bounded, synchronous trusted worker callback."""
        if not callable(worker):
            raise AdapterError("A trusted worker callback is required")
        recovery = self.recover()
        pending = self._pending()
        if pending["holds"] or pending["operator_stop"] or pending["other_stops"]:
            return {"status": "blocked", "recovery": recovery}
        ticket = self.queue.claim(owner, lease_ms=lease_ms)
        if ticket is None:
            return {"status": "idle", "recovery": recovery}
        started = False
        hold = None
        try:
            binding = self._binding(ticket)
            snapshot = self._snapshot(ticket)
            self._authority(snapshot, binding)
            if ticket["effectful"]:
                # Host atomically checks snapshot CAS version AND every assignment
                # predicate before creating a unique, durable action identity.
                self.host.acquire_hold(binding, snapshot)
                snapshot = self._snapshot(ticket)
                hold = self._hold(snapshot["hold"], binding)
                self._authority(snapshot, binding, hold)
                self.queue.begin_effect(ticket["dispatch_id"], owner, ticket["fence"])
                started = True
            else:
                # Recheck the lease immediately before a read-only callback too.
                self.queue.heartbeat(ticket["dispatch_id"], owner, ticket["fence"], lease_ms=lease_ms)
            result = worker(copy.deepcopy(ticket), copy.deepcopy(hold))
            _json(result, "worker result")
            if hold is None:
                receipt = {"adapter": "trusted-host-v1", "binding": binding,
                           "worker_result": result, "effectful": False}
                completed = self.queue.complete(ticket["dispatch_id"], owner, ticket["fence"], receipt)
                return {"status": "completed_read_only", "ticket": completed}
            outcome = self._outcome(self.host.observe(hold, result), hold)
            return self._finish(hold, outcome, result)
        except BaseException:
            # Preserve interruption as failure, never success. A crash that cannot
            # run cleanup is covered by the already durable canonical hold.
            try:
                current = self.queue.get(ticket["dispatch_id"])
                if current["state"] == "leased" and current["fence"] == ticket["fence"]:
                    self.queue.fail(ticket["dispatch_id"], owner, ticket["fence"],
                                    "Trusted adapter interrupted after effect start" if started
                                    else "Trusted adapter interrupted before effect start", retry=not started)
            except Exception:
                pass  # Original error survives; no claim that persistence succeeded.
            raise

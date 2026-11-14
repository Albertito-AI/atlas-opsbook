"""Disk-backed synthetic coordinator contract. Test fixture, not a deployment."""
import copy
import fcntl
import json
import os
from pathlib import Path
import tempfile
import uuid

from execution_adapter import AdapterError, digest


class DurableHost:
    def __init__(self, path):
        self.path = Path(path)
        self.fail_acquire_after_commit = False
        self.fail_resolve_before_commit = False
        self.fail_resolve_after_commit = False
        self.incomplete = False
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"version": 0, "claims": {}, "holds": {},
                "resolutions": {}, "observations": {}, "dispatchers": {},
                "operator_stop": False, "other_stops": [], "effects": []}))

    def state(self):
        return json.loads(self.path.read_text())

    def mutate(self, operation, expected=None):
        with self.path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = self.state()
            if expected is not None and str(state["version"]) != expected:
                raise AdapterError("Synthetic canonical CAS conflict")
            result = operation(state)
            state["version"] += 1
            with tempfile.NamedTemporaryFile(mode="w", dir=self.path.parent, delete=False) as handle:
                json.dump(state, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
                temporary = handle.name
            os.replace(temporary, self.path)
            return result

    @staticmethod
    def claim_from_binding(binding):
        return {key: value for key, value in binding.items()
                if key not in {"dispatch_id", "fence", "payload_sha256"}}

    def register(self, ticket, owner="worker"):
        authority = ticket["payload"]["authority"]
        claim = {key: ticket[key] for key in ("job_key", "resource_key", "outer_revision", "outer_deadline_ms", "effectful")}
        claim.update(authority, owner=owner)
        self.mutate(lambda state: state["claims"].update({ticket["job_key"]: claim}))

    def read(self, ticket):
        state = self.state()
        own = [hold for hold in state["holds"].values()
               if hold["binding"]["dispatch_id"] == ticket["dispatch_id"]]
        resolutions = [item for item in state["resolutions"].values()
                       if item["binding"]["dispatch_id"] == ticket["dispatch_id"]
                       and item["binding"]["fence"] == ticket["fence"]]
        return {"version": str(state["version"]), "claim": state["claims"].get(ticket["job_key"]),
                "operator_stop": state["operator_stop"],
                "other_stops": state["other_stops"] + [key for key, hold in state["holds"].items()
                    if hold["binding"]["dispatch_id"] != ticket["dispatch_id"]],
                "hold": own[0] if len(own) == 1 else None,
                "resolution": resolutions[0] if len(resolutions) == 1 else None}

    def pending_holds(self):
        state = self.state()
        return {"complete": not self.incomplete, "holds": list(state["holds"].values()),
                "operator_stop": state["operator_stop"], "other_stops": state["other_stops"]}

    def acquire_hold(self, binding, snapshot):
        def commit(state):
            if (state["claims"].get(binding["job_key"]) != self.claim_from_binding(binding)
                    or state["operator_stop"] or state["other_stops"] or state["holds"]):
                raise AdapterError("Synthetic canonical authority changed or stopped")
            action_id = "action-" + uuid.uuid4().hex
            state["holds"][action_id] = {"action_id": action_id, "binding": copy.deepcopy(binding)}
            state["dispatchers"][action_id] = os.getpid()
        self.mutate(commit, snapshot["version"])
        if self.fail_acquire_after_commit:
            raise RuntimeError("Synthetic lost hold acknowledgement")

    @staticmethod
    def alive(pid):
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False

    def apply(self, hold, *, quiescent=True):
        def commit(state):
            if state["holds"].get(hold["action_id"]) != hold:
                raise AdapterError("Synthetic effect lacks current action hold")
            if hold["action_id"] not in state["effects"]:
                state["effects"].append(hold["action_id"])
            state["observations"][hold["action_id"]] = {"decision": "applied", "quiescent": quiescent}
        self.mutate(commit)
        return {"synthetic_effect": hold["action_id"], "external_actions": 0}

    def confirm_not_applied(self, hold):
        self.mutate(lambda state: state["observations"].update(
            {hold["action_id"]: {"decision": "not_applied", "quiescent": True}}))

    def observe(self, hold, result):
        state = self.state()
        observation = state["observations"].get(hold["action_id"],
            {"decision": "not_applied", "quiescent": False})
        quiescent = observation["quiescent"] or not self.alive(state["dispatchers"][hold["action_id"]])
        return {"action_id": hold["action_id"], "binding": copy.deepcopy(hold["binding"]),
                "decision": observation["decision"], "quiescent": quiescent,
                "evidence": {"synthetic_disk_observation": observation["decision"],
                    "effect_recorded": hold["action_id"] in state["effects"],
                    "old_worker_quiescent": quiescent, "real_external_actions": 0}}

    def resolve(self, hold, outcome, snapshot):
        if self.fail_resolve_before_commit:
            raise RuntimeError("Synthetic canonical write unavailable")
        if outcome != self.observe(hold, None) or not outcome["quiescent"] or outcome["decision"] == "unknown":
            raise AdapterError("Synthetic trusted observer does not establish this resolution")
        record = {"action_id": hold["action_id"], "binding": hold["binding"],
                  "outcome": outcome, "outcome_sha256": digest(outcome)}
        def commit(state):
            previous = state["resolutions"].get(hold["action_id"])
            if previous is not None:
                if previous != record:
                    raise AdapterError("Synthetic terminal action conflicts")
                return
            if state["holds"].get(hold["action_id"]) != hold:
                raise AdapterError("Synthetic action hold changed")
            state["resolutions"][hold["action_id"]] = record
            del state["holds"][hold["action_id"]]
            if (outcome["decision"] == "applied"
                    and state["claims"].get(hold["binding"]["job_key"]) == self.claim_from_binding(hold["binding"])):
                del state["claims"][hold["binding"]["job_key"]]
        self.mutate(commit, snapshot["version"])
        if self.fail_resolve_after_commit:
            raise RuntimeError("Synthetic lost resolution acknowledgement")

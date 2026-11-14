# Local execution tickets and uncertain effects

`execution_queue.py` is an original Python standard-library exercise for coordinating a small number of processes on one host. It stores local execution tickets, leases and recovery evidence. It does not execute task payloads, start agents, contact GitHub or make network requests.

**The existing Atlas coordinator remains the authority for assignments, permission, review and global task state.** This optional component is neither its replacement nor a mirror of its distributed ledger. Before enqueueing a real ticket, the caller must persist its outer claim, supply stable job/resource identities and bind the ticket to that claim's revision and deadline. Local success produces evidence for the coordinator to reconcile; it does not complete or approve a global task.

Local uncertainty alone cannot stop another host or the canonical coordinator from dispatching again. Before any global redispatch of an uncertain operation, the integration must persist and read back an explicit canonical dispatch block. If no per-job hold exists, use the coordinator's existing global dispatch stop, currently `kill_switch` in Atlas's controller. An unknown-outcome receipt alone does not supply this block. Clear it only after the exact attempt has been reconciled under the coordinator's own policy. If propagating the resolution fails, retain the canonical block; local success cannot authorise resumption. This module does not install that integration or mutate the switch.

The fixed policy admits at most six occupied tickets, including uncertain effects, and at most one occupied effectful ticket. It does not create 50 running agents or increase an existing engineering quota. These limits concern recorded ownership, not the physical number of processes that might still be alive after lease expiry.

## API and a synthetic ticket

```python
from pathlib import Path
from execution_queue import Queue

queue = Queue(Path("local-execution.db"))
queue.init()
queue.enqueue(
    "synthetic-dispatch-1",
    job_key="synthetic-job-1",
    resource_key="synthetic-repository",
    outer_revision="synthetic-reviewed-assignment-v1",
    outer_deadline_ms=YOUR_PERSISTED_OUTER_DEADLINE_MS,
    payload={"check": "synthetic-local-contract"},
    effectful=False,
    max_attempts=3,
)
lease = queue.claim("synthetic-worker-1", lease_ms=30_000)
if lease is not None:
    # This example exercises bookkeeping only; no task is executed.
    queue.complete(lease["dispatch_id"], lease["owner"], lease["fence"],
                   {"result": "synthetic ticket lifecycle only", "external_actions": 0})
```

`outer_deadline_ms` is an absolute UTC millisecond deadline from the persisted outer assignment. `outer_revision` is a nonempty printable string of at most 200 characters. The queue cannot establish whether that assignment is authentic, fresh or cancelled. The caller must check current coordinator authority and prerequisites immediately before consequential work. A queue lease alone grants no permission.

| Method | Result and purpose |
| --- | --- |
| `Queue(path, clock=None)` | Configure a local database and an optional trusted clock. |
| `init()` | Initialise or validate schema version 1 and the fixed six/one policy. |
| `enqueue(dispatch_id, *, job_key, resource_key, outer_revision, outer_deadline_ms, payload, effectful=False, max_attempts=3)` | Store an immutable ticket; return an existing identical ticket on exact replay. |
| `claim(owner, *, lease_ms=30000)` | Atomically acquire one eligible ticket or return `None`. |
| `heartbeat(dispatch_id, owner, fence, *, lease_ms=30000)` | Renew a still-valid lease, capped by the outer deadline. |
| `begin_effect(dispatch_id, owner, fence)` | Durably record entry into a potentially effectful operation before invoking it. |
| `complete(dispatch_id, owner, fence, receipt)` | Store a nonempty result receipt and release ownership. |
| `fail(dispatch_id, owner, fence, error, *, retry=True, delay_ms=0)` | Record failure; retry only when no effect began and the budget permits. |
| `reap()` | Recover expired leases and return the changed ticket records. |
| `reconcile(dispatch_id, *, expected_fence, decision, evidence, quiescent)` | Resolve the exact uncertain attempt using external evidence and old-attempt quiescence. |
| `get(dispatch_id)` / `events(dispatch_id)` | Inspect the stored ticket or ordered transition evidence without reaping. |

Validation and coordination failures raise `QueueError`, a subclass of `ValueError`. An empty eligible queue returns `None`; lock contention is an error after a bounded five-second wait, not an empty-queue result. This component has no daemon or automatic retry loop.

Identifiers contain 1 to 200 ASCII letters, digits, underscores, dots, colons, slashes or hyphens, beginning with a letter or digit. Payload, receipt and evidence values must be JSON objects of at most 64 KiB. Receipts and reconciliation evidence must be nonempty. Attempts are limited to 1 through 10, leases to 1 through 60,000 ms and explicit retry delays to one hour. Admission is limited to 10,000 retained tickets. Tickets and events are not automatically pruned; heartbeat history can grow and requires a separate retention policy before operational adoption.

## Identity, ownership and fencing

An identical dispatch ID can be safely re-enqueued without resetting attempts or terminal state. Changing any immutable field is a conflict. Reusing a logical `job_key` under a new dispatch ID is also a conflict. This protects local ticket identity; it does not make an external service idempotent.

A `resource_key` admits only one leased or uncertain ticket. An uncertain effect therefore blocks another dispatch for that resource and continues occupying the global effectful slot. These keys must represent the actual shared work and resource consistently. The queue cannot recognise that two misleading names refer to the same repository or external effect.

Claims use a persisted, globally increasing integer fence. Every worker heartbeat, effect-start, completion and failure requires the exact dispatch, owner and fence, plus an unexpired local lease and outer deadline. A late owner cannot complete or renew a newer claim. Fences increase across committed claims in this database history; restoring an older database backup does not preserve that property and requires outer-coordinator reconciliation before reuse.

Fencing here controls database transitions. It cannot cancel an already-running external request or compel another service to reject an old fence. An external adapter needs its own appropriate idempotency or fencing mechanism where available.

## State transitions

| Current state and event | Next state |
| --- | --- |
| `ready`, eligible claim | `leased`, increment attempt and fence. |
| `leased`, completion with a valid token | `succeeded`, retain receipt. |
| `leased`, failure or expiry before effect-start | `ready` within attempts/deadline, otherwise `dead`. |
| `leased`, failure or expiry after effect-start | `uncertain`, regardless of retry preference or remaining attempts. |
| `uncertain`, evidence confirms applied and old attempt is quiescent | `succeeded`. |
| `uncertain`, evidence confirms not applied and old attempt is quiescent | `ready` within attempts/deadline, otherwise `dead`. |

`begin_effect` is permitted only once per effectful attempt. The caller must commit it before crossing the external-effect boundary. A crash immediately afterward may create uncertainty even if no remote call happened; conservative reconciliation is intentional. An effectful ticket can complete before effect-start when the authorised work determines that no external change is needed, but its receipt must make that no-op outcome clear.

After an effect has started, exception, timeout or lost ownership cannot establish whether it happened. The queue never automatically re-enqueues that uncertain attempt. A reconciler must supply that attempt's `expected_fence`, `decision="applied"` or `"not_applied"`, a nonempty evidence object, and `quiescent=True`. The fence is compared atomically with the currently uncertain row, so delayed evidence from an older attempt cannot resolve a newer attempt. Quiescence means the old attempt cannot still issue or finish an unaccounted effect. The flag records a trusted caller's assertion; it is not independently verified by SQLite. Reconciliation belongs to the authoritative coordinator or a designated operator, not an unreviewed agent tool.

If the old attempt may still finish, observing that an effect is absent now is insufficient grounds for retry. Keep the ticket uncertain until its outcome and quiescence can be established. This design does not claim exactly-once external effects.

## Clocks and persistence

The default clock uses Linux boot identity, UTC milliseconds and `time.monotonic_ns()` milliseconds. Claims and renewals use elapsed time for lease duration and UTC for the outer assignment deadline; both must remain valid. The elapsed deadline is capped using the remaining outer UTC interval. Shortening a heartbeat duration is permitted; renewing an expired lease is not.

Every mutating operation samples its clock after acquiring the transaction lock. UTC rollback, or elapsed-time rollback within the same boot, rejects the transaction instead of extending authority. A new boot invalidates old leases: started effects become uncertain, while pre-effect work follows bounded recovery. Pending retry delays preserve their previously unelapsed interval, which may delay retry after reboot. Reads expose stored state; call `reap()` to materialise expiry without claiming new work.

Tests can inject a callable returning `(utc_ms, elapsed_ms, epoch)`. A non-Linux integration must supply a trusted same-host clock with stable elapsed time and reliable boot/session identity. This is not a client-controlled scheduling timestamp in a distributed system.

Each operation opens its own SQLite connection, uses a short `BEGIN IMMEDIATE` transaction and commits state plus its event together. No external work runs inside that transaction. The `queue_meta`, `tickets` and `events` tables are separate from Opsbook's existing manual database format. Initialisation refuses unrelated or incomplete databases and operations reject an unsupported schema or policy.

SQLite documents that [an immediate transaction can encounter an existing writer](https://www.sqlite.org/lang_transaction.html). Keep the database on a local filesystem shared by processes on the same host, not a mounted network filesystem; see [SQLite's guidance on network use](https://www.sqlite.org/useovernet.html). The implementation uses SQLite's ordinary rollback journal and full synchronous setting. Process-crash tests exercise transaction rollback, not every possible storage-device or power-loss failure.

Storage and callers are trusted processes under the same local user. Path checks do not provide a hostile-writer filesystem boundary or eliminate symlink races. Leases and fences do not sandbox workers, revoke operating-system access or prevent a caller from bypassing this API. Appropriate coordinator policy, credentials, process containment and external-service controls remain separate requirements.

## Validation and attribution

```sh
python -m unittest discover -s tests -p test_execution_queue.py -v
python examples/execution_queue_trial.py --contenders 50
```

Independent tests exercise actual competing processes, immutable enqueue identity, resource exclusion, six/one limits, stale owners, deadline bounds, effect uncertainty, reconciliation, clock rollback, reboot recovery and interrupted transactions. A synthetic contention test establishes the tested contract on that host; it is not a production throughput benchmark or a deployment of six or 50 agents.

Public conceptual inspirations include PatchLoop's [task lifecycle](https://github.com/ZhuLinsen/patchloop/blob/03eb09b2248b60be2205dee6db33e2a80f20aae6/autocode/agent/task_queue.py), MiniAgent's [uncertain-effect handling](https://github.com/ZhuLinsen/MiniAgent/blob/25d87daff9a789713cb4aa56b4b689a6ebcb48cb/miniagent/agent.py), and REA's [exact proof bindings](https://github.com/morluto/rea/blob/69386962569de27a1201847bf50a8c9ea592c5bd/src/application/ReconstructionObligationAuthority.ts). This implementation is original; it copies neither those sources nor Atlas's private controller. It is an optional local execution primitive awaiting explicit integration, with the existing coordinator retaining global authority.

Copyright 2026 Albert Tan Sin Hon. Licensed under MIT.

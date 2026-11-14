# Trusted-host execution adapter

`execution_adapter.py` connects the local execution queue to a synchronous
worker callback supplied by a trusted host. It invokes that callback, retains
its result and, for effectful work, calls the host's independent observation
and canonical reconciliation operations. It does not interpret payloads as
code, start a daemon, contact services or install a production Atlas binding.
The tests use synthetic files and a disk-backed host fixture.

The existing coordinator remains the authority for assignments and global
results. A callback result alone proves neither an external outcome nor old
worker quiescence. A normal effectful operation finishes autonomously when the
trusted host establishes both, records the exact result and removes only its
owned action hold. No routine user confirmation is added.

## API and immutable assignment

```python
from execution_adapter import ExecutionAdapter

# The host and worker below are trusted integrations supplied by the operator.
adapter = ExecutionAdapter(queue, host)
result = adapter.run_once("existing-worker-execution-id", trusted_worker)
# A fresh instance can recover without invoking a worker:
recovery = ExecutionAdapter(queue, host).recover()
```

`run_once(owner, worker, lease_ms=30000)` invokes at most one eligible callback.
`worker(ticket, hold)` receives copies of its ticket and canonical action hold
(or `None` for read-only work). It returns a nonempty bounded JSON object and
must actually wait for its declared work to finish. An asynchronous launch
acknowledgement is not a finished worker.

Read-only tickets return `completed_read_only` with a persisted local receipt
for the existing coordinator handoff. This does not claim global completion.
The adapter does not add a canonical outbox for read-only results.

Each immutable ticket payload must contain `authority` with exactly
`claim_token` and `source_revision`, both nonempty printable strings of at most
200 characters. Other payload fields remain inert host-defined task data.
The queue's `outer_revision` is the stable assignment revision, distinct from
the mutable canonical CAS version. The action binding also includes dispatch,
job, resource, worker, local fence, deadline, effect classification and payload
SHA-256. Released ownership is recovered from the exact persisted claim event.

The adapter retains the queue's admission/input/lease bounds. It does **not**
enforce a callback timeout or terminate an operating-system process or remote
request. Expiry prevents fresh local authority; it cannot retract an effect
already started. The trusted host supplies any runtime limits, destination
fencing, cancellation and actual quiescence checks.

## Required trusted host methods

Methods are injected directly; none is selected by a name in the payload.
Returning expected dictionaries without performing the underlying checks does
not satisfy this contract.

| Method | Authoritative operation |
| --- | --- |
| `pending_holds()` | Completely read durable pending action holds and global stop reasons. Return `complete: true`, `holds: [...]`, `operator_stop: bool`, `other_stops: [reason identifiers]`. Missing pages, access failures and incomplete reads fail closed. |
| `read(ticket)` | Freshly read the assignment, current source, exact owned hold, terminal resolution and separate stop reasons using the snapshot below. |
| `acquire_hold(binding, snapshot)` | Atomic CAS against the snapshot version **and** exact assignment/token/owner/source/deadline/admission predicates. Create a unique durable action only while authority is unexpired; never overwrite another hold or operator stop. |
| `observe(hold, worker_result)` | Independently establish this action's exact external outcome and old-dispatcher/worker quiescence. Treat worker output as a clue, not authority. |
| `resolve(hold, outcome, snapshot)` | Distinct trusted coordinator operation: verify outcome and quiescence, CAS-record the terminal result and remove only the exact owned hold. Preserve operator and other-job stops, and retain terminal records for idempotent replay. |

A snapshot contains `version` (a printable CAS-version string), `claim`,
`operator_stop` (boolean), `other_stops` (reason identifiers), `hold` and
`resolution`. `claim` equals the action binding with `dispatch_id`, `fence`
and `payload_sha256` omitted, or is `null` when no longer active. Expired,
revoked and completed assignments must be inactive for new execution.

An action hold has exactly `action_id` and `binding`. The host durably issues
the globally unique action ID, binds it to this operation and retains its
history independently of the local database. Use that ID as a destination
idempotency key where supported and enforced. This is not a universal
exactly-once guarantee. Retired claims cannot become active merely because
local storage was restored; simultaneous rollback of every authority store is
outside this component's guarantees.

An observation has exactly `action_id`, `binding`, `decision`, `quiescent` and
a nonempty `evidence` object. `decision` is `applied`, `not_applied` or `unknown`.
`applied` means the authorised operation's required outcome was established,
including an explicitly evidenced no-op when no change was needed. The exact
old dispatcher and worker must be quiescent before resolving either outcome.
A worker currently absent, an expired lease or a missing output does not prove
that a paused dispatcher or in-flight request cannot still act.

The retained terminal record has `action_id`, `binding`, the exact `outcome`
and `outcome_sha256` using the adapter's canonical JSON encoding. A missing
hold without that matching terminal record is unknown. Recovery, observation
and resolution remain available while admission is stopped and after expiry.

## Execution and recovery order

1. Reap local leases and reconcile discoverable pending canonical holds.
2. Read complete admission/stop state before claiming; stable stopped polling
   must not consume the attempt budget.
3. Claim a ticket and check fresh exact canonical assignment evidence.
4. For effectful work, CAS-create the canonical hold and read it back. Recheck
   assignment and distinguish the owned hold from unrelated stops.
5. Durably mark local effect-start, invoke the worker, and obtain independently
   observed outcome and quiescence evidence.
6. Complete or reconcile the exact local attempt, then autonomously resolve
   the canonical action and read back its terminal record.

A host action hold must reserve the operation across competing dispatchers.
Revocation after the last read cannot instantly cancel an instruction already
in progress. It prevents new admission and must not grant a competing effect
until the reserved attempt is observed and quiescent. This is a host/destination
requirement, not atomicity supplied by Python callbacks. Quiescence includes a
still-alive dispatcher paused **before** worker invocation.

This first adapter conservatively blocks all new invocations while canonical
actions remain unresolved. Unrelated read-only work does not inherently require
that policy. Recovery can still resolve owned actions while other holds or an
operator stop remain, preserving those other reasons.

Recovery enumerates canonical holds, so it finds a crash after hold creation
but before local effect-start, and after local completion but before canonical
acknowledgement. It also checks the queue's read-only `uncertain()` view. Missing
canonical protection for a local uncertain effect fails closed. A hold belonging
to another queue remains blocked for its owner; incomplete history is not repair
authority.

A late successful callback cannot renew expired permission. The adapter can
reap and reconcile that exact fence from observed applied/quiescent evidence.
Confirmed not-applied work retains the existing attempt/deadline budget.
Unknown outcomes, failed reads, malformed output, CAS conflicts and interrupted
callbacks never manufacture success or blindly retry an effect.

When local completion precedes a failed canonical acknowledgement, recovery
finds the hold and retained receipt, independently checks applicability and
hands off the original exact outcome without invoking the worker again. A lost
resolution response receives one readback, not an unbounded mutation retry.

Atlas's private maintenance controller currently refuses ordinary `record()`
while `kill_switch` is true. A production host therefore needs a reviewed
reconciliation operation that records the exact result and resolves only its
owned hold in the appropriate atomic order. Blindly setting `kill_switch=false`
before `record()` is insufficient. This public module installs no such private
mutation and does not bypass the existing controller.

## Performed local tests and limits

```sh
python -m unittest discover -s tests -p test_execution_adapter.py -v
python -m unittest discover -s tests -v
```

`tests/adapter_host_fixture.py` is a synthetic disk-backed host with same-host
file locking, CAS writes and retained terminal results. It is test infrastructure,
not a production access-control or distributed service. The tests actually kill
a child after a retained synthetic effect, reopen both stores, establish process
termination and reconcile without a second effect. Other cases cover autonomous
success, lost acknowledgements, changed authority, pre-effect orphan holds,
expired completion, control-flow interruption, malformed output, incomplete
enumeration, preserved stops and idempotent re-entry.

The performed process-crash/reopen check does not establish power-loss durability
or filesystem crash consistency; the fixture does not fsync its parent directory.

These observations do not establish live agent deployment, learning, external
exactly-once delivery, hostile-process isolation, distributed consensus or a
productivity multiplier. All participating hosts must honour the stated contract.

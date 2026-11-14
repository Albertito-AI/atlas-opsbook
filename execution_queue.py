"""Bounded same-host execution tickets; never executes tasks or contacts services.

Copyright 2026 Albert Tan Sin Hon. Licensed under MIT. Python 3.9+.
"""

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time

MAX_ACTIVE = 6
MAX_EFFECTS = 1
MAX_LEASE_MS = 60_000
MAX_DELAY_MS = 3_600_000
MAX_JSON_BYTES = 65_536
MAX_TICKETS = 10_000


class QueueError(ValueError):
    pass


def _identifier(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}", value):
        raise QueueError("Invalid " + label)
    return value


def _integer(value, label, minimum=0, maximum=2 ** 62):
    if type(value) is not int or not minimum <= value <= maximum:
        raise QueueError("Invalid " + label)
    return value


def _text(value, label, maximum=1000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or not value.isprintable():
        raise QueueError("Invalid " + label)
    return value


def _json(value, label, nonempty=False, maximum=MAX_JSON_BYTES):
    if type(value) is not dict or (nonempty and not value):
        raise QueueError(label + " must be a JSON object" + (" with evidence" if nonempty else ""))
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False)
        if json.loads(raw) != value or len(raw.encode("utf-8")) > maximum:
            raise ValueError("non-JSON values or excessive size")
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise QueueError("Invalid or oversized " + label) from error
    return raw


def _host_clock():
    """Linux boot identity plus UTC deadline and boot-relative elapsed time."""
    try:
        epoch = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    except OSError as error:
        raise QueueError("Default clock requires Linux boot_id; supply a trusted same-host clock") from error
    return time.time_ns() // 1_000_000, time.monotonic_ns() // 1_000_000, epoch


class Queue:
    def __init__(self, path, *, clock=None):
        self.path = Path(path)
        if str(self.path) == ":memory:":
            raise QueueError("Execution tickets require a persistent local database file")
        self.clock = _host_clock if clock is None else clock
        if not callable(self.clock):
            raise QueueError("clock must be callable")

    @contextmanager
    def _transaction(self, *, initialize=False):
        if self.path.is_symlink():
            raise QueueError("Database must not be a symlink")
        if self.path.exists() and not self.path.is_file():
            raise QueueError("Database must be a regular file")
        if not initialize and not self.path.is_file():
            raise QueueError("Initialize the execution queue first")
        if initialize:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = None
        try:
            connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            if initialize:
                self._initialize(connection)
            self._validate(connection)
            yield connection
            connection.execute("COMMIT")
        except sqlite3.Error as error:
            raise QueueError("SQLite transaction failed: " + str(error)) from error
        finally:
            if connection is not None:
                if connection.in_transaction:
                    connection.rollback()
                connection.close()

    @staticmethod
    def _initialize(connection):
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if tables:
            if tables != {"queue_meta", "tickets", "events"}:
                raise QueueError("Refusing an unrelated or incomplete database")
            return
        connection.execute("""CREATE TABLE queue_meta (
            id INTEGER PRIMARY KEY CHECK(id=1), schema_version INTEGER NOT NULL,
            max_active INTEGER NOT NULL, max_effects INTEGER NOT NULL,
            next_fence INTEGER NOT NULL, last_wall_ms INTEGER, last_elapsed_ms INTEGER,
            clock_epoch TEXT)""")
        connection.execute("INSERT INTO queue_meta VALUES(1,1,6,1,0,NULL,NULL,NULL)")
        connection.execute("""CREATE TABLE tickets (
            dispatch_id TEXT PRIMARY KEY, job_key TEXT NOT NULL UNIQUE,
            resource_key TEXT NOT NULL, outer_revision TEXT NOT NULL,
            outer_deadline_ms INTEGER NOT NULL, payload TEXT NOT NULL,
            effectful INTEGER NOT NULL CHECK(effectful IN(0,1)),
            max_attempts INTEGER NOT NULL CHECK(max_attempts BETWEEN 1 AND 10),
            state TEXT NOT NULL CHECK(state IN('ready','leased','uncertain','succeeded','dead')),
            attempts INTEGER NOT NULL CHECK(attempts>=0), owner TEXT,
            fence INTEGER NOT NULL CHECK(fence>=0), lease_until_ms INTEGER,
            available_at_ms INTEGER NOT NULL, effect_started INTEGER NOT NULL CHECK(effect_started IN(0,1)),
            receipt TEXT, error TEXT)""")
        connection.execute("""CREATE UNIQUE INDEX occupied_resource ON tickets(resource_key)
            WHERE state IN('leased','uncertain')""")
        connection.execute("CREATE INDEX eligible_tickets ON tickets(state,available_at_ms,dispatch_id)")
        connection.execute("""CREATE TABLE events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            dispatch_id TEXT NOT NULL REFERENCES tickets(dispatch_id),
            fence INTEGER NOT NULL, utc_ms INTEGER NOT NULL,
            event TEXT NOT NULL, details TEXT NOT NULL)""")
        connection.execute("PRAGMA user_version=1")

    @staticmethod
    def _validate(connection):
        row = connection.execute("SELECT * FROM queue_meta WHERE id=1").fetchone()
        if (row is None or row["schema_version"] != 1 or row["max_active"] != MAX_ACTIVE
                or row["max_effects"] != MAX_EFFECTS
                or connection.execute("PRAGMA user_version").fetchone()[0] != 1
                or type(row["next_fence"]) is not int or row["next_fence"] < 0):
            raise QueueError("Unsupported execution queue schema or policy")
        clock_fields = (row["last_wall_ms"], row["last_elapsed_ms"], row["clock_epoch"])
        if clock_fields != (None, None, None):
            _integer(row["last_wall_ms"], "stored UTC clock")
            _integer(row["last_elapsed_ms"], "stored elapsed clock")
            _identifier(row["clock_epoch"], "stored clock epoch")

    @staticmethod
    def _row(connection, dispatch_id):
        row = connection.execute("SELECT * FROM tickets WHERE dispatch_id=?", (dispatch_id,)).fetchone()
        if row is None:
            raise QueueError("Unknown dispatch ID")
        result = dict(row)
        result["payload"] = json.loads(result["payload"])
        result["receipt"] = json.loads(result["receipt"]) if result["receipt"] is not None else None
        result["effectful"] = bool(result["effectful"])
        result["effect_started"] = bool(result["effect_started"])
        return result

    @staticmethod
    def _event(connection, row, wall, event, details):
        connection.execute("INSERT INTO events(dispatch_id,fence,utc_ms,event,details) VALUES(?,?,?,?,?)",
                           (row["dispatch_id"], row["fence"], wall, event,
                            _json(details, "event details", maximum=MAX_JSON_BYTES + 2048)))

    def _tick(self, connection, *, changes=None):
        try:
            wall, elapsed, epoch = self.clock()
        except (TypeError, ValueError) as error:
            raise QueueError("Clock must return UTC milliseconds, elapsed milliseconds and epoch") from error
        _integer(wall, "UTC clock")
        _integer(elapsed, "elapsed clock")
        _identifier(epoch, "clock epoch")
        meta = connection.execute("SELECT * FROM queue_meta WHERE id=1").fetchone()
        if meta["last_wall_ms"] is not None and wall < meta["last_wall_ms"]:
            raise QueueError("UTC clock rollback; mutation refused")
        if meta["clock_epoch"] == epoch and elapsed < meta["last_elapsed_ms"]:
            raise QueueError("Elapsed clock rollback; mutation refused")
        if meta["clock_epoch"] is not None and meta["clock_epoch"] != epoch:
            # Preserve a pending retry's remaining delay across a reboot.
            connection.execute("""UPDATE tickets SET available_at_ms=? + MAX(0,available_at_ms-?)
                WHERE state='ready'""", (elapsed, meta["last_elapsed_ms"]))
            recovered = self._expire(connection, wall, elapsed, force=True)
            if changes is not None:
                changes.extend(recovered)
        connection.execute("UPDATE queue_meta SET last_wall_ms=?,last_elapsed_ms=?,clock_epoch=? WHERE id=1",
                           (wall, elapsed, epoch))
        return wall, elapsed

    def _expire(self, connection, wall, elapsed, *, force=False):
        changed = []
        rows = connection.execute("SELECT * FROM tickets WHERE state='leased' ORDER BY dispatch_id").fetchall()
        for row in rows:
            if not force and row["lease_until_ms"] > elapsed and row["outer_deadline_ms"] > wall:
                continue
            if row["effect_started"]:
                state = "uncertain"
            else:
                state = "ready" if row["attempts"] < row["max_attempts"] and wall < row["outer_deadline_ms"] else "dead"
            connection.execute("""UPDATE tickets SET state=?,owner=NULL,lease_until_ms=NULL,
                available_at_ms=?,error=? WHERE dispatch_id=?""",
                               (state, elapsed, "clock epoch changed" if force else "lease or outer deadline expired",
                                row["dispatch_id"]))
            updated = self._row(connection, row["dispatch_id"])
            self._event(connection, updated, wall, "expired", {"state": state, "epoch_changed": force})
            changed.append(updated)
        for row in connection.execute("SELECT * FROM tickets WHERE state='ready' AND outer_deadline_ms<=?", (wall,)).fetchall():
            connection.execute("UPDATE tickets SET state='dead',error='outer deadline expired' WHERE dispatch_id=?",
                               (row["dispatch_id"],))
            updated = self._row(connection, row["dispatch_id"])
            self._event(connection, updated, wall, "deadline_expired", {})
            changed.append(updated)
        return changed

    @staticmethod
    def _owned(connection, dispatch_id, owner, fence, wall, elapsed):
        _identifier(dispatch_id, "dispatch ID")
        _identifier(owner, "owner")
        _integer(fence, "fence", 1)
        row = Queue._row(connection, dispatch_id)
        if (row["state"] != "leased" or row["owner"] != owner or row["fence"] != fence
                or row["lease_until_ms"] <= elapsed or row["outer_deadline_ms"] <= wall):
            raise QueueError("Stale, expired or foreign lease")
        return row

    def init(self):
        with self._transaction(initialize=True) as connection:
            self._tick(connection)
            return {"schema_version": 1, "max_active": MAX_ACTIVE, "max_effects": MAX_EFFECTS}

    def enqueue(self, dispatch_id, *, job_key, resource_key, outer_revision,
                outer_deadline_ms, payload, effectful=False, max_attempts=3):
        for value, label in ((dispatch_id, "dispatch ID"), (job_key, "job key"), (resource_key, "resource key")):
            _identifier(value, label)
        _text(outer_revision, "outer revision", 200)
        _integer(outer_deadline_ms, "outer deadline", 1)
        _integer(max_attempts, "max attempts", 1, 10)
        if type(effectful) is not bool:
            raise QueueError("effectful must be boolean")
        payload_json = _json(payload, "payload")
        immutable = (job_key, resource_key, outer_revision, outer_deadline_ms,
                     payload_json, int(effectful), max_attempts)
        with self._transaction() as connection:
            wall, elapsed = self._tick(connection)
            old = connection.execute("SELECT * FROM tickets WHERE dispatch_id=?", (dispatch_id,)).fetchone()
            if old is not None:
                fields = ("job_key", "resource_key", "outer_revision", "outer_deadline_ms",
                          "payload", "effectful", "max_attempts")
                if tuple(old[key] for key in fields) != immutable:
                    raise QueueError("Dispatch ID conflicts with immutable ticket content")
                return self._row(connection, dispatch_id)
            if connection.execute("SELECT 1 FROM tickets WHERE job_key=?", (job_key,)).fetchone():
                raise QueueError("Job key already belongs to another dispatch")
            if outer_deadline_ms <= wall:
                raise QueueError("Outer dispatch deadline has expired")
            if connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] >= MAX_TICKETS:
                raise QueueError("Execution ticket capacity reached")
            connection.execute("""INSERT INTO tickets VALUES(?,?,?,?,?,?,?,?,'ready',0,NULL,0,NULL,?,0,NULL,NULL)""",
                               (dispatch_id, *immutable, elapsed))
            row = self._row(connection, dispatch_id)
            self._event(connection, row, wall, "enqueued", {"outer_revision": outer_revision})
            return row

    def claim(self, owner, *, lease_ms=30_000):
        _identifier(owner, "owner")
        _integer(lease_ms, "lease duration", 1, MAX_LEASE_MS)
        with self._transaction() as connection:
            wall, elapsed = self._tick(connection)
            self._expire(connection, wall, elapsed)
            occupied = connection.execute("SELECT COUNT(*) FROM tickets WHERE state IN('leased','uncertain')").fetchone()[0]
            if occupied >= MAX_ACTIVE:
                return None
            effect_count = connection.execute("SELECT COUNT(*) FROM tickets WHERE effectful=1 AND state IN('leased','uncertain')").fetchone()[0]
            row = connection.execute("""SELECT t.* FROM tickets t WHERE t.state='ready'
                AND t.available_at_ms<=? AND t.outer_deadline_ms>?
                AND t.attempts<t.max_attempts AND (t.effectful=0 OR ?<1)
                AND NOT EXISTS(SELECT 1 FROM tickets busy WHERE busy.resource_key=t.resource_key
                    AND busy.state IN('leased','uncertain'))
                ORDER BY t.available_at_ms,t.dispatch_id LIMIT 1""", (elapsed, wall, effect_count)).fetchone()
            if row is None:
                return None
            fence = connection.execute("SELECT next_fence FROM queue_meta WHERE id=1").fetchone()[0] + 1
            _integer(fence, "next fence", 1)
            connection.execute("UPDATE queue_meta SET next_fence=? WHERE id=1", (fence,))
            deadline = elapsed + min(lease_ms, row["outer_deadline_ms"] - wall)
            connection.execute("""UPDATE tickets SET state='leased',attempts=attempts+1,owner=?,
                fence=?,lease_until_ms=?,effect_started=0,receipt=NULL,error=NULL WHERE dispatch_id=?""",
                               (owner, fence, deadline, row["dispatch_id"]))
            result = self._row(connection, row["dispatch_id"])
            self._event(connection, result, wall, "claimed", {"owner": owner, "lease_until_ms": deadline})
            return result

    def heartbeat(self, dispatch_id, owner, fence, *, lease_ms=30_000):
        _integer(lease_ms, "lease duration", 1, MAX_LEASE_MS)
        with self._transaction() as connection:
            wall, elapsed = self._tick(connection)
            row = self._owned(connection, dispatch_id, owner, fence, wall, elapsed)
            deadline = elapsed + min(lease_ms, row["outer_deadline_ms"] - wall)
            connection.execute("UPDATE tickets SET lease_until_ms=? WHERE dispatch_id=?", (deadline, dispatch_id))
            result = self._row(connection, dispatch_id)
            self._event(connection, result, wall, "heartbeat", {"lease_until_ms": deadline})
            return result

    def begin_effect(self, dispatch_id, owner, fence):
        with self._transaction() as connection:
            wall, elapsed = self._tick(connection)
            row = self._owned(connection, dispatch_id, owner, fence, wall, elapsed)
            if not row["effectful"] or row["effect_started"]:
                raise QueueError("Effect must be declared and may begin only once per attempt")
            connection.execute("UPDATE tickets SET effect_started=1 WHERE dispatch_id=?", (dispatch_id,))
            result = self._row(connection, dispatch_id)
            self._event(connection, result, wall, "effect_started", {})
            return result

    def complete(self, dispatch_id, owner, fence, receipt):
        encoded = _json(receipt, "completion receipt", nonempty=True)
        with self._transaction() as connection:
            wall, elapsed = self._tick(connection)
            self._owned(connection, dispatch_id, owner, fence, wall, elapsed)
            connection.execute("""UPDATE tickets SET state='succeeded',owner=NULL,
                lease_until_ms=NULL,receipt=?,error=NULL WHERE dispatch_id=?""", (encoded, dispatch_id))
            result = self._row(connection, dispatch_id)
            self._event(connection, result, wall, "completed", {"receipt_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest()})
            return result

    def fail(self, dispatch_id, owner, fence, error, *, retry=True, delay_ms=0):
        _text(error, "failure description")
        _integer(delay_ms, "retry delay", 0, MAX_DELAY_MS)
        if type(retry) is not bool:
            raise QueueError("retry must be boolean")
        with self._transaction() as connection:
            wall, elapsed = self._tick(connection)
            row = self._owned(connection, dispatch_id, owner, fence, wall, elapsed)
            state = "uncertain" if row["effect_started"] else (
                "ready" if retry and row["attempts"] < row["max_attempts"]
                and wall + delay_ms < row["outer_deadline_ms"] else "dead")
            connection.execute("""UPDATE tickets SET state=?,owner=NULL,lease_until_ms=NULL,
                available_at_ms=?,error=? WHERE dispatch_id=?""", (state, elapsed + delay_ms, error, dispatch_id))
            result = self._row(connection, dispatch_id)
            self._event(connection, result, wall, "failed", {"state": state, "error": error})
            return result

    def reap(self):
        with self._transaction() as connection:
            changed = []
            wall, elapsed = self._tick(connection, changes=changed)
            changed.extend(self._expire(connection, wall, elapsed))
            return changed

    def reconcile(self, dispatch_id, *, expected_fence, decision, evidence, quiescent):
        _identifier(dispatch_id, "dispatch ID")
        _integer(expected_fence, "reconciliation fence", 1)
        if decision not in ("applied", "not_applied") or type(decision) is not str:
            raise QueueError("Reconciliation decision must be applied or not_applied")
        if quiescent is not True:
            raise QueueError("Reconciliation requires explicit old-attempt quiescence")
        encoded = _json(evidence, "reconciliation evidence", nonempty=True)
        with self._transaction() as connection:
            wall, elapsed = self._tick(connection)
            row = self._row(connection, dispatch_id)
            if row["state"] != "uncertain" or row["fence"] != expected_fence:
                raise QueueError("Reconciliation requires the exact current uncertain fence")
            state = "succeeded" if decision == "applied" else (
                "ready" if row["attempts"] < row["max_attempts"] and wall < row["outer_deadline_ms"] else "dead")
            connection.execute("""UPDATE tickets SET state=?,available_at_ms=?,effect_started=0,
                receipt=?,error=NULL WHERE dispatch_id=?""", (state, elapsed, encoded, dispatch_id))
            result = self._row(connection, dispatch_id)
            self._event(connection, result, wall, "reconciled", {"decision": decision,
                         "quiescent": True, "evidence": evidence})
            return result

    def get(self, dispatch_id):
        _identifier(dispatch_id, "dispatch ID")
        with self._transaction() as connection:
            return self._row(connection, dispatch_id)

    def uncertain(self):
        """Read all unresolved effects without claiming or reaping work."""
        with self._transaction() as connection:
            identifiers = [row[0] for row in connection.execute(
                "SELECT dispatch_id FROM tickets WHERE state='uncertain' ORDER BY dispatch_id")]
            return [self._row(connection, identifier) for identifier in identifiers]

    def events(self, dispatch_id):
        _identifier(dispatch_id, "dispatch ID")
        with self._transaction() as connection:
            self._row(connection, dispatch_id)
            return [dict(row, details=json.loads(row["details"])) for row in connection.execute(
                "SELECT * FROM events WHERE dispatch_id=? ORDER BY sequence", (dispatch_id,))]

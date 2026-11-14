# Exact-byte artifact integrity

`artifact_integrity.py` checks whether listed distribution files match supplied byte
counts and SHA256 digests. It uses Python's standard library, streams the original
bytes and performs no network requests, extraction, execution or writes.

This complements `archive_audit.py`, which reconstructs upstream Git trees including
file modes. It does not replace that check or understand the contents of a ZIP/PDF.

## Manifest and command

```json
{
  "schema": "atlas.artifact.integrity.v1",
  "entries": [
    {
      "path": "abc.txt",
      "bytes": 3,
      "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    }
  ]
}
```

The example expects exactly the three ASCII bytes `abc`, without a newline.

```sh
python3 artifact_integrity.py check --root /absolute/path/to/distribution --manifest /path/to/manifest.json
```

Both paths are explicit. The command prints a JSON report and exits **0** on
success or **2** on mismatch, invalid input or an operational error. Each entry
reports its expected values, bytes read, observed values when available, and any
failure. A malformed manifest or invalid root produces a top-level error.

The default limits are 1,000 entries and 1 GiB total declared artifact bytes.
`--max-files` and `--max-bytes` can set explicit limits. The CLI also caps manifest
input at 1 MiB. At most 64 KiB of artifact data is read per operation; mismatched
file sizes fail before hashing. An EOF probe rejects extra data even when a virtual
file reports a misleading size. Total reads are bounded to `max_bytes` plus at
most one detection byte; exhaustion prevents further artifact reads.
Only listed artifacts are checked. Unlisted files
are not covered, and success does not establish that a directory is complete.

For Python callers:

```python
from artifact_integrity import verify_manifest
report = verify_manifest(root, manifest, max_files=1000, max_bytes=1024**3)
assert report["ok"]
```

Malformed manifests and roots raise `ValueError` or `OSError` in the Python API;
per-artifact failures appear in the structured result. JSON object keys, schema
fields and entry fields must be unique and exact. Digests must be lowercase hex;
byte counts must be non-negative integers, excluding booleans.

## Filesystem boundaries

Artifact paths are canonical relative POSIX paths. Absolute paths, parent or dot
components, empty components, backslashes, colons, ASCII control characters, duplicate
names and case-folding collisions are rejected. Paths are bounded to 4,096
characters and 64 components. Artifacts must be regular files.

Directory traversal uses anchored directory descriptors and `O_NOFOLLOW` for
every component, including the root's ancestors. Symlinks are rejected, even when
they point within the root. Non-blocking opens prevent a named pipe from stalling
the checker. Unsupported platforms fail closed; currently this requires POSIX
descriptor-relative opens, `O_DIRECTORY`, `O_NOFOLLOW` and `O_NONBLOCK`.
Windows has no insecure fallback. Select a root whose ancestors are real
directories; on macOS a convenience path such as `/tmp` may itself be a symlink.

Size and file metadata are checked before and after streaming. This detects common
concurrent modifications but is not a filesystem snapshot or a guarantee against
an adversarial writer. Verify an immutable release directory. Hard links are not
rejected. Manifest entries are not shell commands or instructions to the agent.

## Meaning and evidence

SHA256 agreement establishes agreement with the supplied manifest. Someone who
can replace both files and manifest can provide matching hashes. This tool makes
no signature, authorship, authenticity, safety, scientific validity or copyright
claim. Establish trusted expected hashes separately when provenance matters.

No JSON reserialisation or text normalisation occurs. LF and CRLF differ. In
particular, hashing an Atlas Reweave export's raw bytes does not independently
validate its internal Python JSON encoding, acceptance policy or scientific claims.

Tests include fixed SHA256 known-answer vectors for empty input and `abc`, UTF-8,
binary zeros, line endings, chunk boundaries, changed/truncated/missing files,
unsafe paths, symlinks, named pipes, bounds and malformed manifests. When Node is
available, a separate streaming `node:crypto` implementation compares the same
fixtures using different chunk sizes. Its absence is reported as a test skip.
Python and Node may share an underlying crypto implementation; this is a runtime
and byte-handling comparison, not proof of independent cryptographic primitives.

This test discipline is informed by Paul Miller's
[noble-hashes tests at commit 17cbd0b0c9fad101aa03fe0a45035e98e917640c](https://github.com/paulmillr/noble-hashes/blob/17cbd0b0c9fad101aa03fe0a45035e98e917640c/test/hashes.test.ts),
which combine known-answer vectors with comparison and boundary tests. The Atlas
implementation is original and copies no Noble code. A separate pinned Noble
implementation comparison remains **unimplemented**; no Noble production or test
dependency is introduced.

```sh
python3 -m unittest discover -s tests -p 'test_artifact_integrity.py' -v
```

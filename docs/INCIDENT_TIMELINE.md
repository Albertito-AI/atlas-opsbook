# Offline incident timeline

`incident_timeline.py` turns explicitly selected local JSONL evidence into a
chronological report with source hashes. It helps an Opsbook investigator inspect
an incident before proposing a rule or constructing a labelled replay case. It
does not infer a cause, change the Opsbook database, run commands, contact a
service, or submit a report. Python 3.9 or later and the standard library suffice.

## Input contract

Each nonblank line must be one UTF-8 JSON object with exactly these supported
fields:

| Field | Requirement | Meaning |
|---|---|---|
| `message` | Required, nonempty string | Original observation to preserve |
| `source` | Optional, nonempty string | Label for the observer; defaults to the input path |
| `time` | Optional string or `null` | Explicit observation timestamp; missing or `null` remains undated |

Unknown fields, duplicate JSON keys, invalid UTF-8, nonstandard JSON constants,
blank lines and invalid field types fail explicitly. Empty files are permitted
and retain their own hash and zero count. A trailing newline is permitted.

For example, `evidence/build.jsonl` could contain:

```jsonl
{"source":"test-runner","message":"Replay rejected candidate rule","time":"2026-11-14T10:02:00+01:00"}
{"source":"reviewer","message":"Original failure report has no recorded time"}
{"source":"test-runner","message":"Replay started","time":"2026-11-14T09:01:59.125Z"}
```

Timestamps require `YYYY-MM-DDTHH:MM:SS`, an optional fraction of one to six
digits, and either `Z` or an explicit `+HH:MM`/`-HH:MM` offset. Uppercase `T` and
`Z` are required. Calendar-invalid values, leap seconds, more precise fractions,
naive local times and the unknown-offset notation `-00:00` are rejected. Offsets
normalize to UTC without dropping supported fractional precision. This is a
deliberately restricted timestamp format, not a parser for every log format.

## Build and verify

Run from the repository root after creating the evidence directory and files:

```sh
python incident_timeline.py build \
  --root ./evidence \
  --input build.jsonl \
  --out incident.json

python incident_timeline.py check \
  --root ./evidence \
  --receipt incident.json
```

Repeat `--input` to include another file. All input, output and receipt paths are
relative to `--root`. Absolute paths, traversal, empty path components,
backslashes, colons and symlinks are rejected. Input paths are limited to 256
UTF-8 bytes, and inputs must be regular files. The root directory and its path
components must not be symlinks. Files are not discovered recursively.

Output uses exclusive creation. An existing output, input file, directory,
hard-link destination or symlink will not be overwritten. The output's parent
directory must already exist. Choose a new output name for a rebuilt report.
Validation failures return exit code `2`; successful build/check returns `0`.

Both public functions also work without the CLI:

```python
from incident_timeline import build_timeline, verify_timeline

receipt = build_timeline("evidence", ["build.jsonl"],
                         max_bytes=1048576, max_records=10000)
result = verify_timeline(receipt, "evidence")
```

## What the receipt establishes

The schema is `atlas.incident.timeline.v1`. The `inputs` manifest records each
path, SHA-256 hash of its complete original bytes, byte length and record count.
`dated` events retain message, source, input path and one-based line number, with
a UTC timestamp rendered to six fractional digits. `undated` events retain the
same provenance with `time: null`.

Dated events sort by UTC time, then source, message, input path and line number.
Undated events sort by those four latter fields. Input-list order has no effect.
Duplicates are retained as separate observations. Equal timestamps use a stable
presentation order, not an inferred causal order. Editing or rearranging source
lines deliberately changes provenance and hashes.

`coverage.start` and `coverage.end` describe the earliest and latest dated
observations, or are both `null` when none exist. They do not assert that all
events in that interval were captured. `total_bytes`, `total_records` and
`limits` make the collection's scope explicit.

Verification rebuilds the report from its declared inputs and limits, then
compares the entire receipt, including JSON value types. Changed whitespace,
modified content, deleted sources and edited event metadata invalidate the
saved report. Hashes establish consistency with the supplied files, not the
truth of observations or the identity of their author. Verification cannot
authenticate a receipt that someone has replaced together with its evidence.
Use a stable local directory; this is not an isolation boundary against another
process concurrently replacing files.

## Bounds and validation

Defaults permit 1 MiB of aggregate raw input and 10,000 total records. Set
`--max-bytes` and `--max-records` explicitly for a larger collection. Hard ceilings
are 16 MiB, 100,000 records and 256 input files. Exceeding a limit fails instead
of truncating evidence. Serialized receipts have a separate 128 MiB ceiling,
also applied when reading a receipt for verification.

Run the behavioural suite with:

```sh
python -m unittest discover -s tests -p 'test_incident_timeline.py' -v
```

The fixtures exercise shuffled observations, offsets, equal timestamps,
duplicates, missing and invalid times, exact byte and record boundaries,
malformed JSON, unsafe paths, source drift and preservation of existing files.

## Design attribution

This is an original Atlas implementation. It was informed by Ivan Sim's public
operational tools, inspected on 14 November 2026:

- [sbsearch README, commit eefdbde](https://github.com/ihcsim/sbsearch/blob/eefdbdec257d42fe4e777538eb9098dc5927387d/README.md)
  and [search implementation](https://github.com/ihcsim/sbsearch/blob/eefdbdec257d42fe4e777538eb9098dc5927387d/src/sbsearch.rs):
  chronological support-bundle search and explicit treatment of undated entries.
- [promdump README, commit be920d1](https://github.com/ihcsim/promdump/blob/be920d15c8739eb2f93059415cfcad0b6e21a1ca/README.md):
  collecting inspectable incident evidence when the investigator lacks direct
  access to the affected environment.

No upstream source code was copied. This module does not implement Prometheus
restore or parse Harvester bundles. Those integrations require their own
requirements and review.

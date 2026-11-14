# A bounded reconstruction lesson

This original, offline exercise demonstrates how to investigate an observable contract, distinguish competing explanations, implement one candidate and retain evidence of what was checked. It uses Python's standard library and an Atlas-owned local fixture. It does not install or execute third-party programs, contact services or examine another party's software.

Run it from the repository root:

```sh
python examples/reconstruction_trial.py
python -m unittest discover -s tests -p test_reconstruction_trial.py -v
```

The example prints a JSON receipt and verification results. It writes no files. Its public Python functions are `reference(bytes)`, `candidate(bytes)`, `build_receipt()`, `verify_receipt(receipt)` and `run_trial()`.

## The question and the experiment

Suppose a local text-normalisation function has an undocumented treatment of case and whitespace. Three plausible explanations are supplied before testing:

| Hypothesis | Whitespace rule | Case rule | Discovery matches |
| --- | --- | --- | --- |
| `unicode_casefold` | Split on Unicode whitespace | Unicode case folding | 3 of 6 |
| `unicode_lower` | Trim and collapse ASCII whitespace | Unicode lowercasing | 5 of 6 |
| `ascii_only` | Trim and collapse ASCII whitespace | Lowercase ASCII A to Z only | 6 of 6 |

Ordinary English examples do not distinguish these explanations. Probes containing `Straße`, the Turkish capital dotted `İ`, and non-breaking spaces do. The exercise retains the failing hypotheses and their counts instead of presenting only the successful candidate.

The original reference implementation uses decoded strings, an explicit regular expression and an ASCII translation table. The candidate uses a byte state machine: it tracks pending separators and maps uppercase ASCII byte values while retaining other UTF-8 bytes. Both use Python's UTF-8 decoder and a shared response formatter; they are not independent implementations of every component.

The six discovery inputs and 32 held-out inputs are disjoint. Held-out cases cover non-ASCII letters and whitespace, combining characters, repeated separators, exact byte limits and malformed input. The function contract is:

- Accept at most 256 input bytes, measured before decoding.
- Reject invalid UTF-8, then embedded NUL, then an empty result, in that order after the size check.
- Trim and collapse only ASCII space, tab, newline, carriage return, vertical tab and form feed.
- Lowercase only ASCII A to Z and retain all other Unicode characters.
- Return exactly `stdout`, `stderr` and `exit_code` fields. Success adds a newline to the normalised text. Failure returns an empty `stdout`, one error label plus newline, and code `2`.

The size limit is a byte limit: 128 copies of `é` fit, while 129 exceed it. An overlong malformed byte sequence produces `too-long`, so tests also examine error precedence.

The function-level `exit_code` field models a response contract. It is not an observed operating-system process exit. The example never launches the target as a subprocess and does not claim verification of packaging, process cancellation or cleanup.

## What the receipt establishes

The receipt records an obligation identifier and revision, the source SHA-256 of the complete example module, its maximum input size, every input as hexadecimal bytes, reference and candidate responses, hypothesis results and coverage limits. `evidence_digest` hashes the canonical JSON receipt excluding that digest field.

`verify_receipt` checks the receipt digest, matches the current module bytes and regenerates the experiment using the owned fixture. A checksum alone is insufficient. The experiment deliberately checks three failures:

| Negative control | Required result |
| --- | --- |
| A stale implementation hash with a newly recomputed receipt digest | Rejected as stale evidence. |
| An invented observation with a newly recomputed receipt digest | Rejected because replay does not match. |
| A candidate that applies Unicode case folding | Rejected by six held-out mismatches. |

The module hash covers the reference, candidate, probe corpus and receipt code. A change to any of them invalidates an old receipt. This is a structural freshness check, not a signature or proof of authorship. Run against a stable checkout; concurrent source-file changes are outside this small example's model.

Passing these probes establishes the recorded results. It does not establish universal equivalence, recover the reference's original source or prove that no other hypothesis fits. The fixture's source and held-out corpus are visible for teaching, so this is not a blind benchmark. To use the pattern for training, a separate fixture author can withhold the oracle implementation and evaluation cases from the learner until its reconstruction is committed.

## Lessons adopted from Morluto's public work

The example is original Atlas code. It adopts methodological ideas from these inspected sources:

- **REA:** [proof qualification](https://github.com/morluto/rea/blob/69386962569de27a1201847bf50a8c9ea592c5bd/src/application/ReconstructionObligationAuthority.ts) binds a result to the exact obligation, implementation digest, revision and case or claim. Its [adversarial fixtures](https://github.com/morluto/rea/blob/69386962569de27a1201847bf50a8c9ea592c5bd/tests/fixtures/reconstructionProofApplicability.ts) distinguish stale, mismatched and failed proof. This example adopts that separation at function level; it does not implement REA's schema or claim compatibility.
- **Flameox:** [evidence models](https://github.com/morluto/flameox/blob/c7ea167bf51bf10da9bc17a9ffc1124f4166f32f/src/flameox/evidence_models.py) preserve capture completeness and byte accounting. This example keeps complete bounded inputs and outputs; a future process-level exercise would also need capture, timeout and truncation evidence.
- **SmokingGun:** [source snapshots](https://github.com/morluto/smokinggun/blob/cf3a3872a2638a68d2d123126f98dfa84c85643d/src/scan/source-snapshot.ts) include visible omissions in the evidence identity. This example likewise makes its finite observation boundary and unsupported claims explicit.

The upstream source and tests were read for this comparison. They were not installed or executed. REA-authored code is MIT, while its third-party components and external tools retain their own terms; its [notice inventory](https://github.com/morluto/rea/blob/69386962569de27a1201847bf50a8c9ea592c5bd/THIRD_PARTY_NOTICES.md) documents that distinction.

## Apply the method to an Atlas project

Start with an owned or expressly authorised interface and a narrow question. Freeze its version, record the allowed observation boundary, and separate observations from hypotheses. Choose probes that discriminate between those hypotheses, including malformed and boundary cases. Write an original candidate, preserve a held-out evaluation set and include a deliberately faulty candidate so the checker must demonstrate that it can fail.

Carry only the verified finite claims into an Atlas handoff. Keep unresolved behaviour visible, bind the receipt to the tested implementation and repeat validation after changes. If the claim concerns a shipped CLI, browser lifecycle or protocol exchange, gather evidence at that boundary; this function-level lesson cannot establish those behaviours. For upstream contributions, check current guidance and overlapping work before proposing a focused change.

Copyright 2026 Albert Tan Sin Hon. Licensed under MIT.

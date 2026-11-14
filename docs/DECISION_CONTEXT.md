# Decision context from an explicit catalogue

`decision_context.py` builds a bounded context pack containing current, explicitly accepted decisions for a requested area of work. It also checks whether that pack still matches its catalogue and selected source files. The implementation uses the Python 3.9+ standard library and requires no service, model, API key or network connection.

This is an original Atlas prototype motivated by the ADR context-management problem discussed in [Matt Pocock's skills community](https://github.com/mattpocock/skills/discussions/1409). His [ADR format](https://github.com/mattpocock/skills/blob/main/skills/engineering/domain-modeling/ADR-FORMAT.md) allows status metadata to be omitted. This prototype therefore requires a separate, explicit catalogue instead of guessing acceptance from prose. It does not copy an upstream implementation. See [the learning record](POCOCK_LEARNING.md) for the broader comparison.

## Run the synthetic trial

From the repository root:

```sh
python examples/decision_context_trial.py
python -m unittest discover -s tests -p test_decision_context.py -v
```

The trial creates 150 original synthetic decision files in a temporary directory. It selects one current billing decision and one global decision, preserves their complete text, and validates the resulting pack. A proposed successor does not suppress the accepted billing decision. Six deliberate negative cases must be detected: selected-source drift, catalogue-byte drift, pack tampering, budget overflow, scoped unspecified status and an out-of-scope graph cycle. The script prints a JSON result and removes its temporary files. Failure to detect any deliberate negative case raises an exception and exits unsuccessfully.

This fixture demonstrates declared selection and failure behaviour. It is not evidence of improved agent reasoning, lower token cost on a real repository, or the correctness of any architectural decision.

## Declare the decisions

Create a UTF-8 JSON catalogue inside the repository root. Every entry must have exactly these five fields:

```json
{
  "schema": "atlas.decision.catalogue.v1",
  "decisions": [
    {
      "id": "ADR-0001",
      "path": "docs/adr/0001-receipts.md",
      "status": "accepted",
      "scopes": ["global"],
      "supersedes": []
    },
    {
      "id": "ADR-0002",
      "path": "docs/adr/0002-draft-storage.md",
      "status": "accepted",
      "scopes": ["billing"],
      "supersedes": []
    }
  ]
}
```

The paths must refer to existing UTF-8 source files. The tool does not create, edit, summarise or interpret these files. Catalogue and source paths are relative to `--root`; an absolute catalogue path is also accepted if it is inside that root. Paths use POSIX separators and cannot contain traversal, empty components or symlink components below the supplied root.

Identifiers, scopes and supersession targets contain 1 to 100 ASCII letters, digits, underscores, hyphens or dots, beginning with a letter or digit. Lists must contain distinct entries. Each decision needs at least one scope; `global` is a reserved scope included in every selection. Identifiers and source paths must be unique across the catalogue. Duplicate JSON object keys and non-JSON numeric constants are rejected.

| Status | Selection behaviour |
| --- | --- |
| `accepted` | Included when relevant and not superseded by an accepted descendant. |
| `proposed` | Excluded; does not by itself supersede an accepted decision. |
| `deprecated` | Excluded. |
| `rejected` | Excluded. |
| `unspecified` | Excluded and reported. A relevant record makes the pack unready, even if it has an accepted successor. |

An unspecified status is an unresolved declaration, not implied acceptance or rejection. A human must review and update the catalogue before a pack containing a relevant unspecified record can pass `check`.

## Supersession and scopes

An entry's `supersedes` list names its predecessors. Validation covers the entire declared graph before scope filtering. Missing targets, self-references, cycles and competing terminal accepted successors of one predecessor are rejected. A unique later accepted descendant replaces an accepted ancestor even if the connecting history includes proposed decisions. Dates and filenames are not used to resolve ambiguity.

**Supersession replaces a predecessor in every scope.** For example, if a warehouse-only accepted decision supersedes a global accepted decision, that predecessor is also removed from a billing pack. Scopes are not inherited or automatically copied. The catalogue author must carry forward every scope in which the replacement applies, or split the decisions before recording a partial replacement. An empty selection may be ready: readiness means that the declared structural checks passed, not that the requested work has sufficient policy coverage.

## Build and check

```sh
python decision_context.py build \
  --root . --manifest decisions.json \
  --scope billing --max-bytes 24000 --out decision-context.json

python decision_context.py check \
  --root . --bundle decision-context.json
```

Repeat `--scope` to select several areas. The default budget is 24,000 UTF-8 bytes of selected source text. It is not a token count. Sources are included in full; exceeding the budget fails instead of truncating them. The build command refuses to overwrite a declared source or the catalogue, including through an existing hardlink, and refuses a symlink as its output file.

| Result | Exit status |
| --- | --- |
| Ready pack built; fresh ready pack checked | `0` |
| Pack built with a relevant unspecified decision | `2`, with the unready pack still written for review |
| Invalid catalogue, stale pack, excessive budget, unsafe path or other validation error | `2`, with a diagnostic on standard error |

A failed validation does not write a new pack. If an older output file already exists, that file remains; callers must check the command's exit status and run `check` before using a pack. The CLI prints a small JSON summary on success. The complete selected text and omitted-entry reasons are in the output file.

Python callers can use:

```python
from pathlib import Path
from decision_context import build_context, check_context

pack = build_context(Path("."), Path("decisions.json"), ["billing"], max_bytes=24000)
result = check_context(pack, Path("."))
# {"valid": True, "selected": <count>, "scope": ["billing"]}
```

Validation errors raise `ValueError`. `build_context` returns an unready pack for relevant unspecified records; `check_context` rejects that pack until the catalogue is reviewed and the pack rebuilt.

## Evidence and limits

The `atlas.decision.context.v1` pack records:

- The catalogue's relative path and exact-byte SHA-256, plus a digest of its canonical declaration fields.
- Sorted requested scopes, the budget, readiness and source count.
- Each selected entry's declaration, complete text, UTF-8 byte count and source SHA-256.
- Every omitted entry's identifier, path and structural reason.
- Selected bytes, total declared source bytes at build time, and a digest of the canonical pack excluding `bundle_digest` itself.

`check` verifies the pack digest, rebuilds selection against the current catalogue and compares the selected text and provenance. A selected-source edit or any catalogue-byte edit, including whitespace, requires rebuilding. Edits to valid unselected sources do not invalidate the pack; `total_source_bytes` remains a historical metric. All declared sources must still be readable regular UTF-8 files within the limits, so deleting an unselected file or making it invalid still fails validation.

The limits are 2,000 catalogue entries, 4 MiB per catalogue or source file, 128 MiB across declared sources, and a selected-text budget from 1 byte to 4 MiB. Serialized CLI packs have a separate 64 MiB ceiling because JSON escaping and metadata enlarge the output.

These are structural hashes, not signatures or attestations of authorship. An operator able to modify the catalogue and sources can create a different internally consistent pack. Hash checks do not prove semantic truth, policy completeness, trustworthy instructions, approval authority or the absence of contradictions in prose. Human review remains responsible for those judgments.

The tool assumes a trusted local repository and operator. It rejects symlink components in catalogue and decision-source paths below the supplied root and checks regular files, but does not establish a hostile-filesystem sandbox or a transactionally consistent snapshot. The root may itself be reached through a symlink, and path checks can race concurrent filesystem changes. Run against a stable checkout, keep the generated pack with its source revision when reproducibility matters, and rebuild after changes. Reading and checking a pack does not execute its decision text.

Copyright 2026 Albert Tan Sin Hon. Licensed under MIT.

# Learning from Matt Pocock's engineering ecosystem

Audit date: **14 November 2026**. This is a focused examination of public projects relevant to Atlas, not an exhaustive assessment of their author or a claim that adopting them establishes superior performance. Source revisions below freeze the material inspected. Repository state and contribution policies can subsequently change.

Atlas Opsbook already records incidents, tests proposed instructions against labelled cases and persists accepted procedures outside the model. Its existing pstack integration supplies a separate workflow catalogue. The opportunity examined here is to improve how a later agent discovers the decisions that apply to its task, then extend the same evidence discipline to reviews and teaching.

## Project selection

| Project | Inspected revision and state | Licence evidence | Decision for Atlas |
| --- | --- | --- | --- |
| [skills][skills] | `5863806dd4e15c63174bee4e7515a4256792ecfa`, 12 November 2026; unarchived | Root MIT licence, copyright Matt Pocock | Adapt selected practices with attribution; avoid installing the whole catalogue indiscriminately. Its `misc/` bucket is explicitly frozen and unmaintained. |
| [sandcastle][sandcastle] | `0ed674e5195b200d34bc4128eec33409f2952dcf`, 13 November 2026; unarchived; source package version `0.14.0` | Root MIT licence | Candidate execution layer for a bounded future trial. No live integration is asserted here. |
| [ts-reset][ts-reset] | `81b3b2614a32e47948cd4b8d5468879c07c2b361`, 1 April 2026; unarchived; source package version `0.7.0` | Root MIT licence | Consider for a specific TypeScript application after compatibility checks; it is not needed by this Python prototype. |
| [dictionary-of-ai-coding][dictionary] | `8a56b8ae80dd184f83a958e898516bff52653633`, 12 November 2026; unarchived | No root licence or package licence field found | Reference its distinctions; do not assume redistribution permission. |
| [beginners-typescript-tutorial][tutorial] | Default-branch README and root directory inspected on the audit date; unarchived | No root licence found | Learn the exercise structure and write original Atlas cases. |
| [evalite](https://github.com/mattpocock/evalite), [xstate-catalogue](https://github.com/mattpocock/xstate-catalogue), [xstate-codegen](https://github.com/mattpocock/xstate-codegen) | GitHub metadata marked each archived on the audit date | Not assessed for this selection | Historical references, not selected dependencies. Archival status says nothing by itself about their technical quality. |

For the MIT projects, retain the upstream copyright and permission notice when distributing copies or substantial portions. Being publicly readable is not itself evidence of an open-source licence. Being unarchived is not a promise of continuing support.

## Eight lessons and their Atlas applications

### 1. Separate specification review from standards review

The [code-review practice][review] gives separate agents different questions: whether the change fulfils the specification, and whether it follows repository standards. It resolves a comparison point before reviewing the diff. Atlas should retain both findings rather than average them into a reassuring overall score. **Proposed extension:** evidence-bound review receipts that identify the exact reviewed commit and specification. Opsbook's existing rule replay is not a substitute for these reviews.

### 2. Distinguish validated structure from justified conclusions

Sandcastle's [structured-output interface][output] parses an answer against a supplied schema and reports extraction or validation failures. This is useful for machine-readable review results, but a well-formed approval can still describe obsolete code. **Prototype application:** the decision-context builder uses explicit catalogue fields and source hashes. These establish what material was selected and whether it changed; they do not establish that a decision is substantively correct.

### 3. Bound work by ownership and execution context

Sandcastle's [branch strategies][branches] distinguish direct work, temporary branches and named branches. Its worktree lifecycle preserves certain unfinished work rather than treating cleanup as successful delivery. **Proposed Atlas application:** give each maintenance job a named branch, a bounded objective and a designated integration owner. A large roster of agent roles does not create these properties automatically. Execution concurrency must remain within the actual runner's capacity.

### 4. Test an observable contract with independent expectations

The [TDD reference][tdd] emphasises public interfaces and warns against tests that reproduce the implementation's own calculation. The beginner tutorial similarly pairs a problem with tests and a separately available solution. **Existing Atlas foundation:** Opsbook tests rules against supplied case labels. **Prototype application:** use hand-labelled decision chains and malformed catalogues to challenge selection, supersession and drift behaviour. Passing those fixtures will support bounded claims only.

### 5. Treat unavailable evidence as an explicit failure

Sandcastle's [inspected head commit][ratchet] addresses a lint comparison that could silently skip when the checkout lacked `origin/main`. Its change obtains the comparison history and makes the missing baseline fail in continuous integration. **Prototype application:** refuse a catalogue with missing references, cycles or ambiguous supersession, and fail when the context budget is exceeded. Silent truncation would hide the very uncertainty the builder should expose.

### 6. Make current knowledge easy to locate

The skills repository distinguishes a glossary from architectural decisions, and provides instructions for loading decisions relevant to the area being changed. **Chosen Atlas application:** select explicitly accepted decisions for the requested scope, together with explicitly global decisions. Keep historical files available, but do not require every session to traverse the full history. Records with unspecified status must be reported as unresolved, not silently promoted into current policy.

### 7. Preserve learning as something that can be revisited

The [teaching practice][teach] separates a learning mission, resources, lessons and learning records. **Existing Atlas foundation:** the launch case records a packaging failure and a tested instruction. **Proposed extension:** convert actual maintenance incidents into original problem/solution exercises, then test an unseen related case later. Completing an explanation or seeing the answer is not evidence of durable skill acquisition.

### 8. Contribute within the receiving project's scope

The inspected [contribution policy][contributing] asks for a short, reproducible problem and limits pull requests to collaborators. Its [scope policy][scope] requires an observed failure and rejects project-specific workflow demands as upstream changes. **Atlas application:** develop our own integration locally, explain useful findings in the appropriate discussion, and offer a focused upstream issue only when a general defect is demonstrated. Acceptance is a maintainer decision; a fork is not an upstream contribution by itself.

## The real problem and chosen prototype

[Discussion #1409][discussion], opened on 10 November 2026, describes a project with approximately 150 architectural decision records. Renamed concepts and increasingly complicated supersession chains were overloading agent context. At inspection it was unanswered in GitHub's accepted-answer sense, although replies already offered useful guidance about glossary entries, decision thresholds and loading only relevant areas. This prototype supplements that guidance; it does not claim to resolve the questioner's actual repository.

The selected experiment is **a decision-context builder**, documented separately in [DECISION_CONTEXT.md](DECISION_CONTEXT.md). Its intended contract is a standard-library Python `build`/`check` interface over an explicit sidecar catalogue. Selection should retain accepted current decisions for a requested scope and global decisions, validate the supersession graph, record hashes of full selected source texts, and check drift against the original manifest and sources. Missing references, cycles, ambiguous successors and oversized output should fail visibly. It should report unspecified records rather than infer their status from prose.

The implementation now has 31 passing decision-context tests. Its synthetic trial selects two complete records from 150, retaining 201 of 16,045 source bytes, and detects six deliberate negative cases. Independent review found four defects before publication; their regression tests now pass. These results concern the declared local contract, not improved agent reasoning in an external project. The builder neither judges whether a decision was wise nor rewrites or deletes historical records. The synthesis is explicit decision status plus selective context plus change detection.

## Three bounded next trials

1. **Review receipts:** exercise separate standards/specification results against one small change. Inject a changed head, changed specification and missing evidence; measure whether stale approval is rejected.
2. **Sandcastle execution:** run one disposable maintenance branch with an explicitly selected sandbox and bounded execution. Inspect cancellation, preserved work and output-validation failures before considering unattended integration.
3. **Teaching cases:** turn one verified incident into an original Atlas exercise, a solution and an unseen transfer case. Record what the learner actually demonstrates, including failures.

Each trial should state its baseline, expected behaviour, observed result and limits. Claims about wider effectiveness require matched comparisons and real users, beyond a successful demonstration.

[skills]: https://github.com/mattpocock/skills/tree/5863806dd4e15c63174bee4e7515a4256792ecfa
[sandcastle]: https://github.com/mattpocock/sandcastle/tree/0ed674e5195b200d34bc4128eec33409f2952dcf
[ts-reset]: https://github.com/mattpocock/ts-reset/tree/81b3b2614a32e47948cd4b8d5468879c07c2b361
[dictionary]: https://github.com/mattpocock/dictionary-of-ai-coding/tree/8a56b8ae80dd184f83a958e898516bff52653633
[tutorial]: https://github.com/total-typescript/beginners-typescript-tutorial/blob/main/README.md
[review]: https://github.com/mattpocock/skills/blob/5863806dd4e15c63174bee4e7515a4256792ecfa/skills/engineering/code-review/SKILL.md
[output]: https://github.com/mattpocock/sandcastle/blob/0ed674e5195b200d34bc4128eec33409f2952dcf/docs/guide/structured-output.md
[branches]: https://github.com/mattpocock/sandcastle/blob/0ed674e5195b200d34bc4128eec33409f2952dcf/docs/guide/branch-strategies.md
[tdd]: https://github.com/mattpocock/skills/blob/5863806dd4e15c63174bee4e7515a4256792ecfa/skills/engineering/tdd/SKILL.md
[ratchet]: https://github.com/mattpocock/sandcastle/commit/0ed674e5195b200d34bc4128eec33409f2952dcf
[teach]: https://github.com/mattpocock/skills/blob/5863806dd4e15c63174bee4e7515a4256792ecfa/skills/productivity/teach/SKILL.md
[contributing]: https://github.com/mattpocock/skills/blob/5863806dd4e15c63174bee4e7515a4256792ecfa/CONTRIBUTING.md
[scope]: https://github.com/mattpocock/skills/blob/5863806dd4e15c63174bee4e7515a4256792ecfa/SCOPE.md
[discussion]: https://github.com/mattpocock/skills/discussions/1409

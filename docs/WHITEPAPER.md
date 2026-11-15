# Who writes the agent's operations manual?

## Revisioned procedures, replay and the limits of retained experience

Albert Tan Sin Hon · Atlas Opsbook · Expanded design paper, 15 November 2026

**Source boundary.** This account describes the public source at
[`a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5`](https://github.com/Albertito-AI/atlas-opsbook/tree/a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5).
The project remains a public alpha. Current source includes components added
after the published 0.1.1 archive; this paper does not replace that archive or
report a new experimental evaluation.

## Abstract

An agent may retain a conversation without retaining a reliable procedure for
its next task. Atlas Opsbook addresses a narrower problem: how a project can
record an incident, formulate a conditional obligation, test its routing on
labelled cases and retain an accepted revision. The implementation separates
the wording of an instruction, the conditions selecting it, the check it names
and the authority to execute that check. A bounded deterministic learner can
propose conditions; replay rejects proposals that introduce a new recorded
error. Revision and case identities prevent stale promotion, while rollback
retains the history of a rejected experiment. Additional local tools prepare
decision context, check distribution bytes, assemble incident observations and
study recovery from uncertain effects. The supplied exercises demonstrate
specific software behaviour on public synthetic cases. They do not establish
improved model reasoning, general transfer, production reliability or a
productivity multiplier. This paper explains the implemented method, gives a
worked counterexample and specifies what a stronger empirical claim would need.

## 1. The problem and intended contribution

A reliable colleague can tell the next person what went wrong and when a remedy
matters. A coding agent faces the same practical question when its context ends.
A transcript preserves observations but does not necessarily identify which
obligation should govern later work. An unqualified instruction can also be
harmful: requiring a package installation for every release obstructs a release
containing only reading notes.

Opsbook turns this question into an inspectable local data model. Its concrete
contribution is a revisioned manual whose conditional checks can be compared
against explicit cases before adoption. It persists procedures outside the
model. It neither updates model weights nor establishes that an agent will read,
understand or obey the resulting manual. The intended users are agent builders,
maintainers investigating recurring mistakes and educators teaching the scope
of a generalisation.

The implementation distinguishes four questions:

| Question | Object used to answer it | Remaining judgement |
| --- | --- | --- |
| What happened? | A case and its evidence reference | Whether the observation is reliable and the label appropriate |
| When should a check apply? | A conjunction of context values | Whether the vocabulary captures the relevant circumstances |
| What should be checked? | A named check and explanatory instruction | Whether the actual check is adequate |
| Who may execute it? | The owner's environment and reviewed command mapping | Whether the action is authorised now |

Acceptance of a manual revision does not independently verify the truth of an
observation, the adequacy of a check or the authority to execute it.

## 2. Cases, rules and bounded inference

A case contains an identifier, a `practice` or `exam` label, categorical context,
an expected set of checks and an evidence reference. A rule contains an
identifier, its `when` conditions, one check identifier, an instruction and a
matching practice case as its basis. An optional replacement identifier permits
revision of an active rule. The [implementation][implementation] rejects
duplicate contexts under different identifiers; renaming the same example does
not create a separate case.

Let $x$ denote a context and $R$ a manual. A rule matches when every declared
field equals the corresponding value in $x$. A missing field fails to match.
The prediction $P_R(x)$ is the set of checks prescribed by all matching rules.
This is categorical routing. It contains no semantic interpretation of the
instruction's prose and cannot express sequence, duration or causation.

The learner starts with one missed check in a practice case. It enumerates
conjunctions of one to three fields drawn from that case. A candidate is excluded
if it matches a practice case whose expected set omits the check. Remaining
candidates are ranked by the number of practice cases in which they add the
selected missing check, then by fewer conditions, then by a stable lexical
tie-break. This describes the actual `learn` ranking. A case may still contain
other missing or unnecessary checks after that gain. A person can author a
longer conjunction directly.

The learner selects conditions using practice cases only. The exam partition
participates in subsequent replay and promotion. However, both partitions are
public local data. The names do not create a confidential examination boundary,
and repeated observation of exam outcomes can inform later proposals. After
inspection, those examples should be treated as regression fixtures.

## 3. Replay and acceptance

For a labelled case with expected check set $Y$, define its error set as
$E_R(x)=P_R(x)\mathbin{\triangle}Y$, where the symmetric difference contains
both missing and unnecessary check identifiers. Replay records which errors a
proposal fixes and which it introduces. In each partition, acceptance requires:

1. At least one recorded error is removed.
2. No new check-level error is introduced on any case.
3. At least one already-correct case remains correct and unchanged in its checks.

A total score alone could conceal an unnecessary new check behind a larger
improvement elsewhere. These conditions instead retain each changed decision.
They are conservative tests of the supplied corpus, not a statistical guarantee
of future performance. Incorrect labels, sparse contexts and repeated adaptation
to public cases can still produce a favourable replay.

A draft records the active manual revision and a digest of the case corpus.
Promotion rechecks both and performs replay and revision creation in a database
transaction. A changed manual or corpus requires a fresh proposal. Rollback
creates a new revision containing an earlier rule set; it preserves the previous
experiment instead of erasing it. The [core tests][core-tests] cover stale
proposals, changed cases, concurrent promotion, rollback and a regression hidden
inside an already-incorrect case.

## 4. Worked example: an installation rule that is too broad

The [supplied corpus][cases] has four practice cases and four further public
synthetic replay cases. The two positive practice cases ship packages. The
negative cases ship a guide and inspect an existing package. The context needs
both `task = ship` and `artefact = package`: either field alone would include an
unnecessary check.

| Replay context | Expected check | Empty manual | Every shipped item | Shipping a package |
| --- | --- | --- | --- | --- |
| Ship a package on macOS | `install-clean` | Missing | Correct | Correct |
| Ship a package on FreeBSD | `install-clean` | Missing | Correct | Correct |
| Ship a guide on macOS | None | Correct | Unnecessary | Correct |
| Inspect a package on FreeBSD | None | Correct | Correct | Correct |

The empty manual is correct on two of these four contexts. The overbroad rule
is correct on three but introduces an error for the guide, so promotion is
refused. The conjunction is correct on all four and preserves the negative
controls. These numbers describe the committed [replay fixture][replay], not a
new study or an estimate of general accuracy.

The [archive exercise][package-trial] then connects the selected check to an
actual local process. It creates a ZIP whose module is mispackaged. With the
empty manual, verification selects no command. After promotion, an isolated
Python import fails on the broken ZIP and succeeds after the module is restored.
The fixture checks the importability of this small archive. It does not test a
complete package installation, dependency resolution or every distribution
format; the check's name must not enlarge its observed coverage.

This distinction is essential: routing the right check and implementing an
adequate check are separate engineering obligations. A production packaging
procedure may require a clean environment, installation of the final wheel and
tests outside the source checkout. The operator must supply and review those
commands for the actual project.

## 5. Current architecture and responsibility boundaries

The manual is the core component. Other modules support evidence preparation or
bounded execution experiments; they do not automatically turn an observation
into an accepted rule.

| Component | Implemented purpose | Important limit |
| --- | --- | --- |
| `opsbook.py` | Store cases, propose or infer rules, replay, promote, render and restore the manual | Labels and evidence references are trusted inputs; prose quality is not evaluated |
| `decision_context.py` | Select explicitly accepted decisions by scope and check catalogue/source freshness | Structural selection does not establish semantic consistency, sufficient policy coverage or authority |
| `artifact_integrity.py` | Check listed files against expected lengths and hashes using bounded reads | Only listed bytes are covered; matching hashes do not establish authenticity or scholarly validity; POSIX features are required |
| `incident_timeline.py` | Preserve supplied observations, normalise supported timestamps and retain undated entries | Chronology does not infer causation or establish capture completeness |
| `execution_queue.py` | Record local tickets, leases, fences and uncertain effects | Same-host bookkeeping does not launch agents, cancel remote requests or create global permission |
| `execution_adapter.py` | Invoke a trusted synchronous worker and reconcile an observed outcome through a host contract | Production host binding, external-effect controls and quiescence evidence remain separate responsibilities |
| Reconstruction exercise | Compare hypotheses against an owned local target and preserve finite observations | Public probes do not establish universal equivalence or a blind benchmark |

The implementation guides supply the contracts and platform conditions:
[decision context][decisions], [artifact integrity][integrity],
[incident timeline][timeline], [execution queue][queue],
[trusted-host adapter][adapter] and [reconstruction][reconstruction].

The queue admits at most six occupied local tickets and one occupied effectful
ticket. An uncertain effect retains ownership until appropriately reconciled.
The adapter requires a durable canonical hold before effectful invocation and
independently observed outcome and old-attempt quiescence before resolution.
An expired lease cannot establish that an earlier request will never finish.
These components do not claim exactly-once external effects or a deployed fleet.
SQLite's documentation explains its single-writer transaction model and the
additional hazards of direct database access over network filesystems.[^sqlite]

The core `verify` command executes operator-supplied argument vectors with the
current user's privileges, without a shell, and with a timeout per check. Learned
prose does not supply an executable command. The distinct `gate` command compares
declared completed check names; it does not execute or independently confirm
them. A context matching no rules yields an empty check list, which can pass.
The operator must therefore consider whether the manual provides sufficient
coverage before interpreting a successful gate.

## 6. Evidence map and reproduction

The following map binds claims to the inspected source revision. Tests are
executable specifications with finite coverage. Their presence is separate from
evidence that a particular run succeeded.

| Claim or question | Inspectable evidence | Appropriate interpretation |
| --- | --- | --- |
| How conditions are ranked and proposals accepted | [`learn`, `trial` and `assess`][implementation] | Implemented rule selection and corpus-level criterion |
| Can an overbroad rule pass by increasing the total score? | [Core tests][core-tests] and [replay fixture][replay] | Specific adverse examples are rejected |
| Does a selected check detect an actual broken artefact? | [Archive exercise][package-trial] and its test in [the core suite][core-tests] | A deliberately faulty ZIP import can be detected |
| What was checked at earlier releases? | [Dated verification record][verification] | Historical observations with their original source and platform scope |
| Which upstream distribution is integrated? | [Pinned lock][lock] and [host integration guide][pstack-guide] | The named upstream revision and host-dependent entry points |
| How do newer tools fail and recover? | [Component guides](#5-current-architecture-and-responsibility-boundaries) and their linked tests | Stated bounded contracts and reproducible failure exercises |

For a fixed-source reproduction, use a separate checkout:

```sh
git clone https://github.com/Albertito-AI/atlas-opsbook.git
cd atlas-opsbook
git checkout a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5
python3 -m unittest discover -s tests -v
python3 opsbook.py demo
python3 examples/package_trial.py
```

The core requires Python 3.9 or later. The broader suite includes
platform-dependent filesystem/process checks and an optional Node comparison;
inspect skips and errors instead of reporting only the exit status. The queue's
default clock uses Linux boot identity. No model account is needed for the local
examples. Fetching and checking the separately pinned upstream distribution
requires Git and network access, as described in the integration guide.

Retain the source revision, runtime and operating-system versions, commands,
standard output/error, exit statuses and all skips with the reproduction record.
For a current-branch reproduction, record that branch's resolved commit instead.
Do not combine results from different commits under one undated total.

## 7. Related work and attribution

Lauren Tan's pstack supplies engineering skills, playbooks, reflection and
host-specific execution workflows. Opsbook's [locked distribution][lock] points
to commit `2776ddd2355d6d6c8747d3964600f28daf62f049` of `cursor/plugins`.
Opsbook adds its local obligation model and replay criterion alongside that
upstream work. The [integration guide][pstack-guide] identifies which features
require the original host, tools or model configuration. Upstream authorship and
licence remain distinct from original Opsbook code.

Reflexion studies linguistic feedback retained in memory without updating model
weights.[^reflexion] Voyager combines an automatic curriculum, executable skill
library and feedback in Minecraft.[^voyager] Both make persistent experience a
relevant research direction. Their empirical findings apply to their systems and
tasks; neither establishes that Opsbook's simpler conditional rules improve an
unseen project. Opsbook's inspectable check routing also differs from evaluating
the semantic usefulness of an unrestricted reflection.

Cemri and colleagues analyse failures in multi-agent systems, including system
design, coordination and task verification.[^mast] Their published dataset and
taxonomy support asking which failure an intervention actually addresses.
Increasing the number of agents does not itself validate a manual or provide
independent labels. The NIST generative artificial intelligence profile offers
a broader voluntary framework for governance, provenance, testing and incident
disclosure.[^nist] It informs the questions a responsible evaluation should ask;
this project does not claim certification or demonstrated conformity.

These are relevant comparisons, not an exhaustive novelty review. The separate
[ecosystem study][ecosystem] records further inspected software inspirations,
licence boundaries and implementation status.

## 8. Threats to validity and proposed evaluation

**Construct validity.** Routing correctness is a property of expected check
names. It is not the same outcome as successful work, an understandable
instruction or a useful check. An evaluation should measure completed artefacts
and escaped defects as well as routing.

**Internal validity.** A rule author who also chooses exam labels can manufacture
success. Shared prompts, models and evidence can produce correlated reviewer
errors. Extra inference effort or a more experienced reviewer can explain an
apparent benefit attributed to retained procedures. Record these conditions and
use independently prepared task labels where possible.

**External validity.** Eight visible synthetic contexts cannot support claims
across repositories, languages, domains or changing environments. Sparse
categorical contexts may omit the factor that matters. Transfer should be tested
on separately prepared task families and later source versions, including cases
in which the learned procedure should not apply.

**Operational validity.** A valid local rule may be ignored; a trusted check may
be incomplete; evidence can become stale; a filesystem writer can replace both
data and digests. Process-crash tests do not establish every power-loss or
distributed-service guarantee. Keep those limits explicit in deployment claims.

### How to test a larger claim

A comparative study should freeze a pstack revision, model configuration,
resource budget, task families and scoring criteria before comparison. Compare
pstack alone with pstack plus Opsbook on paired tasks in separate repositories.
Balance order, isolate retained state between conditions and account for the
cost of writing, reviewing and maintaining rules. Useful ablations include a
static manual and retained instructions without replay, where ethically and
operationally appropriate. Score outcomes independently of the treatment label.

Report the denominator of attempted tasks, failures, unnecessary checks,
latency, operator intervention, resource use and uncertainty. Preserve adverse
results and disclose deviations from the planned protocol. A proposed multiplier
requires a named metric and credible baseline; no such result is reported here.

## 9. Questions for teaching and further investigation

1. Why does “ship a package” require two conditions in the supplied corpus?
   Give a near miss that defeats each one-condition rule.
2. If a new field is absent from a later task, what does the matcher do? Explain
   why the result does not establish that the task needs no checking.
3. Construct a proposal that improves the total number of correct cases while
   introducing a new check-level error. Explain the acceptance decision.
4. What independent observation would distinguish a poorly scoped instruction
   from a correctly selected but ineffective check?
5. Design a held-out task family that tests transfer rather than another spelling
   of the public examples. Identify possible leakage and correlated review.
6. After an external request times out, why are “not observed” and “cannot still
   happen” different claims? State what evidence would justify retry.

The practical research question is whether retaining appropriately scoped,
reviewed procedures reduces recurring defects without imposing excessive checks
or maintenance costs. This repository supplies a small, inspectable instrument
for investigating that question.

## References

[^reflexion]: Noah Shinn, Federico Cassano, Ashwin Gopinath, Karthik Narasimhan and Shunyu Yao, “Reflexion: Language Agents with Verbal Reinforcement Learning”, *Advances in Neural Information Processing Systems* 36 (2023). [Published proceedings](https://papers.nips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html).
[^voyager]: Guanzhi Wang and others, “Voyager: An Open-Ended Embodied Agent with Large Language Models”, arXiv:2305.16291v2 (2023). [Versioned paper record](https://arxiv.org/abs/2305.16291v2).
[^mast]: Mert Cemri and others, “Why Do Multi-Agent LLM Systems Fail?”, *Advances in Neural Information Processing Systems* 38, Datasets and Benchmarks Track (2025). [Published proceedings](https://proceedings.neurips.cc/paper_files/paper/2025/hash/b1041e52d3be19f0a9bc491657488e4a-Abstract-Datasets_and_Benchmarks_Track.html).
[^nist]: National Institute of Standards and Technology, *Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile*, NIST AI 600-1 (July 2024). [Full report](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf).
[^sqlite]: SQLite, [“Transaction”](https://www.sqlite.org/lang_transaction.html), sections 2.1–2.2; and [“SQLite Over a Network, Caveats and Considerations”](https://www.sqlite.org/useovernet.html). These explain relevant database behaviour; they do not certify this application.

[implementation]: https://github.com/Albertito-AI/atlas-opsbook/blob/a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5/opsbook.py
[core-tests]: https://github.com/Albertito-AI/atlas-opsbook/blob/a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5/tests/test_opsbook.py
[cases]: https://github.com/Albertito-AI/atlas-opsbook/blob/a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5/examples/cases.json
[replay]: https://github.com/Albertito-AI/atlas-opsbook/blob/a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5/examples/replay.json
[package-trial]: https://github.com/Albertito-AI/atlas-opsbook/blob/a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5/examples/package_trial.py
[verification]: https://github.com/Albertito-AI/atlas-opsbook/blob/a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5/docs/VERIFICATION.md
[lock]: https://github.com/Albertito-AI/atlas-opsbook/blob/a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5/upstream.lock.json
[pstack-guide]: https://github.com/Albertito-AI/atlas-opsbook/blob/a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5/docs/PSTACK.md
[decisions]: https://github.com/Albertito-AI/atlas-opsbook/blob/a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5/docs/DECISION_CONTEXT.md
[integrity]: https://github.com/Albertito-AI/atlas-opsbook/blob/a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5/docs/ARTIFACT_INTEGRITY.md
[timeline]: https://github.com/Albertito-AI/atlas-opsbook/blob/a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5/docs/INCIDENT_TIMELINE.md
[queue]: https://github.com/Albertito-AI/atlas-opsbook/blob/a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5/docs/EXECUTION_QUEUE.md
[adapter]: https://github.com/Albertito-AI/atlas-opsbook/blob/a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5/docs/EXECUTION_ADAPTER.md
[reconstruction]: https://github.com/Albertito-AI/atlas-opsbook/blob/a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5/docs/RECONSTRUCTION.md
[ecosystem]: https://github.com/Albertito-AI/atlas-opsbook/blob/a7b52a34c3d52eb95d2c0e545fb48d4320a2f4f5/docs/ECOSYSTEM_SYNTHESIS.md

# Learning across the Atlas ecosystem

Review date: 14 November 2026. This is a representative source review of 27 requested profiles, not an audit of every repository or a ranking of people. Commit links identify the inspected material. Recent activity, stars, a successful build and a top-level licence each answer different questions; none establishes fitness for a new use by itself.

## What this change implements

Three original, optional Python standard-library tools make evidence easier to inspect before an Opsbook rule is proposed:

| Tool | Observable result | Limit |
| --- | --- | --- |
| [Decision context](DECISION_CONTEXT.md) | Select declared accepted decisions by scope, retain their complete text and check for changed evidence | Explicit metadata is required; no semantic contradiction detection |
| [Artifact integrity](ARTIFACT_INTEGRITY.md) | Compare listed files with expected byte lengths and SHA256 values | Hash agreement is not authenticity; descriptor-relative checking requires POSIX |
| [Incident timeline](INCIDENT_TIMELINE.md) | Combine supplied JSONL observations, normalise known offsets and retain undated observations separately | Supplied evidence may be incomplete or incorrect; timestamps do not establish causation |

These tools do not execute the evidence they read, start agents, grant permissions, change live systems or promote rules automatically. Outputs can be attached to an Opsbook incident and reviewed alongside a counterexample. The existing repair-and-control promotion gate remains the authority for accepting a rule.

The synthesis is practical: combine small decision records, source-bound evidence and separately tested failure cases. No claim of a new algorithm, universal superiority or freedom from defects is made. The [Matt Pocock research fork](https://github.com/Albertito-AI/mattpocock-skills-atlas) retains its upstream attribution. The implementations here were written for Atlas; upstream skills were not silently installed.

## Profile findings

### Matt Pocock

[skills at 5863806](https://github.com/mattpocock/skills/tree/5863806dd4e15c63174bee4e7515a4256792ecfa) and [sandcastle at 0ed674e](https://github.com/mattpocock/sandcastle/tree/0ed674e5195b200d34bc4128eec33409f2952dcf) are MIT licensed. Useful patterns are small decision records, explicit standards and specifications, independent review, and checks that fail when a required comparison is unavailable. A typed result alone does not establish the truth of its contents. Some other educational repositories have no verified reuse licence, and several older tools are archived.

**Implemented:** the decision-context tool addresses the context-volume problem raised in [discussion 1409](https://github.com/mattpocock/skills/discussions/1409). Status is optional in the upstream short-record format, so Atlas uses an explicit catalogue rather than inferring acceptance from the existence of a file. A synthetic trial selects two relevant records from 150 and detects deliberate stale evidence. [Detailed learning review](POCOCK_LEARNING.md).

### TryGhost

[Ghost at c2617d0](https://github.com/TryGhost/Ghost/tree/c2617d08d01ccc96ce88f3f8bd99c9383b518a7b), [SDK at a6d8072](https://github.com/TryGhost/SDK/tree/a6d80727d4301f8275ed0125e34bee8c8a341922) and [GScan at afc49bb](https://github.com/TryGhost/GScan/tree/afc49bb4b35fb9a6ce39d74b593a8f0075a5d478) are MIT licensed. Ghost demonstrates a mature separation of publishing interfaces, compatibility checking and editorial state. Its documentation repository has separate restrictive terms; MIT in the application does not cover every associated asset.

**Proposed:** an offline announcement-draft adapter from the journal's already validated public catalogue. Preserve author names, canonical article links, corrected PDF hashes, licences and optional DOI values. Require an explicit staff author before constructing an upload-ready payload. Test stale `updated_at` values and replacement of relationship arrays. No CMS migration or live publication is included.

### paulmillr

[noble-hashes at 17cbd0b](https://github.com/paulmillr/noble-hashes/tree/17cbd0b0c9fad101aa03fe0a45035e98e917640c) and [noble-curves at e7316eb](https://github.com/paulmillr/noble-curves/tree/e7316eb26d4d052bd6786cd954c1ed33b8484ec0) are MIT licensed. The transferable discipline is small dependency surfaces, known-answer vectors, independent implementation comparisons and precise audit scope. A historical audit of one version does not automatically cover later releases.

**Implemented:** raw-byte artifact verification, including known vectors and a differential comparison with Node's crypto implementation when available. This does not add Noble as a runtime dependency or invent cryptography. Atlas Reweave's Python JSON rules must not be replaced by JavaScript parse/stringify: large integers and numeric distinctions can change the evidence.

### ChenBohan

[Quintic solver study at f84483f](https://github.com/ChenBohan/Robotics-Path-Planning-04-Quintic-Polynomial-Solver/tree/f84483fb41be1c472a2032165132b313bdbb29ec) illustrates a curriculum connecting equations, boundary conditions and executable results. Inspected educational material includes third-party ancestry and lacks a verified reuse licence. Several projects are historical coursework, which requires a different maintenance assessment from a supported library.

**Proposed:** write an original exact-arithmetic quintic exercise with independently checked endpoint derivatives and jerk integral. For unit rest-to-rest motion, test coefficients `[0, 0, 0, 10, -15, 6]`, integral 720 and the scale law `720 D²/T⁵`; a changed coefficient must fail. This proves a limited mathematical contract, not collision avoidance or vehicle safety.

### ihcsim

[sbsearch at eefdbde](https://github.com/ihcsim/sbsearch/tree/eefdbdec257d42fe4e777538eb9098dc5927387d), [hep-gen at be4113a](https://github.com/ihcsim/hep-gen/tree/be4113a2b7a28f8e30c7cda3c7588e1268e598c1) and [cpu_caps at 531578d](https://github.com/ihcsim/cpu_caps/tree/531578dd602b424bc18c54c89fffa59ce966bb1d) have Apache-2.0 terms. They offer focused examples of support evidence, incident investigation and capability probing. Other account repositories are forks of wider community projects. Older experimental backup/restore code should not become production recovery infrastructure without dedicated validation.

**Implemented:** an offline incident timeline with bounded inputs, complete source hashes, preserved duplicate observations and explicit unknown times. A static upstream documentation discrepancy in sbsearch's search-flag example is a candidate for a small contribution, pending a fresh reproduction and current contribution guidance.

### zhou-hao

Relevant organisational work includes Apache-2.0 [hsweb-framework at f2617a5](https://github.com/hs-web/hsweb-framework/tree/f2617a56d8b1d5b11e2bb504b8d419406eba7116), [JetLinks at 5b7dc84](https://github.com/jetlinks/jetlinks-community/tree/5b7dc8410b486ca65c74ac2d10b0561bccd88f63) and [reactor-ql at a13118a](https://github.com/jetlinks/reactor-ql/tree/a13118ab179061eb652f1e07086670931bb06e01). Attribute these to their projects and contributors. Useful patterns include bounded allocation, permission checks across an entire delivery path, context-aware cache identity and cancellation handling.

**Proposed:** synthetic message-delivery fixtures for wrong tenant, stale subscription, duplicates, altered payload and incomplete bytes. The new Atlas tools adopt bounded-input and explicit-error principles, but do not implement an IoT or tenant-isolation layer.

### xuyiqing

MIT [fect at eccc973](https://github.com/xuyiqing/fect/tree/eccc9731ad74d049b22a3e769393c6a6c47b33bd), [gsynth at f288aa2](https://github.com/xuyiqing/gsynth/tree/f288aa23697fa77791157a254c73eef6a351fbbf) and [interflex at 6e79e4f](https://github.com/xuyiqing/interflex/tree/6e79e4fc9db68c826c4e4f98a4e5c56888bd8fe9) connect research methods, diagnostics and software. Lessons include explicit estimands and assumptions, data-health checks, compatibility during consolidation and distinct rights for code, teaching materials and third-party figures.

**Proposed:** extend research-publication evidence with per-figure source, generator parameters, dataset rights, assumptions and known discrepancies. A passing software test does not validate a causal interpretation. Use the existing journal integrity machinery rather than creating a second incompatible manifest.

### jaehyukchoi

The relevant community project is GPL-2.0 [quants-net/PyFENG at c3e2e21](https://github.com/quants-net/PyFENG/tree/c3e2e21fdcb0a54e2f82186524a98321f1802b5c), with separately licensed paper examples. It demonstrates paper-to-code traceability, analytic-versus-numeric checks, convergence criteria and explicit pricing conventions. Static inspection found a test labelled for gamma that repeats delta calls; this is a test-coverage finding, not proof of an incorrect pricing implementation.

**Proposed:** optional conformance experiments in a separate environment, comparing independently written identities and finite-difference checks. Preserve licence boundaries and document tolerances, seeds and dividend/forward conventions. No trading edge or investment recommendation follows from agreement on synthetic cases.

### txyyss

Apache-2.0 [wallpaper-groups at bb706f3](https://github.com/txyyss/wallpaper-groups/tree/bb706f3ec435ff8f3a69eb93b70c44c5dcca7c97) and MIT software [opt-maze at bf552b4](https://github.com/txyyss/opt-maze/tree/bf552b4053a18ee9334c8a42f05fbb1151e3b40d) connect formal statements, constructive examples and visual explanation. Formal success proves the encoded statement under its assumptions. Paper and artwork rights need separate attention. Other examples have no verified licence or different terms.

**Proposed:** an original independent maze-witness checker before considering a generator. Validate topology and connectivity; distinguish validity from optimality. A documented Lean-version mismatch is a focused upstream documentation candidate, subject to rechecking the current files.

### bin456789

GPL-3.0 [reinstall at 8ac9db6](https://github.com/bin456789/reinstall/tree/8ac9db68f9bca0b26c4143b2f3e206f2aa342d6b) is useful for studying compatibility probes, stable target identity and recovery preparation. Its operational impact demands careful reading: the inspected debug option enables tracing, and a hold option can still lead to reboot. Neither establishes a dry run. No reinstall or privileged command was executed for this review.

**Proposed:** a pure-data maintenance-plan validator returning `blocked`, `needs_evidence` or `ready_for_review`, with recovery evidence and target identity. None of these statuses would authorise execution. Preserve a separate execution and approval boundary.

### neoeno

[toy-c-project-template at fa9e0c9](https://github.com/neoeno/toy-c-project-template/tree/fa9e0c9e79d880351fe232eee7067f34c6e57969) and related small systems examples are useful teaching references but have no verified reuse licence. Unlicensed public source is not a blanket permission to copy. Unlicensed status must also be distinguished from projects such as [wcarm64](https://github.com/neoeno/wcarm64/tree/f8f59ba1c24c7131aaa76783fb86e8a123462a83), which declares the Unlicense and acknowledges its port ancestry.

**Proposed:** original exercises showing why a check can print an error yet exit successfully, and why missing prerequisites must stop a dependent check. Static inspection of the Make check found this false-success pattern. The new Atlas CLI tests already exercise nonzero failure results; this does not establish that every ecosystem check is correct.

### zjffdu

Apache-2.0 [zeppelin_airflow at eb873b7](https://github.com/zjffdu/zeppelin_airflow/tree/eb873b70bbda8c18ff45b9ac0fe30684a03c67f4) and [pyzeppelin at 66b2942](https://github.com/zjffdu/pyzeppelin/tree/66b2942db0fbba8d4add7247bdeb29bf834bcb5a) connect notebooks to scheduled jobs through narrow adapters. Apache Zeppelin is a community project. Default-branch code dates from 2021/2022 despite later repository activity.

**Proposed:** a job-result contract covering missing steps, strict booleans, unknown/running/aborted states, immutable run identity and failure-preserving cleanup. Static inspection found empty paragraph results counted as successful, string `"False"` treated as true, and cleanup capable of masking a primary error. These are bounded test targets, not reproduced deployment incidents. Notebook examples and newer demos have separate or unresolved licence conditions.

### Carolinasgoncalves21

MIT [Pong-JavaScript at 140a9ee](https://github.com/Carolinasgoncalves21/Pong-JavaScript/blob/140a9ee068e9c44ff1452f532a446f0f284ccce1/sketch.js) separates motion, collisions, input and scoring into small teaching functions. The [digital-education portfolio at 2dc5088](https://github.com/Carolinasgoncalves21/Portfolio-EducacaoDigital2026/blob/2dc508853f445d7f0480f660c57997d802ebef43/index.html) also has MIT terms. Flashcard and adventure repositories are forks of silviosnjr and femascheti projects; their inspected reuse rights remain unresolved. These are educational examples, not evidence of a new game algorithm.

**Proposed:** an original Atlas School exercise separating a pure game-state transition from rendering. Replay synthetic inputs; require deterministic state, bounded paddles, one score per crossing and no movement while paused. Include keyboard operation and textual scores. The inspected opponent movement motivates boundary tests, but no runtime defect was reproduced.

### jtao1735

Verified [TDengine documentation work at 120bb96](https://github.com/taosdata/TDengine/blob/120bb96e049dd43aae4a9260ef62f731814fe64a/docs/zh/05-basic/01-model.md) connects measurements, resource labels and timestamp semantics. TDengine belongs to its organisation and contributors; current repository metadata identifies AGPL-3.0. The account's [SeaTunnel repository at 42bb012](https://github.com/jtao1735/incubator-seatunnel/tree/42bb0129327fef63e5e048baa7985b3d1b96ff30) is an Apache-2.0 fork of apache/seatunnel. Its time-series catalogue is also a fork, not an original collection of models or a licence grant for linked projects.

**Proposed:** extend existing maintenance-evidence fixtures with explicit timestamp units, resource identity and missing observations. Test deterministic ordering, declared duplicate handling and exclusion of future observations from past snapshots. Missing data must remain distinct from zero or health. No database deployment or source copying is required.

### alstn2468

The MIT [CPU scheduling simulator at 60a2069](https://github.com/alstn2468/cpu-scheduling-simulator/blob/60a2069cb90a6db1b2ccdc9374fd9a80cd3019e1/CpuSchedulingAlgorithmsModule/RR.h) makes classic scheduling policies inspectable. The Apache-2.0 [JSConf presentation at 7a7112e](https://github.com/alstn2468/2022-jsconf-presentation/blob/7a7112eb6de94f40bf92d96345652b83d45bcde1/README.md) credits Minsu Kim and Changhui Lee; notable libraries such as use-funnel are upstream forks. The separate localisation experiment has no verified reuse licence. Static inspection of the round-robin loop motivates arrival-eligibility and nonpositive-quantum checks.

**Proposed:** compare original local FCFS and round-robin models on identical synthetic maintenance jobs. Require no execution before arrival, correct idle gaps, positive quantum, conserved service time and deterministic ties. Report waiting and response times without dispatching agents or claiming an optimal scheduler. This teaches scheduling contracts before changing live maintenance coordination.

### MiryangJung

MIT [learn-go-with-tests-ko at e2a0ff3](https://github.com/MiryangJung/learn-go-with-tests-ko/blob/e2a0ff3f711499834351d663fa40065f01ad05b7/README.md) is a coordinated translation of quii/learn-go-with-tests despite its non-fork metadata. Preserve the original curriculum and translator credits. The [FOSSASIA image-load tracker at 7d07038](https://github.com/MiryangJung/fossasia2026/blob/7d07038476c954722af54d96f1263f78ce8d559a/demo/hooks/useLoadTimeTracker.ts) illustrates measurement before performance claims, but has no verified reuse licence. Its accumulating average and simulator results do not establish cross-device superiority.

**Proposed:** an original offline summary of synthetic image-loading traces, recording sample count, failures, device/workload metadata, mean, median and a defined p95 calculation. Reject negative or nonfinite durations, preserve empty samples as unknown and separate cold from warm runs. Reuse Atlas's evidence records rather than deploying a mobile gallery.

### chenBingX

[SuperTextView at 058f4e2](https://github.com/chenBingX/SuperTextView/tree/058f4e2730f9c20c164ba5bd43b1cffb46948a41) combines replaceable image-engine interfaces with evidence about native release packaging. GitHub's licence field is null, but inspected source and README notices declare Apache-2.0; giflib retains separate attribution. [frefresh at 6176074](https://github.com/chenBingX/frefresh/tree/61760746a7f59ad4ef507dc952a551cc9376cca1) is an Apache-2.0 Fliggy-Mobile fork, not an original chenBingX framework. A packaged architecture and a runtime-tested architecture are different claims.

**Proposed:** extend existing Opsbook release checks with synthetic ZIP/manifest cases for missing required files, altered bytes, omitted notices and accidentally packaged test fixtures. Require separate fields for packaged platforms, executed platforms and tests not performed. This would complement artifact integrity without publishing a release, running native binaries or promising universal device compatibility.

### erhwenkuo

MIT [Deep Agents filesystem example at 1238bd3](https://github.com/erhwenkuo/deepagents-filesystem-example/blob/1238bd3f04a61d39b49f143049889bf1798bfffd/backends/sqlite_backend.py) exposes relational data through a read-only file interface. Its README credits a Python adaptation of Christian Bromann's TypeScript example despite non-fork metadata. MIT [mcp-searxng at 779409b](https://github.com/erhwenkuo/mcp-searxng/blob/779409b8d8ccba9307383187bf337809dc7d70b1/server.py) separates discovery from page retrieval. Static inspection shows its zero-count case does not enforce a zero-result bound.

**Proposed:** test Atlas's existing evidence readers against two local fixtures, with deterministic content and hashes, explicit pagination, unknown-path handling and rejection of write/edit/upload operations. Keep output storage separate from source evidence. This adopts a narrow storage contract without installing another agent framework, starting S3 services or enabling live web retrieval.

### eastroots92

The [DailyQT presenter at b7ec48b](https://github.com/eastroots92/DailyQT/blob/b7ec48bdcdc3af341945287787d3095039a97f51/app/src/main/java/openull/com/dailyqt/ui/main/MainPresenter.java) illustrates why declared behaviour needs contrasting-input tests: its date calculation remains a constant-return placeholder. No licence was found in that project's inspected tree. The MIT [property-data MCP tests at 030a16d](https://github.com/eastroots92/real-estate-mcp/blob/030a16d84b786028fef56806c8094a4c59d100ef/tests/mcp_server/test_apartment_trades.py) belong to a fork of tae0y/real-estate-mcp. Both clean-architecture examples are also upstream forks; their package declarations identify MIT terms.

**Proposed:** original local public-data fixtures exercising valid, cancelled, malformed and unavailable records through an injected adapter. Preserve source/query identity, distinguish no data from provider failure and reject a deliberately constant implementation. These would teach ingestion contracts without calling property APIs or copying unlicensed application code.

### nickliqian

Apache-2.0 [paddle_ocr_engine at 38e51ac](https://github.com/nickliqian/paddle_ocr_engine/blob/38e51acf1bf1335d2cd83da9b7bfa30ef0c9b60c/README.md) is a deployment wrapper around PaddleOCR, not an original OCR model. It retains confidence and text-region coordinates. Apache-2.0 [cnn_captcha at 2a3353e](https://github.com/nickliqian/cnn_captcha/blob/2a3353ef0f25f6faaa582bcde224dad0987087f4/README.md) distinguishes training accuracy from held-out results and inference time from request overhead. These are historical author-reported measurements. The newer tdxquant README declares MIT, although no root licence file was found.

**Proposed:** hand-authored OCR observation receipts for Atlas research evidence. Validate source hashes, page regions and confidence ranges; keep uncertain text explicitly unverified. A changed source, impossible polygon or invalid confidence must fail. No model download, paid OCR, trading integration or third-party access-control bypass is involved.

### SeanChenxy

[HandMesh at 3c87e95](https://github.com/SeanChenxy/HandMesh/blob/3c87e958d4855f890e3884ec94bcfc0f99422c3d/utils/zimeval.py) exposes metric coverage and transformation-consistency questions. Its root MIT licence does not erase the inspected evaluator's GPL-2.0-or-later notice. [Mimic3D at 77d3136](https://github.com/SeanChenxy/Mimic3D/blob/77d313656df3cd5536d2c4c5766db3a56208eea6/training/dual_triplane.py) acknowledges NVIDIA EG3D ancestry and includes a proprietary file notice despite root MIT terms. These are coauthored research implementations; external datasets and models need separate rights checks.

**Proposed:** a research-evaluation receipt beside the existing artifact verifier, retaining source/checkpoint/config hashes, metric units, thresholds, denominators and evaluated/skipped/failed states. Synthetic CPU fixtures should reject missing metrics, preserve partial coverage and test declared chunking or transformation invariants. Disabled evaluation cannot become a passing result; no GPU experiment or paper reproduction is claimed.

### ZhuLinsen

Apache-2.0 [PatchLoop at 03eb09b](https://github.com/ZhuLinsen/patchloop/blob/03eb09b2248b60be2205dee6db33e2a80f20aae6/autocode/agent/autocode_state_store.py) makes task claims, retries and recovery explicit. Its instance-local lock and JSON persistence do not demonstrate safe coordination across independent processes. Apache-2.0 [MiniAgent at 25d87da](https://github.com/ZhuLinsen/MiniAgent/blob/25d87daff9a789713cb4aa56b4b689a6ebcb48cb/miniagent/agent.py) bounds execution steps and records uncertain effects after interrupted non-read operations. Its policy checks are not an operating-system sandbox. These selected projects are non-forks; account copies of vLLM and LangChain are forks.

**Proposed:** fake-tool state-machine tests for duplicate dispatch, stale claim owners, expired leases, invalid arguments and capped retries. Interrupted effects must remain uncertain. Connect resulting receipts to Opsbook and its incident timeline before considering broader worker deployment. No 50-agent concurrency guarantee follows from these examples.

### xahlee

[xah-fly-keys at e526d02](https://github.com/xahlee/xah-fly-keys/blob/e526d025425776a47987369c490e26f33a8b35cf/xah-fly-keys.el) declares GPL v3 in its source header despite null GitHub licence metadata. Its modal design and discoverable help illustrate explicit interaction state; contributor credits remain relevant. MIT [PlaneCurveFormulas at b38da64](https://github.com/xahlee/PlaneCurveFormulas/blob/b38da64fc7937a2c2244ba356e4bcac22e6a3705/PlaneCurveFormulas.wl) pairs named functions with parameter ranges and executable examples. These observations do not establish ergonomic superiority or complete mathematical correctness.

**Proposed:** check the existing decision-context, incident-timeline and artifact-integrity documentation examples against actual CLI help and temporary fixtures. Require documented files and exit codes; deliberately stale flags and unsupported combinations must fail. Learn the interface discipline without copying GPL code into MIT modules or adding a Wolfram runtime dependency.

### helensouz

[task-flow at be49784](https://github.com/helensouz/task-flow/blob/be49784fc061bf783a743279d2aea82c7dc56051/src/app/features/Task/task.service.ts) separates an Angular client from an Express backend, but static inspection found a client path differing from the registered server route and several empty operations. The [Spring controller at 804decf](https://github.com/helensouz/taskflowdemo/blob/804decf8f0c822c95b83f9fc6cab92646f0bfba5/demo/src/main/java/controller/TaskController.java) illustrates constructor-injected persistence. An application-startup test does not establish CRUD correctness. Neither inspected project supplied a verified reuse licence.

**Proposed:** an original dependency-free task-API teaching fixture for Atlas maintenance. Test a valid lifecycle alongside mismatched paths/methods, unknown identifiers and omitted update behaviour. Require observable state changes, not merely a present test file or successful context load. These source findings were not reproduced by installing or running the upstream applications.

### pbakaus

MIT [agent-reviews at 5c85f14](https://github.com/pbakaus/agent-reviews/blob/5c85f14cad5d2233883f991faf9312ddc807c063/lib/checks.js) associates checks with the current PR commit and distinguishes missing checks, timeout and conflicts. Apache-2.0 [Impeccable at 5ffe90b](https://github.com/pbakaus/impeccable/blob/5ffe90b8403424a0888e0575bc1fb90517c7af74/README.md) acknowledges Anthropic frontend-design ancestry and separates source inspection from rendered-page review. Its installation and execution defaults require separate review; this audit installs nothing.

**Proposed:** local maintenance-review snapshots producing ready, failed, pending, missing-check, changed-head and nonconvergent outcomes. A new commit must invalidate prior evidence, and absent required checks cannot pass. Declare Atlas's treatment of neutral/skipped checks rather than inheriting upstream defaults. Bound repeated fix/review rounds, retain finding identity and avoid automatic posting or merging. Inspected tests were not executed here.

### poteto

Lauren Tan's MIT [pstack at 2776ddd](https://github.com/cursor/plugins/tree/2776ddd2355d6d6c8747d3964600f28daf62f049/pstack) is already integrated through Opsbook's lock, catalogue and source reader. The inspected [current upstream at 3dbd22f](https://github.com/cursor/plugins/tree/3dbd22ff12742fb28c9700b9760baa29ed41dc13/pstack) has identical pstack and generated harness trees, so retain the lock. Version 0.15.36 still contains 58 skills and 23 playbooks. poteto/plugins is a fork of cursor/plugins; pstack belongs to the latter. Her unlicensed verification example uses a fictional, unrelated Atlas.

**Proposed:** verify existing brief/propose/evaluate/promote/rollback behaviours using local fixtures and the already integrated maintenance workflow. Separate documentation drift, harness gaps and product defects. Reject invalid promotion and verify rollback restoration. Upstream welcomes focused PRs and requires regeneration of its harness copy after pstack changes; no duplicate integration is needed.

The [additional-profile evidence records](research/profiles.json) retain inspected commits, provenance, licence distinctions and proposal limits. These fourteen sections add no new dependency installation or live integration.

### morluto

MIT [REA at 6938696](https://github.com/morluto/rea/tree/69386962569de27a1201847bf50a8c9ea592c5bd) is particularly relevant to an evidence-driven learning workflow. Its [reconstruction ledger](https://github.com/morluto/rea/blob/69386962569de27a1201847bf50a8c9ea592c5bd/src/application/ReconstructionObligationLedgerEvaluation.ts) separates open, failed and verified obligations. Its authority tests require evidence applicable to the exact implementation and requirement revision; unit-test evidence cannot close a claim about a packaged process. These are inspected contracts and test intentions, not results of running REA here. Third-party notices and external-tool licences retain separate scope.

[Flameox at c7ea167](https://github.com/morluto/flameox/tree/c7ea167bf51bf10da9bc17a9ffc1124f4166f32f) makes retained and omitted observations explicit. [SmokingGun at cf3a387](https://github.com/morluto/smokinggun/tree/cf3a3872a2638a68d2d123126f98dfa84c85643d) records skipped source coverage. [GitContribute at 2c719af](https://github.com/morluto/gitcontribute/tree/2c719afc0b0ebd34e3fcf833076bdd82c4ac6443) checks research freshness before patching. [Jacobian at f693b76](https://github.com/morluto/jacobian/tree/f693b76a600f8ee0d95a4e429a53bb576e9aeac1) illustrates independent mathematical identities. All four declare MIT. Leantoken separately declares MIT OR Apache-2.0; a single API licence label missed that choice.

**Implemented:** [an original local reconstruction lesson](RECONSTRUCTION.md) compares competing hypotheses for a small text-normalisation contract, uses distinct discovery and held-out probes, preserves malformed-input outcomes and binds evidence to current source bytes. The method is to observe, hypothesise, discriminate, reconstruct and attempt to disprove the reconstruction. Finite agreement does not recover the original source or prove universal equivalence. [Detailed pinned evidence](research/morluto.json) covers eight representative repositories and the methodology. The [Atlas REA research fork](https://github.com/Albertito-AI/rea-atlas) preserves upstream attribution; REA itself has not been installed or executed.

## How Atlas should adopt and contribute

1. State a real user problem and measurable acceptance criteria before choosing a dependency or fork.
2. Inspect the actual implementation, its ancestry, file-level rights and supported environment. Pin the evidence.
3. Create a small independent baseline, a failure case and a control case. Distinguish source inspection from executed tests.
4. Compare alternatives under the same inputs. Record limits and rejected hypotheses alongside successes.
5. Integrate through the smallest stable interface. Reuse an existing Atlas component when it already supplies the required contract.
6. Review the exact proposed commit, run the applicable checks and merge only with evidence. Keep rollback and failure reporting explicit.
7. Return a focused bug report, test, documentation correction or useful discussion answer that respects upstream scope and contributor terms.

The next highest-value experiments are a publication-evidence adapter, a job-result contract and a worker-ownership exercise. Mathematical and performance experiments need separate domain-specific validation. They are proposals, not completed integrations. More repositories and more agent roles do not by themselves establish greater capability.

## Community participation and achievements

Galaxy Brain concerns useful GitHub Discussion answers accepted by eligible participants. Forks and merges do not establish eligibility. The reported numerical tiers are community observations, not a stable official contract. The current process should pursue accurate answers to real questions, and leave acceptance to the discussion's authorised participants.

References: [GitHub achievement introduction](https://github.blog/news-insights/product-news/introducing-achievements-recognizing-the-many-stages-of-a-developers-coding-journey/), [discussion participation and answer permissions](https://docs.github.com/en/discussions/collaborating-with-your-community-using-discussions/participating-in-a-discussion), and [GitHub Community's own achievement exclusion](https://github.com/orgs/community/discussions/106536). An external contribution or badge must be reported as completed only after its resulting state is verified.

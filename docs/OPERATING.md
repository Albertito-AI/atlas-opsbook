# Operating a project manual

The CLI runs inside the project whose manual you want to use. After installation, its entry point is `python3 .opsbook/bin/opsbook.py`. The examples below use `python3 opsbook.py` from the distribution root. Insert `--db PATH` before a subcommand to select a different book. These examples use disposable synthetic data.

## Teach the first procedure

```sh
python3 opsbook.py init
python3 opsbook.py record examples/cases.json
python3 opsbook.py propose examples/overbroad.json
```

Copy the returned proposal ID and run `python3 opsbook.py evaluate ID`. Under the exam case `release-notes`, the broad draft introduces an unnecessary package check. Attempting to promote it returns code 2. Drafts cannot change the active manual.

```sh
python3 opsbook.py learn missing-wheel install-clean 'Install the built package in a clean environment and import it.'
```

Copy the new ID and run the following, substituting that ID.

```sh
python3 opsbook.py evaluate ID
python3 opsbook.py promote ID
python3 opsbook.py manual
python3 opsbook.py brief '{"task":"ship","artefact":"package","os":"linux"}'
python3 opsbook.py revision 1
```

To write a rule directly, use the JSON shape in [the candidate example](../examples/overbroad.json). The agent chooses the instruction, its check name and the conditions. Add `"replaces":"existing-rule-id"` to revise an active procedure. The learner can also infer a conjunction of up to three equality conditions from labelled practice cases. An operator can author longer conjunctions. Missing context fields do not match.

## Collect useful cases

A case has a stable ID, a practice or exam set, observed context, expected check names, and a short evidence reference. Keep a test log, issue or reproduction under the owner's normal access controls. Give Opsbook its identifier and a sanitised observation. The software trusts those labels and references. An authorised reviewer should supply exam labels independently of the drafting agent. Both sets need at least one corrected decision and one correct unaffected control. Identical contexts under different IDs are refused.

Add near misses. A guide being shipped and a package being inspected expose different mistakes. Reserve additional projects or time periods for independent validation. Once an agent or reviewer has seen the exam outcomes, those cases are regression fixtures for subsequent iterations. The local files and database share one operating-system account and offer no secret examination boundary.

## Use an instruction during work

The handoff or checkout used by the next session must retain its database. To share a book, use an intentional, reviewed project transfer. Close active writers before copying the SQLite file. `manual` prints portable Markdown, `brief` selects applicable instructions and `revision N` returns the accepted rule set and its recorded comparison where available.

For an executable gate, the operator supplies a trusted JSON mapping from check names to executable argument vectors, for example:

```json
{"run-tests":["python3","-m","unittest","discover","-s","tests"]}
```

An applicable rule must prescribe that check name. Run `python3 opsbook.py verify '{"task":"test"}' --checks checks.json` from the intended working directory. Inspect the reported revision and checks. A context matching no rules yields an empty check list. Unmapped checks and malformed commands fail closed. The command executes with the current user's privileges, without a shell, and has a sixty-second timeout per check. Configure reviewed local commands only. Learned prose cannot supply executable commands.

`gate CONTEXT --done CHECK ...` is a separate declaration-based check for work already verified by another trusted system. It compares names only. Status 0 means all applicable checks passed or were declared, 1 means an applicable check failed or is missing, and 2 indicates invalid input, state or a refused promotion. `evaluate` returns the comparison on stdout, including `eligible`.

## Recover or contest a rule

View `history`. Restore revision 0 with `rollback 0 "The rule obstructed an unrelated task"`. A rollback creates a new revision and preserves the earlier accepted rule and its evidence. Replaying an identical promotion or the most recent rollback is safe. A change in the case corpus or active revision invalidates an unpromoted draft. Recreate it and rerun evaluation. Reinstating an old revision is an explicit operator action. A new counterexample can motivate a narrower replacement. Editing wording alone has no measurable effect on this routing test and needs separate behavioural evaluation.

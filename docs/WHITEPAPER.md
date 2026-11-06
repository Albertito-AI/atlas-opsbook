# Who writes the agent's operations manual?

Albert Tan Sin Hon · Atlas Opsbook · Public alpha, 6 November 2026

A reliable colleague can tell the next person what went wrong and when the remedy matters. A coding agent faces the same practical question when its context expires. A transcript can preserve the entire conversation and still leave the next session to discover which part should govern its conduct. A project manual gives that judgement a durable form. Giving the agent authorship raises a further question. What earns one of its sentences a place in the manual?

## An instruction has a domain

Suppose a release passes its source tests and the delivered package fails to import. “Test every release by installing it” seems sensible until the next release is a set of reading notes. “Test every package” would also slow a colleague who merely inspects metadata. An operator can express the narrower obligation as a pair of facts, shipping and package, with a required check. Those facts and the check can be evaluated separately from the agent's choice of words. This distinction also limits the conclusion. Successful routing says little about whether a vague instruction can be followed well.

## What may change

A case names the relevant circumstances, the expected checks and the evidence for the judgement. A proposed rule binds a conjunction of those circumstances to an action and an explanation. An agent can write both itself. For a missed action it can instead ask a small deterministic learner to enumerate candidate conjunctions from the practice case. The learner excludes candidates that assign the action to negative practice examples. It favours greater practice coverage, then the shorter condition, with a stable tie-break. It never uses exam labels to choose its condition.

A separate replay compares the current and proposed manuals. Each case has an expected set of checks. The symmetric difference from the prescribed set counts missed and unnecessary checks separately. A proposal must remove an error on each split, introduce none on any case, and preserve a correct control on each split. A net score could conceal a newly introduced mistake. Recording the changed decisions enables the owner to examine that mistake directly.

## Responsibility and recovery

An instruction is a claim about how this project should operate. Its adoption changes the local manual. Permission to deploy, purchase services or disclose data comes from the owner and execution environment. A project should have an independent source of labels whenever the consequences matter. A learner with write access to both the rule and its examination can manufacture a favourable result. The ordinary local filesystem in this release cannot establish independence.

The accepted revision records its source proposal and case digest. Replay and promotion share a transaction. A second session arriving with an obsolete candidate must start again from the current manual. Restoring an earlier set of rules makes a new revision, leaving a record of the failed experiment. An owner can export the text, inspect the recorded comparison and choose which local commands may run.

## Relationship to pstack

Lauren Tan's pstack already supports reflection, personal modes, evaluation and verification playbooks. It provides the engineering work in this design. Atlas adds a data model for local obligations, a replay criterion and a way to put the accepted instructions into the next session. Keeping upstream versioned separately acknowledges authorship and lets an operator inspect the exact behaviour on which a project depends.

## Value and limits

A small team can retain the lesson from a packaging incident, and a teacher can show students exactly why a generalisation fails. A project could equally record which source documents an editor needs to inspect before accepting a factual change. In each case the judgement about the appropriate check must come from the people or evidence qualified to supply it.

Sparse cases, mislabelled evidence and leaking exam questions can all produce an apparently successful rule. Equality conditions cannot express sequence, duration or causation. Two projects may use the same label for different things. A check can be badly implemented. A future agent can ignore its manual. Each failure calls for a different observation. Adding more prose or more cases indiscriminately will not resolve it.

## How to test a larger claim

Freeze an upstream pstack version, a model configuration and a set of unseen tasks before comparison. Run pstack alone and pstack with Opsbook on paired tasks in separate repositories. Balance run order, isolate carry-over between conditions and log learning costs as well as execution costs. An independent assessor should score completed work, escaped defects, unnecessary checks, latency and operator intervention using criteria fixed before the runs. Publish denominators, failures and uncertainty. A twentyfold improvement needs a named metric, a credible baseline and replication. The two small exercises shipped here establish a narrower result: a learned local procedure can change which check runs and detect a broken artefact.

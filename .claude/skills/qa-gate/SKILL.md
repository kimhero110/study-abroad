---
name: qa-gate
description: Quality gate process for the C stage of PRDCA. Use when defining or executing quality checks for implementation deliverables, including functional tests, data quality tests, RAG/AI evaluation, security testing, performance testing, defect triage, release blocking criteria, and whether work may move from Check to Act.
---

# QA Gate

Use this skill to run the C stage. The quality gate proves that implementation matches the approved plan and is safe to submit for acceptance.

Do not treat model agreement as test evidence.

## Deterministic Decisions

The C decision comes from these controls, not from narrative judgement:

```text
prdca validate    --input .prdca/evidence/delivery-evidence-pack.json --base-dir .
prdca arbitrate   --input .prdca/evidence/arbitration-input.json
prdca defect-check --input .prdca/evidence/defect-closure.json
prdca threshold-check --declared .prdca/reviews/thresholds.json \
                      --measured .prdca/evidence/threshold-results.json \
                      --manifest .prdca/reviews/frozen-packet.json
prdca gate --value .prdca/evidence/value-assessment.json \
           --evidence .prdca/evidence/delivery-evidence-pack.json \
           --arbitration .prdca/evidence/arbitration-input.json --base-dir .
```

Read the exit code: `0` pass, `2` block, `3` human review. A non-zero exit code is the decision.
Run `prdca defect-check` before closing any P0/P1 defect; an unverified root cause or missing
sibling-surface audit blocks closure. Templates for each input are in `.prdca/framework/templates/`.

When the work package declared a delivery decomposition, acceptance is incremental and
bottom-up — accept leaves during D, and let C check closure instead of re-verifying
everything:

```text
prdca accept  --root . --decomposition .prdca/evidence/decomposition.json \
              --results .prdca/evidence/acceptance-results.json
prdca closure --root . --decomposition .prdca/evidence/decomposition.json
```

`accept` verifies one leaf against the criteria the decomposition declared before work
began: every dominant item met, every general item within its declared numeric target.
A leaf whose covered dependency is not yet accepted cannot be accepted — covered work
must be verified before anything is built on top of it. A decomposition edited after
acceptance began blocks. `closure` is the C-gate feed: every leaf under the root must
hold an acceptance record, and its passing output is the evidence `prdca advance --to C`
consumes.

Capture test evidence at the source instead of writing it into the pack by hand:

```text
prdca evidence run --pack .prdca/evidence/delivery-evidence-pack.json \
                   --test-id TST-001 --requirement REQ-001 -- <actual test command>
prdca evidence attach --pack .prdca/evidence/delivery-evidence-pack.json --path <artifact>
```

`evidence run` executes the real command and records passed or failed from its exit code —
the recorded status cannot disagree with what the command did. `evidence attach` computes
artifact hashes; never type a sha256 by hand.

## QA Inputs

Require these before testing:

- Approved R decision and plan package
- Implemented artifacts and change summary
- Requirement-to-test mapping
- Test data and expected outcomes
- Self-test report from implementation team
- Known issue list
- Deployment or run instructions
- Delivery Evidence Pack with requirement-to-change and requirement-to-test mappings
- Independent review artifacts required by the risk route

If these are missing, return to D for completion.

## Test Lanes

Evaluate each applicable lane:

- Functional: approved user scenarios, API behavior, UI behavior, workflows
- Data quality: parse success, field completeness, accuracy, consistency, deduplication
- Knowledge quality: entity/relation correctness, ontology compliance, traceability
- AI/RAG quality: answer correctness, citation accuracy, refusal behavior, hallucination rate
- Security: authentication, authorization, data isolation, injection, secrets, audit logs
- Performance: latency, throughput, batch processing time, concurrent usage
- Reliability: retry behavior, failure handling, backup, restore, idempotency
- Usability: task completion, confusing flows, visible error states
- Regression: existing critical paths still work
- Documentation: setup, operation, troubleshooting, known limits
- Skill quality: structure validation, trigger precision, forward tests, overlap, safety, and measured reuse benefit
- Evidence quality: pack completeness, artifact identity, dissent preservation, and arbitration result
- Test independence: supplemental tests derived from requirements without implementation-led expected answers

## Default Release Thresholds

Use project-specific thresholds when provided. Otherwise propose thresholds before testing, such as:

- Core end-to-end workflows pass: 100%
- P0/P1 defects open: 0
- High-risk security findings: 0
- Document parse success for supported samples: >= 95%
- Key field extraction accuracy: >= 90%
- Evidence citation accuracy for AI answers: >= 95%
- RAG answer correctness on evaluation set: agreed target before test
- Performance meets agreed response-time and batch-time limits
- Changed project skills pass structural validation and at least two realistic forward tests
- Required independent review slots are satisfied or explicitly escalated
- Delivery Evidence Pack validation and evidence arbitration permit A

Do not invent a passing grade after seeing the result.

Numeric thresholds are bound by time, not by promise: declare them in a threshold declaration
during P, freeze that file into the review manifest, and at C run `prdca threshold-check` with
the manifest. A declaration edited after freezing, an unmeasured threshold, or a missed target
blocks. A measured value with no declared threshold cannot count toward the gate.

## Defect Severity

Classify defects:

- P0: system unusable, data loss, severe security issue, or false critical business conclusion.
- P1: core workflow broken, major data/AI correctness issue, privilege bypass, or release blocker.
- P2: important but workaround exists.
- P3: minor defect, polish, documentation gap.

P0 and P1 block A. P2 blocks A only when it affects agreed acceptance criteria or risk tolerance.

## Decision Rules

Use these decisions:

- Pass to A: all blocking gates pass and residual risks are documented.
- Return to D: any blocking defect or missing evidence remains.
- Return to P: failures show the approved plan, acceptance criteria, architecture, data model, or AI approach is wrong.

Return to P instead of D when repeated fixes cannot address the root cause.

## QA Output

Produce a quality report with:

- Decision: pass to A, return to D, or return to P
- The commands that produced the decision and their exit codes
- Test scope and exclusions
- Lane-by-lane results
- Defect list with severity and owner
- Metrics versus thresholds
- Residual risks
- Evidence links or artifact names
- Explicit statement whether A may start

Use evidence-based language. Avoid saying a feature is acceptable without a test or rationale.

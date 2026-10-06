---
name: prdca-governance
description: PRDCA project governance for strict stage-gated delivery. Use when planning, starting, controlling, or auditing this project's Plan-Review-Do-Check-Act workflow, including project charters, stage gates, RACI ownership, decision rules, change control, and whether work may advance to the next PRDCA stage.
---

# PRDCA Governance

Use this skill as the process controller for this project. Enforce the sequence:

```text
P: Plan -> R: Review -> D: Do -> C: Check -> A: Act
```

Do not allow a stage to advance because it is convenient. Advance only when the gate evidence exists.

Use `.prdca/framework/governance/software-production-system.md` as the operating contract.

## Stage Ownership

Control P, D, and A here. Delegate R and C to their owning skills and do not restate their criteria:

| Stage | Owner | Decision source |
|---|---|---|
| P | This skill | `prdca value-check`, `prdca plan-check`, `prdca route` |
| R | `review-board` skill | `prdca gate` inputs prepared during R |
| D | This skill | Requirement-to-change mapping and self-test evidence |
| C | `qa-gate` skill | `prdca validate`, `prdca arbitrate` |
| A | This skill | `prdca gate`, `prdca report` |

Skill lifecycle questions belong to the `evolve-project-skills` skill.

## Deterministic Decisions

Never assert a gate outcome from narrative judgement. Run the control and report its output.

```text
prdca route        --input .prdca/evidence/risk-assessment.json  --output .prdca/reports/route.json
prdca value-check  --input .prdca/evidence/value-assessment.json
prdca plan-check   --input .prdca/evidence/project-plan.json
prdca decomposition-check --input .prdca/evidence/decomposition.json
prdca change-check --input .prdca/evidence/change-request.json
prdca gate --value .prdca/evidence/value-assessment.json \
           --evidence .prdca/evidence/delivery-evidence-pack.json \
           --arbitration .prdca/evidence/arbitration-input.json --base-dir .
prdca report --input .prdca/evidence/delivery-evidence-pack.json --as-of <timestamp>
```

Read the exit code: `0` pass, `2` block, `3` human review. A non-zero exit code is the decision.
Never restate a blocked result as a conditional pass.

Record every stage transition through the state machine — it is the only path a work
package advances on:

```text
prdca stage   --root . --wp WP-001
prdca advance --root . --wp WP-001 --to R --evidence .prdca/reports/p-gate.json
```

`advance` refuses skipped stages, simulated evidence, and any evidence file whose decision
is not a registered pass. Regressions to P or D require `--reason`. Do not declare a stage
change in prose that the state file does not record.

Templates for each input are in `.prdca/framework/templates/`.

## Core Rules

Apply these rules by default:

- Do not start P for a work package until `prdca value-check` passes.
- Use macro milestone IDs only for product outcomes; use bounded work-package IDs for implementation increments.
- Require end-to-end, workflow, or user-task evidence in every value assessment.
- Enforce WIP, blocked-decision propagation, direction review, and diminishing-return stop rules.
- R cannot start until P has a complete stage plan package.
- D cannot start until R is approved by all required reviewers.
- C cannot start until D is complete and self-tested.
- A cannot start until C passes all blocking quality gates.
- The next project stage cannot start until A explicitly approves it.
- A major change in scope, architecture, data, AI behavior, security, or acceptance criteria must return to P.
- The team that submits work cannot be the only team approving it.
- Every rejection must produce a concrete issue list and required corrections.
- Every approval must cite evidence, owner, date, and accepted residual risks.
- One primary AI remains accountable; optional reviewer AIs produce findings and never vote on the final decision.
- Parsing failure, unavailable reviewers, or missing structured output cannot count as approval.

## P Gate: Plan Complete

Require these artifacts before Review:

- Stage objective and non-goals
- PRD or requirement statement
- Technical architecture or implementation approach
- Data and knowledge design
- AI/RAG/model design when applicable
- Security and permission approach
- QA and acceptance criteria
- Delivery plan and role ownership
- Risk list and rollback plan
- Existing skill reuse and candidate assessment for repeated workflows
- Risk vector, review route, and initialized Delivery Evidence Pack
- Must requirements mapped to predeclared acceptance tests
- Threshold declaration for every numeric release criterion the C gate will use
- Delivery decomposition for L2 and above: a tree whose leaves each declare their own
  acceptance criteria, with covered work marked and dependencies drawn

If any artifact is missing or vague, keep the work in P.

The decomposition rule is risk-scaled. A flat work package remains valid at L0 and L1 —
the whole package is then one implicit acceptance unit. From L2, declare the decomposition
with `prdca decomposition-check`, mark every piece of work that later work will cover
(schema migrations, API contracts, security boundaries), and let the tree's shape and
depth (2-4 levels) follow the delivery, not a fixed taxonomy. During D, leaves are
accepted one by one through the `qa-gate` skill; the C gate then verifies closure
instead of re-verifying the whole delivery.

Freeze the package, including the threshold declaration, before handing it to R:

```text
prdca freeze --root .prdca/reviews --include prd.md --include thresholds.json --manifest .prdca/reviews/frozen-packet.json
```

Freezing the thresholds at P is what lets `prdca threshold-check` prove at C that no
passing grade was invented after the results were seen.

## R Gate

Hand the frozen package to the `review-board` skill. Accept its report as the R decision.
Record the decision, the independent review IDs, and unresolved dissent. Do not re-adjudicate
lane findings here. Any unresolved critical reviewer objection blocks D.

## D Gate: Implementation Complete

Require:

- Implemented scope mapped to approved requirements
- Code, configuration, data pipeline, prompt, model, or deployment changes documented
- Developer self-test complete
- Known issues listed with severity
- Deployment or run instructions available
- Requirement-to-change mapping and current rollback evidence

If implementation diverges from the approved plan in a major way, return to P.

## C Gate

Hand the implementation to the `qa-gate` skill. Accept its quality report as the C decision.
Any blocking defect returns to D. Do not lower a threshold to clear this gate.

## A Gate: Accepted or Replanned

Require:

- Stage outcome compared with the original objective
- User/business acceptance recorded
- Residual risks accepted or rejected
- Lessons learned recorded
- Skill candidates dispositioned through the `evolve-project-skills` skill
- Reviewer scorecards updated and ineffective reviewers revised or retired
- Learning classified as test, rule, skill, retained judgment, or human authority
- Decision made: next stage, conditional fix, return to D, return to P, or stop

Run `prdca score --input .prdca/reviews/reviewer-events.json` to update scorecards.

If the issue is structural or caused by a wrong plan, return to P instead of patching in D.

## Change Control

Classify every change and confirm the classification with `prdca change-check`:

- Minor: wording, layout, small configuration. Approve by project manager or product owner.
- Moderate: limited behavior change without architecture, data, security, or acceptance impact. Approve by product owner, tech lead, and QA.
- Major: scope, architecture, data model, AI behavior, security, cost, schedule, or acceptance criteria change. Return to P and pass R again.

State the classification and reason before acting on a change.

## Required Output

When using this skill, produce:

- Current PRDCA stage
- Gate decision: pass, conditional pass, or block
- The command that produced the decision and its exit code
- Missing evidence
- Required next actions
- Owner roles for each action
- Whether the work may advance

Use concise, auditable language.

## Authority

Read the `authorization` block in this project's `prdca.json` before acting without confirmation.
Treat any flag that is absent or `false` as not granted.

| Flag | Grants |
|---|---|
| `standing_execution` | Continue from P to R, D, C, and A when the gate evidence exists, and record gate decisions without pausing |
| `routine_document_updates` | Create or update routine governance, review, QA, acceptance, roadmap, and template documents |
| `non_destructive_commands` | Run validation and inspection commands |
| `local_skill_changes` | Create or update local, reversible project skills once the governed candidate threshold and approval evidence are satisfied |
| `destructive_filesystem_or_git` | Destructive filesystem or git operations |
| `external_deploy_or_publish` | External deployment, network dependency installation, or publication |

Regardless of flags, route major scope, architecture, data, AI behavior, security, cost, or
schedule changes through change control. When a gate decision is block or return to P/D,
perform the required rework when it is in scope and permitted; otherwise report the blocker
and the next required action.

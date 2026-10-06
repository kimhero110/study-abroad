---
name: review-board
description: Expert review board process for the R stage of PRDCA. Use when reviewing a project plan, PRD, architecture proposal, data/knowledge design, AI/RAG design, security plan, QA plan, delivery plan, or any stage package before implementation, especially when deciding pass, conditional pass, or return to Plan.
---

# Review Board

Use this skill to perform the R stage. The review board protects the project from weak plans entering implementation.

Follow `.prdca/framework/governance/independent-review-protocol.md`. Use the risk route to select review intensity; additional AIs are optional and must not vote.

## Deterministic Decisions

Derive review intensity, reviewer identity, and the blocking outcome from these controls rather
than from narrative judgement:

```text
prdca route            --input .prdca/evidence/risk-assessment.json --output .prdca/reports/route.json
prdca freeze           --root .prdca/reviews --include prd.md --manifest .prdca/reviews/frozen-packet.json
prdca select-reviewers --registry .prdca/reviewers.json \
                       --risk .prdca/evidence/risk-assessment.json --primary-family <primary-family>
prdca arbitrate        --input .prdca/evidence/arbitration-input.json
```

Read the exit code: `0` pass, `2` block, `3` human review. A non-zero exit code is the decision.
Freeze the packet before reviewers see it and verify it afterwards with
`prdca freeze --manifest .prdca/reviews/frozen-packet.json --verify`; a packet that changed
during review invalidates the review. Templates for each input are in `.prdca/framework/templates/`.

## Review Inputs

Do not review informally. Require a plan package with:

- Stage objective and business value
- Scope and non-goals
- User scenarios and acceptance criteria
- Architecture and component design
- Data sources, schemas, quality rules, and lineage
- Knowledge model or ontology when applicable
- AI/RAG/model behavior, evaluation, and evidence strategy
- Security, privacy, permission, and audit approach
- QA plan and measurable release criteria
- Delivery plan, dependencies, risks, and rollback
- Existing skill reuse, candidate evidence, trigger boundary, overlap, and validation plan when capability reuse is applicable
- Risk assessment, frozen review packet, and initialized Delivery Evidence Pack
- Passed value assessment linking the work to a macro milestone and user capability

If the package is incomplete, return it to P without detailed scoring.

## Expert Lanes

Review through these lanes. Assign each lane a result: pass, conditional pass, or block.

- Product: goals, users, scope, non-goals, workflow fit
- Domain: industrial/engineering correctness, terminology, standards, evidence needs
- Architecture: modularity, integration, maintainability, deployment feasibility
- Data governance: source quality, schema, metadata, lineage, retention, ownership
- Knowledge engineering: entities, relationships, ontology, graph/query usefulness
- AI/RAG: retrieval quality, grounding, hallucination controls, evaluation set, prompts
- Security: authentication, authorization, audit, secrets, sensitive data, isolation
- QA: testability, measurable criteria, defect policy, regression coverage
- Operations: observability, backup, recovery, capacity, runbooks
- Delivery: effort, schedule, cost, staffing, dependency risk

## Blocking Criteria

Block the plan if any item applies:

- Business goal or user scenario is unclear.
- Scope cannot be tested.
- Acceptance criteria are not measurable.
- Critical data source is unavailable or undefined.
- AI answer quality has no evaluation method.
- Evidence citation or traceability is missing for knowledge answers.
- Security or permission model is vague.
- Architecture depends on unproven assumptions without fallback.
- QA cannot independently verify success.
- Risk, rollback, or operations plan is missing for a production-impacting stage.
- A proposed skill duplicates an existing skill, lacks repeated-work evidence, or expands high-risk authority without explicit approval.
- The package reports only local activity or component metrics without user, workflow, or end-to-end evidence.

## Decision Rules

Use these decisions:

- Pass: all required lanes pass and no blocking objections remain.
- Conditional pass: only minor, non-blocking corrections remain; list owners and due dates.
- Return to P: any blocking issue remains or the plan package is incomplete.

Unanimous approval is required for key lanes: product, domain, architecture, data, AI/RAG when applicable, security, and QA.

Before deciding, run evidence arbitration. A single substantiated P0/P1 issue blocks regardless of reviewer count. Unsubstantiated opinions remain advisory. Preserve material dissent and route domain, regulatory, business-value, and accepted-risk disputes to human authority.

## Review Output

Produce a review report with:

- Decision: pass, conditional pass, or return to P
- The commands that produced the decision and their exit codes
- Lane-by-lane findings
- Blocking issues
- Non-blocking recommendations
- Required plan revisions
- Evidence requested for the next review
- Explicit statement whether D may start
- Independent review IDs, context-isolation status, and evidence locations
- Arbitration decision and unresolved dissent

Keep findings specific enough that the plan team can revise without guessing.

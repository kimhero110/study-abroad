---
name: evolve-project-skills
description: Govern the discovery, creation, validation, promotion, update, and retirement of reusable project skills. Use when PRDCA work reveals repeated specialized workflows, recurring defects, duplicated instructions or scripts, frequently rediscovered domain knowledge, or an existing project skill that may be stale or incomplete.
---

# Evolve Project Skills

Turn proven project workflows into small, reusable skills without creating skill clutter. Treat skills as governed process assets.

Follow `.prdca/framework/governance/skill-lifecycle.md`.

## Deterministic Decisions

Two controls decide whether a skill may exist and whether it is structurally sound:

```text
prdca learning-check --input .prdca/evidence/learning-candidate.json
prdca skill-check    --path .claude/skills
prdca skill-check    --path .codex/skills
```

Read the exit code: `0` pass, `2` block, `3` human review. A non-zero exit code is the decision.
`learning-check` also returns `defer` with exit code `2` when the reuse evidence is thin; that
means do not create the skill yet, not proceed carefully.

`learning-check` authorizes creation; `skill-check` gates promotion. Never promote a skill whose
`skill-check` run is failing, and never record a registry decision without the candidate ID that
`learning-check` accepted. Templates for each input are in `.prdca/framework/templates/`.

## Assess the Candidate

Inspect PRDCA plans, implementation reports, QA findings, acceptance lessons, decision records, and existing skills. Create a candidate only when at least two signals apply:

- The same workflow appeared in at least three cycles.
- The same instructions or domain rules were reconstructed at least three times.
- The same avoidable failure recurred at least twice.
- A script, template, or checklist was rewritten at least twice.
- Specialized project knowledge was rediscovered at least twice.
- A reusable skill is expected to reduce time, errors, or context use measurably.

Record the signals in the candidate file and let `prdca learning-check` count them. A `defer`
decision means collect more evidence, not proceed carefully.

Do not create a skill for a one-off task, generic engineering knowledge, an unstable workflow, or behavior already covered by an existing skill. Prefer updating an existing skill when its ownership and trigger still fit.

## Decide the Lifecycle Action

Choose exactly one action:

- `create`: no existing skill owns the stable workflow.
- `update`: an existing skill owns it but lacks proven instructions or resources.
- `defer`: evidence is promising but the workflow is not stable enough.
- `reject`: the candidate is generic, duplicated, unsafe, or not reusable.
- `retire`: the skill is obsolete, unused, or replaced.

Record the decision in this project's skill registry at `.prdca/skills/registry.md`. Use
`.prdca/framework/templates/skill-candidate-template.md` when a detailed proposal is needed.

## Plan the Skill

Define:

- Concrete user requests that should trigger the skill.
- Explicit exclusions and overlap with existing skills.
- The minimum reusable workflow.
- Whether scripts, references, or assets are genuinely necessary.
- Risk level, owner, validator, and expected efficiency gain.
- Validation tasks and promotion criteria.

Keep `SKILL.md` concise. Put detailed domain material in one-level references and deterministic repeated operations in scripts.

## Create or Update

Project skills are installed for every agent runtime this project uses. Read `paths.skills` in
`prdca.json` for the authoritative list; it is `.claude/skills` and `.codex/skills` by default.

Write the skill once and keep every target byte-identical:

1. Create `<skill-name>/SKILL.md` with `name` and `description` frontmatter. The name must be
   lowercase, hyphenated, and equal to the directory name.
2. Write a `description` that states both what the skill does and when to use it. This is the
   only text an agent reads when deciding whether to load the skill.
3. Add `<skill-name>/agents/openai.yaml` with `interface.display_name`, `short_description`,
   and a `default_prompt` that references `$<skill-name>`. Codex needs it; Claude ignores it.
4. Copy the finished directory into every path listed in `paths.skills`.
5. Reference framework assets under `.prdca/framework/`. A repository-relative path into a bare
   docs or templates directory does not exist inside an adopting project, and `prdca skill-check`
   rejects it.

Include only `SKILL.md`, `agents/openai.yaml`, and resources that are required.

For an update, preserve the existing trigger boundary unless the approved proposal changes it. Regenerate `agents/openai.yaml` when its interface metadata becomes stale.

Never embed secrets, personal credentials, generated reports, or volatile runtime data in a skill.

## Validate

Require all applicable evidence before promotion:

1. Run `prdca skill-check --path <skills-directory>` for every configured target and get exit code `0`.
2. Exercise at least two realistic tasks without leaking the expected answer.
3. Compare results with the previous workflow or a no-skill baseline.
4. Confirm output quality is not worse and the skill reduces at least one of time, repeated steps, context use, or avoidable defects.
5. Confirm the author is not the sole validator for semantic, security, or production-impacting skills.

Keep a new skill in `trial` until it succeeds in three real uses. Then mark it `active`. Mark it `needs-review` after a related recurring failure or material process change.

## Retire or Merge

Review skills during PRDCA A and periodic governance retrospectives. Retire or merge a skill when it is superseded, unused for five relevant cycles, repeatedly fails validation, or duplicates another skill. Preserve the decision in the registry before removal.

## Required Output

Report:

- Evidence signals and lifecycle action.
- The commands that produced the decision and their exit codes.
- Skill name, trigger, exclusions, and owner.
- Files created or changed, per configured target.
- Validation and forward-test results.
- Registry status: `candidate`, `trial`, `active`, `needs-review`, `retired`, or `rejected`.
- Measured or expected efficiency effect.

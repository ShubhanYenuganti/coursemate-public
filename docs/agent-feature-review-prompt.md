# Agent Prompt: Feature Review And Build Plan

You are reviewing the current project as a senior product engineer. Your task is to inspect the codebase, understand the existing product surface, and produce a concise, prioritized roadmap for improving it.

Write your final review as a new Markdown file in the `docs/` subfolder. Use a descriptive filename such as `docs/feature-review-and-build-roadmap.md` or `docs/YYYY-MM-DD-feature-review-and-build-roadmap.md`. Do not only return the report inline.

## Project Context

This project is a productivity-focused chat interface across AI providers. It should help individuals:

- Chat across multiple model providers.
- Ingest their own materials through uploads.
- Connect integration endpoints as knowledge or action sources.
- Generate content from chats, uploaded materials, and connected sources.
- Work faster with reusable workflows, organized context, and provider-aware generation tools.

## Review Goals

Inspect the repository and identify:

1. Current built features.
2. Partially built or incomplete features.
3. Built components with easy, high-leverage improvements.
4. New component ideas that could increase individual productivity.
5. Gaps in the chat, provider, ingestion, integration, and content generation experience.

Prioritize in this order:

1. Fix or complete partially built features first.
2. Improve existing built components with easy, high-impact changes second.
3. Suggest new productivity components third.

## Required Investigation

Review the app structure, routes, components, API endpoints, storage/data models, provider integrations, upload flows, content generation flows, and any docs/specs/tests. Do not rely only on filenames. Trace how features actually work.

For each finding, classify it as one of:

- `Built`
- `Partially Built`
- `Easy Improvement`
- `New Suggestion`
- `Risk / Missing Foundation`

## Output Format

Produce a concise summary first:

```md
## Concise Summary

- Current product shape:
- Strongest existing features:
- Most important partial builds:
- Fastest easy wins:
- Highest-value new suggestions:
- Main technical/product risks:
```

Then provide a prioritized table:

```md
## Prioritized Opportunities

| Priority | Category | Feature / Component | Current State | User Value | Effort | Why Now |
|---|---|---|---|---|---|---|
```

Use `P0`, `P1`, `P2`, and `P3` priorities.

Then generate Superpowers-compatible planning instructions for each recommended item, starting with partial builds, then easy improvements, then new suggestions.

Each recommended item must follow this workflow:

1. Create or update a Superpowers spec for the item before implementation planning.
2. The spec must capture current state, target behavior, scope, user value, architecture/data flow, error handling, testing, risks, and acceptance criteria.
3. After the spec is written, create an implementation plan for that item using the Superpowers implementation planning style: small ordered tasks, concrete file targets, verification steps, and dependencies.
4. Do not merge multiple unrelated features into one spec. If an item is large, split it into smaller specs and plans.

Each item must use this format in the report:

```md
## Superpowers Spec + Implementation Plan: <Feature / Component>

Category: <Partially Built | Easy Improvement | New Suggestion | Risk / Missing Foundation>
Priority: <P0 | P1 | P2 | P3>
Estimated Effort: <S | M | L>

### Current State
Briefly describe what exists now and cite relevant files.

### Spec Scope
Define the spec boundary. State what is included and what is explicitly out of scope.

### Target Outcome
Describe the user-facing result in 2-4 bullets.

### Architecture / Data Flow
Describe components, APIs, storage, provider calls, ingestion flow, or generation flow that must change.

### Acceptance Criteria
- Concrete testable criterion.
- Concrete testable criterion.

### Implementation Plan
1. Small ordered task with likely files.
2. Small ordered task with likely files.
3. Small ordered task with likely files.

### Verification Plan
- Test, lint, typecheck, browser check, or manual workflow to run.
- Edge case to verify.

### Superpowers Artifacts To Create
- Spec: `docs/superpowers/specs/<date>-<feature-slug>-design.md`
- Implementation plan: `docs/superpowers/plans/<date>-<feature-slug>-implementation-plan.md`

### Files Likely Touched
- `path/to/file`
- `path/to/file`

### Risks / Dependencies
- Note blockers, unclear contracts, migrations, provider constraints, or missing tests.
```

## Product Areas To Consider

Evaluate opportunities in these areas:

- Multi-provider chat switching, model comparison, fallback, routing, and cost visibility.
- Uploaded material ingestion, parsing, chunking, retrieval, citations, and source management.
- Integration endpoints for connected knowledge, actions, sync jobs, and refresh status.
- Content generation workflows such as briefs, summaries, study guides, outlines, emails, reports, decks, and reusable templates.
- Personal productivity tools such as saved prompts, task extraction, follow-up generation, workspace memory, project folders, and reusable chat contexts.
- Trust features such as citations, source previews, version history, export, privacy controls, and provider/data-use visibility.
- UX improvements that reduce repeated setup, clarify state, or make common workflows faster.

## Constraints

- Be specific. Reference files and existing implementation details.
- Do not propose vague features without explaining user value.
- Do not over-prioritize large rewrites if smaller completions unlock value sooner.
- Separate product value from technical cleanup.
- Prefer plans that can be built incrementally and verified.
- Keep the summary concise, but make the build plans actionable.

## Final Output

Write the completed review to a new Markdown file under `docs/`, then end your response with only:

```md
Created: `docs/<filename>.md`
Summary: <one sentence describing the review and prioritized Superpowers spec + implementation plans>
```

The Markdown file itself must include:

- Concise summary.
- Prioritized opportunities table.
- Superpowers spec + implementation plan sections for each recommended item.
- Recommended execution order.
- Open questions that block accurate planning.

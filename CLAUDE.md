# CourseMate Development Guidelines

## File Editing

Always use the Write or Edit tools to create or modify files. Never use `sed`, `cat`, `awk`, `echo >`, or other shell commands for file editing.

## Database Migrations

For simple migrations (one-liners or a few SQL commands), provide the commands directly in chat for the user to run against the database — do NOT create a migration script file. Only create a migration script for complex, multi-step migrations that benefit from a file.

## Git Safety Rules (Mandatory)

- DONT suggest git commands `git commit` or `git add` unless I request it explicitly.
- NEVER run `git push` unless I explicitly say: "push now".
- NEVER run `gh` commands that modify remote state (`gh pr create`, `gh issue create`, merges, releases) unless explicitly requested.
- If a task would normally end with pushing, stop after local changes and ask for confirmation.
- Default behavior: local-only (`git status`, `git diff`, local commits only when asked).

## Figma Capture Workflow

This project uses the Figma MCP server (remote) to push the live production UI back to Figma as editable design layers.

### Prerequisites

- Figma MCP connected via `/plugin` in Claude Code
- Production URL set in environment: `PRODUCTION_URL`
- **Google OAuth**: the human completes sign-in in the capture browser before capturing authenticated views (see `.cursor/skills/capture-ui-to-figma/SKILL.md`)

### Capture Instructions

When asked to capture the UI to Figma:

1. Read the production URL from the environment variable `PRODUCTION_URL`. If not set, ask the user to provide it before proceeding — do not fall back to localhost.

2. Use the Figma MCP capture tool (`generate_figma_design`) and Playwright MCP as described in the capture skill: open a browser pointed at the production URL, with the user signed in via Google OAuth in that same browser session where required.

3. On the **first** capture run for this workflow, capture the following states **in order** (navigate to the correct routes or query params for each):

   - **Login page** — logged-out / sign-in entry (before OAuth completes)
   - **Dashboard** — after successful Google sign-in
   - **Robotics — materials** — course materials view for the robotics flow
   - **Robotics — chat** — main chat surface for that flow
   - **Robotics — chat (new chat + verbose stream)** — create a **new** chat, send this exact user message, wait for the response stream, and capture the UI showing **both** the verbose stream and the chat together:

     `provide me with a detailed documentation from Robosuite about tracking a robotic arm's pose`

4. Send all captured frames to a **new** Figma file in Drafts. Name the file: `CourseMate — UI Capture YYYY-MM-DD` (use today’s date).

5. Return the Figma file link when complete.

### After Capture

Once frames are in Figma:

- Designer refines layout/spacing in Make
- Paste updated Figma frame URL back into Claude Code

### Implementing from Figma (design → code)

When the task is to **read a Figma design and implement it in this codebase**:

1. Use the **Figma MCP `get_screenshot`** tool for the target frame as the primary visual reference (parse `fileKey` and `nodeId` from the user’s Figma URL). **Do not** call `get_design_context`, generated design/code export, or other full ingest unless the user explicitly asks for that.
2. If `get_screenshot` is unavailable or the user already attached a PNG of the frame, use that image instead.
3. Implement as **visual diffs** against existing components (see **Important** below): match layout, spacing, and hierarchy from the screenshot; preserve logic, Tailwind patterns, and props.
4. Example prompt: `Implement the changes from this Figma frame: [URL]` — agent uses **`get_screenshot`** on that node, then implements from the image.

**Why:** Full Figma ingest is token-heavy; **`get_screenshot`** keeps context small while still showing layout and style.

### Important

- Never fall back to a local dev server — production only
- Never regenerate components from scratch — apply only visual diffs
- Preserve all existing `className` conventions (Tailwind + indigo/gray)
- Do not remove or rename existing props or event handlers
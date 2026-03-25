---
name: capture-ui-to-figma
description: >-
  Capture the live production CourseMate UI with Playwright MCP and send it to
  Figma via generate_figma_design. CourseMate uses Google OAuth — default to
  human-in-the-loop login in the capture browser, then capture. Trigger:
  capture/push/sync/send UI to Figma.
---

# Capture UI to Figma (CourseMate)

## Purpose

Capture the **live production** web UI and import it into Figma as editable design output for iteration. This workflow combines **Playwright MCP** (browser automation on the real URL) and **Figma MCP** (`generate_figma_design` capture pipeline).

## Trigger phrases

- "capture the UI to Figma"
- "push to Figma"
- "send current state to Figma"
- "sync UI to Figma"

## Prerequisites (read before acting)

1. **MCP tool schemas**: Before calling any MCP tool, read its descriptor JSON under the enabled MCP folder (parameters and behavior change with server versions).
2. **This skill overrides generic copy**: For **external/production URLs**, the Figma MCP expects you to drive the page with **Playwright MCP** — do not rely on opening hash-only URLs in ways the tool docs forbid for external sites.

## Step 1 — Verify Figma MCP and identity

1. Call Figma MCP **`whoami`**.
2. If the call fails or shows no authenticated user, stop and tell the user to connect and sign in to the **remote** Figma MCP server (`https://mcp.figma.com/mcp` in their Claude Code / environment config), then retry.
3. From **`whoami`**, note **`planKey`** values. If there is exactly one plan, use its `key` for new-file creation. If there are several, ask which team/org to use before creating a file.

## Step 2 — Resolve production base URL

1. Read **`PRODUCTION_URL`** from the environment (shell env or project `.env` / deployment config the user uses — do not invent a variable name; prefer `PRODUCTION_URL` if present).
2. If it is missing or empty, **stop** and ask the user to set it or paste the canonical production origin (e.g. `https://app.example.com`).
3. **Never** use `localhost`, `127.0.0.1`, LAN IPs, or any dev-server URL for this workflow, even if other docs mention local capture.

Normalize the value to an **origin + path** only if the user provided a full URL; avoid trailing ambiguity.

## Step 3 — Decide which UI states to capture

1. Open **`CLAUDE.md`** in the repo root and look for a **"Capture Instructions"** (or similarly named) subsection listing routes, deep links, or in-app steps.
2. If that section **exists**, treat it as authoritative: capture **each** listed state in order.
3. If it **does not exist** (or is empty), ask the user for an explicit list (paths, tabs, or steps). Do **not** guess sensitive or authenticated flows without confirmation.

## Production authentication (CourseMate: Google OAuth)

CourseMate signs in with **Google OAuth**. Unattended automation cannot complete that flow reliably or safely (consent screens, MFA, org policies). **Default pattern: human-in-the-loop** — assume it unless the user explicitly chooses another row.

**Human-in-the-loop (preferred for Google OAuth)**

1. Open the **same browser context** used for capture (Figma capture UI and/or Playwright MCP session per tool docs).
2. The **human** completes **Sign in with Google** (and any MFA) in that window.
3. After the app shows an authenticated session, continue: navigate to each target state (agent can drive **post-login** navigation), then run **`generate_figma_design`** per state as usual.
4. Do **not** ask the user to paste Google passwords or OAuth tokens into chat.

| Pattern | When to use | Agent behavior |
|--------|-------------|------------------|
| **Human-in-the-loop** | **Default** for CourseMate production | User completes Google OAuth in the capture browser; then agent captures each agreed state. |
| **Public / marketing only** | Listed URLs need no login | Playwright + `generate_figma_design` without a login step. |
| **Dedicated Google test user** | Team uses a separate account for captures | Same as human-in-the-loop: user still completes OAuth in-browser unless they provide a **local** `storageState` out of band (optional repeatability). |
| **Saved browser state** | Repeatable runs without re-OAuth each time | User exports Playwright **`storageState`** after one manual login; path stays **local**, never committed. |
| **Cannot obtain a session** | Policy / blockers | Stop; offer public routes or static mocks only. |

If the session strategy is unclear, **stop** after Step 3 and confirm: production requires Google OAuth → use **human-in-the-loop** unless the user overrides.

## Step 4 — Capture with Playwright + Figma MCP

For **each** state (only after **Production authentication** above is resolved for that run):

1. **Playwright MCP**: Navigate and drive the **production** URL only (`browser_navigate`, then `browser_snapshot` / clicks / fills as needed). With **Google OAuth**, wait for the user to finish sign-in in that browser before deep-linking to capture targets. Do not script Google credential entry. Resize if the project’s capture instructions specify a viewport.
2. **Figma MCP — `generate_figma_design`**:
   - On **first** use in the session (or when instructions are needed), call **`generate_figma_design`** **without** `outputMode` so the response can include **capture instructions** and options. Follow that response exactly (it is the source of truth for URL vs HTML vs polling).
   - For a **fresh file per run**, use `outputMode: "newFile"` with:
     - **`fileName`**: `CourseMate — UI Capture YYYY-MM-DD` (use today’s date in ISO form; if multiple files are needed in one day, suffix with ` — 2`, ` — 3`, etc., only if the user asked for multiple files).
     - **`planKey`**: from **`whoami`** (Step 1).
   - **Polling**: After a capture is started, if the tool returns a **`captureId`**, poll with that id **every ~5 seconds**, up to **~10** times, until status is **completed** (or handle failure per the tool response).
   - **Multiple states / pages**: The tool may require **one capture id per page** or document toolbar flow. If one capture cannot cover all states, repeat **`generate_figma_design`** per state as the tool’s instructions require — do not assume a single capture covers every navigation.

3. **Confirm with the user** between captures when instructions are ambiguous or when capture is slow/failed — keep them unblocked.

**Important**: Use **`generate_figma_design`** for **importing/capturing** the web UI. Do not manually compose equivalent layouts with **`use_figma`** for this workflow. Reserve **`use_figma`** for edits **after** a page is already captured, only if the user asks for follow-up sync (see Figma tool descriptions: default to `generate_figma_design` for first-time capture).

## Step 5 — Return the Figma link and summary

1. Return the **direct Figma design file URL** (from the completed capture response or from `create_new_file` / file metadata as applicable).
2. Summarize **which states** were captured (route names or short labels matching `CLAUDE.md` or the user’s list).

## Constraints

| Rule | Detail |
|------|--------|
| Figma endpoint | Use the **remote** Figma MCP server the project has configured (`https://mcp.figma.com/mcp`). Do not substitute an unofficial server. |
| URL scope | **Production only** — never localhost or local dev servers for this skill. |
| Repo | **Do not** modify application source, config, or assets solely to run this workflow (no drive-by edits). |
| Frames | Do not **manually** build Figma frames to replicate the UI for this task — use **`generate_figma_design`** per the capture pipeline. |
| New file | Each run defaults to a **new** Figma file named as above. Do not append to an existing file unless the user explicitly asks. |
| Auth (Figma) | If **`whoami`** fails, fix Figma MCP authentication first. |
| Auth (app) | Google OAuth: prefer **human-in-the-loop**; do not bypass sign-in or harvest tokens into the repo. |

## CourseMate-specific notes

- **Sign-in**: Production uses **Google OAuth** — plan on the user logging in once per capture session in the capture browser unless they use a local `storageState`.
- **`CLAUDE.md`** may not yet list capture targets; when missing, rely on the user’s explicit list (Step 3).
- For visual parity with design work, see `docs/FIGMA_STYLE_REFERENCE.md` **after** capture if the user wants design tokens or polish — that doc is reference, not a substitute for MCP capture steps.

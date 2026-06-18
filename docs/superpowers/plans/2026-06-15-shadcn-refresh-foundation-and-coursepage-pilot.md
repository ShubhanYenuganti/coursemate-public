# shadcn Visual Refresh — Foundation + CoursePage Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the indigo token foundation + shared shadcn primitives, then fully migrate CoursePage as the reference pattern for the rest of the frontend refresh.

**Architecture:** Re-point shadcn's neutral CSS variables in `src/App.css` to indigo-600 once, so every shadcn component inherits the brand accent with no per-component edits. Batch-install the reused primitives. Migrate CoursePage section-by-section to those primitives + tokens, keeping all logic/handlers untouched. Capture the repeatable steps as a migration checklist for later waves.

**Tech Stack:** Vite + React 19 (JavaScript/JSX), Tailwind v4 (PostCSS), shadcn/ui (`radix-luma`, neutral base, lucide), `radix-ui` primitives.

**Branch:** Already on `shadcn-visual-refresh`.

**Verification model (read first):** This is a presentation-layer refactor. The project's test suite is pure-logic vitest (no jsdom/testing-library), so there are NO React render tests and we do not add a DOM harness. Each task is verified by:
1. `npm run build` → clean (catches JSX/import/alias breaks).
2. `npm test` → existing suite stays green (catches logic regressions).
3. Visual check against the approved mockup (Clean Minimal + indigo).
Logic and handlers (`fetch`, `localStorage`, state) must remain byte-identical — only markup/className changes.

---

### Task 1: Re-point indigo tokens in App.css

**Files:**
- Modify: `src/App.css:100-134` (the `:root` block)

OKLCH values are Tailwind v4 canonical: indigo-600 `oklch(0.511 0.262 276.966)`, indigo-700 `oklch(0.457 0.24 277.023)`, indigo-50 `oklch(0.962 0.018 272.314)`.

- [ ] **Step 1: Edit the four accent tokens in `:root`**

In `src/App.css`, inside the `:root {` block, change these four lines:

```css
  --primary: oklch(0.205 0 0);
```
to
```css
  --primary: oklch(0.511 0.262 276.966); /* indigo-600 */
```

```css
  --accent: oklch(0.97 0 0);
  --accent-foreground: oklch(0.205 0 0);
```
to
```css
  --accent: oklch(0.962 0.018 272.314); /* indigo-50 */
  --accent-foreground: oklch(0.457 0.24 277.023); /* indigo-700 */
```

```css
  --ring: oklch(0.708 0 0);
```
to
```css
  --ring: oklch(0.511 0.262 276.966); /* indigo-600 */
```

(`--primary-foreground: oklch(0.985 0 0)` already near-white — leave it.)

- [ ] **Step 2: Align the sidebar accent tokens to match**

Still in `:root`, change:

```css
  --sidebar-primary: oklch(0.205 0 0);
```
to
```css
  --sidebar-primary: oklch(0.511 0.262 276.966); /* indigo-600 */
```

```css
  --sidebar-accent: oklch(0.97 0 0);
  --sidebar-accent-foreground: oklch(0.205 0 0);
```
to
```css
  --sidebar-accent: oklch(0.962 0.018 272.314); /* indigo-50 */
  --sidebar-accent-foreground: oklch(0.457 0.24 277.023); /* indigo-700 */
```

```css
  --sidebar-ring: oklch(0.708 0 0);
```
to
```css
  --sidebar-ring: oklch(0.511 0.262 276.966); /* indigo-600 */
```

Leave the `.dark` block (lines 135-168) unchanged — light-only for now.

- [ ] **Step 3: Build to verify CSS compiles**

Run: `npm run build`
Expected: `✓ built in …`, no errors.

- [ ] **Step 4: Visual check**

Run: `npm run dev`, open the app, view any existing shadcn `Button` (or temporarily render one). Expected: primary button is indigo, not black. Stop dev server after confirming.

- [ ] **Step 5: Commit**

```bash
git add src/App.css
git commit -m "feat(ui): re-point shadcn tokens to indigo-600 accent"
```

---

### Task 2: Install the shared primitives layer

**Files:**
- Create: `src/components/ui/{card,dialog,tabs,input,textarea,label,select,popover,command,badge,progress,dropdown-menu,sonner,skeleton,tooltip}.jsx`

- [ ] **Step 1: Add the primitives in one batch**

Run:
```bash
npx shadcn@latest add card dialog tabs input textarea label select popover command badge progress dropdown-menu sonner skeleton tooltip
```
Expected: each component reported as created/added under `src/components/ui/`. If any prompt about overwriting `button.jsx`, choose **no**.

- [ ] **Step 2: Verify the files exist**

Run: `ls src/components/ui`
Expected: `badge.jsx button.jsx card.jsx command.jsx dialog.jsx dropdown-menu.jsx input.jsx label.jsx popover.jsx progress.jsx select.jsx skeleton.jsx sonner.jsx tabs.jsx textarea.jsx tooltip.jsx`

- [ ] **Step 3: Build to verify all imports resolve**

Run: `npm run build`
Expected: clean build (this confirms `radix-ui`/`sonner`/`cmdk` deps installed by the CLI resolve).

- [ ] **Step 4: Commit**

```bash
git add src/components/ui package.json package-lock.json
git commit -m "feat(ui): add shared shadcn primitives (card, dialog, select, etc.)"
```

---

### Task 3: Migrate CoursePage header to Button

**Files:**
- Modify: `src/CoursePage.jsx` (imports + header block lines 205-245)

- [ ] **Step 1: Add the Button import**

At the top of `src/CoursePage.jsx`, after the existing component imports (after line 8 `import CourseStatsWidget...`), add:

```jsx
import { Button } from '@/components/ui/button';
```

- [ ] **Step 2: Replace the back button**

Replace:
```jsx
            <button
              type="button"
              onClick={() => navigate('/')}
              className="p-2 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-colors"
              title="Back to home"
            >
              <BackIcon />
            </button>
```
with:
```jsx
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate('/')}
              title="Back to home"
            >
              <BackIcon />
            </Button>
```

- [ ] **Step 3: Replace the sign-out button**

Replace:
```jsx
            <button
              type="button"
              onClick={onSignOut}
              className="p-2 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-colors"
              title="Sign out"
            >
              <SignOutIcon />
            </button>
```
with:
```jsx
            <Button
              variant="ghost"
              size="icon"
              onClick={onSignOut}
              title="Sign out"
            >
              <SignOutIcon />
            </Button>
```

- [ ] **Step 4: Update the profile focus ring to the token**

In the profile button (line ~224), change `focus:ring-indigo-400` to `focus:ring-ring`:
```jsx
                className="rounded-full focus:outline-none focus:ring-2 focus:ring-ring"
```

- [ ] **Step 5: Build + test**

Run: `npm run build && npm test`
Expected: clean build; existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/CoursePage.jsx
git commit -m "refactor(coursepage): header buttons -> shadcn Button"
```

---

### Task 4: Migrate the description editor to Textarea + Button

**Files:**
- Modify: `src/CoursePage.jsx` (imports + description block lines 253-282)

- [ ] **Step 1: Add Textarea import**

Below the Button import, add:
```jsx
import { Textarea } from '@/components/ui/textarea';
```

- [ ] **Step 2: Replace the textarea element**

Replace:
```jsx
                  <textarea
                    autoFocus
                    value={descValue}
                    onChange={(e) => { setDescValue(e.target.value); setDescError(''); }}
                    rows={4}
                    maxLength={2000}
                    placeholder="Add a description…"
                    className="w-full px-3 py-2 rounded-lg border border-gray-200 bg-white text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent resize-none transition-all"
                  />
```
with:
```jsx
                  <Textarea
                    autoFocus
                    value={descValue}
                    onChange={(e) => { setDescValue(e.target.value); setDescError(''); }}
                    rows={4}
                    maxLength={2000}
                    placeholder="Add a description…"
                    className="resize-none"
                  />
```

- [ ] **Step 3: Replace the Save/Cancel buttons**

Replace:
```jsx
                    <button
                      type="button"
                      onClick={handleSaveDesc}
                      disabled={descStatus === 'saving'}
                      className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                    >
                      {descStatus === 'saving' ? 'Saving…' : 'Save'}
                    </button>
                    <button
                      type="button"
                      onClick={cancelEditDesc}
                      className="px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 text-sm font-medium hover:bg-gray-50 transition-colors"
                    >
                      Cancel
                    </button>
```
with:
```jsx
                    <Button size="sm" onClick={handleSaveDesc} disabled={descStatus === 'saving'}>
                      {descStatus === 'saving' ? 'Saving…' : 'Save'}
                    </Button>
                    <Button size="sm" variant="outline" onClick={cancelEditDesc}>
                      Cancel
                    </Button>
```

- [ ] **Step 4: Retint the edit-pencil hover to tokens**

In the edit-description button (line ~297), change `hover:text-indigo-600 hover:bg-indigo-50` to `hover:text-primary hover:bg-accent`:
```jsx
                      className="absolute top-0 right-0 p-1.5 rounded-lg text-gray-300 hover:text-primary hover:bg-accent opacity-0 group-hover:opacity-100 transition-all"
```

- [ ] **Step 5: Build + test**

Run: `npm run build && npm test`
Expected: clean build; tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/CoursePage.jsx
git commit -m "refactor(coursepage): description editor -> Textarea + Button"
```

---

### Task 5: Migrate the Default AI Model panel to Card + Label + Select + Button

**Files:**
- Modify: `src/CoursePage.jsx` (imports + AI model block lines 310-358)

> Gotcha: Radix Select (used by shadcn `Select`) forbids empty-string item values. The current code uses `value=""` for "None"/"Default". We map a sentinel (`"none"` / `"default"`) to `''` in the change handler so behavior is identical.

- [ ] **Step 1: Add Card, Label, Select imports**

Below the Textarea import, add:
```jsx
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
```

- [ ] **Step 2: Replace the entire AI model panel**

Replace the whole block (from `<div className="rounded-xl border border-gray-200 bg-white/80 px-4 py-4 space-y-3">` through its closing `</div>` at line ~358) with:

```jsx
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Default AI Model</CardTitle>
                  <CardDescription>
                    When set, chats in this course will default to this provider and model instead of the global default.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-3 items-end">
                    <div className="flex flex-col gap-1.5">
                      <Label>Provider</Label>
                      <Select
                        value={aiProvider || 'none'}
                        onValueChange={(v) => {
                          setAiProvider(v === 'none' ? '' : v);
                          setAiModel('');
                          setAiPickerStatus(null);
                        }}
                      >
                        <SelectTrigger className="w-[180px]">
                          <SelectValue placeholder="None (use global)" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">None (use global)</SelectItem>
                          <SelectItem value="openai">OpenAI</SelectItem>
                          <SelectItem value="claude">Claude</SelectItem>
                          <SelectItem value="gemini">Gemini</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    {aiProvider && (
                      <div className="flex flex-col gap-1.5">
                        <Label>Model</Label>
                        <Select
                          value={aiModel || 'default'}
                          onValueChange={(v) => {
                            setAiModel(v === 'default' ? '' : v);
                            setAiPickerStatus(null);
                          }}
                        >
                          <SelectTrigger className="w-[200px]">
                            <SelectValue placeholder="Default for provider" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="default">Default for provider</SelectItem>
                            {(PROVIDER_MODELS[aiProvider] || []).map((m) => (
                              <SelectItem key={m.id} value={m.id}>{m.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                    <Button onClick={handleSaveAiModel} disabled={aiPickerStatus === 'saving'}>
                      {aiPickerStatus === 'saving' ? 'Saving…' : aiPickerStatus === 'saved' ? 'Saved!' : 'Save'}
                    </Button>
                  </div>
                  {aiPickerStatus === 'error' && (
                    <p className="text-xs text-destructive mt-3">Failed to save. Please try again.</p>
                  )}
                </CardContent>
              </Card>
```

- [ ] **Step 3: Build + test**

Run: `npm run build && npm test`
Expected: clean build; tests pass.

- [ ] **Step 4: Manual interaction check**

Run `npm run dev`, open a course you own → Overview. Confirm: Provider select opens, choosing a provider reveals Model select, "Save" works (network PUT), "None (use global)" resets correctly. Stop dev server.

- [ ] **Step 5: Commit**

```bash
git add src/CoursePage.jsx
git commit -m "refactor(coursepage): AI model panel -> Card + Select + Label"
```

---

### Task 6: Retint page shell + floating toolbar to Clean Minimal tokens

**Files:**
- Modify: `src/CoursePage.jsx` (root/header lines 202-205, ToolbarItem lines 34-57, toolbar bar lines 403-413)

- [ ] **Step 1: Neutralize the page background and header**

Replace:
```jsx
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-cyan-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-sm border-b border-gray-200 shadow-sm">
```
with:
```jsx
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-background/80 backdrop-blur-sm border-b border-border shadow-sm">
```

- [ ] **Step 2: Retint ToolbarItem to tokens**

In `ToolbarItem` (lines 43-54), replace the two `<span>`/`<div>` className expressions:

```jsx
      <span className={`max-w-0 overflow-hidden whitespace-nowrap text-sm font-medium transition-all duration-200 ease-out group-hover:max-w-xs ${
        active ? 'text-indigo-700 max-w-xs' : 'text-gray-700'
      }`}>
        {label}
      </span>
      <div className={`w-10 h-10 flex items-center justify-center rounded-xl border shadow-sm text-lg transition-all duration-200 ${
        active
          ? 'bg-indigo-600 border-indigo-600 text-white shadow-md'
          : 'bg-white/80 border-gray-200 text-gray-600 group-hover:text-indigo-600 group-hover:border-indigo-300 group-hover:shadow-md'
      }`}>
        {icon}
      </div>
```
with:
```jsx
      <span className={`max-w-0 overflow-hidden whitespace-nowrap text-sm font-medium transition-all duration-200 ease-out group-hover:max-w-xs ${
        active ? 'text-accent-foreground max-w-xs' : 'text-foreground'
      }`}>
        {label}
      </span>
      <div className={`w-10 h-10 flex items-center justify-center rounded-xl border shadow-sm text-lg transition-all duration-200 ${
        active
          ? 'bg-primary border-primary text-primary-foreground shadow-md'
          : 'bg-background/80 border-border text-muted-foreground group-hover:text-primary group-hover:border-primary/40 group-hover:shadow-md'
      }`}>
        {icon}
      </div>
```

- [ ] **Step 3: Retint the toolbar bar + dividers**

Replace:
```jsx
      <div className="fixed bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-3 px-4 py-3 rounded-2xl bg-white/70 backdrop-blur-md border border-gray-200 shadow-lg">
```
with:
```jsx
      <div className="fixed bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-3 px-4 py-3 rounded-2xl bg-background/70 backdrop-blur-md border border-border shadow-lg">
```
and replace each of the three divider lines `<div className="w-px h-6 bg-gray-200" />` with `<div className="w-px h-6 bg-border" />` (use replace-all for the exact string `className="w-px h-6 bg-gray-200"` → `className="w-px h-6 bg-border"`).

- [ ] **Step 4: Retint the Default-AI-Model card's empty-state border (cleanup of stray grays)**

Confirm no remaining `border-gray-200` / `bg-white` literals in CoursePage:
Run: `grep -nE "gray-[0-9]|bg-white|indigo-[0-9]" src/CoursePage.jsx`
Expected: only intentional remainders (none should reference the migrated sections). Retint any leftover wrapper grays to `border-border` / `bg-background` as needed.

- [ ] **Step 5: Build + test + visual**

Run: `npm run build && npm test`
Expected: clean build; tests pass. Then `npm run dev` and confirm CoursePage matches the Clean-Minimal/indigo mockup (neutral shell, indigo active toolbar item + primary buttons). Stop dev server.

- [ ] **Step 6: Commit**

```bash
git add src/CoursePage.jsx
git commit -m "refactor(coursepage): page shell + toolbar -> Clean Minimal tokens"
```

---

### Task 7: Capture the reusable migration checklist

**Files:**
- Create: `docs/superpowers/migration-checklist.md`

- [ ] **Step 1: Write the checklist distilled from the pilot**

Create `docs/superpowers/migration-checklist.md` with:

```markdown
# Page Migration Checklist (shadcn Visual Refresh)

Apply per page. Logic/handlers stay byte-identical — markup/className only.

## 1. Inventory
- List the page's UI blocks and map each to a primitive:
  buttons→Button, panels→Card, modals→Dialog, native <select>→Select,
  inputs/textarea→Input/Textarea+Label, pills→Badge, bars→Progress,
  menus→DropdownMenu, toasts→sonner, loading→Skeleton, hints→Tooltip.

## 2. Imports
- Add `import { X } from '@/components/ui/x'` for each primitive used.

## 3. Replace (surgical)
- Buttons: `<button class="bg-indigo-600…">` → `<Button>`;
  secondary → `variant="outline"`; icon-only → `size="icon"`; ghost for header/nav.
- Native `<select>` → composed `Select` (Trigger/Value/Content/Item).
  GOTCHA: Radix Select forbids empty-string values — map a sentinel
  ("none"/"default") to '' in onValueChange.
- Panels/cards → `Card`/`CardHeader`/`CardTitle`/`CardDescription`/`CardContent`.
- Modals → `Dialog` (replaces CreateCourseModal/SharingAccessModal patterns).

## 4. Retint leftovers to tokens
- `indigo-600`→`primary`, `indigo-700`/active→`accent-foreground`,
  `indigo-50`→`accent`, `gray-200` borders→`border`, `bg-white`→`background`,
  `text-gray-*`→`text-foreground`/`text-muted-foreground`,
  `focus:ring-indigo-400`→`focus:ring-ring`, `text-red-600`→`text-destructive`.
- Grep gate: `grep -nE "gray-[0-9]|bg-white|indigo-[0-9]|red-[0-9]" src/<File>.jsx`
  should return only intentional remainders.

## 5. Verify
- `npm run build` clean → `npm test` green → visual check vs mockup.
- Commit per logical section, message: `refactor(<page>): <section> -> shadcn`.

## Notes
- Keep signature custom pieces (e.g. CoursePage floating toolbar) as styled
  elements retinted to tokens — do not force them into a primitive.
- Light-only: never add `dark:` classes; tokens carry future dark mode.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/migration-checklist.md
git commit -m "docs(ui): reusable page migration checklist from CoursePage pilot"
```

---

## Self-Review

**Spec coverage:** Section 1 tokens → Task 1. Section 2 primitives → Task 2; chat surface noted as later wave (out of scope for this pilot plan, by design). Section 3 pilot pattern (CoursePage) → Tasks 3-6; reusable checklist → Task 7. Section 4 rollout/monoliths → explicitly deferred to follow-on plans generated after this pilot. Light-only, indigo accent, untouched-logic constraints → enforced in every task + verification model.

**Placeholder scan:** No TBD/TODO; every code step shows exact old→new. Verification model documents why no render tests (project has no DOM test harness; adding one would violate surgical scope).

**Type/name consistency:** State vars (`aiProvider`, `aiModel`, `aiPickerStatus`, `descValue`, `descStatus`) and handlers (`handleSaveDesc`, `cancelEditDesc`, `handleSaveAiModel`) referenced exactly as defined in `CoursePage.jsx`. `PROVIDER_MODELS` import already present (line 6). Primitive import paths match the files Task 2 creates.

**Out of scope (follow-on plans):** Wave 1-4 page migrations, ChatTab/MaterialsPage decomposition + chat-surface refresh. These get their own plans using `docs/superpowers/migration-checklist.md` once the pilot validates the pattern.

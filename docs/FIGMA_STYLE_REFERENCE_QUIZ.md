# CourseMate Quiz — Figma style reference (`src/Quiz.jsx`)

This is a focused style reference for the Quiz screen only, derived from `src/Quiz.jsx`.

Use this when creating a new Figma template for the Quiz experience so it stays visually aligned with the shipped UI.

---

## 1) Screen structure

- Two-column layout: `flex gap-4 items-start`
- Left rail: fixed width `220px`, min-height `520px`
- Right panel: flexible form canvas
- Both surfaces are card-style white panels:
  - `bg-white rounded-2xl border border-gray-200 shadow-sm`

---

## 2) Color system used in Quiz

Primary tone is **Indigo + Gray** with semantic accent colors for status/file types.

### Core UI colors

- Primary action: `indigo-600` (`hover: indigo-700`)
- Focus: `ring-indigo-300`, `border-indigo-400`
- Selected/assistive surface: `bg-indigo-50`, `border-indigo-100`, text `indigo-700`
- Base text:
  - title `gray-900`
  - body `gray-500` / `gray-600`
  - micro/meta `gray-400`
- Base borders: `gray-200`, dividers `gray-100`

### Semantic

- Error text: `red-600`
- Informational confidence dot: `green-400`

### File-type badge palette

- PDF: `rose-100 / rose-600`
- DOC: `blue-100 / blue-600`
- XLS/CSV: `green-100 / green-700`
- IMG: `purple-100 / purple-600`
- SVG: `orange-100 / orange-600`
- TXT/default: `gray-100 / gray-500`

---

## 3) Typography

Font family inherits app default system stack (`src/App.css`):

- `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif`

Text hierarchy in Quiz:

- Main heading: `text-xl font-bold text-gray-900`
- Intro/body: `text-sm text-gray-500`
- Field label (primary): `text-sm font-medium text-gray-700`
- Field label (secondary): `text-xs font-medium text-gray-600`
- Sidebar label/meta: `text-[10px] text-gray-400`, uppercase + tracking on section title
- Button label:
  - primary CTA: `text-sm font-semibold`
  - secondary controls: `text-xs font-medium`

Micro-typography details:

- Uses `tabular-nums` for counters/stepper numbers
- Uses `tracking-wider` for sidebar "Sources" label

---

## 4) Component specs (Quiz-specific)

### A) Sources sidebar card

- Container: `w-[220px] ... rounded-2xl border border-gray-200 shadow-sm`
- Header:
  - Title: uppercase `text-[10px] font-semibold text-gray-400 tracking-wider`
  - Count: `text-[10px] text-gray-400 tabular-nums`
- List item:
  - `px-3 py-1.5 rounded-lg text-xs text-gray-600 hover:bg-gray-50`
  - Active state adds `border-l-2 border-indigo-400`
- Footer divider: `border-t border-gray-100`
- Add Source button:
  - `rounded-lg border border-dashed border-gray-300`
  - hover: `hover:border-indigo-400 hover:text-indigo-600 hover:bg-indigo-50`

### B) Source toggle switch

- Track:
  - on: `bg-indigo-500`
  - off: `bg-gray-200`
- Thumb: white circular knob with `shadow-sm`
- Compact dimensions: `h-4 w-7` with translated thumb states

### C) Stepper control

- Wrapper: `border border-gray-200 rounded-lg px-3 py-2 bg-white`
- Minus/plus icons: gray icon buttons with darker gray hover
- Value: `text-sm font-semibold text-gray-900 tabular-nums`

### D) Topic input

- Input: `rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800`
- Placeholder: `gray-400`
- Focus: `ring-2 ring-indigo-300` + `border-indigo-400`

### E) MCQ option segmented control

- Group shell: `p-1 bg-gray-100 rounded-lg w-fit`
- Segment:
  - Active: `bg-indigo-600 text-white shadow-sm`
  - Inactive: `text-gray-600 hover:text-gray-800`

### F) Summary info strip

- Container: `rounded-lg bg-indigo-50 border border-indigo-100 px-3 py-2.5`
- Text: `text-xs text-indigo-700` with bold count
- Leading icon: filled sparkle

### G) Primary CTA (Generate Quiz)

- Full width, prominent:
  - `rounded-xl bg-indigo-600 text-white text-sm font-semibold`
  - `hover:bg-indigo-700`
  - disabled: `opacity-50 cursor-not-allowed`
  - includes `shadow-sm`
- Loading state includes compact spinner (`h-4 w-4`, `animate-spin`)

### H) Helper footnote

- `text-[10px] text-gray-400`
- green status dot + indigo inline link with underline hover

---

## 5) Radius, spacing, elevation

- Radii:
  - Large cards: `rounded-2xl`
  - Inputs/controls: `rounded-lg`
  - Segments inside controls: `rounded-md`
- Spacing:
  - Outer split gap: `gap-4`
  - Form vertical rhythm: `gap-5`
  - Dense list rows: `py-1.5`
- Elevation:
  - Primary surfaces and CTA use `shadow-sm`

---

## 6) Iconography

- Stroke icons mostly use `strokeWidth=2.5` for controls
- Sparkle icon uses filled style to emphasize AI action/state
- Icon sizes are compact (13-14 px), aligned with dense utility UI

---

## 7) Figma prompt block (paste-ready)

Use this exact prompt in Figma:

Design a "Custom Quiz Generator" screen for an education app. Use a clean light UI with two cards: a narrow left "Sources" sidebar (220px) and a flexible right configuration form. Style language: white surfaces, gray borders (`gray-200`), subtle `shadow-sm`, large card corners (16px), control corners (8px). Primary color is indigo (`indigo-600`) for actions, selected states, and focus accents; hover states go darker (`indigo-700`). Typography is system sans, with a bold xl title, 14px labels/body, and 10-12px metadata text in gray tones. Include compact steppers, a segmented MCQ options control, and a full-width indigo primary CTA with optional loading spinner. Use a soft indigo info strip for question totals and semantic accents for errors (red) and status dot (green). Keep the layout dense but breathable, with clear hierarchy and utility-first spacing.


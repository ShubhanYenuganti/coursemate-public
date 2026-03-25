# CourseMate Flashcards — Figma style reference (`src/Flashcards.jsx`)

This is a focused style reference for the Flashcards screen only, derived from `src/Flashcards.jsx`.

Use this when creating a new Figma template for the Flashcards experience so it stays visually aligned with the shipped UI.

---

## 1) Screen structure

- Two-column layout: `flex gap-4 items-start`
- Left rail: fixed width `220px`, min-height `520px`
- Right panel: flexible flashcard-config canvas
- Shared card shell style:
  - `bg-white rounded-2xl border border-gray-200 shadow-sm`

---

## 2) Color system used in Flashcards

Primary tone is **Indigo + Gray** with semantic accents and a neutral preview-card zone.

### Core UI colors

- Primary action: `indigo-600` (`hover: indigo-700`)
- Focus: `ring-indigo-300`, `border-indigo-400`
- Selection states:
  - segmented active `bg-indigo-600 text-white`
  - source selected marker `border-indigo-400`
  - front-label accent `text-indigo-400`
- Base text:
  - title `gray-900`
  - body/labels `gray-500` to `gray-700`
  - micro/meta `gray-400`
- Base borders: `gray-200`, subtle dividers `gray-100`

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

Text hierarchy in Flashcards:

- Main heading: `text-xl font-bold text-gray-900`
- Intro/body: `text-sm text-gray-500`
- Field labels: `text-sm font-medium text-gray-700`
- Option labels/captions: `text-xs` to `text-sm`
- Sidebar labels/meta: `text-[10px] text-gray-400`, uppercase + tracking
- CTA label: `text-sm font-semibold`

Micro-typography details:

- Uses `tabular-nums` for source count and card count stepper
- Preview headers use uppercase micro labels (`text-[10px] font-semibold tracking-wider`)

---

## 4) Component specs (Flashcards-specific)

### A) Sources sidebar card

- Same shell pattern:
  - `w-[220px] ... rounded-2xl border border-gray-200 shadow-sm`
- Header:
  - title `text-[10px] font-semibold uppercase tracking-wider text-gray-400`
  - count `text-[10px] text-gray-400 tabular-nums`
- List item:
  - `px-3 py-1.5 rounded-lg text-xs text-gray-600 hover:bg-gray-50`
  - active marker `border-l-2 border-indigo-400`
- Footer button:
  - dashed border + indigo hover treatment

### B) Source toggle switch

- Track:
  - on `bg-indigo-500`
  - off `bg-gray-200`
- Thumb: white, rounded, `shadow-sm`
- Dimensions: `h-4 w-7`

### C) Card-count stepper

- Wrapper: `border border-gray-200 rounded-lg px-3 py-2 bg-white`
- Buttons: gray icon buttons with darker hover and disabled fade
- Value: `text-sm font-semibold text-gray-900 tabular-nums`
- Adjacent helper text: `text-sm text-gray-400` ("N cards")

### D) Definition depth segmented control

- Group shell: `p-1 bg-gray-100 rounded-lg w-fit`
- Segment:
  - active: `bg-indigo-600 text-white shadow-sm`
  - inactive: `text-gray-600 hover:text-gray-800`
- Below-group description text: `text-xs text-gray-500`

### E) Preview card block (unique to Flashcards)

- Outer preview container:
  - `rounded-xl border border-gray-200 bg-gray-50 p-4`
- Title label:
  - `text-[10px] font-semibold text-gray-400 uppercase tracking-wider`
- Inner card:
  - `bg-white rounded-lg border border-gray-200 p-4`
- Front section:
  - header `text-[10px] font-semibold text-indigo-400 uppercase tracking-wider`
  - value `text-sm text-gray-400 italic`
- Back section:
  - top divider `border-t border-gray-100`
  - header `text-[10px] font-semibold text-gray-400 uppercase tracking-wider`
  - value `text-sm text-gray-400 italic`

### F) Topic input

- `rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800`
- Placeholder `gray-400`
- Focus `ring-2 ring-indigo-300` + `border-indigo-400`

### G) Primary CTA (Generate Flashcards)

- Full-width action:
  - `rounded-xl bg-indigo-600 text-white text-sm font-semibold shadow-sm`
  - hover `indigo-700`
  - disabled `opacity-50 cursor-not-allowed`
- Loading state: `animate-spin` 4x4 spinner icon

### H) Footer trust note

- `text-[10px] text-gray-400` with `green-400` dot and indigo help link

---

## 5) Radius, spacing, elevation

- Radii:
  - Main cards `rounded-2xl`
  - Controls/inner cards `rounded-lg`
  - Segmented options `rounded-md`
  - Preview wrapper `rounded-xl`
- Spacing:
  - Split gap `gap-4`
  - Form rhythm `gap-5`
  - Dense list rows `py-1.5`
- Elevation:
  - Surfaces and primary CTA use `shadow-sm`

---

## 6) Iconography

- Utility/source icons: compact stroke icons (`13px`, `strokeWidth=2.5`)
- Sparkle icon is filled to denote AI generation
- Spinner icon for loading state is minimal and monochrome

---

## 7) Figma prompt block (paste-ready)

Use this exact prompt in Figma:

Design a "Custom Flashcard Generator" screen for a learning app using a clean light UI. Structure it as two cards: a left 220px Sources sidebar and a larger right configuration panel. Visual language: white cards, gray-200 borders, rounded-2xl outer shells, rounded-lg controls, subtle shadow-sm. Use indigo (`indigo-600`) for primary CTA, selected segmented options, source selection accents, and focus rings; hover to `indigo-700`. Include controls for topic input, card-count stepper (+/-), depth segmented toggle (Brief / Moderate / In-Depth), and a preview flashcard block with a light-gray outer container and white inner card showing Front/Back sections. Typography should be system sans with xl bold title, 14px labels/body, and 10-12px metadata labels. Include red error text, a full-width indigo generate button with loading spinner, and a tiny trust note with a green status dot.


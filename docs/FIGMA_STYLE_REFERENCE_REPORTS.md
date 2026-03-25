# CourseMate Reports — Figma style reference (`src/Reports.jsx`)

This is a focused style reference for the Reports screen only, derived from `src/Reports.jsx`.

Use this when creating a new Figma template for the Reports experience so it stays visually aligned with the shipped UI.

---

## 1) Screen structure

- Two-column layout: `flex gap-4 items-start`
- Left rail: fixed width `220px`, min-height `520px`
- Right panel: flexible report-config canvas
- Both surfaces are white card shells:
  - `bg-white rounded-2xl border border-gray-200 shadow-sm`

---

## 2) Color system used in Reports

Primary tone is **Indigo + Gray** with semantic accent colors and subtle template-state highlighting.

### Core UI colors

- Primary action: `indigo-600` (`hover: indigo-700`)
- Focus: `ring-indigo-300`, `border-indigo-400`
- Selected/template active state:
  - card bg `indigo-50`
  - border `indigo-300`
  - text `indigo-600 / indigo-700`
- Base text:
  - title `gray-900`
  - body `gray-500`
  - labels `gray-700`
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

Text hierarchy in Reports:

- Main heading: `text-xl font-bold text-gray-900`
- Intro/body copy: `text-sm text-gray-500`
- Field labels: `text-sm font-medium text-gray-700`
- Template title: `text-sm font-semibold` (indigo when active)
- Template description: `text-xs text-gray-500`
- Sidebar labels/meta: `text-[10px] text-gray-400` with uppercase + tracking
- CTA label: `text-sm font-semibold`

Micro-typography details:

- Uses `tabular-nums` for source counter
- Character count helper uses `text-[10px]`

---

## 4) Component specs (Reports-specific)

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
- Compact size: `h-4 w-7`

### C) Template selection grid

- Grid: `grid grid-cols-2 gap-3`
- Template card:
  - Base: `p-4 rounded-xl border bg-white border-gray-200`
  - Hover: `hover:border-gray-300 hover:bg-gray-50`
  - Active: `bg-indigo-50 border-indigo-300`
- Active indicator dot:
  - `absolute top-3 right-3 w-3 h-3 rounded-full bg-indigo-600`
- Icon/text states:
  - icon `indigo-600` when active, `gray-400` otherwise
  - title `indigo-700` when active, `gray-800` otherwise

### D) Custom prompt textarea (conditional)

- Appears only for "Create Your Own" template
- Input shell:
  - `rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800`
  - `focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400`
  - `resize-none` for controlled vertical size
- Meta helper: character count `text-[10px] text-gray-400`

### E) Summary strip

- Container: `rounded-lg bg-indigo-50 border border-indigo-100 px-3 py-2.5`
- Leading icon: filled sparkle
- Text:
  - primary `text-xs text-indigo-700`
  - secondary `text-indigo-500`
- Emphasis on selected template label with `font-semibold`

### F) Primary CTA (Generate Report)

- Full-width action:
  - `rounded-xl bg-indigo-600 text-white text-sm font-semibold shadow-sm`
  - hover `indigo-700`
  - disabled `opacity-50 cursor-not-allowed`
- Loading state:
  - inline spinner `h-4 w-4 animate-spin`

### G) Footer trust note

- `text-[10px] text-gray-400` line with `green-400` status dot
- Inline help link: `text-indigo-500 hover:underline`

---

## 5) Radius, spacing, elevation

- Radii:
  - Panels: `rounded-2xl`
  - Template cards + controls: `rounded-xl` / `rounded-lg`
- Spacing:
  - Split gap `gap-4`
  - Form rhythm `gap-5`
  - Template grid gap `gap-3`
- Elevation:
  - Primary surfaces and CTA use `shadow-sm`

---

## 6) Iconography

- Template icons are larger than utility icons (`18px`) with stroke style (`strokeWidth=1.75`)
- Utility/source icons are compact (`13px`) with stroke `2.5`
- Sparkle icon is filled for AI-action emphasis

---

## 7) Figma prompt block (paste-ready)

Use this exact prompt in Figma:

Design a "Custom Report Generator" screen for an education app. Keep a two-column layout: left a narrow 220px Sources rail, right a larger configuration card. Use white surfaces, soft gray borders (`gray-200`), rounded corners (16px outer, 12px template cards, 8px controls), and subtle `shadow-sm`. Primary accent is indigo (`indigo-600`) for CTA, active template states, and focus rings; hover to `indigo-700`. Include a 2x2 template grid with icon, title, description, and active state (indigo-tinted card with a small top-right selection dot). Add an optional custom prompt textarea for "Create Your Own". Use system sans typography: xl bold title, 14px labels/body, 12px descriptions, 10px metadata. Include an indigo info strip, red error text, and a full-width indigo generate button with loading spinner.


# CourseMate — Figma style reference

Use this document as a **paste-in prompt** for Figma (Make / AI layout) or as a checklist when building a new template. The app uses **Tailwind CSS v4** with the **default palette** (utility classes in source). **No custom `@theme` color tokens** — brand is expressed through **Indigo + Gray** with **Cyan** accents in gradients.

---

## 1. Visual personality (one paragraph for Figma)

Clean, academic-product UI: **light surfaces**, **soft borders**, **indigo as the single strong brand color**, generous **rounded corners** (lg → 2xl), subtle **shadow-sm** on cards, occasional **full-viewport gradients** (indigo → white → cyan). Typography is **system UI**: crisp, readable, with **small caps labels** (uppercase + wide tracking) for section headers. Dense information (chat, sources) uses **xs (10–11px)** metadata and **sm** body; marketing-style headers use **lg / xl / 3xl**.

---

## 2. Typography

| Role | Implementation | Figma suggestion |
|------|----------------|------------------|
| **Font family** | `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif` (`src/App.css`) | **Inter** or **SF Pro** / system stack |
| **Page / hero title** | `text-3xl font-bold text-gray-900` | ~30px, bold, Gray 900 |
| **Section title** | `text-sm font-semibold text-gray-700 uppercase tracking-wide` | 14px semibold, Gray 700, uppercase, +0.05em tracking |
| **Card / panel title** | `text-sm font-semibold text-gray-800` | 14px semibold, Gray 800 |
| **Body** | `text-sm text-gray-700` with relaxed leading | 14px, Gray 700, line-height ~1.5–1.6 |
| **Secondary body** | `text-sm text-gray-600` | 14px Gray 600 |
| **Caption / meta** | `text-xs text-gray-400` or `text-gray-500` | 12px Gray 400/500 |
| **Micro labels** | `text-[9px]`, `text-[10px]`, `text-[11px]` for badges, table cells | 9–11px |
| **Brand line in chat** | `text-xs font-semibold text-indigo-600 uppercase tracking-wide` | 12px semibold Indigo 600, uppercase |
| **Code / API** | `font-mono` on inputs and keys | Monospace 12–14px |
| **Math** | KaTeX (inline/display) — keep body size consistent | Match body, serif for equations |

**Emphasis:** `font-medium`, `font-semibold`, `font-bold` — avoid extra weights.

---

## 3. Color system (semantic usage + Tailwind default hex)

Brand and neutrals drive the UI; other hues are **semantic** or **file-type** accents.

### 3.1 Core brand — Indigo

| Token | Hex (Tailwind default) | Usage |
|-------|-------------------------|--------|
| Indigo 50 | `#EEF2FF` | Selected row, light panels, streaming status bubble |
| Indigo 100 | `#E0E7FF` | Badges, citation chips, focus backgrounds |
| Indigo 200 | `#C7D2FE` | Borders on indigo pills |
| Indigo 400 | `#818CF8` | Focus ring (`focus:ring-indigo-400`), active borders |
| Indigo 500 | `#6366F1` | Icons, checkbox checked |
| Indigo 600 | `#4F46E5` | **Primary buttons**, links, strong brand |
| Indigo 700 | `#4338CA` | Primary hover |

### 3.2 Neutrals — Gray

| Token | Hex | Usage |
|-------|-----|--------|
| Gray 50 | `#F9FAFB` | Panel backgrounds, alternating rows |
| Gray 100 | `#F3F4F6` | Borders `divide-gray-100`, inactive pills |
| Gray 200 | `#E5E7EB` | **Default card/input border** |
| Gray 300 | `#D1D5DB` | Placeholder borders, disabled feel |
| Gray 400 | `#9CA3AF` | Icons, tertiary text |
| Gray 500 | `#6B7280` | Secondary labels |
| Gray 600 | `#4B5563` | Body secondary |
| Gray 700 | `#374151` | Headings, emphasis |
| Gray 800 | `#1F2937` | Strong titles |
| Gray 900 | `#111827` | Primary headings |

### 3.3 Page atmosphere — Gradients

- **Background:** `bg-gradient-to-br from-indigo-50 via-white to-cyan-50` — soft corner wash (Indigo 50 → White → Cyan 50).
- **Hero / avatar blob:** `from-indigo-500 to-cyan-500` or `from-indigo-400 to-cyan-400` — use for logo tiles, empty avatars.

**Cyan** is **accent only** (gradients, decorative), not for primary actions.

### 3.4 Semantic

| Meaning | Colors |
|---------|--------|
| Success | Green 50 bg, Green 600/700 text, Green 200 border |
| Error / danger | Red 50 bg, Red 600/700 text, Red 200/300 border; destructive buttons **Red 600** |
| Warning | Amber 50 / Amber 700 (sharing pending, etc.) |
| Info highlight | Indigo 50 / Indigo 100 panels |

### 3.5 File-type badges (chat materials)

Small pill: **rose** (PDF), **blue** (DOC), **green** (XLS/CSV), **purple** (images), **orange** (SVG), **gray** (TXT). Text one step darker than bg (e.g. `bg-blue-100 text-blue-600`).

### 3.6 Web / sources

- Teal pills for external links: `bg-teal-50 text-teal-700 border-teal-200`.
- Source panel: left accent `border-l-4 border-indigo-400` when focused.

---

## 4. Layout & spacing

- **Base unit:** Tailwind **4px** (`gap-1` = 4px). Common gaps: `gap-1.5`, `gap-2`, `gap-3`.
- **Page padding:** `px-4`, `px-6` for main content.
- **Card padding:** `p-3`, `p-4`, `p-6` depending on density.
- **Max width:** profile and auth often `max-w-md` (~448px) for forms.

---

## 5. Shape, elevation, borders

| Element | Classes | Figma |
|---------|---------|--------|
| Inputs, small buttons | `rounded-lg` | 8px radius |
| Cards, modals | `rounded-xl` | 12px |
| Shell cards, chat container | `rounded-2xl` | 16px |
| Pills / chips | `rounded-full` | 9999 |
| Default border | `border border-gray-200` | 1px Gray 200 |
| Hairline dividers | `border-gray-100` | 1px Gray 100 |
| Shadow | `shadow-sm` on cards; `shadow-xl` for overlay panels | subtle / modal |
| Glass | `bg-white/80 backdrop-blur-sm` | semi-transparent white + blur |

---

## 6. Components (recurring patterns)

**Primary button**

- `bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors`

**Secondary / ghost**

- `border border-gray-200 text-gray-600 hover:bg-gray-50 rounded-lg`

**Destructive**

- Outline: `border-red-300 text-red-600 hover:bg-red-50`
- Solid: `bg-red-600 hover:bg-red-700 text-white`

**Text input**

- `border border-gray-200 bg-white rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400`

**Icon button**

- `p-1.5 rounded-lg text-gray-400 hover:text-indigo-600 hover:bg-indigo-50`

**List row / sidebar item**

- Default `text-gray-600`; active `bg-indigo-50 text-indigo-700 font-medium`

**Streaming / status bubble**

- `bg-indigo-50 border border-indigo-100 rounded-xl px-4 py-3` with pulsing `bg-indigo-400` dot

**Modal / sheet**

- `bg-white/80 backdrop-blur-sm border border-gray-200 rounded-2xl shadow-sm`

---

## 7. Icons

- Stroke icons: **2–2.5** stroke width, `currentColor`, typically **12–16px** viewBox 24.
- Default icon color: **Gray 400**; hover **Indigo 600** or **Gray 600**.

---

## 8. Short “Figma AI” paste block

Copy everything below the line into Figma:

---

**Prompt:** Design a template for a learning app called CourseMate. Style: light UI, white and gray-50 surfaces, **indigo (#4F46E5)** primary buttons and focus states, **gray** text hierarchy (900 titles, 700 body, 400–500 meta). Use **rounded-xl** cards and **rounded-2xl** main panels, **1px gray-200** borders, **shadow-sm**. Page background: subtle **diagonal gradient** from indigo-50 through white to cyan-50. Typography: **system UI** (Inter-like), **14px** body, **12px** captions, **uppercase wide-tracked** section labels. Primary CTA: filled indigo; secondary: outlined gray. Include semantic red for errors and green for success. Dense chat UI uses small pills, monospace for code keys, and teal accents for external links. No dark mode. Avoid heavy borders; prefer soft fills (indigo-50) for selection.

---

## 9. Optional: screenshots for Figma

For pixel-perfect match, capture:

1. **Sign-in** — gradient hero, centered card.
2. **Profile** — form sections, API key list, danger zone.
3. **Chat** — sidebar + main thread + input bar + model dropdown.
4. **Sharing modal** — pills and member list.

---

*Generated from repository conventions (`src/App.css`, Tailwind v4, `src/ChatTab.jsx`, `ProfilePage.jsx`, `SignInPage.jsx`, `SharingAccessModal.jsx`).*

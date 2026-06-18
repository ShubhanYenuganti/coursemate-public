# Page Migration Checklist (shadcn Visual Refresh)

Apply per page. Logic/handlers stay byte-identical — markup/className only.
Derived from the CoursePage pilot (`src/CoursePage.jsx`).

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
  ("none"/"default") to '' in onValueChange (and `value={x || 'sentinel'}`),
  so the saved value stays identical. See CoursePage AI-model panel.
- Panels/cards → `Card`/`CardHeader`/`CardTitle`/`CardDescription`/`CardContent`.
- Modals → `Dialog` (replaces CreateCourseModal/SharingAccessModal patterns).

## 4. Retint leftovers to tokens
- `indigo-600`→`primary`, `indigo-700`/active→`accent-foreground`,
  `indigo-50`→`accent`, `gray-200` borders→`border`, `bg-white`→`background`,
  `text-gray-900`→`text-foreground`, `text-gray-600`/`-400`→`text-muted-foreground`,
  `focus:ring-indigo-400`→`focus:ring-ring`, `text-red-600`→`text-destructive`.
- Grep gate (must return nothing in a fully-migrated page):
  `grep -nE "gray-[0-9]|bg-white|indigo-[0-9]|red-[0-9]" src/<File>.jsx`

## 5. Verify
- `npm run build` clean → `npm test` green → visual check vs mockup.
- Commit per logical section, message: `refactor(<page>): <section> -> shadcn`.

## Notes
- Keep signature custom pieces (e.g. CoursePage floating toolbar / ToolbarItem)
  as styled elements retinted to tokens — do not force them into a primitive.
- Light-only: never add `dark:` classes; tokens carry future dark mode.

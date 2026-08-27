# Design System

Personal tool, so the goal is clarity and speed — not polish. Every session should produce UI that looks like it belongs to the same app.

## Stack

React + Vite. No UI framework. Use Tailwind CSS for all styling. No component library (keeps the dep tree small and avoids version drift). Custom components live in `frontend/src/components/`.

---

## Colours

```
Background          #0f172a   (slate-900)
Surface (cards)     #1e293b   (slate-800)
Border              #334155   (slate-700)
Text primary        #f1f5f9   (slate-100)
Text secondary      #94a3b8   (slate-400)
Accent / action     #3b82f6   (blue-500)
Accent hover        #2563eb   (blue-600)
```

Status badge colours:

| Status       | Background   | Text       |
|---|---|---|
| New          | #1e3a5f      | #93c5fd (blue-300)   |
| Saved        | #1e3a2f      | #86efac (green-300)  |
| Applied      | #3b2a1e      | #fdba74 (orange-300) |
| Interviewing | #2d1e3b      | #c4b5fd (violet-300) |
| Rejected     | #2d1e1e      | #fca5a5 (red-300)    |
| Offer        | #1a3320      | #4ade80 (green-400)  |

Score ring / bar colours:

| Range   | Colour           |
|---|---|
| 80–100  | #4ade80 (green-400)  |
| 60–79   | #facc15 (yellow-400) |
| 40–59   | #fb923c (orange-400) |
| 0–39    | #f87171 (red-400)    |

---

## Typography

- Font: system-ui stack — no Google Fonts import.
- Body: `text-sm` (14px), `text-slate-100`
- Card title (job title): `text-base font-semibold`
- Section headings: `text-lg font-semibold`
- Labels / secondary info: `text-xs text-slate-400`
- Monospace (scores, IDs): `font-mono`

---

## Spacing and layout

- Page max-width: `max-w-7xl mx-auto px-6`
- Card padding: `p-4`
- Card gap in grid: `gap-4`
- Section vertical spacing: `space-y-6`
- Dashboard layout: sidebar (filters, 280px fixed) + main content area (flex-1)

---

## Components

### JobCard

```
┌──────────────────────────────────────────────────────┐
│  [Score ring]  Title                      [Source]   │
│                Company · Location · $salary range     │
│                                                       │
│  LLM rationale (2–3 lines, slate-400, italic)        │
│                                                       │
│  [Status badge]                  [↗ View listing]    │
│  Date fetched                                        │
└──────────────────────────────────────────────────────┘
```

- Score ring: small circular progress (40px), colour from score range table above, number inside in `font-mono`.
- Source badge: top-right, uppercase, `text-xs`, `bg-slate-700 text-slate-300 rounded px-2 py-0.5`.
- Status badge: clickable — clicking it opens an inline dropdown to change status.
- "View listing" opens the job URL in a new tab.

### FiltersBar

Vertical sidebar, sticky. Controls in order:

1. Score threshold — range slider (0–100), shows current value
2. Source — checkbox group: Adzuna, Jooble, (All)
3. Status — checkbox group: New, Saved, Applied, Interviewing, Rejected, Offer, (All)
4. Date fetched — select: Today, Last 7 days, Last 30 days, All time

"Reset filters" link at the bottom resets all to defaults.

### ProfileForm

Standard stacked form. Fields in order:

1. Target titles (tag input — comma-separated or Enter to add)
2. Skills (tag input)
3. Seniority (radio: Junior / Mid / Senior / Lead / Exec)
4. Locations (tag input — city/province)
5. Salary range (two number inputs: Min CAD / Max CAD)
6. Preferences (optional textarea)

Submit button: `bg-blue-500 hover:bg-blue-600 text-white rounded px-4 py-2`.
Show a success toast (3 s, bottom-right) on save.

### FetchButton

```
[↻ Fetch new jobs]
```

Top-right of the dashboard header. While fetching: spinner + "Fetching…" text, button disabled. On success: show "12 new jobs found" (or "No new jobs") as a dismissible banner below the header. On error: red banner with the error message.

### StatusDropdown

Inline dropdown triggered by clicking the status badge on a card. Shows all six statuses as options; current one is checked. Selecting a new one fires `PATCH /jobs/{id}/status` immediately (optimistic update).

### NotesPanel

Slide-in panel from the right (not a modal) triggered by a "Notes" button on a card. Contains a `<textarea>` pre-filled with current notes. Auto-saves on blur (debounced 500 ms).

---

## Interaction patterns

- **No modals** for job details — use a slide-in panel or inline expansion.
- **Optimistic updates** for status changes and notes — update the UI immediately, revert on error.
- **Loading state**: skeleton cards (same dimensions as real cards, `animate-pulse bg-slate-700`).
- **Empty state**: centred message + icon, e.g. "No jobs match your filters. Try lowering the score threshold."
- **Error state**: red banner at the top of the affected section with the message from the API.
- **Toasts**: bottom-right, 3 s auto-dismiss, one visible at a time.

---

## What not to add

- No light mode. Dark only.
- No animations beyond Tailwind's `animate-pulse` and simple `transition-colors`.
- No charts or graphs for MVP (score ring is sufficient).
- No drag-and-drop.

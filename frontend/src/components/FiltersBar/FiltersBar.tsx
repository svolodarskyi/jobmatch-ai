import { type Filters, DEFAULT_FILTERS } from './types'

export type { Filters, FiltersBarProps }
export { DEFAULT_FILTERS }

export interface FiltersBarProps {
  filters: Filters
  onFilterChange: (filters: Filters) => void
}

const SOURCES = ['adzuna', 'jooble'] as const
const STATUSES = ['New', 'Saved', 'Applied', 'Interviewing', 'Rejected', 'Offer'] as const

const DATE_OPTIONS = [
  { label: 'Today', value: 'today' },
  { label: 'Last 7 days', value: '7d' },
  { label: 'Last 30 days', value: '30d' },
  { label: 'All time', value: 'all' },
] as const

type DateOption = (typeof DATE_OPTIONS)[number]['value']

function dateOptionToSince(option: DateOption): string | null {
  if (option === 'all') return null
  const now = new Date()
  if (option === 'today') {
    const d = new Date(now)
    d.setHours(0, 0, 0, 0)
    return d.toISOString()
  }
  const days = option === '7d' ? 7 : 30
  const d = new Date(now)
  d.setDate(d.getDate() - days)
  d.setHours(0, 0, 0, 0)
  return d.toISOString()
}

function sinceToDateOption(since: string | null): DateOption {
  if (since === null) return 'all'
  const sinceDate = new Date(since)
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  const diff = Math.round((now.getTime() - sinceDate.getTime()) / (1000 * 60 * 60 * 24))
  if (diff === 0) return 'today'
  if (diff <= 7) return '7d'
  if (diff <= 30) return '30d'
  return 'all'
}

// ── Section header ───────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">
      {children}
    </p>
  )
}

// ── FiltersBar ───────────────────────────────────────────────────────────────

export default function FiltersBar({ filters, onFilterChange }: FiltersBarProps) {
  const selectedDateOption = sinceToDateOption(filters.since)

  function handleScoreChange(e: React.ChangeEvent<HTMLInputElement>) {
    onFilterChange({ ...filters, min_score: Number(e.target.value) })
  }

  function handleSourceChange(src: string | null) {
    onFilterChange({ ...filters, source: src })
  }

  function handleStatusChange(st: string | null) {
    onFilterChange({ ...filters, status: st })
  }

  function handleDateChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const option = e.target.value as DateOption
    onFilterChange({ ...filters, since: dateOptionToSince(option) })
  }

  function handleReset() {
    onFilterChange({ ...DEFAULT_FILTERS })
  }

  return (
    <aside
      aria-label="Filters"
      className="w-[280px] flex-shrink-0 sticky top-0 h-screen bg-slate-800 border-r border-slate-700 flex flex-col overflow-y-auto"
    >
      <div className="p-5 flex flex-col gap-6 flex-1">
        {/* ── Score threshold ──────────────────────────────────────────── */}
        <section>
          <SectionLabel>Score threshold</SectionLabel>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={0}
              max={100}
              value={filters.min_score}
              onChange={handleScoreChange}
              aria-label="Score threshold"
              className="flex-1 accent-blue-500"
            />
            <span className="text-sm font-mono text-slate-100 w-8 text-right">
              {filters.min_score}
            </span>
          </div>
        </section>

        {/* ── Source ───────────────────────────────────────────────────── */}
        <section>
          <SectionLabel>Source</SectionLabel>
          <div className="flex flex-col gap-1.5">
            {SOURCES.map((src) => (
              <label key={src} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={filters.source === src}
                  onChange={(e) => handleSourceChange(e.target.checked ? src : null)}
                  className="accent-blue-500"
                  aria-label={src.charAt(0).toUpperCase() + src.slice(1)}
                />
                <span className="text-sm text-slate-100 capitalize">{src}</span>
              </label>
            ))}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={filters.source === null}
                onChange={(e) => { if (e.target.checked) handleSourceChange(null) }}
                className="accent-blue-500"
                aria-label="All sources"
              />
              <span className="text-sm text-slate-100">All</span>
            </label>
          </div>
        </section>

        {/* ── Status ───────────────────────────────────────────────────── */}
        <section>
          <SectionLabel>Status</SectionLabel>
          <div className="flex flex-col gap-1.5">
            {STATUSES.map((st) => (
              <label key={st} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={filters.status === st}
                  onChange={(e) => handleStatusChange(e.target.checked ? st : null)}
                  className="accent-blue-500"
                  aria-label={st}
                />
                <span className="text-sm text-slate-100">{st}</span>
              </label>
            ))}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={filters.status === null}
                onChange={(e) => { if (e.target.checked) handleStatusChange(null) }}
                className="accent-blue-500"
                aria-label="All statuses"
              />
              <span className="text-sm text-slate-100">All</span>
            </label>
          </div>
        </section>

        {/* ── Date fetched ─────────────────────────────────────────────── */}
        <section>
          <SectionLabel>Date fetched</SectionLabel>
          <select
            value={selectedDateOption}
            onChange={handleDateChange}
            aria-label="Date fetched"
            className="w-full bg-slate-700 border border-slate-600 text-slate-100 text-sm rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {DATE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </section>
      </div>

      {/* ── Reset ────────────────────────────────────────────────────────── */}
      <div className="p-5 border-t border-slate-700">
        <button
          onClick={handleReset}
          className="text-sm text-blue-400 hover:text-blue-300 underline bg-transparent border-0 p-0 cursor-pointer"
        >
          Reset filters
        </button>
      </div>
    </aside>
  )
}

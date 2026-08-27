import { useEffect, useState } from 'react'
import JobCard, { type Job } from '../../components/JobCard/JobCard'
import { type StatusHistoryEntry } from '../../components/StatusDropdown/StatusDropdown'

const API_BASE = 'http://localhost:8000'

// Fetch once on mount with a limit large enough to cover the whole table.
// Do NOT use limit=0 expecting "unlimited" — GET /jobs/ slices results as
// merged[offset:offset+limit], so limit=0 returns zero rows.
const FETCH_LIMIT = 1000

// "All" plus the five actionable statuses, in the canonical order used
// throughout the app (design-system.md's status badge table,
// StatusDropdown.ALL_STATUSES, FiltersBar.STATUSES). No "New" tab — jobs
// that haven't been acted on yet already have a home in Matches/All Jobs.
const TABS = ['All', 'Saved', 'Applied', 'Interviewing', 'Rejected', 'Offer'] as const
type Tab = (typeof TABS)[number]

// ── Skeleton card ────────────────────────────────────────────────────────────
// Mirrors Dashboard's/AllJobs's SkeletonCard — duplicated here rather than
// shared since this issue is scoped to page-local markup only (no new
// shared component).

function SkeletonCard() {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 flex flex-row gap-4 animate-pulse">
      <div className="w-10 h-10 rounded-full bg-slate-700 flex-shrink-0" />
      <div className="flex flex-col gap-2 flex-1">
        <div className="h-4 bg-slate-700 rounded w-2/3" />
        <div className="h-3 bg-slate-700 rounded w-1/2" />
        <div className="h-3 bg-slate-700 rounded w-full" />
        <div className="h-3 bg-slate-700 rounded w-5/6" />
        <div className="h-5 bg-slate-700 rounded w-16 mt-1" />
      </div>
    </div>
  )
}

// ── Tab button ────────────────────────────────────────────────────────────────
// Copy of AllJobs.tsx's FilterButton — inline per the issue's constraint
// (it isn't exported, so it's copied, not imported).

function FilterButton({
  active,
  onClick,
  label,
  children,
  testId,
}: {
  active: boolean
  onClick: () => void
  label?: string
  children: React.ReactNode
  testId?: string
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      aria-label={label}
      data-testid={testId}
      className={`text-xs rounded px-3 py-1.5 font-medium transition-colors ${
        active
          ? 'bg-blue-500 text-white'
          : 'bg-slate-800 border border-slate-700 text-slate-300 hover:text-slate-100'
      }`}
    >
      {children}
    </button>
  )
}

// ── Tracking ─────────────────────────────────────────────────────────────────

export default function Tracking() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<Tab>('All')
  const [fitsMeFilter, setFitsMeFilter] = useState(false)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetch(`${API_BASE}/jobs/?limit=${FETCH_LIMIT}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((data: { total: number; jobs: Job[] }) => {
        setTotal(data.total)
        setJobs(data.jobs)
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load jobs.')
      })
      .finally(() => setLoading(false))
  }, [])

  function handleStatusChange(id: string, newStatus: string, history: StatusHistoryEntry[]) {
    setJobs((prev) =>
      prev.map((j) => (j.id === id ? { ...j, status: newStatus, status_history: history } : j)),
    )
  }

  function handleNotesChange(id: string, notes: string) {
    setJobs((prev) => prev.map((j) => (j.id === id ? { ...j, notes } : j)))
  }

  function handleFitsMeToggle(id: string, next: boolean) {
    setJobs((prev) => prev.map((j) => (j.id === id ? { ...j, fits_me: next } : j)))
  }

  // Jobs the user has taken some action on — the universe this whole view
  // operates over. "All" tab = every one of these.
  const trackedJobs = jobs.filter((job) => job.status !== 'New')

  const tabFilteredJobs =
    activeTab === 'All' ? trackedJobs : trackedJobs.filter((job) => job.status === activeTab)

  const filteredJobs = fitsMeFilter
    ? tabFilteredJobs.filter((job) => job.fits_me === true)
    : tabFilteredJobs

  return (
    <div className="flex-1 text-slate-100 font-[system-ui]">
      <div className="px-6 py-10">
        <div className="flex items-baseline gap-2 mb-6">
          <h1 className="text-lg font-semibold text-slate-100">Tracking</h1>
          {!loading && !error && (
            <span className="text-slate-400 text-sm" data-testid="tracking-count">
              ({filteredJobs.length})
            </span>
          )}
        </div>

        {/* Error banner */}
        {error && (
          <div
            role="alert"
            className="mb-4 rounded bg-red-900/50 border border-red-700 text-red-300 px-4 py-3 text-sm"
          >
            {error}
          </div>
        )}

        {/* Loading skeletons */}
        {loading && (
          <div className="flex flex-col gap-4" data-testid="loading-skeletons">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        )}

        {!loading && !error && (
          <>
            {/* Empty state — zero jobs total */}
            {total === 0 && (
              <div className="flex items-center justify-center py-24">
                <p className="text-slate-400 text-sm text-center">
                  No jobs yet. Go to Dashboard and run a fetch to pull in listings.
                </p>
              </div>
            )}

            {total > 0 && (
              <>
                {/* Tab bar */}
                <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
                  <div className="flex items-center flex-wrap gap-2" role="group" aria-label="Status tabs">
                    {TABS.map((tab) => (
                      <FilterButton key={tab} active={activeTab === tab} onClick={() => setActiveTab(tab)}>
                        {tab}
                      </FilterButton>
                    ))}
                  </div>

                  <div className="flex items-center gap-2" role="group" aria-label="Filters">
                    <FilterButton
                      active={fitsMeFilter}
                      onClick={() => setFitsMeFilter((prev) => !prev)}
                      label="Show only Fits Me jobs"
                      testId="fits-me-filter-button"
                    >
                      ★ Fits Me
                    </FilterButton>
                  </div>
                </div>

                {/* Empty state — no jobs tracked yet (every job is still New) */}
                {trackedJobs.length === 0 && (
                  <div className="flex items-center justify-center py-24">
                    <p className="text-slate-400 text-sm text-center">
                      No jobs tracked yet. Save a job or change its status from Matches or All Jobs
                      to start tracking it here.
                    </p>
                  </div>
                )}

                {/* Empty state — this tab has zero matches, other tabs have jobs */}
                {trackedJobs.length > 0 && tabFilteredJobs.length === 0 && (
                  <div className="flex items-center justify-center py-24">
                    <p className="text-slate-400 text-sm text-center">
                      No jobs are marked {activeTab}.
                    </p>
                  </div>
                )}

                {/* Empty state — tab has jobs, but none are Fits Me */}
                {tabFilteredJobs.length > 0 && filteredJobs.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-24 gap-3">
                    <p className="text-slate-400 text-sm text-center">No jobs match your filters.</p>
                    <button
                      onClick={() => setFitsMeFilter(false)}
                      className="text-sm text-blue-400 hover:text-blue-300 underline"
                    >
                      Reset filters
                    </button>
                  </div>
                )}

                {/* Job cards */}
                {filteredJobs.length > 0 && (
                  <div className="flex flex-col gap-4">
                    {filteredJobs.map((job) => (
                      <JobCard
                        key={job.id}
                        job={job}
                        onStatusChange={handleStatusChange}
                        onNotesChange={handleNotesChange}
                        onFitsMeToggle={handleFitsMeToggle}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}

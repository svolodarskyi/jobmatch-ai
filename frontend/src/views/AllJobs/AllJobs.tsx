import { useEffect, useState } from 'react'
import JobCard, { type Job } from '../../components/JobCard/JobCard'
import { type StatusHistoryEntry } from '../../components/StatusDropdown/StatusDropdown'

const API_BASE = 'http://localhost:8000'

// Fetch once on mount with a limit large enough to cover the whole table.
// Do NOT use limit=0 expecting "unlimited" — GET /jobs/ slices results as
// merged[offset:offset+limit], so limit=0 returns zero rows.
const FETCH_LIMIT = 1000

type ScoreFilter = 'all' | 'has' | 'none'
type SourceFilter = 'all' | 'adzuna' | 'jooble'

// ── Skeleton card ────────────────────────────────────────────────────────────
// Mirrors Dashboard's SkeletonCard — duplicated here rather than shared since
// this issue is scoped to page-local markup only (no new shared component).

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

// ── Filter toggle button ─────────────────────────────────────────────────────

function FilterButton({
  active,
  onClick,
  label,
  children,
}: {
  active: boolean
  onClick: () => void
  label?: string
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      aria-label={label}
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

// ── AllJobs ──────────────────────────────────────────────────────────────────

export default function AllJobs() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [scoreFilter, setScoreFilter] = useState<ScoreFilter>('all')
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all')

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

  function handleSave(id: string, status: string) {
    setJobs((prev) => prev.map((j) => (j.id === id ? { ...j, status } : j)))
  }

  function handleFitsMeToggle(id: string, next: boolean) {
    setJobs((prev) => prev.map((j) => (j.id === id ? { ...j, fits_me: next } : j)))
  }

  function handleResetFilters() {
    setScoreFilter('all')
    setSourceFilter('all')
  }

  const filtersActive = scoreFilter !== 'all' || sourceFilter !== 'all'

  const filteredJobs = jobs.filter((job) => {
    if (scoreFilter === 'has' && job.raw_score === null) return false
    if (scoreFilter === 'none' && job.raw_score !== null) return false
    if (sourceFilter !== 'all' && job.source !== sourceFilter) return false
    return true
  })

  return (
    <div className="flex-1 text-slate-100 font-[system-ui]">
      <div className="px-6 py-10">
        <h1 className="text-lg font-semibold text-slate-100 mb-6">All Jobs</h1>

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
                {/* Top filter bar */}
                <div className="flex items-center flex-wrap gap-6 mb-4" role="group" aria-label="Filters">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">Score:</span>
                    <FilterButton
                      active={scoreFilter === 'all'}
                      onClick={() => setScoreFilter('all')}
                      label="All scores"
                    >
                      All
                    </FilterButton>
                    <FilterButton active={scoreFilter === 'has'} onClick={() => setScoreFilter('has')}>
                      Has score
                    </FilterButton>
                    <FilterButton active={scoreFilter === 'none'} onClick={() => setScoreFilter('none')}>
                      No score
                    </FilterButton>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">Source:</span>
                    <FilterButton
                      active={sourceFilter === 'all'}
                      onClick={() => setSourceFilter('all')}
                      label="All sources"
                    >
                      All
                    </FilterButton>
                    <FilterButton
                      active={sourceFilter === 'adzuna'}
                      onClick={() => setSourceFilter('adzuna')}
                    >
                      Adzuna
                    </FilterButton>
                    <FilterButton
                      active={sourceFilter === 'jooble'}
                      onClick={() => setSourceFilter('jooble')}
                    >
                      Jooble
                    </FilterButton>
                  </div>
                </div>

                {/* Truncation note — limit=1000 cap was hit */}
                {jobs.length < total && (
                  <p className="text-xs text-slate-400 mb-4">
                    Showing {jobs.length} of {total} jobs
                  </p>
                )}

                {/* Empty state — filters applied, zero matches */}
                {filteredJobs.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-24 gap-3">
                    <p className="text-slate-400 text-sm text-center">No jobs match your filters.</p>
                    {filtersActive && (
                      <button
                        onClick={handleResetFilters}
                        className="text-sm text-blue-400 hover:text-blue-300 underline"
                      >
                        Reset filters
                      </button>
                    )}
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
                        onSave={handleSave}
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

import { useEffect, useState } from 'react'
import JobCard, { type Job } from '../../components/JobCard/JobCard'
import { type StatusHistoryEntry } from '../../components/StatusDropdown/StatusDropdown'
import FiltersBar, {
  type Filters,
  DEFAULT_FILTERS,
} from '../../components/FiltersBar/FiltersBar'
import FetchButton from '../../components/FetchButton/FetchButton'

const API_BASE = 'http://localhost:8000'

// ── Skeleton card ────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 flex flex-row gap-4 animate-pulse">
      {/* Score ring placeholder */}
      <div className="w-10 h-10 rounded-full bg-slate-700 flex-shrink-0" />
      {/* Content placeholder */}
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

// ── Build query params from filters ─────────────────────────────────────────

function buildJobsUrl(filters: Filters): string {
  const params = new URLSearchParams()
  if (filters.min_score > 0) params.set('min_score', String(filters.min_score))
  if (filters.source) params.set('source', filters.source)
  if (filters.status) params.set('status', filters.status)
  if (filters.since) params.set('since', filters.since)
  const qs = params.toString()
  return `${API_BASE}/jobs/${qs ? `?${qs}` : ''}`
}

// ── Dashboard ────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [filters, setFilters] = useState<Filters>({ ...DEFAULT_FILTERS })
  const [jobs, setJobs] = useState<Job[]>([])
  const [total, setTotal] = useState<number>(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetch(buildJobsUrl(filters))
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
  }, [filters, refreshTrigger])

  function handleStatusChange(id: string, newStatus: string, history: StatusHistoryEntry[]) {
    setJobs((prev) =>
      prev.map((j) =>
        j.id === id ? { ...j, status: newStatus, status_history: history } : j,
      ),
    )
  }

  function handleNotesChange(id: string, notes: string) {
    setJobs((prev) => prev.map((j) => (j.id === id ? { ...j, notes } : j)))
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 font-[system-ui] flex flex-row">
      {/* Sidebar */}
      <FiltersBar filters={filters} onFilterChange={setFilters} />

      {/* Main content */}
      <main className="flex-1 min-w-0">
        <div className="max-w-4xl mx-auto px-6 py-10">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-lg font-semibold text-slate-100">Job Matches</h1>
            <FetchButton onFetchComplete={() => setRefreshTrigger((n) => n + 1)} />
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

          {/* Loaded state */}
          {!loading && !error && (
            <>
              {/* Total count */}
              {jobs.length > 0 && (
                <p className="text-sm text-slate-400 mb-4">
                  {total} job{total !== 1 ? 's' : ''} found
                </p>
              )}

              {/* Empty state */}
              {jobs.length === 0 && (
                <div className="flex items-center justify-center py-24">
                  <p className="text-slate-400 text-sm text-center">
                    No jobs match your filters. Try lowering the score threshold.
                  </p>
                </div>
              )}

              {/* Job cards grid */}
              {jobs.length > 0 && (
                <div className="flex flex-col gap-4">
                  {jobs.map((job) => (
                    <JobCard
                      key={job.id}
                      job={job}
                      onStatusChange={handleStatusChange}
                      onNotesChange={handleNotesChange}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  )
}

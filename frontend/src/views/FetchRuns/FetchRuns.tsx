import { useEffect, useState } from 'react'

const API_BASE = 'http://localhost:8000'

interface SourceStat {
  new?: number | null
  updated?: number | null
}

interface FetchRun {
  id: string
  started_at: string | null
  completed_at: string | null
  window_days: number | null
  fetched_total: number | null
  new_jobs: number | null
  scored_pass2: number | null
  source_stats?: Record<string, SourceStat> | null
  cost_usd: number | null
  status: string | null
}

type RowStatus = 'running' | 'ok' | 'partial' | 'error'

function formatDate(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('en-CA', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function formatNumber(value: number | null): string {
  return value == null ? '—' : String(value)
}

function formatCost(value: number | null): string {
  return value == null ? '—' : `$${value.toFixed(4)}`
}

function sourceSummary(run: FetchRun, source: string): string {
  const stats = run.source_stats?.[source]
  return `${stats?.new ?? 0} new / ${stats?.updated ?? 0} updated`
}

function rowStatus(run: FetchRun): RowStatus {
  if (run.completed_at === null) return 'running'
  if (run.status === 'error') return 'error'
  if (run.status === 'partial') return 'partial'
  return 'ok'
}

function rowClass(status: RowStatus): string {
  if (status === 'running') return 'text-blue-400'
  if (status === 'error') return 'text-red-400'
  if (status === 'partial') return 'text-amber-400'
  return 'text-slate-100'
}

function statusLabel(status: RowStatus): string {
  return status.charAt(0).toUpperCase() + status.slice(1)
}

export default function FetchRuns() {
  const [runs, setRuns] = useState<FetchRun[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${API_BASE}/fetch-runs?limit=100`)
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json() as Promise<{ runs: FetchRun[] }>
      })
      .then((data) => setRuns(data.runs))
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : 'Failed to load fetch runs.')
      })
      .finally(() => setLoading(false))
  }, [])

  return (
    <main className="flex-1 min-w-0 px-6 py-10 text-slate-100 font-[system-ui]">
      <h1 className="text-lg font-semibold">Fetch Runs</h1>
      <p className="text-sm text-slate-400 mt-1 mb-6">
        {runs.length} run{runs.length === 1 ? '' : 's'}
      </p>
      {loading && <p className="text-sm text-slate-400">Loading fetch runs…</p>}
      {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
      {!loading && !error && runs.length === 0 && (
        <p className="text-sm text-slate-400">No fetch runs yet</p>
      )}
      {!loading && !error && runs.length > 0 && (
        <div className="overflow-x-auto rounded bg-slate-800 border border-slate-700">
          <table aria-label="Fetch runs" className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-slate-400 border-b border-slate-700">
                {['Date', 'Window', 'Retrieved', 'Adzuna', 'Jooble', 'New', 'Scoped', 'Cost', 'Status'].map((heading) => (
                  <th key={heading} className="text-left py-2 px-3 font-medium whitespace-nowrap">{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => {
                const status = rowStatus(run)
                return (
                  <tr key={run.id} data-status={status} className={`border-b border-slate-700/50 ${rowClass(status)}`}>
                    <td className="py-2 px-3 whitespace-nowrap">{formatDate(run.started_at)}</td>
                    <td className="py-2 px-3 font-mono">{run.window_days == null ? '—' : `${run.window_days}d`}</td>
                    <td className="py-2 px-3 font-mono">{formatNumber(run.fetched_total)}</td>
                    <td className="py-2 px-3 font-mono whitespace-nowrap">{sourceSummary(run, 'adzuna')}</td>
                    <td className="py-2 px-3 font-mono whitespace-nowrap">{sourceSummary(run, 'jooble')}</td>
                    <td className="py-2 px-3 font-mono">{formatNumber(run.new_jobs)}</td>
                    <td className="py-2 px-3 font-mono">{formatNumber(run.scored_pass2)}</td>
                    <td className="py-2 px-3 font-mono">{formatCost(run.cost_usd)}</td>
                    <td className="py-2 px-3">{statusLabel(status)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </main>
  )
}

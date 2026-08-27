import { useEffect, useState } from 'react'

const API_BASE = 'http://localhost:8000'

interface SourceStat {
  retrieved?: number
  new?: number
  updated?: number
}

interface FetchRun {
  id: string
  started_at: string
  completed_at: string | null
  window_days: number
  fetched_total: number
  new_jobs: number
  updated_jobs: number
  scored_pass1: number
  scored_pass2: number
  source_stats?: {
    adzuna?: SourceStat
    jooble?: SourceStat
  }
  tokens_in: number
  tokens_out: number
  cost_usd: number
  status: 'ok' | 'partial' | 'error'
  error_message: string | null
}

interface FetchHistoryProps {
  refreshTrigger?: number
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('en-CA', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function formatCost(usd: number): string {
  // Format to 4 significant digits after $
  return `$${usd.toFixed(4)}`
}

function rowClass(status: FetchRun['status']): string {
  if (status === 'error') return 'text-red-400'
  if (status === 'partial') return 'text-amber-400'
  return 'text-slate-100'
}

export default function FetchHistory({ refreshTrigger = 0 }: FetchHistoryProps) {
  const [runs, setRuns] = useState<FetchRun[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    setLoading(true)
    fetch(`${API_BASE}/fetch-runs?limit=10`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((data: { runs: FetchRun[] }) => {
        setRuns(data.runs)
      })
      .catch(() => {
        setRuns([])
      })
      .finally(() => setLoading(false))
  }, [refreshTrigger])

  const last = runs[0] ?? null

  const collapsedSummary = last ? (
    <span className="text-sm text-slate-300">
      Last fetch: {formatDate(last.started_at)} —{' '}
      {last.fetched_total} retrieved (Adzuna {last.source_stats?.adzuna?.retrieved ?? 0},{' '}
      Jooble {last.source_stats?.jooble?.retrieved ?? 0}) · {last.new_jobs} new ·{' '}
      {last.scored_pass2} scoped · {formatCost(last.cost_usd)}
    </span>
  ) : (
    <span className="text-sm text-slate-400">No fetch history yet</span>
  )

  return (
    <div className="mb-4 rounded bg-slate-800 border border-slate-700 px-4 py-2">
      {/* Collapsed bar */}
      <div className="flex items-center justify-between gap-4">
        {loading ? (
          <span className="text-sm text-slate-500">Loading history…</span>
        ) : (
          collapsedSummary
        )}
        <button
          onClick={() => setExpanded((v) => !v)}
          aria-label={expanded ? 'Collapse history' : 'Expand history'}
          className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1 shrink-0"
        >
          {expanded ? '▲' : '▼'} History
        </button>
      </div>

      {/* Expanded table */}
      {expanded && (
        <div className="mt-3 overflow-x-auto">
          {runs.length === 0 ? (
            <p className="text-sm text-slate-400 py-2">No fetch history yet</p>
          ) : (
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="text-slate-400 border-b border-slate-700">
                  <th className="text-left py-1 pr-3 font-medium">Date</th>
                  <th className="text-left py-1 pr-3 font-medium">Window</th>
                  <th className="text-right py-1 pr-3 font-medium">Retrieved</th>
                  <th className="text-right py-1 pr-3 font-medium">Adzuna</th>
                  <th className="text-right py-1 pr-3 font-medium">Jooble</th>
                  <th className="text-right py-1 pr-3 font-medium">New</th>
                  <th className="text-right py-1 pr-3 font-medium">Scoped</th>
                  <th className="text-right py-1 font-medium">Cost</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr
                    key={run.id}
                    className={`border-b border-slate-700/50 ${rowClass(run.status)}`}
                    data-status={run.status}
                  >
                    <td className="py-1 pr-3">{formatDate(run.started_at)}</td>
                    <td className="py-1 pr-3">{run.window_days}d</td>
                    <td className="text-right py-1 pr-3">{run.fetched_total}</td>
                    <td className="text-right py-1 pr-3">
                      {run.source_stats?.adzuna?.retrieved ?? 0}
                    </td>
                    <td className="text-right py-1 pr-3">
                      {run.source_stats?.jooble?.retrieved ?? 0}
                    </td>
                    <td className="text-right py-1 pr-3">{run.new_jobs}</td>
                    <td className="text-right py-1 pr-3">{run.scored_pass2}</td>
                    <td className="text-right py-1">{formatCost(run.cost_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

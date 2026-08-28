import { useEffect, useRef, useState } from 'react'

const API_BASE = 'http://localhost:8000'
const POLL_INTERVAL_MS = 3000
const POLL_TIMEOUT_MS = 5 * 60 * 1000

interface SourceStat {
  retrieved?: number
  new?: number
  updated?: number
}

interface FetchRun {
  id: string
  started_at: string | null
  completed_at: string | null
  window_days: number | null
  fetched_total: number | null
  new_jobs: number | null
  updated_jobs: number | null
  scored_pass1: number | null
  scored_pass2: number | null
  source_stats: {
    adzuna?: SourceStat
    jooble?: SourceStat
  }
  tokens_in: number | null
  tokens_out: number | null
  cost_usd: number | null
  status: string
  error_message: string | null
}

type DisplayStatus = 'running' | 'ok' | 'partial' | 'error'

function displayStatus(run: FetchRun): DisplayStatus {
  if (run.completed_at === null) return 'running'
  if (run.status === 'error') return 'error'
  if (run.status === 'partial') return 'partial'
  return 'ok'
}

const STATUS_LABEL: Record<DisplayStatus, string> = {
  running: 'Running',
  ok: 'OK',
  partial: 'Partial',
  error: 'Error',
}

function rowClass(status: DisplayStatus): string {
  if (status === 'error') return 'text-red-400'
  if (status === 'partial') return 'text-amber-400'
  if (status === 'running') return 'text-blue-400'
  return 'text-slate-100'
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('en-CA', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function formatWindow(days: number | null): string {
  return days === null || days === undefined ? '—' : `${days}d`
}

function formatNum(n: number | null | undefined): string {
  return n === null || n === undefined ? '—' : String(n)
}

function formatCost(usd: number | null | undefined): string {
  return usd === null || usd === undefined ? '—' : `$${usd.toFixed(4)}`
}

function formatSourceStat(stat: SourceStat | undefined): string {
  const n = stat?.new ?? 0
  const u = stat?.updated ?? 0
  if (typeof stat?.retrieved === 'number') {
    return `${stat.retrieved} retrieved · ${n} new / ${u} updated`
  }
  return `${n} new / ${u} updated`
}

function sourceStatClass(stat: SourceStat | undefined): string {
  if (typeof stat?.retrieved !== 'number') return ''
  if (stat.retrieved === 0) return 'text-red-400'
  const n = stat.new ?? 0
  const u = stat.updated ?? 0
  if (n === 0 && u === 0) return 'text-slate-400'
  return ''
}

function hasRunningRow(runs: FetchRun[]): boolean {
  return runs.some((run) => run.completed_at === null)
}

interface FetchRunsProps {
  /** Override poll interval (ms). Default 3000. Use a small value in tests. */
  pollInterval?: number
}

export default function FetchRuns({ pollInterval = POLL_INTERVAL_MS }: FetchRunsProps = {}) {
  const [runs, setRuns] = useState<FetchRun[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const deadlineRef = useRef<number>(0)

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  async function pollForUpdates() {
    if (Date.now() > deadlineRef.current) {
      stopPolling()
      return
    }

    try {
      const res = await fetch(`${API_BASE}/fetch-runs?limit=100`)
      if (!res.ok) return
      const data = (await res.json()) as { runs: FetchRun[] }
      setRuns(data.runs)
      if (!hasRunningRow(data.runs)) {
        stopPolling()
      }
    } catch {
      // transient network error — keep polling
    }
  }

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetch(`${API_BASE}/fetch-runs?limit=100`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((data: { runs: FetchRun[] }) => {
        setRuns(data.runs)
        if (hasRunningRow(data.runs)) {
          deadlineRef.current = Date.now() + POLL_TIMEOUT_MS
          pollRef.current = setInterval(pollForUpdates, pollInterval)
        }
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load fetch runs.')
      })
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="flex-1 text-slate-100 font-[system-ui]">
      <div className="px-6 py-10">
        <h1 className="text-lg font-semibold text-slate-100">Fetch Runs</h1>
        <p className="text-sm text-slate-400 mb-6">
          {runs.length} run{runs.length !== 1 ? 's' : ''}
        </p>

        {error && (
          <div
            role="alert"
            className="mb-4 rounded bg-red-900/50 border border-red-700 text-red-300 px-4 py-3 text-sm"
          >
            {error}
          </div>
        )}

        {loading && (
          <p className="text-sm text-slate-400" data-testid="loading">
            Loading…
          </p>
        )}

        {!loading && !error && (
          <>
            {runs.length === 0 ? (
              <div className="flex items-center justify-center py-24">
                <p className="text-slate-400 text-sm text-center">No fetch runs yet</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="text-slate-400 border-b border-slate-700">
                      <th className="text-left py-2 pr-3 font-medium">Date</th>
                      <th className="text-left py-2 pr-3 font-medium">Window</th>
                      <th className="text-right py-2 pr-3 font-medium">Retrieved</th>
                      <th className="text-right py-2 pr-3 font-medium">Adzuna</th>
                      <th className="text-right py-2 pr-3 font-medium">Jooble</th>
                      <th className="text-right py-2 pr-3 font-medium">New</th>
                      <th className="text-right py-2 pr-3 font-medium">Scoped</th>
                      <th className="text-right py-2 pr-3 font-medium">Cost</th>
                      <th className="text-left py-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => {
                      const status = displayStatus(run)
                      return (
                        <tr
                          key={run.id}
                          className={`border-b border-slate-700/50 ${rowClass(status)}`}
                          data-status={status}
                        >
                          <td className="py-2 pr-3 font-mono">{formatDate(run.started_at)}</td>
                          <td className="py-2 pr-3 font-mono">{formatWindow(run.window_days)}</td>
                          <td className="text-right py-2 pr-3 font-mono">
                            {formatNum(run.fetched_total)}
                          </td>
                          <td
                            className={`text-right py-2 pr-3 font-mono ${sourceStatClass(run.source_stats?.adzuna)}`}
                          >
                            {formatSourceStat(run.source_stats?.adzuna)}
                          </td>
                          <td
                            className={`text-right py-2 pr-3 font-mono ${sourceStatClass(run.source_stats?.jooble)}`}
                          >
                            {formatSourceStat(run.source_stats?.jooble)}
                          </td>
                          <td className="text-right py-2 pr-3 font-mono">
                            {formatNum(run.new_jobs)}
                          </td>
                          <td className="text-right py-2 pr-3 font-mono">
                            {formatNum(run.scored_pass2)}
                          </td>
                          <td className="text-right py-2 pr-3 font-mono">
                            {formatCost(run.cost_usd)}
                          </td>
                          <td className="py-2">{STATUS_LABEL[status]}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

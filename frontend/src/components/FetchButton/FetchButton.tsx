import { useEffect, useRef, useState } from 'react'

const API_BASE = 'http://localhost:8000'
const POLL_INTERVAL_MS = 3000
const POLL_TIMEOUT_MS = 5 * 60 * 1000

interface FetchRun {
  started_at: string
  completed_at: string | null
  new_jobs: number
  status: string
  error_message: string | null
}

interface FetchButtonProps {
  onFetchComplete?: () => void
  /** Override poll interval (ms). Default 3000. Use a small value in tests. */
  pollInterval?: number
}

export default function FetchButton({ onFetchComplete, pollInterval = POLL_INTERVAL_MS }: FetchButtonProps) {
  const [loading, setLoading] = useState(false)
  const [banner, setBanner] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const startedAtRef = useRef<Date | null>(null)
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

  async function pollForCompletion() {
    if (Date.now() > deadlineRef.current) {
      stopPolling()
      setLoading(false)
      setBanner({ type: 'error', message: 'Fetch timed out — check Fetch Runs tab.' })
      return
    }

    try {
      const res = await fetch(`${API_BASE}/fetch-runs?limit=1`)
      if (!res.ok) return
      const data = (await res.json()) as { runs: FetchRun[] }
      const run = data.runs[0]
      if (!run || !run.completed_at) return

      const runStarted = new Date(run.started_at)
      if (startedAtRef.current && runStarted >= startedAtRef.current) {
        stopPolling()
        setLoading(false)
        onFetchComplete?.()
        if (run.status === 'error') {
          setBanner({ type: 'error', message: run.error_message ?? 'Fetch failed.' })
        } else {
          const msg =
            run.new_jobs > 0
              ? `${run.new_jobs} new job${run.new_jobs !== 1 ? 's' : ''} found`
              : 'No new jobs'
          setBanner({ type: 'success', message: `${msg}${run.status === 'partial' ? ' (some sources failed)' : ''}` })
        }
      }
    } catch {
      // transient network error — keep polling
    }
  }

  async function handleClick() {
    setLoading(true)
    setBanner(null)
    startedAtRef.current = new Date()
    deadlineRef.current = Date.now() + POLL_TIMEOUT_MS

    try {
      const res = await fetch(`${API_BASE}/jobs/fetch`, { method: 'POST' })
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
        throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`)
      }
      // 202 accepted — start polling
      pollRef.current = setInterval(pollForCompletion, pollInterval)
    } catch (err: unknown) {
      setLoading(false)
      setBanner({ type: 'error', message: err instanceof Error ? err.message : 'Fetch failed.' })
    }
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <button
        onClick={handleClick}
        disabled={loading}
        className={`flex items-center gap-2 bg-blue-500 hover:bg-blue-600 text-white rounded px-4 py-2 text-sm font-medium transition-colors ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        {loading ? (
          <>
            <span
              aria-hidden="true"
              className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"
            />
            Fetching…
          </>
        ) : (
          '↻ Fetch new jobs'
        )}
      </button>

      {banner && (
        <div
          role={banner.type === 'error' ? 'alert' : 'status'}
          className={`flex items-center gap-2 rounded p-3 text-sm ${
            banner.type === 'success'
              ? 'bg-blue-900/50 border border-blue-500 text-blue-200'
              : 'bg-red-900/50 border border-red-500 text-red-200'
          }`}
        >
          <span>{banner.message}</span>
          <button
            onClick={() => setBanner(null)}
            aria-label="Dismiss"
            className="ml-2 leading-none opacity-70 hover:opacity-100"
          >
            ×
          </button>
        </div>
      )}
    </div>
  )
}

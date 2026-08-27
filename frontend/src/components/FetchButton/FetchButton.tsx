import { useState } from 'react'

const API_BASE = 'http://localhost:8000'

interface FetchResult {
  fetched: number
  new: number
  updated: number
  scored_pass1: number
  scored_pass2: number
}

interface FetchButtonProps {
  onFetchComplete?: () => void
}

export default function FetchButton({ onFetchComplete }: FetchButtonProps) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<FetchResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleClick() {
    setLoading(true)
    setResult(null)
    setError(null)

    try {
      const res = await fetch(`${API_BASE}/jobs/fetch`, { method: 'POST' })
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
        const detail = (body as { detail?: string }).detail ?? `HTTP ${res.status}`
        throw new Error(detail)
      }
      const data = (await res.json()) as FetchResult
      setResult(data)
      onFetchComplete?.()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Fetch failed.')
    } finally {
      setLoading(false)
    }
  }

  function dismissResult() {
    setResult(null)
  }

  function dismissError() {
    setError(null)
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

      {result !== null && (
        <div
          role="status"
          className="flex items-center gap-2 bg-blue-900/50 border border-blue-500 text-blue-200 rounded p-3 text-sm"
        >
          <span>
            {result.new > 0 ? `${result.new} new jobs found` : 'No new jobs'}
          </span>
          <button
            onClick={dismissResult}
            aria-label="Dismiss"
            className="ml-2 text-blue-300 hover:text-white leading-none"
          >
            ×
          </button>
        </div>
      )}

      {error !== null && (
        <div
          role="alert"
          className="flex items-center gap-2 bg-red-900/50 border border-red-500 text-red-200 rounded p-3 text-sm"
        >
          <span>{error}</span>
          <button
            onClick={dismissError}
            aria-label="Dismiss"
            className="ml-2 text-red-300 hover:text-white leading-none"
          >
            ×
          </button>
        </div>
      )}
    </div>
  )
}

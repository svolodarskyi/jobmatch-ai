import { useEffect, useRef } from 'react'

const ALL_STATUSES = ['New', 'Saved', 'Applied', 'Interviewing', 'Rejected', 'Offer'] as const

const STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  New: { bg: '#1e3a5f', text: '#93c5fd' },
  Saved: { bg: '#1e3a2f', text: '#86efac' },
  Applied: { bg: '#3b2a1e', text: '#fdba74' },
  Interviewing: { bg: '#2d1e3b', text: '#c4b5fd' },
  Rejected: { bg: '#2d1e1e', text: '#fca5a5' },
  Offer: { bg: '#1a3320', text: '#4ade80' },
}

export interface StatusHistoryEntry {
  status: string
  changed_at: string
}

export interface StatusDropdownProps {
  jobId: string
  currentStatus: string
  history?: StatusHistoryEntry[]
  onClose: () => void
  onStatusChange: (newStatus: string, history: StatusHistoryEntry[]) => void
}

export default function StatusDropdown({
  jobId,
  currentStatus,
  history = [],
  onClose,
  onStatusChange,
}: StatusDropdownProps) {
  const ref = useRef<HTMLDivElement>(null)

  // Close on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [onClose])

  async function handleSelect(newStatus: string) {
    if (newStatus === currentStatus) {
      onClose()
      return
    }

    // Optimistic update — tell parent immediately
    const optimisticHistory: StatusHistoryEntry[] = [
      { status: newStatus, changed_at: new Date().toISOString() },
      ...history,
    ]
    onStatusChange(newStatus, optimisticHistory)
    onClose()

    try {
      const res = await fetch(`http://localhost:8000/jobs/${jobId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = (await res.json()) as { status: string; history: StatusHistoryEntry[] }
      // Sync with server response
      onStatusChange(data.status, data.history)
    } catch {
      // Revert to previous status on failure
      onStatusChange(currentStatus, history)
    }
  }

  return (
    <div
      ref={ref}
      role="listbox"
      aria-label="Change status"
      className="absolute z-20 mt-1 bg-slate-900 border border-slate-600 rounded-lg shadow-xl py-1 min-w-[160px]"
      data-testid="status-dropdown"
    >
      {ALL_STATUSES.map((status) => {
        const style = STATUS_STYLES[status] ?? { bg: '#334155', text: '#cbd5e1' }
        const isSelected = status === currentStatus
        return (
          <button
            key={status}
            role="option"
            aria-selected={isSelected}
            onClick={() => handleSelect(status)}
            className="w-full text-left px-3 py-2 flex items-center gap-2 hover:bg-slate-700 transition-colors"
          >
            <span
              className="text-xs rounded px-2 py-0.5 font-medium"
              style={{ backgroundColor: style.bg, color: style.text }}
            >
              {status}
            </span>
            {isSelected && (
              <span className="ml-auto text-slate-400 text-xs" aria-label="current">
                ✓
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

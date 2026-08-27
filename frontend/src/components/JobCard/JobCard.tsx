import { useState } from 'react'
import StatusDropdown, { type StatusHistoryEntry } from '../StatusDropdown/StatusDropdown'
import NotesPanel from '../NotesPanel/NotesPanel'

const API_BASE = 'http://localhost:8000'

export interface Job {
  id: string
  source: string
  title: string
  company: string
  location: string
  salary_min: number | null
  salary_max: number | null
  url: string
  date_fetched: string
  raw_score: number | null
  llm_score: number | null
  llm_rationale: string | null
  status: string
  notes: string
  status_history?: StatusHistoryEntry[]
  fits_me: boolean
}

// ── Score Ring ───────────────────────────────────────────────────────────────

function ScoreRing({ score }: { score: number | null }) {
  const radius = 16
  const circumference = 2 * Math.PI * radius

  if (score === null) {
    return (
      <svg width="40" height="40" viewBox="0 0 40 40" aria-label="Score unavailable">
        <circle cx="20" cy="20" r={radius} fill="none" stroke="#334155" strokeWidth="4" />
        <text x="20" y="24" textAnchor="middle" fill="#94a3b8" fontSize="10" fontFamily="monospace">
          —
        </text>
      </svg>
    )
  }

  const offset = circumference - (score / 100) * circumference
  const color =
    score >= 80
      ? '#4ade80'
      : score >= 60
        ? '#facc15'
        : score >= 40
          ? '#fb923c'
          : '#f87171'
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" aria-label={`Score ${score}`}>
      <circle cx="20" cy="20" r={radius} fill="none" stroke="#334155" strokeWidth="4" />
      <circle
        cx="20"
        cy="20"
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth="4"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform="rotate(-90 20 20)"
      />
      <text x="20" y="24" textAnchor="middle" fill={color} fontSize="10" fontFamily="monospace">
        {score}
      </text>
    </svg>
  )
}

// ── Status badge colors ──────────────────────────────────────────────────────

const STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  New: { bg: '#1e3a5f', text: '#93c5fd' },
  Saved: { bg: '#1e3a2f', text: '#86efac' },
  Applied: { bg: '#3b2a1e', text: '#fdba74' },
  Interviewing: { bg: '#2d1e3b', text: '#c4b5fd' },
  Rejected: { bg: '#2d1e1e', text: '#fca5a5' },
  Offer: { bg: '#1a3320', text: '#4ade80' },
}

// ── Salary formatting ────────────────────────────────────────────────────────

function formatSalary(min: number | null, max: number | null): string | null {
  if (min == null && max == null) return null
  const fmt = (n: number) => `$${n.toLocaleString('en-CA')}`
  if (min != null && max != null) return `${fmt(min)} – ${fmt(max)} CAD`
  if (min != null) return `From ${fmt(min)} CAD`
  return `Up to ${fmt(max!)} CAD`
}

// ── Date formatting ──────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-CA', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

// ── Status history ───────────────────────────────────────────────────────────

function StatusHistory({ history }: { history: StatusHistoryEntry[] }) {
  const [expanded, setExpanded] = useState(false)
  if (history.length === 0) return null
  return (
    <div className="mt-1">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
        aria-expanded={expanded}
      >
        {expanded ? '▾ Hide history' : '▸ Status history'}
      </button>
      {expanded && (
        <ul className="mt-1 flex flex-col gap-0.5 pl-2 border-l border-slate-700">
          {history.map((entry, i) => {
            const style = STATUS_STYLES[entry.status] ?? { bg: '#334155', text: '#cbd5e1' }
            return (
              <li key={i} className="flex items-center gap-2 text-xs text-slate-400">
                <span
                  className="rounded px-1.5 py-0.5 font-medium"
                  style={{ backgroundColor: style.bg, color: style.text }}
                >
                  {entry.status}
                </span>
                <span>{formatDate(entry.changed_at)}</span>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

// ── JobCard ──────────────────────────────────────────────────────────────────

export interface JobCardProps {
  job: Job
  onStatusChange?: (id: string, newStatus: string, history: StatusHistoryEntry[]) => void
  onNotesChange?: (id: string, notes: string) => void
  onSave?: (id: string, status: string) => void
  onFitsMeToggle?: (id: string, next: boolean) => void
}

export default function JobCard({
  job,
  onStatusChange,
  onNotesChange,
  onSave,
  onFitsMeToggle,
}: JobCardProps) {
  const score = job.llm_score ?? job.raw_score
  const salary = formatSalary(job.salary_min, job.salary_max)

  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [notesOpen, setNotesOpen] = useState(false)

  const statusStyle = STATUS_STYLES[job.status] ?? { bg: '#334155', text: '#cbd5e1' }

  function handleStatusChange(newStatus: string, history: StatusHistoryEntry[]) {
    onStatusChange?.(job.id, newStatus, history)
  }

  function handleNotesSaved(notes: string) {
    onNotesChange?.(job.id, notes)
  }

  async function handleSaveClick() {
    if (job.status === 'Saved') return // already saved — no-op, use the dropdown to un-save

    const previousStatus = job.status
    onSave?.(job.id, 'Saved')

    try {
      const res = await fetch(`${API_BASE}/jobs/${job.id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'Saved' }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
    } catch {
      // Revert through the same parent-state channel used for the optimistic
      // write — matches StatusDropdown.handleSelect / onFitsMeToggle's shape,
      // so AllJobs.jobs and the rendered badge never desync.
      onSave?.(job.id, previousStatus)
    }
  }

  async function handleFitsMeClick() {
    const previous = job.fits_me
    const next = !previous
    onFitsMeToggle?.(job.id, next)

    try {
      const res = await fetch(`${API_BASE}/jobs/${job.id}/fits_me`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fits_me: next }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
    } catch {
      onFitsMeToggle?.(job.id, previous)
    }
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 flex flex-row gap-4 relative">
      {/* Source badge — top right */}
      <span
        className="absolute top-3 right-3 bg-slate-700 text-slate-300 text-xs rounded px-2 py-0.5 uppercase"
      >
        {job.source}
      </span>

      {/* Score ring — left */}
      <div className="flex-shrink-0 pt-0.5">
        <ScoreRing score={score} />
      </div>

      {/* Content — right */}
      <div className="flex flex-col gap-1 min-w-0 flex-1 pr-16">
        {/* Title */}
        <p className="text-base font-semibold text-slate-100 truncate">{job.title}</p>

        {/* Company · location · salary · date */}
        <p className="text-sm text-slate-400 truncate">
          {job.company}
          {job.location ? ` · ${job.location}` : ''}
          {salary ? ` · ${salary}` : ''}
          {` · ${formatDate(job.date_fetched)}`}
        </p>

        {/* LLM rationale */}
        {job.llm_rationale && (
          <p
            className="text-sm italic text-slate-400 line-clamp-3 mt-0.5"
            style={{ WebkitLineClamp: 3, display: '-webkit-box', WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
          >
            {job.llm_rationale}
          </p>
        )}

        {/* Footer row: status badge + buttons */}
        <div className="flex items-center gap-3 mt-2">
          {/* Clickable status badge — toggles dropdown */}
          <div className="relative">
            <button
              onClick={() => setDropdownOpen((v) => !v)}
              aria-haspopup="listbox"
              aria-expanded={dropdownOpen}
              className="text-xs rounded px-2 py-0.5 font-medium cursor-pointer hover:opacity-80 transition-opacity"
              style={{ backgroundColor: statusStyle.bg, color: statusStyle.text }}
              data-testid="status-badge"
            >
              {job.status}
            </button>

            {dropdownOpen && (
              <StatusDropdown
                jobId={job.id}
                currentStatus={job.status}
                history={job.status_history ?? []}
                onClose={() => setDropdownOpen(false)}
                onStatusChange={handleStatusChange}
              />
            )}
          </div>

          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-400 hover:text-blue-300 underline"
          >
            View listing
          </a>

          {onSave && (
            <button
              onClick={handleSaveClick}
              aria-pressed={job.status === 'Saved'}
              data-testid="save-button"
              className={
                job.status === 'Saved'
                  ? 'text-xs rounded px-2 py-0.5 font-medium bg-blue-500 text-white transition-colors'
                  : 'text-xs rounded px-2 py-0.5 font-medium border border-blue-500 text-blue-400 hover:bg-blue-500/10 transition-colors'
              }
            >
              Save
            </button>
          )}

          {onFitsMeToggle && (
            <button
              onClick={handleFitsMeClick}
              aria-pressed={job.fits_me}
              aria-label={job.fits_me ? 'Remove from Fits Me' : 'Mark as Fits Me'}
              data-testid="fits-me-button"
              className={
                job.fits_me
                  ? 'text-base leading-none text-blue-500 hover:text-blue-400 transition-colors'
                  : 'text-base leading-none text-slate-400 hover:text-blue-400 transition-colors'
              }
            >
              {job.fits_me ? '★' : '☆'}
            </button>
          )}

          <button
            onClick={() => setNotesOpen(true)}
            className="text-xs text-slate-400 hover:text-slate-200 transition-colors"
            data-testid="notes-button"
          >
            Notes
          </button>
        </div>

        {/* Status history */}
        <StatusHistory history={job.status_history ?? []} />
      </div>

      {/* Notes panel */}
      {notesOpen && (
        <NotesPanel
          jobId={job.id}
          jobTitle={job.title}
          initialNotes={job.notes}
          onClose={() => setNotesOpen(false)}
          onNotesSaved={handleNotesSaved}
        />
      )}
    </div>
  )
}

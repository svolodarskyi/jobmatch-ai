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
  raw_score: number
  llm_score: number | null
  llm_rationale: string | null
  status: string
  notes: string
}

// ── Score Ring ───────────────────────────────────────────────────────────────

function ScoreRing({ score }: { score: number }) {
  const radius = 16
  const circumference = 2 * Math.PI * radius
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

// ── JobCard ──────────────────────────────────────────────────────────────────

export interface JobCardProps {
  job: Job
}

export default function JobCard({ job }: JobCardProps) {
  const score = job.llm_score ?? job.raw_score
  const statusStyle = STATUS_STYLES[job.status] ?? { bg: '#334155', text: '#cbd5e1' }
  const salary = formatSalary(job.salary_min, job.salary_max)

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

        {/* Footer row: status badge + view link */}
        <div className="flex items-center gap-3 mt-2">
          <span
            className="text-xs rounded px-2 py-0.5 font-medium"
            style={{ backgroundColor: statusStyle.bg, color: statusStyle.text }}
            data-testid="status-badge"
          >
            {job.status}
          </span>

          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-400 hover:text-blue-300 underline"
          >
            View listing
          </a>
        </div>
      </div>
    </div>
  )
}

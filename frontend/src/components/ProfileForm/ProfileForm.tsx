import { KeyboardEvent, useEffect, useRef, useState } from 'react'

const API_BASE = 'http://localhost:8000'

const SENIORITY_OPTIONS = ['Junior', 'Mid', 'Senior', 'Lead', 'Exec'] as const
type Seniority = (typeof SENIORITY_OPTIONS)[number]

interface ProfilePayload {
  target_titles: string[]
  skills: string[]
  seniority: string
  locations: string[]
  salary_min: number
  salary_max: number
  preferences: Record<string, unknown>
}

interface Toast {
  id: number
  message: string
}

// ── Tag Input ────────────────────────────────────────────────────────────────

interface TagInputProps {
  label: string
  tags: string[]
  onChange: (tags: string[]) => void
  id: string
}

function TagInput({ label, tags, onChange, id }: TagInputProps) {
  const [input, setInput] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  function addTag(value: string) {
    const trimmed = value.trim().replace(/,$/, '').trim()
    if (trimmed && !tags.includes(trimmed)) {
      onChange([...tags, trimmed])
    }
    setInput('')
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addTag(input)
    } else if (e.key === 'Backspace' && input === '' && tags.length > 0) {
      onChange(tags.slice(0, -1))
    }
  }

  function handleBlur() {
    if (input.trim()) addTag(input)
  }

  function removeTag(tag: string) {
    onChange(tags.filter((t) => t !== tag))
  }

  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={id}
        className="text-xs text-slate-400 font-medium uppercase tracking-wide"
      >
        {label}
      </label>
      <div
        className="flex flex-wrap gap-1.5 rounded border border-slate-700 bg-slate-900 p-2 min-h-[42px] cursor-text"
        onClick={() => inputRef.current?.focus()}
        role="group"
        aria-label={label}
      >
        {tags.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 rounded bg-blue-500/20 border border-blue-500/40 text-blue-300 text-xs px-2 py-0.5"
          >
            {tag}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation()
                removeTag(tag)
              }}
              aria-label={`Remove ${tag}`}
              className="hover:text-white leading-none"
            >
              ×
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          id={id}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
          className="flex-1 min-w-[120px] bg-transparent text-sm text-slate-100 outline-none placeholder-slate-500"
          placeholder={tags.length === 0 ? 'Type and press Enter or comma…' : ''}
        />
      </div>
    </div>
  )
}

// ── Toast ────────────────────────────────────────────────────────────────────

interface ToastItemProps {
  toast: Toast
  onDismiss: (id: number) => void
}

function ToastItem({ toast, onDismiss }: ToastItemProps) {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), 3000)
    return () => clearTimeout(timer)
  }, [toast.id, onDismiss])

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-3 rounded-lg bg-slate-800 border border-slate-700 shadow-lg px-4 py-3 text-sm text-slate-100 min-w-[260px]"
    >
      <span className="text-green-400">✓</span>
      {toast.message}
    </div>
  )
}

// ── ProfileForm ──────────────────────────────────────────────────────────────

export default function ProfileForm() {
  const [targetTitles, setTargetTitles] = useState<string[]>([])
  const [skills, setSkills] = useState<string[]>([])
  const [seniority, setSeniority] = useState<Seniority | ''>('')
  const [locations, setLocations] = useState<string[]>([])
  const [salaryMin, setSalaryMin] = useState('')
  const [salaryMax, setSalaryMax] = useState('')
  const [preferences, setPreferences] = useState('')

  const [errors, setErrors] = useState<Record<string, string>>({})
  const [toasts, setToasts] = useState<Toast[]>([])
  const [loading, setLoading] = useState(true)

  // Fetch profile on mount
  useEffect(() => {
    fetch(`${API_BASE}/profile`)
      .then((r) => r.json())
      .then((data: ProfilePayload & { id?: string }) => {
        setTargetTitles(data.target_titles ?? [])
        setSkills(data.skills ?? [])
        setSeniority((data.seniority as Seniority) ?? '')
        setLocations(data.locations ?? [])
        setSalaryMin(data.salary_min != null ? String(data.salary_min) : '')
        setSalaryMax(data.salary_max != null ? String(data.salary_max) : '')
        setPreferences(
          typeof data.preferences === 'string'
            ? data.preferences
            : data.preferences && Object.keys(data.preferences).length > 0
              ? JSON.stringify(data.preferences)
              : '',
        )
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  function addToast(message: string) {
    const id = Date.now()
    setToasts(() => [{ id, message }])
    return id
  }

  function dismissToast(id: number) {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }

  function validate(): boolean {
    const errs: Record<string, string> = {}

    if (targetTitles.length === 0) {
      errs.targetTitles = 'At least one target title is required.'
    }
    if (skills.length === 0) {
      errs.skills = 'At least one skill is required.'
    }
    if (!seniority) {
      errs.seniority = 'Seniority is required.'
    }

    const minVal = parseInt(salaryMin, 10)
    const maxVal = parseInt(salaryMax, 10)

    if (salaryMin !== '' && (isNaN(minVal) || minVal <= 0)) {
      errs.salaryMin = 'Salary min must be a positive integer.'
    }
    if (salaryMax !== '' && (isNaN(maxVal) || maxVal <= 0)) {
      errs.salaryMax = 'Salary max must be a positive integer.'
    }
    if (
      salaryMin !== '' &&
      salaryMax !== '' &&
      !isNaN(minVal) &&
      !isNaN(maxVal) &&
      minVal >= maxVal
    ) {
      errs.salaryMin = 'Salary min must be less than salary max.'
    }

    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return

    const payload: ProfilePayload = {
      target_titles: targetTitles,
      skills,
      seniority,
      locations,
      salary_min: salaryMin !== '' ? parseInt(salaryMin, 10) : 0,
      salary_max: salaryMax !== '' ? parseInt(salaryMax, 10) : 0,
      preferences: preferences ? { notes: preferences } : {},
    }

    try {
      const res = await fetch(`${API_BASE}/profile`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      addToast('Profile saved successfully.')
    } catch (err) {
      console.error(err)
      setErrors((prev) => ({ ...prev, submit: 'Failed to save profile.' }))
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center text-slate-400 text-sm">
        Loading profile…
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 font-[system-ui]">
      <div className="max-w-7xl mx-auto px-6 py-10">
        <h1 className="text-lg font-semibold text-slate-100 mb-6">
          Your Job Search Profile
        </h1>

        <form
          onSubmit={handleSubmit}
          noValidate
          className="bg-slate-800 border border-slate-700 rounded-lg p-4 flex flex-col gap-6 max-w-2xl"
        >
          {/* Target Titles */}
          <div className="flex flex-col gap-1">
            <TagInput
              id="target-titles"
              label="Target Titles *"
              tags={targetTitles}
              onChange={setTargetTitles}
            />
            {errors.targetTitles && (
              <p className="text-xs text-red-400">{errors.targetTitles}</p>
            )}
          </div>

          {/* Skills */}
          <div className="flex flex-col gap-1">
            <TagInput
              id="skills"
              label="Skills *"
              tags={skills}
              onChange={setSkills}
            />
            {errors.skills && (
              <p className="text-xs text-red-400">{errors.skills}</p>
            )}
          </div>

          {/* Seniority */}
          <fieldset className="flex flex-col gap-2">
            <legend className="text-xs text-slate-400 font-medium uppercase tracking-wide mb-1">
              Seniority *
            </legend>
            <div className="flex flex-wrap gap-4">
              {SENIORITY_OPTIONS.map((opt) => (
                <label
                  key={opt}
                  className="flex items-center gap-2 text-sm text-slate-100 cursor-pointer"
                >
                  <input
                    type="radio"
                    name="seniority"
                    value={opt}
                    checked={seniority === opt}
                    onChange={() => setSeniority(opt)}
                    className="accent-blue-500"
                  />
                  {opt}
                </label>
              ))}
            </div>
            {errors.seniority && (
              <p className="text-xs text-red-400">{errors.seniority}</p>
            )}
          </fieldset>

          {/* Locations */}
          <TagInput
            id="locations"
            label="Locations"
            tags={locations}
            onChange={setLocations}
          />

          {/* Salary Range */}
          <div className="flex flex-col gap-2">
            <span className="text-xs text-slate-400 font-medium uppercase tracking-wide">
              Salary Range (CAD)
            </span>
            <div className="flex gap-4">
              <div className="flex flex-col gap-1 flex-1">
                <label htmlFor="salary-min" className="text-xs text-slate-400">
                  Min
                </label>
                <input
                  id="salary-min"
                  type="number"
                  min="1"
                  step="1"
                  value={salaryMin}
                  onChange={(e) => setSalaryMin(e.target.value)}
                  placeholder="e.g. 80000"
                  className="rounded border border-slate-700 bg-slate-900 text-sm text-slate-100 px-3 py-2 outline-none focus:border-blue-500 placeholder-slate-500"
                />
                {errors.salaryMin && (
                  <p className="text-xs text-red-400">{errors.salaryMin}</p>
                )}
              </div>
              <div className="flex flex-col gap-1 flex-1">
                <label htmlFor="salary-max" className="text-xs text-slate-400">
                  Max
                </label>
                <input
                  id="salary-max"
                  type="number"
                  min="1"
                  step="1"
                  value={salaryMax}
                  onChange={(e) => setSalaryMax(e.target.value)}
                  placeholder="e.g. 130000"
                  className="rounded border border-slate-700 bg-slate-900 text-sm text-slate-100 px-3 py-2 outline-none focus:border-blue-500 placeholder-slate-500"
                />
                {errors.salaryMax && (
                  <p className="text-xs text-red-400">{errors.salaryMax}</p>
                )}
              </div>
            </div>
          </div>

          {/* Preferences */}
          <div className="flex flex-col gap-1">
            <label
              htmlFor="preferences"
              className="text-xs text-slate-400 font-medium uppercase tracking-wide"
            >
              Preferences (optional)
            </label>
            <textarea
              id="preferences"
              value={preferences}
              onChange={(e) => setPreferences(e.target.value)}
              rows={3}
              placeholder="Any notes or preferences about your ideal role…"
              className="rounded border border-slate-700 bg-slate-900 text-sm text-slate-100 px-3 py-2 outline-none focus:border-blue-500 placeholder-slate-500 resize-y"
            />
          </div>

          {errors.submit && (
            <p className="text-xs text-red-400">{errors.submit}</p>
          )}

          <div className="flex justify-end">
            <button
              type="submit"
              className="bg-blue-500 hover:bg-blue-600 text-white rounded px-4 py-2 text-sm font-medium transition-colors"
            >
              Save Profile
            </button>
          </div>
        </form>
      </div>

      {/* Toast portal — bottom-right */}
      <div
        aria-live="polite"
        className="fixed bottom-6 right-6 flex flex-col gap-2 z-50"
      >
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={dismissToast} />
        ))}
      </div>
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'

export interface NotesPanelProps {
  jobId: string
  jobTitle: string
  initialNotes: string
  onClose: () => void
  onNotesSaved: (notes: string) => void
}

export default function NotesPanel({
  jobId,
  jobTitle,
  initialNotes,
  onClose,
  onNotesSaved,
}: NotesPanelProps) {
  const [notes, setNotes] = useState(initialNotes)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Clean up debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current !== null) {
        clearTimeout(debounceRef.current)
      }
    }
  }, [])

  async function saveNotes(value: string) {
    try {
      const res = await fetch(`http://localhost:8000/jobs/${jobId}/notes`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: value }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      onNotesSaved(value)
    } catch {
      // Silently fail — user's text is still in the textarea
    }
  }

  function handleBlur() {
    if (debounceRef.current !== null) {
      clearTimeout(debounceRef.current)
    }
    debounceRef.current = setTimeout(() => {
      void saveNotes(notes)
    }, 500)
  }

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setNotes(e.target.value)
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-20 bg-black/40"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-in panel */}
      <div
        role="dialog"
        aria-label={`Notes for ${jobTitle}`}
        data-testid="notes-panel"
        className="fixed top-0 right-0 h-full z-30 bg-slate-800 border-l border-slate-700 flex flex-col"
        style={{ width: '400px' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
          <h2 className="text-sm font-semibold text-slate-100 truncate pr-2">Notes</h2>
          <button
            onClick={onClose}
            aria-label="Close notes panel"
            className="text-slate-400 hover:text-slate-100 transition-colors text-lg leading-none"
          >
            ×
          </button>
        </div>

        {/* Job title */}
        <p className="px-4 pt-3 text-xs text-slate-400 truncate">{jobTitle}</p>

        {/* Textarea */}
        <div className="flex-1 flex flex-col px-4 pb-4 pt-2">
          <textarea
            aria-label="Job notes"
            value={notes}
            onChange={handleChange}
            onBlur={handleBlur}
            placeholder="Add notes about this job…"
            className="flex-1 resize-none bg-slate-900 border border-slate-600 rounded p-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
          <p className="text-xs text-slate-500 mt-2">Auto-saves when you click away.</p>
        </div>
      </div>
    </>
  )
}

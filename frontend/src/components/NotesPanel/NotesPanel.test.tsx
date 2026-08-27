import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import NotesPanel from './NotesPanel'

describe('NotesPanel', () => {
  it('opens panel with the correct aria label and close button', () => {
    render(
      <NotesPanel
        jobId="1"
        jobTitle="Senior Data Engineer"
        initialNotes=""
        onClose={() => {}}
        onNotesSaved={() => {}}
      />,
    )

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByLabelText('Close notes panel')).toBeInTheDocument()
    expect(screen.getByText('Senior Data Engineer')).toBeInTheDocument()
  })

  it('pre-fills textarea with the initial notes value', () => {
    render(
      <NotesPanel
        jobId="2"
        jobTitle="Backend Engineer"
        initialNotes="Follow up next week."
        onClose={() => {}}
        onNotesSaved={() => {}}
      />,
    )

    const textarea = screen.getByRole('textbox', { name: /job notes/i })
    expect(textarea).toHaveValue('Follow up next week.')
  })

  it('auto-saves on blur and calls onNotesSaved with the new value', async () => {
    const user = userEvent.setup()
    const onNotesSaved = vi.fn()

    render(
      <NotesPanel
        jobId="3"
        jobTitle="Frontend Engineer"
        initialNotes=""
        onClose={() => {}}
        onNotesSaved={onNotesSaved}
      />,
    )

    const textarea = screen.getByRole('textbox', { name: /job notes/i })

    await user.click(textarea)
    await user.type(textarea, 'Great team culture.')
    // Trigger blur
    await user.tab()

    // Wait for debounce (500ms) + fetch to resolve
    await waitFor(
      () => {
        expect(onNotesSaved).toHaveBeenCalledWith('Great team culture.')
      },
      { timeout: 2000 },
    )
  })
})

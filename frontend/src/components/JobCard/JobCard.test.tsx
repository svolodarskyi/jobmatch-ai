import { http, HttpResponse } from 'msw'
import { server } from '../../mocks/server'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import JobCard, { type Job } from './JobCard'

const baseJob: Job = {
  id: '1',
  source: 'adzuna',
  title: 'Senior Data Engineer',
  company: 'Acme Corp',
  location: 'Calgary, AB',
  salary_min: 110000,
  salary_max: 140000,
  url: 'https://example.com/job/1',
  date_fetched: '2026-08-26T14:00:00Z',
  raw_score: 84,
  llm_score: 78,
  llm_rationale: 'Strong Azure match. Worth applying.',
  status: 'New',
  notes: '',
  fits_me: false,
}

describe('JobCard', () => {
  it('renders title, company, and score value in ring', () => {
    render(<JobCard job={baseJob} />)

    expect(screen.getByText('Senior Data Engineer')).toBeInTheDocument()
    expect(screen.getByText(/Acme Corp/)).toBeInTheDocument()
    // Score shown is llm_score (78)
    expect(screen.getByText('78')).toBeInTheDocument()
  })

  it('renders LLM rationale text', () => {
    render(<JobCard job={baseJob} />)
    expect(screen.getByText('Strong Azure match. Worth applying.')).toBeInTheDocument()
  })

  it('status badge shows correct status text and color style', () => {
    render(<JobCard job={baseJob} />)
    const badge = screen.getByTestId('status-badge')
    expect(badge).toHaveTextContent('New')
    // Check inline style for correct bg color
    expect(badge).toHaveStyle({ backgroundColor: '#1e3a5f', color: '#93c5fd' })
  })

  it('"View listing" link has correct href and opens in new tab', () => {
    render(<JobCard job={baseJob} />)
    const link = screen.getByRole('link', { name: /view listing/i })
    expect(link).toHaveAttribute('href', 'https://example.com/job/1')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('omits salary when both salary_min and salary_max are null', () => {
    const job = { ...baseJob, salary_min: null, salary_max: null }
    render(<JobCard job={job} />)
    expect(screen.queryByText(/CAD/)).not.toBeInTheDocument()
  })

  it('falls back to raw_score when llm_score is null', () => {
    const job = { ...baseJob, llm_score: null }
    render(<JobCard job={job} />)
    // raw_score is 84
    expect(screen.getByText('84')).toBeInTheDocument()
  })

  it('omits rationale section when llm_rationale is null', () => {
    const job = { ...baseJob, llm_rationale: null }
    render(<JobCard job={job} />)
    expect(screen.queryByText(/Strong Azure/)).not.toBeInTheDocument()
  })

  it('renders the grey unscored ring with aria-label when raw_score and llm_score are both null', () => {
    const job = { ...baseJob, raw_score: null, llm_score: null }
    render(<JobCard job={job} />)
    expect(screen.getByLabelText('Score unavailable')).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.queryByLabelText(/^Score \d/)).not.toBeInTheDocument()
  })

  it('omits Save button and Fits Me star when onSave/onFitsMeToggle are not provided', () => {
    render(<JobCard job={baseJob} />)
    expect(screen.queryByTestId('save-button')).not.toBeInTheDocument()
    expect(screen.queryByTestId('fits-me-button')).not.toBeInTheDocument()
  })

  it('renders Save button and fires onSave + PATCH /jobs/{id}/status when provided', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    let patchedBody: unknown = null
    server.use(
      http.patch('http://localhost:8000/jobs/:id/status', async ({ request, params }) => {
        patchedBody = await request.json()
        return HttpResponse.json({
          job_id: params.id,
          status: 'Saved',
          history: [{ status: 'Saved', changed_at: new Date().toISOString() }],
          updated_at: new Date().toISOString(),
        })
      }),
    )

    render(<JobCard job={baseJob} onSave={onSave} />)
    await user.click(screen.getByTestId('save-button'))

    expect(onSave).toHaveBeenCalledWith('1')
    await waitFor(() => {
      expect(patchedBody).toEqual({ status: 'Saved' })
    })
  })

  it('renders Fits Me star and fires onFitsMeToggle + PATCH /jobs/{id}/fits_me when provided', async () => {
    const user = userEvent.setup()
    const onFitsMeToggle = vi.fn()
    let patchedBody: unknown = null
    server.use(
      http.patch('http://localhost:8000/jobs/:id/fits_me', async ({ request, params }) => {
        patchedBody = await request.json()
        return HttpResponse.json({ job_id: params.id, fits_me: true })
      }),
    )

    render(<JobCard job={baseJob} onFitsMeToggle={onFitsMeToggle} />)
    await user.click(screen.getByTestId('fits-me-button'))

    expect(onFitsMeToggle).toHaveBeenCalledWith('1', true)
    await waitFor(() => {
      expect(patchedBody).toEqual({ fits_me: true })
    })
  })
})

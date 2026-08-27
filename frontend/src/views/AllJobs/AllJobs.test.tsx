import { delay, http, HttpResponse } from 'msw'
import { server } from '../../mocks/server'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AllJobs from './AllJobs'

function job(overrides: Record<string, unknown> = {}) {
  return {
    id: '1',
    source: 'adzuna',
    title: 'Data Engineer',
    company: 'Acme',
    location: 'Calgary, AB',
    salary_min: 100000,
    salary_max: 130000,
    url: 'https://example.com',
    date_fetched: '2026-08-26T14:00:00Z',
    raw_score: 84,
    llm_score: 78,
    llm_rationale: 'Good match.',
    status: 'New',
    notes: '',
    fits_me: false,
    ...overrides,
  }
}

const mixedJobs = [
  job({ id: '1', title: 'Data Engineer', source: 'adzuna', raw_score: 84, llm_score: 78 }),
  job({
    id: '2',
    title: 'ML Engineer',
    source: 'jooble',
    raw_score: null,
    llm_score: null,
    llm_rationale: null,
  }),
]

function mockJobsList(jobs: unknown[], total?: number) {
  server.use(
    http.get('http://localhost:8000/jobs/', () => {
      return HttpResponse.json({ total: total ?? jobs.length, jobs })
    }),
  )
}

describe('AllJobs', () => {
  it('fetches GET /jobs/?limit=1000 once on mount and renders every job', async () => {
    let requestUrl = ''
    server.use(
      http.get('http://localhost:8000/jobs/', ({ request }) => {
        requestUrl = request.url
        return HttpResponse.json({ total: 2, jobs: mixedJobs })
      }),
    )

    render(<AllJobs />)

    expect(await screen.findByText('Data Engineer')).toBeInTheDocument()
    expect(screen.getByText('ML Engineer')).toBeInTheDocument()

    const url = new URL(requestUrl)
    expect(url.pathname).toBe('/jobs/')
    expect(url.searchParams.get('limit')).toBe('1000')
    expect(url.searchParams.has('min_score')).toBe(false)
    expect(url.searchParams.has('source')).toBe(false)
  })

  it('shows loading skeletons before data arrives', () => {
    server.use(
      http.get('http://localhost:8000/jobs/', () => {
        return new Promise(() => {
          // never resolves — keeps loading state
        })
      }),
    )

    render(<AllJobs />)
    expect(screen.getByTestId('loading-skeletons')).toBeInTheDocument()
  })

  it('shows error banner and no job list when the fetch fails', async () => {
    server.use(
      http.get('http://localhost:8000/jobs/', () => {
        return HttpResponse.json({ detail: 'Server error' }, { status: 500 })
      }),
    )

    render(<AllJobs />)

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
    expect(screen.queryByText('Data Engineer')).not.toBeInTheDocument()
  })

  it('shows a distinct empty state when there are zero jobs total', async () => {
    mockJobsList([], 0)
    render(<AllJobs />)

    expect(await screen.findByText(/no jobs yet/i)).toBeInTheDocument()
    expect(screen.getByText(/dashboard/i)).toBeInTheDocument()
  })

  it('shows the no-matches empty state with a reset control when filters exclude everything', async () => {
    mockJobsList(mixedJobs)
    const user = userEvent.setup()
    render(<AllJobs />)

    await screen.findByText('Data Engineer')

    // Adzuna + No score should exclude both jobs (job 1 is adzuna/scored, job 2 is jooble/unscored)
    await user.click(screen.getByRole('button', { name: 'Adzuna' }))
    await user.click(screen.getByRole('button', { name: 'No score' }))

    expect(await screen.findByText('No jobs match your filters.')).toBeInTheDocument()
    const resetButton = screen.getByRole('button', { name: /reset filters/i })
    expect(resetButton).toBeInTheDocument()

    await user.click(resetButton)
    expect(await screen.findByText('Data Engineer')).toBeInTheDocument()
    expect(screen.getByText('ML Engineer')).toBeInTheDocument()
  })

  it('shows a truncation note when the limit=1000 cap was hit', async () => {
    mockJobsList(mixedJobs, 1500)
    render(<AllJobs />)

    expect(await screen.findByText('Showing 2 of 1500 jobs')).toBeInTheDocument()
  })

  it('Has score / No score filters narrow the list client-side without a second network call', async () => {
    let requestCount = 0
    server.use(
      http.get('http://localhost:8000/jobs/', () => {
        requestCount += 1
        return HttpResponse.json({ total: 2, jobs: mixedJobs })
      }),
    )
    const user = userEvent.setup()
    render(<AllJobs />)

    await screen.findByText('Data Engineer')
    expect(requestCount).toBe(1)

    await user.click(screen.getByRole('button', { name: 'Has score' }))
    expect(screen.getByText('Data Engineer')).toBeInTheDocument()
    expect(screen.queryByText('ML Engineer')).not.toBeInTheDocument()
    expect(requestCount).toBe(1)

    await user.click(screen.getByRole('button', { name: 'No score' }))
    expect(screen.queryByText('Data Engineer')).not.toBeInTheDocument()
    expect(screen.getByText('ML Engineer')).toBeInTheDocument()
    expect(requestCount).toBe(1)

    await user.click(screen.getByRole('button', { name: 'All scores' }))
    expect(screen.getByText('Data Engineer')).toBeInTheDocument()
    expect(screen.getByText('ML Engineer')).toBeInTheDocument()
    expect(requestCount).toBe(1)
  })

  it('source filter narrows the list client-side', async () => {
    mockJobsList(mixedJobs)
    const user = userEvent.setup()
    render(<AllJobs />)

    await screen.findByText('Data Engineer')

    await user.click(screen.getByRole('button', { name: 'Jooble' }))
    expect(screen.queryByText('Data Engineer')).not.toBeInTheDocument()
    expect(screen.getByText('ML Engineer')).toBeInTheDocument()
  })

  it('Save button fires the status PATCH and updates the badge', async () => {
    mockJobsList([mixedJobs[0]])
    server.use(
      http.patch('http://localhost:8000/jobs/:id/status', async ({ request, params }) => {
        const body = (await request.json()) as { status: string }
        return HttpResponse.json({
          job_id: params.id,
          status: body.status,
          history: [{ status: body.status, changed_at: new Date().toISOString() }],
          updated_at: new Date().toISOString(),
        })
      }),
    )
    const user = userEvent.setup()
    render(<AllJobs />)

    await screen.findByText('Data Engineer')
    await user.click(screen.getByTestId('save-button'))

    await waitFor(() => {
      expect(screen.getByTestId('status-badge')).toHaveTextContent('Saved')
    })
  })

  it('reverts parent state (not just the badge) when Save fails, and a second click still works', async () => {
    mockJobsList([mixedJobs[0]]) // status: 'New'
    let patchCount = 0
    server.use(
      http.patch('http://localhost:8000/jobs/:id/status', async ({ request, params }) => {
        patchCount += 1
        const body = (await request.json()) as { status: string }
        if (patchCount === 1) {
          // First Save click: PATCH fails.
          await delay(20)
          return HttpResponse.error()
        }
        // Second Save click: PATCH succeeds.
        return HttpResponse.json({
          job_id: params.id,
          status: body.status,
          history: [{ status: body.status, changed_at: new Date().toISOString() }],
          updated_at: new Date().toISOString(),
        })
      }),
    )
    const user = userEvent.setup()
    render(<AllJobs />)

    await screen.findByText('Data Engineer')
    const saveButton = screen.getByTestId('save-button')
    const badge = screen.getByTestId('status-badge')
    expect(badge).toHaveTextContent('New')

    // First click: optimistic flip, then revert once the PATCH fails.
    await user.click(saveButton)
    await waitFor(() => {
      expect(badge).toHaveTextContent('Saved')
    })
    await waitFor(() => {
      expect(badge).toHaveTextContent('New')
    })
    expect(patchCount).toBe(1)

    // The badge reverted — prove AllJobs's own `jobs` state reverted too
    // (not just a cosmetic local override in JobCard) by clicking Save
    // again: if parent state were still stuck on "Saved", the "already
    // Saved, no-op" guard would swallow this click and patchCount would
    // stay at 1.
    await user.click(saveButton)
    expect(patchCount).toBe(2)
    await waitFor(() => {
      expect(badge).toHaveTextContent('Saved')
    })
    // And it stays "Saved" — no further, unexpected revert.
    await new Promise((resolve) => setTimeout(resolve, 30))
    expect(badge).toHaveTextContent('Saved')
  })

  it('Fits Me star fires the fits_me PATCH and reverts on a mocked failure', async () => {
    mockJobsList([mixedJobs[0]])
    server.use(
      http.patch('http://localhost:8000/jobs/:id/fits_me', async () => {
        // Delay the failure so the optimistic "pressed" state is observable
        // before the revert happens.
        await delay(20)
        return HttpResponse.error()
      }),
    )
    const user = userEvent.setup()
    render(<AllJobs />)

    await screen.findByText('Data Engineer')
    const starButton = screen.getByTestId('fits-me-button')
    expect(starButton).toHaveAttribute('aria-pressed', 'false')

    await user.click(starButton)
    // Optimistic update — fills immediately, before the PATCH resolves
    await waitFor(() => {
      expect(starButton).toHaveAttribute('aria-pressed', 'true')
    })

    // Reverts once the failed request resolves
    await waitFor(() => {
      expect(starButton).toHaveAttribute('aria-pressed', 'false')
    })
  })
})

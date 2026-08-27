import { http, HttpResponse, delay } from 'msw'
import { server } from '../../mocks/server'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Tracking from './Tracking'

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
  job({ id: '1', title: 'New Job', status: 'New' }),
  job({ id: '2', title: 'Saved Job', status: 'Saved' }),
  job({ id: '3', title: 'Applied Job', status: 'Applied' }),
  job({ id: '4', title: 'Interviewing Job', status: 'Interviewing' }),
  job({ id: '5', title: 'Rejected Job', status: 'Rejected' }),
  job({ id: '6', title: 'Offer Job', status: 'Offer' }),
]

function mockJobsList(jobs: unknown[], total?: number) {
  server.use(
    http.get('http://localhost:8000/jobs/', () => {
      return HttpResponse.json({ total: total ?? jobs.length, jobs })
    }),
  )
}

function tabGroup() {
  return screen.getByRole('group', { name: /status tabs/i })
}

describe('Tracking', () => {
  it('fetches GET /jobs/?limit=1000 once on mount and renders tracked jobs, excluding New, on the default All tab', async () => {
    let requestUrl = ''
    server.use(
      http.get('http://localhost:8000/jobs/', ({ request }) => {
        requestUrl = request.url
        return HttpResponse.json({ total: mixedJobs.length, jobs: mixedJobs })
      }),
    )

    render(<Tracking />)

    expect(await screen.findByText('Saved Job')).toBeInTheDocument()
    expect(screen.getByText('Applied Job')).toBeInTheDocument()
    expect(screen.getByText('Interviewing Job')).toBeInTheDocument()
    expect(screen.getByText('Rejected Job')).toBeInTheDocument()
    expect(screen.getByText('Offer Job')).toBeInTheDocument()
    expect(screen.queryByText('New Job')).not.toBeInTheDocument()

    const url = new URL(requestUrl)
    expect(url.pathname).toBe('/jobs/')
    expect(url.searchParams.get('limit')).toBe('1000')

    // Default tab is "All"
    const allTab = within(tabGroup()).getByRole('button', { name: 'All' })
    expect(allTab).toHaveAttribute('aria-pressed', 'true')
  })

  it('renders the six tabs in the exact order All, Saved, Applied, Interviewing, Rejected, Offer with correct active/inactive styling', async () => {
    mockJobsList(mixedJobs)
    render(<Tracking />)

    await screen.findByText('Saved Job')

    const buttons = within(tabGroup()).getAllByRole('button')
    expect(buttons.map((b) => b.textContent)).toEqual([
      'All',
      'Saved',
      'Applied',
      'Interviewing',
      'Rejected',
      'Offer',
    ])

    expect(buttons[0]).toHaveAttribute('aria-pressed', 'true')
    expect(buttons[0].className).toContain('bg-blue-500')
    expect(buttons[0].className).toContain('text-white')

    expect(buttons[1]).toHaveAttribute('aria-pressed', 'false')
    expect(buttons[1].className).toContain('bg-slate-800')
    expect(buttons[1].className).toContain('text-slate-300')
  })

  it('clicking each status tab narrows the list to that status only, with no second network call', async () => {
    let requestCount = 0
    server.use(
      http.get('http://localhost:8000/jobs/', () => {
        requestCount += 1
        return HttpResponse.json({ total: mixedJobs.length, jobs: mixedJobs })
      }),
    )
    const user = userEvent.setup()
    render(<Tracking />)

    await screen.findByText('Saved Job')
    expect(requestCount).toBe(1)

    const tabs = ['Saved', 'Applied', 'Interviewing', 'Rejected', 'Offer']
    const titles: Record<string, string> = {
      Saved: 'Saved Job',
      Applied: 'Applied Job',
      Interviewing: 'Interviewing Job',
      Rejected: 'Rejected Job',
      Offer: 'Offer Job',
    }

    for (const tab of tabs) {
      await user.click(within(tabGroup()).getByRole('button', { name: tab }))
      expect(screen.getByText(titles[tab])).toBeInTheDocument()
      for (const other of tabs) {
        if (other !== tab) {
          expect(screen.queryByText(titles[other])).not.toBeInTheDocument()
        }
      }
      expect(screen.queryByText('New Job')).not.toBeInTheDocument()
    }

    expect(requestCount).toBe(1)
  })

  it('shows loading skeletons before data arrives', () => {
    server.use(
      http.get('http://localhost:8000/jobs/', () => {
        return new Promise(() => {
          // never resolves — keeps loading state
        })
      }),
    )

    render(<Tracking />)
    expect(screen.getByTestId('loading-skeletons')).toBeInTheDocument()
  })

  it('shows error banner and no job list when the fetch fails', async () => {
    server.use(
      http.get('http://localhost:8000/jobs/', () => {
        return HttpResponse.json({ detail: 'Server error' }, { status: 500 })
      }),
    )

    render(<Tracking />)

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
    expect(screen.queryByText('Saved Job')).not.toBeInTheDocument()
  })

  it('shows a distinct empty state when there are zero jobs total', async () => {
    mockJobsList([], 0)
    render(<Tracking />)

    expect(await screen.findByText(/no jobs yet/i)).toBeInTheDocument()
    expect(screen.getByText(/dashboard/i)).toBeInTheDocument()
  })

  it('shows a distinct empty state when jobs exist but none are tracked yet (all New)', async () => {
    mockJobsList([job({ id: '1', title: 'New Job', status: 'New' })])
    render(<Tracking />)

    await waitFor(() => {
      expect(screen.getByText(/no jobs tracked yet/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/matches|all jobs/i)).toBeInTheDocument()
    expect(screen.queryByText('New Job')).not.toBeInTheDocument()
  })

  it('shows distinct copy naming the tab when a specific tab has zero matches while other tabs have jobs', async () => {
    mockJobsList([job({ id: '1', title: 'Saved Job', status: 'Saved' })])
    const user = userEvent.setup()
    render(<Tracking />)

    await screen.findByText('Saved Job')
    await user.click(within(tabGroup()).getByRole('button', { name: 'Applied' }))

    expect(await screen.findByText('No jobs are marked Applied.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /reset filters/i })).not.toBeInTheDocument()
  })

  it('moves a job to its new tab immediately when status is changed via StatusDropdown, no refetch', async () => {
    let requestCount = 0
    server.use(
      http.get('http://localhost:8000/jobs/', () => {
        requestCount += 1
        return HttpResponse.json({
          total: 1,
          jobs: [job({ id: '1', title: 'Saved Job', status: 'Saved' })],
        })
      }),
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
    render(<Tracking />)

    await screen.findByText('Saved Job')
    // Currently on "All" tab, which includes the Saved job.
    await user.click(screen.getByTestId('status-badge'))
    await user.click(screen.getByRole('option', { name: 'Applied' }))

    // Job stays visible on "All" since Applied !== New.
    await waitFor(() => {
      expect(screen.getByTestId('status-badge')).toHaveTextContent('Applied')
    })

    // Switch to the Applied tab — job should show there without a refetch.
    await user.click(within(tabGroup()).getByRole('button', { name: 'Applied' }))
    expect(screen.getByText('Saved Job')).toBeInTheDocument()

    // Switch to Saved — job should no longer be there.
    await user.click(within(tabGroup()).getByRole('button', { name: 'Saved' }))
    expect(screen.queryByText('Saved Job')).not.toBeInTheDocument()

    expect(requestCount).toBe(1)
  })

  it('selecting New from StatusDropdown removes the job from every tab, including All', async () => {
    mockJobsList([job({ id: '1', title: 'Saved Job', status: 'Saved' })])
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
    render(<Tracking />)

    await screen.findByText('Saved Job')
    await user.click(screen.getByTestId('status-badge'))
    await user.click(screen.getByRole('option', { name: 'New' }))

    await waitFor(() => {
      expect(screen.queryByText('Saved Job')).not.toBeInTheDocument()
    })
    expect(screen.getByText(/no jobs tracked yet/i)).toBeInTheDocument()
  })

  it('notes save on blur through the existing NotesPanel', async () => {
    mockJobsList([job({ id: '1', title: 'Saved Job', status: 'Saved', notes: '' })])
    server.use(
      http.patch('http://localhost:8000/jobs/:id/notes', async ({ request, params }) => {
        const body = (await request.json()) as { notes: string }
        return HttpResponse.json({
          job_id: params.id,
          notes: body.notes,
          updated_at: new Date().toISOString(),
        })
      }),
    )
    const user = userEvent.setup()
    render(<Tracking />)

    await screen.findByText('Saved Job')
    await user.click(screen.getByTestId('notes-button'))

    const textarea = screen.getByRole('textbox', { name: /job notes/i })
    await user.click(textarea)
    await user.type(textarea, 'Follow up Friday.')
    await user.tab()

    await waitFor(
      () => {
        expect(textarea).toHaveValue('Follow up Friday.')
      },
      { timeout: 2000 },
    )
  })

  it('Fits Me filter narrows the active tab to fits_me jobs only, no second network call, and restores on toggle off', async () => {
    let requestCount = 0
    const fitsMeJobs = [
      job({ id: '1', title: 'Saved Fits', status: 'Saved', fits_me: true }),
      job({ id: '2', title: 'Saved No Fits', status: 'Saved', fits_me: false }),
    ]
    server.use(
      http.get('http://localhost:8000/jobs/', () => {
        requestCount += 1
        return HttpResponse.json({ total: fitsMeJobs.length, jobs: fitsMeJobs })
      }),
    )
    const user = userEvent.setup()
    render(<Tracking />)

    await screen.findByText('Saved Fits')
    expect(screen.getByText('Saved No Fits')).toBeInTheDocument()
    expect(requestCount).toBe(1)

    const fitsMeButton = screen.getByTestId('fits-me-filter-button')
    expect(fitsMeButton).toHaveAttribute('aria-pressed', 'false')

    await user.click(fitsMeButton)
    expect(fitsMeButton).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('Saved Fits')).toBeInTheDocument()
    expect(screen.queryByText('Saved No Fits')).not.toBeInTheDocument()
    expect(requestCount).toBe(1)

    await user.click(fitsMeButton)
    expect(fitsMeButton).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByText('Saved Fits')).toBeInTheDocument()
    expect(screen.getByText('Saved No Fits')).toBeInTheDocument()
    expect(requestCount).toBe(1)
  })

  it('Fits Me filter combines with a non-All tab (Fits Me + Applied) to the intersection', async () => {
    const combinedJobs = [
      job({ id: '1', title: 'Applied Fits', status: 'Applied', fits_me: true }),
      job({ id: '2', title: 'Applied No Fits', status: 'Applied', fits_me: false }),
      job({ id: '3', title: 'Saved Fits', status: 'Saved', fits_me: true }),
    ]
    mockJobsList(combinedJobs)
    const user = userEvent.setup()
    render(<Tracking />)

    await screen.findByText('Applied Fits')

    await user.click(within(tabGroup()).getByRole('button', { name: 'Applied' }))
    await user.click(screen.getByTestId('fits-me-filter-button'))

    expect(screen.getByText('Applied Fits')).toBeInTheDocument()
    expect(screen.queryByText('Applied No Fits')).not.toBeInTheDocument()
    expect(screen.queryByText('Saved Fits')).not.toBeInTheDocument()
  })

  it('shows a new empty state with a working Reset (tab has jobs but none are Fits Me), leaving the tab selection untouched', async () => {
    mockJobsList([job({ id: '1', title: 'Saved Job', status: 'Saved', fits_me: false })])
    const user = userEvent.setup()
    render(<Tracking />)

    await screen.findByText('Saved Job')
    await user.click(within(tabGroup()).getByRole('button', { name: 'Saved' }))
    await user.click(screen.getByTestId('fits-me-filter-button'))

    expect(await screen.findByText('No jobs match your filters.')).toBeInTheDocument()
    const resetButton = screen.getByRole('button', { name: /reset filters/i })
    expect(resetButton).toBeInTheDocument()

    await user.click(resetButton)
    expect(await screen.findByText('Saved Job')).toBeInTheDocument()
    expect(screen.getByTestId('fits-me-filter-button')).toHaveAttribute('aria-pressed', 'false')
    // Tab selection is untouched by the reset.
    expect(within(tabGroup()).getByRole('button', { name: 'Saved' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('existing tab-only empty state still has no reset link when Fits Me is off', async () => {
    mockJobsList([job({ id: '1', title: 'Saved Job', status: 'Saved' })])
    const user = userEvent.setup()
    render(<Tracking />)

    await screen.findByText('Saved Job')
    await user.click(within(tabGroup()).getByRole('button', { name: 'Applied' }))

    expect(await screen.findByText('No jobs are marked Applied.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /reset filters/i })).not.toBeInTheDocument()
  })

  it('Fits Me star toggles and reverts on a mocked PATCH failure', async () => {
    mockJobsList([job({ id: '1', title: 'Saved Job', status: 'Saved', fits_me: false })])
    server.use(
      http.patch('http://localhost:8000/jobs/:id/fits_me', async () => {
        await delay(20)
        return HttpResponse.error()
      }),
    )
    const user = userEvent.setup()
    render(<Tracking />)

    await screen.findByText('Saved Job')
    const starButton = screen.getByTestId('fits-me-button')
    expect(starButton).toHaveAttribute('aria-pressed', 'false')

    await user.click(starButton)
    await waitFor(() => {
      expect(starButton).toHaveAttribute('aria-pressed', 'true')
    })

    await waitFor(() => {
      expect(starButton).toHaveAttribute('aria-pressed', 'false')
    })
  })

  it('header count reflects the jobs visible in the currently active tab, not a hardcoded Saved count', async () => {
    mockJobsList(mixedJobs)
    const user = userEvent.setup()
    render(<Tracking />)

    await screen.findByText('Saved Job')
    expect(screen.getByRole('heading', { name: /^tracking$/i })).toBeInTheDocument()
    expect(screen.getByTestId('tracking-count')).toHaveTextContent('(5)')

    await user.click(within(tabGroup()).getByRole('button', { name: 'Saved' }))
    expect(screen.getByTestId('tracking-count')).toHaveTextContent('(1)')

    await user.click(within(tabGroup()).getByRole('button', { name: 'Applied' }))
    expect(screen.getByTestId('tracking-count')).toHaveTextContent('(1)')
  })

  it('does not render a Save button on JobCard (no onSave wired)', async () => {
    mockJobsList([job({ id: '1', title: 'Saved Job', status: 'Saved' })])
    render(<Tracking />)

    await screen.findByText('Saved Job')
    expect(screen.queryByTestId('save-button')).not.toBeInTheDocument()
  })
})

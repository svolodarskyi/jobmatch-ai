import { vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../../mocks/server'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FetchButton from './FetchButton'

const POLL_MS = 50

function completedRun(newJobs: number, status = 'ok', errorMessage: string | null = null) {
  const now = new Date().toISOString()
  return {
    runs: [{
      id: '1',
      started_at: now,
      completed_at: now,
      window_days: 1,
      fetched_total: newJobs,
      new_jobs: newJobs,
      updated_jobs: 0,
      scored_pass1: newJobs,
      scored_pass2: 0,
      source_stats: { adzuna: { retrieved: newJobs }, jooble: { retrieved: 0 } },
      tokens_in: 0,
      tokens_out: 0,
      cost_usd: 0,
      status,
      error_message: errorMessage,
    }],
  }
}

describe('FetchButton', () => {
  it('renders button with correct label', () => {
    render(<FetchButton />)
    expect(screen.getByRole('button', { name: /fetch new jobs/i })).toBeInTheDocument()
  })

  it('click fires POST /jobs/fetch request', async () => {
    let postCalled = false
    server.use(
      http.post('http://localhost:8000/jobs/fetch', () => {
        postCalled = true
        return HttpResponse.json({ status: 'started' }, { status: 202 })
      }),
    )

    render(<FetchButton pollInterval={POLL_MS} />)
    await userEvent.click(screen.getByRole('button', { name: /fetch new jobs/i }))

    await waitFor(() => expect(postCalled).toBe(true))
  })

  it('shows spinner and "Fetching…" text while polling', async () => {
    server.use(
      http.post('http://localhost:8000/jobs/fetch', () =>
        HttpResponse.json({ status: 'started' }, { status: 202 }),
      ),
      http.get('http://localhost:8000/fetch-runs', () =>
        HttpResponse.json({ runs: [{ started_at: new Date().toISOString(), completed_at: null }] }),
      ),
    )

    render(<FetchButton pollInterval={POLL_MS} />)
    await userEvent.click(screen.getByRole('button'))
    expect(await screen.findByText('Fetching…')).toBeInTheDocument()
  })

  it('button is disabled while fetching', async () => {
    server.use(
      http.post('http://localhost:8000/jobs/fetch', () =>
        HttpResponse.json({ status: 'started' }, { status: 202 }),
      ),
      http.get('http://localhost:8000/fetch-runs', () =>
        HttpResponse.json({ runs: [] }),
      ),
    )

    render(<FetchButton pollInterval={POLL_MS} />)
    const btn = screen.getByRole('button')
    await userEvent.click(btn)
    await waitFor(() => expect(btn).toBeDisabled())
  })

  it('shows success banner with correct count after polling completes', async () => {
    server.use(
      http.post('http://localhost:8000/jobs/fetch', () =>
        HttpResponse.json({ status: 'started' }, { status: 202 }),
      ),
      http.get('http://localhost:8000/fetch-runs', () =>
        HttpResponse.json(completedRun(12)),
      ),
    )

    render(<FetchButton pollInterval={POLL_MS} />)
    await userEvent.click(screen.getByRole('button', { name: /fetch new jobs/i }))

    expect(await screen.findByText('12 new jobs found')).toBeInTheDocument()
  })

  it('shows "No new jobs" when new_jobs=0', async () => {
    server.use(
      http.post('http://localhost:8000/jobs/fetch', () =>
        HttpResponse.json({ status: 'started' }, { status: 202 }),
      ),
      http.get('http://localhost:8000/fetch-runs', () =>
        HttpResponse.json(completedRun(0)),
      ),
    )

    render(<FetchButton pollInterval={POLL_MS} />)
    await userEvent.click(screen.getByRole('button', { name: /fetch new jobs/i }))

    expect(await screen.findByText('No new jobs')).toBeInTheDocument()
  })

  it('shows error banner on API failure (POST 4xx)', async () => {
    server.use(
      http.post('http://localhost:8000/jobs/fetch', () =>
        HttpResponse.json({ detail: 'Profile not found' }, { status: 404 }),
      ),
    )

    render(<FetchButton pollInterval={POLL_MS} />)
    await userEvent.click(screen.getByRole('button', { name: /fetch new jobs/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Profile not found')
  })

  it('calls onFetchComplete callback after polling detects completion', async () => {
    const onFetchComplete = vi.fn()

    server.use(
      http.post('http://localhost:8000/jobs/fetch', () =>
        HttpResponse.json({ status: 'started' }, { status: 202 }),
      ),
      http.get('http://localhost:8000/fetch-runs', () =>
        HttpResponse.json(completedRun(5)),
      ),
    )

    render(<FetchButton pollInterval={POLL_MS} onFetchComplete={onFetchComplete} />)
    await userEvent.click(screen.getByRole('button', { name: /fetch new jobs/i }))

    await waitFor(() => expect(onFetchComplete).toHaveBeenCalledOnce())
  })
})

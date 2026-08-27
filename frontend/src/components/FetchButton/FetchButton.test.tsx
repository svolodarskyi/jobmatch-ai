import { http, HttpResponse } from 'msw'
import { server } from '../../mocks/server'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FetchButton from './FetchButton'
import Dashboard from '../../views/Dashboard/Dashboard'

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
        return HttpResponse.json({ fetched: 1, new: 1, updated: 0, scored_pass1: 1, scored_pass2: 0 })
      }),
    )

    render(<FetchButton />)
    await userEvent.click(screen.getByRole('button', { name: /fetch new jobs/i }))

    await waitFor(() => {
      expect(postCalled).toBe(true)
    })
  })

  it('shows spinner and "Fetching…" text while in-progress', async () => {
    server.use(
      http.post('http://localhost:8000/jobs/fetch', () => {
        // never resolves — keeps loading state
        return new Promise(() => {})
      }),
    )

    render(<FetchButton />)
    await userEvent.click(screen.getByRole('button'))

    expect(await screen.findByText('Fetching…')).toBeInTheDocument()
  })

  it('button is disabled while fetching', async () => {
    server.use(
      http.post('http://localhost:8000/jobs/fetch', () => {
        return new Promise(() => {})
      }),
    )

    render(<FetchButton />)
    const btn = screen.getByRole('button')
    await userEvent.click(btn)

    await waitFor(() => {
      expect(btn).toBeDisabled()
    })
  })

  it('shows success banner with correct count after completion', async () => {
    server.use(
      http.post('http://localhost:8000/jobs/fetch', () => {
        return HttpResponse.json({ fetched: 48, new: 12, updated: 3, scored_pass1: 48, scored_pass2: 15 })
      }),
    )

    render(<FetchButton />)
    await userEvent.click(screen.getByRole('button', { name: /fetch new jobs/i }))

    expect(await screen.findByText('12 new jobs found')).toBeInTheDocument()
  })

  it('shows "No new jobs" when new=0', async () => {
    server.use(
      http.post('http://localhost:8000/jobs/fetch', () => {
        return HttpResponse.json({ fetched: 10, new: 0, updated: 0, scored_pass1: 10, scored_pass2: 0 })
      }),
    )

    render(<FetchButton />)
    await userEvent.click(screen.getByRole('button', { name: /fetch new jobs/i }))

    expect(await screen.findByText('No new jobs')).toBeInTheDocument()
  })

  it('shows error banner on API failure', async () => {
    server.use(
      http.post('http://localhost:8000/jobs/fetch', () => {
        return HttpResponse.json({ detail: 'A fetch is already running.' }, { status: 503 })
      }),
    )

    render(<FetchButton />)
    await userEvent.click(screen.getByRole('button', { name: /fetch new jobs/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent('A fetch is already running.')
  })

  it('job list refreshes after successful fetch (GET /jobs/ is called again)', async () => {
    let jobsCallCount = 0

    server.use(
      http.get('http://localhost:8000/jobs/', () => {
        jobsCallCount++
        return HttpResponse.json({
          total: 1,
          jobs: [
            {
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
            },
          ],
        })
      }),
      http.post('http://localhost:8000/jobs/fetch', () => {
        return HttpResponse.json({ fetched: 1, new: 1, updated: 0, scored_pass1: 1, scored_pass2: 0 })
      }),
    )

    render(<Dashboard />)

    // Wait for the initial job list load
    await screen.findByText('Data Engineer')
    expect(jobsCallCount).toBe(1)

    // Click the fetch button
    await userEvent.click(screen.getByRole('button', { name: /fetch new jobs/i }))

    // After fetch completes, GET /jobs/ should be called again
    await waitFor(() => {
      expect(jobsCallCount).toBe(2)
    })
  })
})

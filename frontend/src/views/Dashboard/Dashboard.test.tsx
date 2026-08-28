import { http, HttpResponse } from 'msw'
import userEvent from '@testing-library/user-event'
import { server } from '../../mocks/server'
import { render, screen, waitFor } from '@testing-library/react'
import Dashboard from './Dashboard'

describe('Dashboard', () => {
  it('renders job cards from mocked GET /jobs/ response', async () => {
    render(<Dashboard />)

    // Default handler returns 1 job titled "Data Engineer"
    expect(await screen.findByText('Data Engineer')).toBeInTheDocument()
    // Company is part of a compound text node — use regex
    expect(screen.getByText(/Acme/)).toBeInTheDocument()
    // Score shown: llm_score=78
    expect(screen.getByText('78')).toBeInTheDocument()
  })

  it('shows total job count', async () => {
    render(<Dashboard />)
    await screen.findByText('Data Engineer')
    expect(screen.getByText(/1 job found/i)).toBeInTheDocument()
  })

  it('shows empty state message when jobs array is empty', async () => {
    server.use(
      http.get('http://localhost:8000/jobs/', () => {
        return HttpResponse.json({ total: 0, jobs: [] })
      }),
    )

    render(<Dashboard />)

    expect(
      await screen.findByText(/no jobs match your filters/i),
    ).toBeInTheDocument()
  })

  it('shows loading skeletons before data arrives', () => {
    // Override with a never-resolving handler so loading stays true
    server.use(
      http.get('http://localhost:8000/jobs/', () => {
        return new Promise(() => {
          // never resolves — keeps loading state
        })
      }),
    )

    render(<Dashboard />)

    // Skeletons should be visible immediately
    expect(screen.getByTestId('loading-skeletons')).toBeInTheDocument()
  })

  it('shows error banner when fetch fails', async () => {
    server.use(
      http.get('http://localhost:8000/jobs/', () => {
        return HttpResponse.json({ detail: 'Server error' }, { status: 500 })
      }),
    )

    render(<Dashboard />)

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  })

  it('wires onFitsMeToggle: clicking the star optimistically updates and PATCHes /jobs/:id/fits_me', async () => {
    const user = userEvent.setup()
    let patchBody: { fits_me: boolean } | null = null
    server.use(
      http.patch('http://localhost:8000/jobs/:id/fits_me', async ({ request, params }) => {
        patchBody = (await request.json()) as { fits_me: boolean }
        return HttpResponse.json({ job_id: params.id, fits_me: patchBody.fits_me })
      }),
    )

    render(<Dashboard />)
    await screen.findByText('Data Engineer')

    const starButton = screen.getByTestId('fits-me-button')
    expect(starButton).toHaveAttribute('aria-pressed', 'false')

    await user.click(starButton)

    await waitFor(() => expect(starButton).toHaveAttribute('aria-pressed', 'true'))
    await waitFor(() => expect(patchBody).toEqual({ fits_me: true }))
  })

  it('toggling a card\'s Fits Me flag while the Fits Me filter is active does not remove the card or trigger a refetch', async () => {
    const user = userEvent.setup()
    let getCallCount = 0
    server.use(
      http.get('http://localhost:8000/jobs/', ({ request }) => {
        getCallCount += 1
        const url = new URL(request.url)
        const fitsMe = url.searchParams.get('fits_me')
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
              fits_me: fitsMe === 'true',
            },
          ],
        })
      }),
      http.patch('http://localhost:8000/jobs/:id/fits_me', async ({ request, params }) => {
        const body = (await request.json()) as { fits_me: boolean }
        return HttpResponse.json({ job_id: params.id, fits_me: body.fits_me })
      }),
    )

    render(<Dashboard />)
    await screen.findByText('Data Engineer')
    expect(getCallCount).toBe(1)

    // Activate the Fits Me filter — triggers a refetch; job comes back with fits_me: true
    const fitsMeFilterCheckbox = screen.getByRole('checkbox', { name: /★ fits me/i })
    await user.click(fitsMeFilterCheckbox)

    await waitFor(() => expect(getCallCount).toBe(2))
    await screen.findByText('Data Engineer')

    const starButton = screen.getByTestId('fits-me-button')
    expect(starButton).toHaveAttribute('aria-pressed', 'true')

    // Toggle the star off while the fits_me filter is still active
    await user.click(starButton)

    await waitFor(() => expect(starButton).toHaveAttribute('aria-pressed', 'false'))

    // Card stays visible — local state only, no refetch triggered
    expect(screen.getByText('Data Engineer')).toBeInTheDocument()
    expect(getCallCount).toBe(2)
  })
})

import { http, HttpResponse } from 'msw'
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
})

import { http, HttpResponse } from 'msw'
import { server } from '../../mocks/server'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FetchHistory from './FetchHistory'

const mockRun = {
  id: '1',
  started_at: '2026-08-27T09:00:00Z',
  completed_at: '2026-08-27T09:00:08Z',
  window_days: 1,
  fetched_total: 97,
  new_jobs: 23,
  updated_jobs: 4,
  scored_pass1: 97,
  scored_pass2: 20,
  source_stats: { adzuna: { retrieved: 40 }, jooble: { retrieved: 57 } },
  tokens_in: 7841,
  tokens_out: 591,
  cost_usd: 0.001531,
  status: 'ok',
  error_message: null,
}

describe('FetchHistory', () => {
  it('renders collapsed summary from mocked API data', async () => {
    render(<FetchHistory />)

    // Wait for data to load and collapsed summary to appear
    expect(await screen.findByText(/97 retrieved/)).toBeInTheDocument()
    expect(screen.getByText(/Adzuna 40/)).toBeInTheDocument()
    // Cost formatted to 4 decimal places
    expect(screen.getByText(/\$0\.0015/)).toBeInTheDocument()
  })

  it('renders empty state when runs array is empty', async () => {
    server.use(
      http.get('http://localhost:8000/fetch-runs', () => {
        return HttpResponse.json({ runs: [] })
      }),
    )

    render(<FetchHistory />)

    expect(await screen.findByText('No fetch history yet')).toBeInTheDocument()
  })

  it('expand toggle shows the table and collapse hides it', async () => {
    render(<FetchHistory />)

    // Wait for data
    await screen.findByText(/97 retrieved/)

    // Table should not be visible initially
    expect(screen.queryByRole('table')).not.toBeInTheDocument()

    // Click expand
    await userEvent.click(screen.getByRole('button', { name: /expand history/i }))

    // Table should now be visible
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /Date/i })).toBeInTheDocument()

    // Click collapse
    await userEvent.click(screen.getByRole('button', { name: /collapse history/i }))

    // Table should be hidden again
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('error status row has red text styling', async () => {
    server.use(
      http.get('http://localhost:8000/fetch-runs', () => {
        return HttpResponse.json({
          runs: [
            {
              ...mockRun,
              id: '2',
              status: 'error',
              error_message: 'API timeout',
            },
          ],
        })
      }),
    )

    render(<FetchHistory />)

    // Wait for data to load
    await screen.findByText(/97 retrieved|No fetch history yet|\$/)

    // Expand the table
    await userEvent.click(screen.getByRole('button', { name: /expand history/i }))

    // The row with error status should have red styling
    const row = document.querySelector('tr[data-status="error"]')
    expect(row).toBeInTheDocument()
    expect(row).toHaveClass('text-red-400')
  })
})

import { http, HttpResponse } from 'msw'
import { render, screen } from '@testing-library/react'
import { server } from '../../mocks/server'
import FetchRuns from './FetchRuns'

const completeRun = {
  id: '1',
  started_at: '2026-08-27T09:00:00Z',
  completed_at: '2026-08-27T09:00:08Z',
  window_days: 1,
  fetched_total: 97,
  new_jobs: 23,
  scored_pass2: 20,
  source_stats: { adzuna: { new: 40, updated: 4 }, jooble: { new: 57, updated: 3 } },
  cost_usd: 0.001531,
  status: 'ok',
}

describe('FetchRuns', () => {
  it('renders the full table from API data', async () => {
    render(<FetchRuns />)
    expect(await screen.findByRole('heading', { name: 'Fetch Runs' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Cost' })).toBeInTheDocument()
    expect(screen.getByText('40 new / 4 updated')).toBeInTheDocument()
    expect(screen.getByText('$0.0015')).toBeInTheDocument()
  })

  it('renders the empty state', async () => {
    server.use(http.get('http://localhost:8000/fetch-runs', () => HttpResponse.json({ runs: [] })))
    render(<FetchRuns />)
    expect(await screen.findByText('No fetch runs yet')).toBeInTheDocument()
  })

  it('styles error and partial rows by data status', async () => {
    server.use(http.get('http://localhost:8000/fetch-runs', () => HttpResponse.json({ runs: [
      { ...completeRun, id: 'error', status: 'error' },
      { ...completeRun, id: 'partial', status: 'partial' },
    ] })))
    render(<FetchRuns />)
    await screen.findByText('Error')
    expect(document.querySelector('tr[data-status="error"]')).toHaveClass('text-red-400')
    expect(document.querySelector('tr[data-status="partial"]')).toHaveClass('text-amber-400')
  })

  it('renders a running row with null-safe placeholders', async () => {
    server.use(http.get('http://localhost:8000/fetch-runs', () => HttpResponse.json({ runs: [{
      ...completeRun,
      id: 'running',
      completed_at: null,
      window_days: null,
      fetched_total: null,
      new_jobs: null,
      scored_pass2: null,
      cost_usd: null,
      source_stats: {},
      status: 'ok',
    }] })))
    render(<FetchRuns />)
    expect(await screen.findByText('Running')).toBeInTheDocument()
    expect(document.querySelector('tr[data-status="running"]')).toHaveClass('text-blue-400')
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(5)
  })
})

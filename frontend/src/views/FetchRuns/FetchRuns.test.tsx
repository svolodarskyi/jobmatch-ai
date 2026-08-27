import { http, HttpResponse } from 'msw'
import { server } from '../../mocks/server'
import { render, screen } from '@testing-library/react'
import FetchRuns from './FetchRuns'

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
  source_stats: { adzuna: { new: 15, updated: 8 }, jooble: { new: 8, updated: 4 } },
  tokens_in: 7841,
  tokens_out: 591,
  cost_usd: 0.001531,
  status: 'ok',
  error_message: null,
}

const runningRun = {
  id: '2',
  started_at: '2026-08-27T10:00:00Z',
  completed_at: null,
  window_days: null,
  fetched_total: null,
  new_jobs: null,
  updated_jobs: null,
  scored_pass1: null,
  scored_pass2: null,
  source_stats: {},
  tokens_in: null,
  tokens_out: null,
  cost_usd: null,
  status: 'ok',
  error_message: null,
}

function mockRuns(runs: unknown[]) {
  server.use(
    http.get('http://localhost:8000/fetch-runs', () => {
      return HttpResponse.json({ runs })
    }),
  )
}

describe('FetchRuns', () => {
  it('renders a heading', async () => {
    mockRuns([mockRun])
    render(<FetchRuns />)
    expect(await screen.findByRole('heading', { name: /fetch runs/i })).toBeInTheDocument()
  })

  it('renders the full table from mocked data, with source stats read from new/updated', async () => {
    mockRuns([mockRun])
    render(<FetchRuns />)

    expect(await screen.findByRole('table')).toBeInTheDocument()

    // Subtitle counts runs.length
    expect(screen.getByText('1 run')).toBeInTheDocument()

    // Column headers
    for (const col of ['Date', 'Window', 'Retrieved', 'Adzuna', 'Jooble', 'New', 'Scoped', 'Cost', 'Status']) {
      expect(screen.getByRole('columnheader', { name: col })).toBeInTheDocument()
    }

    // Adzuna/Jooble read .new/.updated, not .retrieved
    expect(screen.getByText('15 new / 8 updated')).toBeInTheDocument()
    expect(screen.getByText('8 new / 4 updated')).toBeInTheDocument()

    // Other fields
    expect(screen.getByText('97')).toBeInTheDocument() // Retrieved (fetched_total)
    expect(screen.getByText('23')).toBeInTheDocument() // New (new_jobs)
    expect(screen.getByText('20')).toBeInTheDocument() // Scoped (scored_pass2)
    expect(screen.getByText('$0.0015')).toBeInTheDocument() // Cost
    expect(screen.getByText('1d')).toBeInTheDocument() // Window
    expect(screen.getByText('OK')).toBeInTheDocument() // Status
  })

  it('defaults Adzuna/Jooble stats to 0 when a source key is absent', async () => {
    mockRuns([{ ...mockRun, source_stats: { adzuna: { new: 15, updated: 8 } } }])
    render(<FetchRuns />)

    await screen.findByRole('table')

    expect(screen.getByText('15 new / 8 updated')).toBeInTheDocument()
    expect(screen.getByText('0 new / 0 updated')).toBeInTheDocument()
  })

  it('renders rows in API order without client-side re-sorting', async () => {
    const second = { ...mockRun, id: '3', started_at: '2026-08-26T09:00:00Z' }
    mockRuns([mockRun, second])
    render(<FetchRuns />)

    await screen.findByRole('table')

    const rows = screen.getAllByRole('row').slice(1) // drop header row
    expect(rows[0]).toHaveAttribute('data-status')
    expect(rows).toHaveLength(2)
    // First data row corresponds to mockRun (started_at 09:00 on Aug 27), second to the older run.
    expect(rows[0].textContent).toContain('27')
    expect(rows[1].textContent).toContain('26')
  })

  it('renders empty state when runs array is empty', async () => {
    mockRuns([])
    render(<FetchRuns />)

    expect(await screen.findByText('No fetch runs yet')).toBeInTheDocument()
    expect(screen.getByText('0 runs')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('error status row has red text styling keyed off data-status', async () => {
    mockRuns([{ ...mockRun, id: '4', status: 'error', error_message: 'API timeout' }])
    render(<FetchRuns />)

    await screen.findByRole('table')

    const row = document.querySelector('tr[data-status="error"]')
    expect(row).toBeInTheDocument()
    expect(row).toHaveClass('text-red-400')
    expect(row?.textContent).toContain('Error')
  })

  it('partial status row has amber text styling keyed off data-status', async () => {
    mockRuns([{ ...mockRun, id: '5', status: 'partial', error_message: 'Jooble failed' }])
    render(<FetchRuns />)

    await screen.findByRole('table')

    const row = document.querySelector('tr[data-status="partial"]')
    expect(row).toBeInTheDocument()
    expect(row).toHaveClass('text-amber-400')
    expect(row?.textContent).toContain('Partial')
  })

  it('renders a running row (completed_at null) with placeholders instead of throwing', async () => {
    mockRuns([runningRun])
    render(<FetchRuns />)

    await screen.findByRole('table')

    const row = document.querySelector('tr[data-status="running"]')
    expect(row).toBeInTheDocument()
    expect(row).toHaveClass('text-blue-400')
    expect(row?.textContent).toContain('Running')

    // Null stat fields render as em dash, not throw from .toFixed() on null
    const dashCells = row?.querySelectorAll('td') ?? []
    const dashTexts = Array.from(dashCells).map((td) => td.textContent)
    expect(dashTexts).toContain('—') // window
    // Retrieved, New, Scoped, Cost all null -> dash
    expect(dashTexts.filter((t) => t === '—').length).toBeGreaterThanOrEqual(4)
    // Missing source keys still default to 0, not dash
    expect(row?.textContent).toContain('0 new / 0 updated')
  })
})

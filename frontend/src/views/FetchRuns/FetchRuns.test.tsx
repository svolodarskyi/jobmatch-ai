import { http, HttpResponse } from 'msw'
import { server } from '../../mocks/server'
import { render, screen, waitFor } from '@testing-library/react'
import FetchRuns from './FetchRuns'

const POLL_MS = 50

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

  it('shows retrieved count with red-400 styling when a source retrieved 0 (failed/empty fetch)', async () => {
    mockRuns([
      {
        ...mockRun,
        id: '10',
        source_stats: {
          adzuna: { retrieved: 0, new: 0, updated: 0 },
          jooble: { new: 8, updated: 4 },
        },
      },
    ])
    render(<FetchRuns />)
    await screen.findByRole('table')

    const cell = screen.getByText('0 retrieved · 0 new / 0 updated')
    expect(cell).toBeInTheDocument()
    expect(cell).toHaveClass('text-red-400')
  })

  it('shows retrieved count with slate-400 styling when a source retrieved jobs but all were duplicates', async () => {
    mockRuns([
      {
        ...mockRun,
        id: '11',
        source_stats: {
          adzuna: { retrieved: 12, new: 0, updated: 0 },
          jooble: { new: 8, updated: 4 },
        },
      },
    ])
    render(<FetchRuns />)
    await screen.findByRole('table')

    const cell = screen.getByText('12 retrieved · 0 new / 0 updated')
    expect(cell).toBeInTheDocument()
    expect(cell).toHaveClass('text-slate-400')
  })

  it('shows retrieved count with default styling when a source has real new/updated activity', async () => {
    mockRuns([
      {
        ...mockRun,
        id: '12',
        source_stats: {
          adzuna: { retrieved: 20, new: 15, updated: 8 },
          jooble: { new: 8, updated: 4 },
        },
      },
    ])
    render(<FetchRuns />)
    await screen.findByRole('table')

    const cell = screen.getByText('20 retrieved · 15 new / 8 updated')
    expect(cell).toBeInTheDocument()
    expect(cell).not.toHaveClass('text-red-400')
    expect(cell).not.toHaveClass('text-slate-400')
  })

  it('falls back to legacy "new / updated" text with default styling for an old-shape source missing the retrieved key', async () => {
    mockRuns([
      {
        ...mockRun,
        id: '13',
        source_stats: {
          adzuna: { new: 3, updated: 1 },
          jooble: { new: 8, updated: 4 },
        },
      },
    ])
    render(<FetchRuns />)
    await screen.findByRole('table')

    const cell = screen.getByText('3 new / 1 updated')
    expect(cell).toBeInTheDocument()
    expect(cell).not.toHaveClass('text-red-400')
    expect(cell).not.toHaveClass('text-slate-400')
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

  it('polls and updates the table in place when a running row completes, with no new spinner/badge', async () => {
    server.use(
      http.get(
        'http://localhost:8000/fetch-runs',
        () => HttpResponse.json({ runs: [runningRun] }),
        { once: true },
      ),
      http.get('http://localhost:8000/fetch-runs', () =>
        HttpResponse.json({ runs: [{ ...runningRun, completed_at: '2026-08-27T10:00:08Z', status: 'ok' }] }),
      ),
    )

    render(<FetchRuns pollInterval={POLL_MS} />)

    await screen.findByRole('table')
    expect(document.querySelector('tr[data-status="running"]')).toBeInTheDocument()

    // Table updates in place after the poll picks up completion — no remount, no new spinner/badge.
    await waitFor(() => {
      expect(document.querySelector('tr[data-status="running"]')).not.toBeInTheDocument()
      expect(document.querySelector('tr[data-status="ok"]')).toBeInTheDocument()
    })
    expect(screen.queryByLabelText(/live/i)).not.toBeInTheDocument()
    expect(document.querySelector('[class*="animate-spin"]')).not.toBeInTheDocument()
  })

  it('does not start polling when the initial load has no running row', async () => {
    let callCount = 0
    server.use(
      http.get('http://localhost:8000/fetch-runs', () => {
        callCount += 1
        return HttpResponse.json({ runs: [mockRun] })
      }),
    )

    render(<FetchRuns pollInterval={POLL_MS} />)
    await screen.findByRole('table')

    // Give a few poll intervals worth of time to elapse; call count should stay at 1 (no polling).
    await new Promise((resolve) => setTimeout(resolve, POLL_MS * 4))
    expect(callCount).toBe(1)
  })

  it('does not start polling when the initial load fails', async () => {
    let callCount = 0
    server.use(
      http.get('http://localhost:8000/fetch-runs', () => {
        callCount += 1
        return HttpResponse.json({ detail: 'boom' }, { status: 500 })
      }),
    )

    render(<FetchRuns pollInterval={POLL_MS} />)
    expect(await screen.findByRole('alert')).toBeInTheDocument()

    await new Promise((resolve) => setTimeout(resolve, POLL_MS * 4))
    expect(callCount).toBe(1)
  })

  it('a failed poll request does not stop polling and does not populate the error banner', async () => {
    let callCount = 0
    server.use(
      http.get('http://localhost:8000/fetch-runs', () => {
        callCount += 1
        if (callCount === 1) {
          return HttpResponse.json({ runs: [runningRun] })
        }
        if (callCount === 2) {
          // Transient failure on the first poll — should be swallowed, not shown, and not stop polling.
          return HttpResponse.json({ detail: 'boom' }, { status: 500 })
        }
        return HttpResponse.json({
          runs: [{ ...runningRun, completed_at: '2026-08-27T10:00:08Z', status: 'ok' }],
        })
      }),
    )

    render(<FetchRuns pollInterval={POLL_MS} />)
    await screen.findByRole('table')

    await waitFor(() => {
      expect(document.querySelector('tr[data-status="ok"]')).toBeInTheDocument()
    })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

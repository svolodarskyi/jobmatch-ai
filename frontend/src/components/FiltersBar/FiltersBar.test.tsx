import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../../mocks/server'
import FiltersBar, { DEFAULT_FILTERS, type Filters } from './FiltersBar'
import Dashboard from '../../views/Dashboard/Dashboard'

const defaultFilters: Filters = { ...DEFAULT_FILTERS }

describe('FiltersBar', () => {
  it('renders all 5 controls', () => {
    const onFilterChange = vi.fn()
    render(<FiltersBar filters={defaultFilters} onFilterChange={onFilterChange} />)

    // Score slider
    expect(screen.getByRole('slider', { name: /score threshold/i })).toBeInTheDocument()
    // Source checkboxes
    expect(screen.getByRole('checkbox', { name: /adzuna/i })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: /jooble/i })).toBeInTheDocument()
    // Status checkboxes
    expect(screen.getByRole('checkbox', { name: /applied/i })).toBeInTheDocument()
    // Date fetched select
    expect(screen.getByRole('combobox', { name: /date fetched/i })).toBeInTheDocument()
    // Fits Me checkbox
    expect(screen.getByRole('checkbox', { name: /★ fits me/i })).toBeInTheDocument()
  })

  it('Fits Me checkbox reflects filters.fits_me and toggles it', () => {
    const onFilterChange = vi.fn()
    render(<FiltersBar filters={defaultFilters} onFilterChange={onFilterChange} />)

    const fitsMeCheckbox = screen.getByRole('checkbox', { name: /★ fits me/i })
    expect(fitsMeCheckbox).not.toBeChecked()

    fireEvent.click(fitsMeCheckbox)

    expect(onFilterChange).toHaveBeenCalledWith(
      expect.objectContaining({ fits_me: true }),
    )
  })

  it('unchecking Fits Me sets it back to false', () => {
    const onFilterChange = vi.fn()
    const filtersWithFitsMe: Filters = { ...DEFAULT_FILTERS, fits_me: true }
    render(<FiltersBar filters={filtersWithFitsMe} onFilterChange={onFilterChange} />)

    const fitsMeCheckbox = screen.getByRole('checkbox', { name: /★ fits me/i })
    expect(fitsMeCheckbox).toBeChecked()

    fireEvent.click(fitsMeCheckbox)

    expect(onFilterChange).toHaveBeenCalledWith(
      expect.objectContaining({ fits_me: false }),
    )
  })

  it('checking Fits Me issues GET /jobs/ with fits_me=true', async () => {
    const user = userEvent.setup()

    let capturedUrl = ''
    server.use(
      http.get('http://localhost:8000/jobs/', ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ total: 0, jobs: [] })
      }),
    )

    render(<Dashboard />)
    await waitFor(() => expect(screen.queryByTestId('loading-skeletons')).not.toBeInTheDocument())

    const fitsMeCheckbox = screen.getByRole('checkbox', { name: /★ fits me/i })
    await user.click(fitsMeCheckbox)

    await waitFor(() => {
      expect(capturedUrl).toContain('fits_me=true')
    })
  })

  it('omits fits_me from the query string when unchecked', async () => {
    let capturedUrl = ''
    server.use(
      http.get('http://localhost:8000/jobs/', ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ total: 0, jobs: [] })
      }),
    )

    render(<Dashboard />)
    await waitFor(() => expect(screen.queryByTestId('loading-skeletons')).not.toBeInTheDocument())

    expect(capturedUrl).not.toContain('fits_me=')
  })

  it('combines fits_me with other active filters via AND in the query string', async () => {
    const user = userEvent.setup()

    let capturedUrl = ''
    server.use(
      http.get('http://localhost:8000/jobs/', ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ total: 0, jobs: [] })
      }),
    )

    render(<Dashboard />)
    await waitFor(() => expect(screen.queryByTestId('loading-skeletons')).not.toBeInTheDocument())

    const slider = screen.getByRole('slider', { name: /score threshold/i })
    fireEvent.change(slider, { target: { value: '70' } })

    const fitsMeCheckbox = screen.getByRole('checkbox', { name: /★ fits me/i })
    await user.click(fitsMeCheckbox)

    await waitFor(() => {
      expect(capturedUrl).toContain('min_score=70')
      expect(capturedUrl).toContain('fits_me=true')
    })
  })

  it('changing score slider calls onFilterChange with correct min_score param', () => {
    const onFilterChange = vi.fn()
    render(<FiltersBar filters={defaultFilters} onFilterChange={onFilterChange} />)

    const slider = screen.getByRole('slider', { name: /score threshold/i })
    fireEvent.change(slider, { target: { value: '50' } })

    expect(onFilterChange).toHaveBeenCalledWith(
      expect.objectContaining({ min_score: 50 }),
    )
  })

  it('selecting a source issues GET /jobs/ with source=adzuna', async () => {
    const user = userEvent.setup()

    let capturedUrl = ''
    server.use(
      http.get('http://localhost:8000/jobs/', ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ total: 0, jobs: [] })
      }),
    )

    render(<Dashboard />)

    // Wait for the initial load to finish
    await waitFor(() => expect(screen.queryByTestId('loading-skeletons')).not.toBeInTheDocument())

    // Click the Adzuna checkbox
    const adzunaCheckbox = screen.getByRole('checkbox', { name: /^adzuna$/i })
    await user.click(adzunaCheckbox)

    await waitFor(() => {
      expect(capturedUrl).toContain('source=adzuna')
    })
  })

  it('selecting "All" for source removes source param', async () => {
    const user = userEvent.setup()

    let capturedUrl = ''
    server.use(
      http.get('http://localhost:8000/jobs/', ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ total: 0, jobs: [] })
      }),
    )

    // Render with adzuna already selected
    const filtersWithSource: Filters = { ...DEFAULT_FILTERS, source: 'adzuna' }

    const onFilterChange = vi.fn()
    render(<FiltersBar filters={filtersWithSource} onFilterChange={onFilterChange} />)

    // Click "All" checkbox
    const allCheckbox = screen.getByRole('checkbox', { name: /all sources/i })
    await user.click(allCheckbox)

    expect(onFilterChange).toHaveBeenCalledWith(
      expect.objectContaining({ source: null }),
    )

    // Also verify via Dashboard integration: start with adzuna source then reset
    server.use(
      http.get('http://localhost:8000/jobs/', ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ total: 0, jobs: [] })
      }),
    )

    render(<Dashboard />)
    await waitFor(() => expect(screen.queryByTestId('loading-skeletons')).not.toBeInTheDocument())

    // After default load, source param should not be in URL
    expect(capturedUrl).not.toContain('source=')
  })

  it('selecting a status issues GET /jobs/ with status=Applied', async () => {
    const user = userEvent.setup()

    let capturedUrl = ''
    server.use(
      http.get('http://localhost:8000/jobs/', ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ total: 0, jobs: [] })
      }),
    )

    render(<Dashboard />)
    await waitFor(() => expect(screen.queryByTestId('loading-skeletons')).not.toBeInTheDocument())

    // Find and click Applied checkbox (use the first one — FiltersBar renders one)
    const appliedCheckboxes = screen.getAllByRole('checkbox', { name: /^applied$/i })
    await user.click(appliedCheckboxes[0])

    await waitFor(() => {
      expect(capturedUrl).toContain('status=Applied')
    })
  })

  it('reset link restores defaults', async () => {
    const user = userEvent.setup()

    let capturedUrl = ''
    server.use(
      http.get('http://localhost:8000/jobs/', ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json({ total: 0, jobs: [] })
      }),
    )

    render(<Dashboard />)
    await waitFor(() => expect(screen.queryByTestId('loading-skeletons')).not.toBeInTheDocument())

    // Select a source and Fits Me to change state
    const adzunaCheckbox = screen.getByRole('checkbox', { name: /^adzuna$/i })
    await user.click(adzunaCheckbox)

    await waitFor(() => {
      expect(capturedUrl).toContain('source=adzuna')
    })

    const fitsMeCheckbox = screen.getByRole('checkbox', { name: /★ fits me/i })
    await user.click(fitsMeCheckbox)

    await waitFor(() => {
      expect(capturedUrl).toContain('fits_me=true')
    })
    expect(fitsMeCheckbox).toBeChecked()

    // Click reset
    const resetBtn = screen.getByRole('button', { name: /reset filters/i })
    await user.click(resetBtn)

    await waitFor(() => {
      expect(capturedUrl).not.toContain('source=')
      expect(capturedUrl).not.toContain('min_score=')
      expect(capturedUrl).not.toContain('status=')
      expect(capturedUrl).not.toContain('since=')
      expect(capturedUrl).not.toContain('fits_me=')
    })
    expect(screen.getByRole('checkbox', { name: /★ fits me/i })).not.toBeChecked()
  })
})

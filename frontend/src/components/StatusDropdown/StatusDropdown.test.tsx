import { http, HttpResponse } from 'msw'
import { server } from '../../mocks/server'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import StatusDropdown from './StatusDropdown'

const noop = () => {}

describe('StatusDropdown', () => {
  it('renders current status with a checkmark', () => {
    render(
      <StatusDropdown
        jobId="1"
        currentStatus="New"
        history={[]}
        onClose={noop}
        onStatusChange={noop}
      />,
    )

    // All 6 statuses rendered
    expect(screen.getByRole('option', { name: /New/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Applied/ })).toBeInTheDocument()

    // Current status (New) has a checkmark indicator
    const newOption = screen.getByRole('option', { name: /New/ })
    expect(newOption).toHaveAttribute('aria-selected', 'true')
    expect(newOption.querySelector('[aria-label="current"]')).toBeInTheDocument()
  })

  it('clicking a new status calls onStatusChange with the new status and closes', async () => {
    const user = userEvent.setup()
    const onStatusChange = vi.fn()
    const onClose = vi.fn()

    render(
      <StatusDropdown
        jobId="42"
        currentStatus="New"
        history={[]}
        onClose={onClose}
        onStatusChange={onStatusChange}
      />,
    )

    await user.click(screen.getByRole('option', { name: /Applied/ }))

    // Optimistic update fired immediately
    expect(onStatusChange).toHaveBeenCalledWith(
      'Applied',
      expect.arrayContaining([expect.objectContaining({ status: 'Applied' })]),
    )
    expect(onClose).toHaveBeenCalled()

    // After PATCH resolves, onStatusChange called again with server data
    await waitFor(() => {
      expect(onStatusChange).toHaveBeenCalledTimes(2)
      const secondCall = onStatusChange.mock.calls[1] as [string, { status: string }[]]
      expect(secondCall[0]).toBe('Applied')
    })
  })

  it('reverts optimistic update when PATCH returns an error', async () => {
    server.use(
      http.patch('http://localhost:8000/jobs/:id/status', () => {
        return HttpResponse.error()
      }),
    )

    const user = userEvent.setup()
    const onStatusChange = vi.fn()

    render(
      <StatusDropdown
        jobId="99"
        currentStatus="New"
        history={[]}
        onClose={noop}
        onStatusChange={onStatusChange}
      />,
    )

    await user.click(screen.getByRole('option', { name: /Applied/ }))

    // First call: optimistic update to "Applied"
    await waitFor(() => {
      expect(onStatusChange).toHaveBeenNthCalledWith(
        1,
        'Applied',
        expect.arrayContaining([expect.objectContaining({ status: 'Applied' })]),
      )
    })

    // Second call: revert back to original status "New"
    await waitFor(() => {
      expect(onStatusChange).toHaveBeenNthCalledWith(2, 'New', [])
    })
  })
})

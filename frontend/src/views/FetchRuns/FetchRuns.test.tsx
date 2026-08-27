import { render, screen } from '@testing-library/react'
import FetchRuns from './FetchRuns'

describe('FetchRuns', () => {
  it('renders a heading', () => {
    render(<FetchRuns />)
    expect(screen.getByRole('heading', { name: /fetch runs/i })).toBeInTheDocument()
  })
})

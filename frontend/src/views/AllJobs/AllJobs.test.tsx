import { render, screen } from '@testing-library/react'
import AllJobs from './AllJobs'

describe('AllJobs', () => {
  it('renders a heading', () => {
    render(<AllJobs />)
    expect(screen.getByRole('heading', { name: /all jobs/i })).toBeInTheDocument()
  })
})

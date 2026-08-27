import { render, screen } from '@testing-library/react'
import Tracking from './Tracking'

describe('Tracking', () => {
  it('renders a heading', () => {
    render(<Tracking />)
    expect(screen.getByRole('heading', { name: /tracking/i })).toBeInTheDocument()
  })
})

import { render, screen } from '@testing-library/react'
import App from './App'

test('renders the JobMatch AI heading', () => {
  render(<App />)
  expect(screen.getByRole('heading', { name: /JobMatch AI/i })).toBeInTheDocument()
})

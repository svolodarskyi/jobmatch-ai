import { render, screen } from '@testing-library/react'
import App from './App'

test('renders the Dashboard', async () => {
  render(<App />)
  // Dashboard heading is visible immediately
  expect(screen.getByRole('heading', { name: /job matches/i })).toBeInTheDocument()
  // Wait for a job card to appear from the mocked GET /jobs/ handler
  expect(await screen.findByText('Data Engineer')).toBeInTheDocument()
})

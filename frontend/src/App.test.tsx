import { render, screen, waitFor } from '@testing-library/react'
import App from './App'

test('renders the ProfileForm', async () => {
  render(<App />)
  // ProfileForm shows a loading state, then the form
  await waitFor(() => {
    expect(screen.queryByText(/loading profile/i)).not.toBeInTheDocument()
  })
  expect(screen.getByRole('button', { name: /save profile/i })).toBeInTheDocument()
})

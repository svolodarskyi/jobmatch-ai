import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'

const TAB_NAMES = ['Matches', 'All Jobs', 'Tracking', 'Fetch Runs', 'Profile']

test('renders all 5 tabs in order', () => {
  render(<App />)
  const nav = screen.getByRole('navigation')
  const tabs = screen.getAllByRole('button', {
    name: /^(matches|all jobs|tracking|fetch runs|profile)$/i,
  })
  expect(tabs.map((t) => t.textContent)).toEqual(TAB_NAMES)
  expect(nav).toBeInTheDocument()
})

test('Matches is the default active tab on load and renders the Dashboard', async () => {
  render(<App />)
  // Dashboard heading is visible immediately
  expect(screen.getByRole('heading', { name: /job matches/i })).toBeInTheDocument()
  // Wait for a job card to appear from the mocked GET /jobs/ handler
  expect(await screen.findByText('Data Engineer')).toBeInTheDocument()

  const matchesTab = screen.getByRole('button', { name: 'Matches' })
  expect(matchesTab).toHaveAttribute('aria-current', 'page')
  expect(matchesTab.className).toContain('bg-blue-500')
  expect(matchesTab.className).toContain('text-white')
})

test('clicking each tab renders only that tab and marks it active', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('Data Engineer') // let initial Dashboard fetch settle

  for (const name of TAB_NAMES) {
    await user.click(screen.getByRole('button', { name }))

    const activeTab = screen.getByRole('button', { name })
    expect(activeTab).toHaveAttribute('aria-current', 'page')
    expect(activeTab.className).toContain('bg-blue-500')
    expect(activeTab.className).toContain('text-white')

    // exactly one tab is marked active
    const allTabs = screen.getAllByRole('button', {
      name: /^(matches|all jobs|tracking|fetch runs|profile)$/i,
    })
    const active = allTabs.filter((t) => t.getAttribute('aria-current') === 'page')
    expect(active).toHaveLength(1)

    // inactive tabs use the inactive styling
    for (const tab of allTabs) {
      if (tab !== activeTab) {
        expect(tab.className).toContain('text-slate-400')
        expect(tab.className).not.toContain('bg-blue-500')
      }
    }

    switch (name) {
      case 'Matches':
        expect(screen.getByRole('heading', { name: /job matches/i })).toBeInTheDocument()
        break
      case 'All Jobs':
        expect(screen.getByRole('heading', { name: /^all jobs$/i })).toBeInTheDocument()
        break
      case 'Tracking':
        expect(screen.getByRole('heading', { name: /^tracking$/i })).toBeInTheDocument()
        break
      case 'Fetch Runs':
        expect(screen.getByRole('heading', { name: /^fetch runs$/i })).toBeInTheDocument()
        break
      case 'Profile':
        expect(screen.getByRole('heading', { name: /profile/i })).toBeInTheDocument()
        break
    }
  }
})

import { http, HttpResponse } from 'msw'
import { server } from '../../mocks/server'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ProfileForm from './ProfileForm'

// Helper: wait for loading spinner to disappear
async function waitForLoad() {
  await waitFor(() => {
    expect(screen.queryByText(/loading profile/i)).not.toBeInTheDocument()
  })
}

describe('ProfileForm', () => {
  it('renders all 6 fields', async () => {
    render(<ProfileForm />)
    await waitForLoad()

    // Tag input sections — identified by heading labels
    expect(screen.getByText(/target titles/i)).toBeInTheDocument()
    expect(screen.getByText(/^skills \*/i)).toBeInTheDocument()
    expect(screen.getByText(/^locations$/i)).toBeInTheDocument()

    // Seniority radio group (fieldset/group role from the div)
    expect(screen.getByRole('group', { name: /locations/i })).toBeInTheDocument()
    // All 5 seniority options
    for (const opt of ['Junior', 'Mid', 'Senior', 'Lead', 'Exec']) {
      expect(screen.getByRole('radio', { name: opt })).toBeInTheDocument()
    }

    // Salary inputs (by label text on the <label> elements)
    expect(screen.getByLabelText(/^min$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^max$/i)).toBeInTheDocument()

    // Preferences textarea
    expect(screen.getByLabelText(/preferences/i)).toBeInTheDocument()

    // Submit button
    expect(screen.getByRole('button', { name: /save profile/i })).toBeInTheDocument()
  })

  it('populates fields from GET /profile response', async () => {
    render(<ProfileForm />)
    await waitForLoad()

    // Tags from mock GET /profile response
    expect(screen.getByText('Data Engineer')).toBeInTheDocument()
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('Calgary AB')).toBeInTheDocument()

    // Seniority radio checked
    const seniorRadio = screen.getByRole('radio', { name: 'Senior' })
    expect(seniorRadio).toBeChecked()

    // Salary fields
    expect(screen.getByLabelText(/^min$/i)).toHaveValue(100000)
    expect(screen.getByLabelText(/^max$/i)).toHaveValue(150000)
  })

  it('fires PUT /profile with correct payload on submit', async () => {
    const user = userEvent.setup()
    let capturedBody: unknown = null

    server.use(
      http.put('http://localhost:8000/profile', async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json({ id: 'test-id', ...(capturedBody as object) })
      }),
    )

    render(<ProfileForm />)
    await waitForLoad()

    // Submit the form with data already populated from mock GET
    await user.click(screen.getByRole('button', { name: /save profile/i }))

    await waitFor(() => {
      expect(capturedBody).not.toBeNull()
    })

    const body = capturedBody as Record<string, unknown>
    expect(body).toMatchObject({
      target_titles: ['Data Engineer'],
      skills: ['Python'],
      seniority: 'Senior',
      locations: ['Calgary AB'],
      salary_min: 100000,
      salary_max: 150000,
    })
    expect(body).toHaveProperty('preferences')
  })

  it('shows toast on successful save', async () => {
    const user = userEvent.setup()

    render(<ProfileForm />)
    await waitForLoad()

    await user.click(screen.getByRole('button', { name: /save profile/i }))

    await waitFor(() => {
      expect(screen.getByText(/profile saved successfully/i)).toBeInTheDocument()
    })
  })

  it('shows validation error when salary_min >= salary_max', async () => {
    const user = userEvent.setup()

    render(<ProfileForm />)
    await waitForLoad()

    // Set salary min > max
    const minInput = screen.getByLabelText(/^min$/i)
    const maxInput = screen.getByLabelText(/^max$/i)

    await user.clear(minInput)
    await user.type(minInput, '200000')
    await user.clear(maxInput)
    await user.type(maxInput, '100000')

    await user.click(screen.getByRole('button', { name: /save profile/i }))

    await waitFor(() => {
      expect(
        screen.getByText(/salary min must be less than salary max/i),
      ).toBeInTheDocument()
    })
  })
})

import { http, HttpResponse } from 'msw'

export const handlers = [
  http.get('http://localhost:8000/profile', () => {
    return HttpResponse.json({
      id: 'test-id',
      target_titles: ['Data Engineer'],
      skills: ['Python'],
      seniority: 'Senior',
      locations: ['Calgary AB'],
      salary_min: 100000,
      salary_max: 150000,
      preferences: {},
    })
  }),

  http.put('http://localhost:8000/profile', async ({ request }) => {
    const body = await request.json()
    return HttpResponse.json({ id: 'test-id', ...(body as object) })
  }),
]

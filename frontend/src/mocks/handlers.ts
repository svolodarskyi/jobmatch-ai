import { http, HttpResponse } from 'msw'

export const handlers = [
  http.get('http://localhost:8000/jobs/', () => {
    return HttpResponse.json({
      total: 1,
      jobs: [
        {
          id: '1',
          source: 'adzuna',
          title: 'Data Engineer',
          company: 'Acme',
          location: 'Calgary, AB',
          salary_min: 100000,
          salary_max: 130000,
          url: 'https://example.com',
          date_fetched: '2026-08-26T14:00:00Z',
          raw_score: 84,
          llm_score: 78,
          llm_rationale: 'Good match.',
          status: 'New',
          notes: '',
        },
      ],
    })
  }),

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

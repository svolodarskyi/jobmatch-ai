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

  http.patch('http://localhost:8000/jobs/:id/status', async ({ request, params }) => {
    const body = await request.json() as { status: string }
    return HttpResponse.json({
      job_id: params.id,
      status: body.status,
      history: [{ status: body.status, changed_at: new Date().toISOString() }],
      updated_at: new Date().toISOString(),
    })
  }),

  http.patch('http://localhost:8000/jobs/:id/notes', async ({ request, params }) => {
    const body = await request.json() as { notes: string }
    return HttpResponse.json({
      job_id: params.id,
      notes: body.notes,
      updated_at: new Date().toISOString(),
    })
  }),

  http.post('http://localhost:8000/jobs/fetch', () => {
    return HttpResponse.json({ fetched: 48, new: 12, updated: 3, scored_pass1: 48, scored_pass2: 15 })
  }),

  http.get('http://localhost:8000/fetch-runs', () => {
    return HttpResponse.json({
      runs: [
        {
          id: '1',
          started_at: '2026-08-27T09:00:00Z',
          completed_at: '2026-08-27T09:00:08Z',
          window_days: 1,
          fetched_total: 97,
          new_jobs: 23,
          updated_jobs: 4,
          scored_pass1: 97,
          scored_pass2: 20,
          source_stats: { adzuna: { retrieved: 40 }, jooble: { retrieved: 57 } },
          tokens_in: 7841,
          tokens_out: 591,
          cost_usd: 0.001531,
          status: 'ok',
          error_message: null,
        },
      ],
    })
  }),
]

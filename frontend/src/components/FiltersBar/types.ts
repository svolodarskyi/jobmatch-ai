export interface Filters {
  min_score: number
  source: string | null
  status: string | null
  since: string | null
  fits_me: boolean
}

export const DEFAULT_FILTERS: Filters = {
  min_score: 0,
  source: null,
  status: null,
  since: null,
  fits_me: false,
}

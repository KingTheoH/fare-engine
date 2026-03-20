import type { DealResult, FilterState } from './types'

export function applyFilters(deals: DealResult[], filters: FilterState): DealResult[] {
  return deals
    .filter(d => filters.deal_types.includes(d.deal_type))
    .filter(d => d.total_price_usd === undefined || d.offer.total_price_usd <= filters.max_price_usd)
    .filter(d => {
      if (filters.airlines.length === 0) return true
      return d.offer.segments.some(s => filters.airlines.includes(s.airline))
    })
    .filter(d => {
      const stops = d.offer.segments.length - 1
      if (filters.max_stops === 0) return stops === 0
      if (filters.max_stops === 1) return stops <= 1
      return true
    })
}

export function sortDeals(deals: DealResult[], sortBy: FilterState['sort_by'], dir: 'asc' | 'desc'): DealResult[] {
  const sorted = [...deals].sort((a, b) => {
    let diff = 0
    if (sortBy === 'savings_pct') diff = a.savings_pct - b.savings_pct
    else if (sortBy === 'price') diff = a.offer.total_price_usd - b.offer.total_price_usd
    else if (sortBy === 'departure_time') {
      const at = a.offer.segments[0]?.departure_time || ''
      const bt = b.offer.segments[0]?.departure_time || ''
      diff = at.localeCompare(bt)
    }
    return dir === 'asc' ? diff : -diff
  })
  return sorted
}

export function rankDeals(deals: DealResult[]): DealResult[] {
  // Default: sort by savings_pct descending, deduplicate by booking_url
  const seen = new Set<string>()
  return deals
    .sort((a, b) => b.savings_pct - a.savings_pct)
    .filter(d => {
      if (seen.has(d.booking_url)) return false
      seen.add(d.booking_url)
      return true
    })
    .slice(0, 50)
}

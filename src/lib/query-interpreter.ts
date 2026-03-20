import type { SearchSpec, DealType, Currency } from './types'

// ─── Airport aliases ──────────────────────────────────────────────────────────
const CITY_TO_IATA: Record<string, string> = {
  'new york': 'JFK', 'nyc': 'JFK', 'new york city': 'JFK',
  'los angeles': 'LAX', 'la': 'LAX',
  'london': 'LHR', 'heathrow': 'LHR',
  'paris': 'CDG',
  'rome': 'FCO',
  'tokyo': 'NRT',
  'osaka': 'KIX',
  'dubai': 'DXB',
  'singapore': 'SIN',
  'sydney': 'SYD',
  'toronto': 'YYZ',
  'amsterdam': 'AMS',
  'frankfurt': 'FRA',
  'madrid': 'MAD',
  'barcelona': 'BCN',
  'milan': 'MXP',
  'hong kong': 'HKG',
  'bangkok': 'BKK',
  'seoul': 'ICN',
  'beijing': 'PEK',
  'shanghai': 'PVG',
  'mumbai': 'BOM',
  'delhi': 'DEL',
  'chicago': 'ORD',
  'miami': 'MIA',
  'san francisco': 'SFO', 'sf': 'SFO',
  'seattle': 'SEA',
  'boston': 'BOS',
  'dallas': 'DFW',
  'houston': 'IAH',
  'atlanta': 'ATL',
  'denver': 'DEN',
  'lisbon': 'LIS',
  'dublin': 'DUB',
  'vienna': 'VIE',
  'zurich': 'ZRH',
  'copenhagen': 'CPH',
  'stockholm': 'ARN',
  'oslo': 'OSL',
  'helsinki': 'HEL',
  'warsaw': 'WAW',
  'prague': 'PRG',
  'budapest': 'BUD',
  'athens': 'ATH',
  'istanbul': 'IST',
  'cairo': 'CAI',
  'johannesburg': 'JNB',
  'nairobi': 'NBO',
  'sao paulo': 'GRU',
  'buenos aires': 'EZE',
  'mexico city': 'MEX',
  'vancouver': 'YVR',
  'montreal': 'YUL',
  'calgary': 'YYC',
  'edmonton': 'YEG',
  'ottawa': 'YOW',
  'manila': 'MNL',
  'philippines': 'MNL',
  'cebu': 'CEB',
  'kuala lumpur': 'KUL', 'kl': 'KUL',
  'jakarta': 'CGK',
  'bali': 'DPS',
  'ho chi minh': 'SGN', 'saigon': 'SGN',
  'hanoi': 'HAN',
  'taipei': 'TPE',
  'guangzhou': 'CAN',
  'chengdu': 'CTU',
  'doha': 'DOH',
  'abu dhabi': 'AUH',
  'riyadh': 'RUH',
  'tel aviv': 'TLV',
  'casablanca': 'CMN',
  'lagos': 'LOS',
  'accra': 'ACC',
  'addis ababa': 'ADD',
  'cape town': 'CPT',
  'lima': 'LIM',
  'bogota': 'BOG',
  'santiago': 'SCL',
  'auckland': 'AKL',
  'melbourne': 'MEL',
  'brisbane': 'BNE',
  'perth': 'PER',
  'las vegas': 'LAS',
  'orlando': 'MCO',
  'phoenix': 'PHX',
  'minneapolis': 'MSP',
  'detroit': 'DTW',
  'charlotte': 'CLT',
  'new orleans': 'MSY',
  'salt lake city': 'SLC',
  'portland': 'PDX',
}

// ─── Month aliases ────────────────────────────────────────────────────────────
const MONTHS: Record<string, number> = {
  jan: 1, january: 1, feb: 2, february: 2,
  mar: 3, march: 3, apr: 4, april: 4,
  may: 5, jun: 6, june: 6, jul: 7, july: 7,
  aug: 8, august: 8, sep: 9, sept: 9, september: 9,
  oct: 10, october: 10, nov: 11, november: 11,
  dec: 12, december: 12,
}

function resolveIATA(token: string): string | null {
  const t = token.toLowerCase().trim()
  if (/^[A-Z]{3}$/.test(token.toUpperCase())) return token.toUpperCase()
  return CITY_TO_IATA[t] || null
}

function resolveDate(query: string): { date_out: string; date_back?: string } {
  const q = query.toLowerCase()
  const year = new Date().getFullYear()

  // explicit date YYYY-MM-DD
  const exactMatch = q.match(/(\d{4}-\d{2}-\d{2})/)
  if (exactMatch) return { date_out: exactMatch[1] }

  // "June 15" or "15 June"
  for (const [month, num] of Object.entries(MONTHS)) {
    const re1 = new RegExp(`${month}\\s+(\\d{1,2})`)
    const re2 = new RegExp(`(\\d{1,2})\\s+${month}`)
    const m = q.match(re1) || q.match(re2)
    if (m) {
      const day = m[1].padStart(2, '0')
      const mo = String(num).padStart(2, '0')
      return { date_out: `${year}-${mo}-${day}` }
    }
    // just a month → first of month
    if (new RegExp(`\\b${month}\\b`).test(q)) {
      const mo = String(num).padStart(2, '0')
      return { date_out: `${year}-${mo}-01` }
    }
  }

  // default: 30 days from now
  const d = new Date()
  d.setDate(d.getDate() + 30)
  return { date_out: d.toISOString().split('T')[0] }
}

export function parseQuery(raw: string): SearchSpec {
  const q = raw.toLowerCase()
  const words = raw.split(/\s+/)

  // ── deal types ─────────────────────────────────────────────────────────────
  const allDealTypes: DealType[] = ['fuel_dump', 'hidden_city', 'throwaway', 'yq_free']
  let deal_types: DealType[] = [...allDealTypes]
  if (q.includes('fuel dump') || q.includes('fuel-dump')) deal_types = ['fuel_dump']
  if (q.includes('hidden city') || q.includes('skiplagg')) deal_types = ['hidden_city']
  if (q.includes('throwaway')) deal_types = ['throwaway']
  if (q.includes('yq free') || q.includes('yq-free') || q.includes('no yq')) deal_types = ['yq_free']

  // ── passengers ────────────────────────────────────────────────────────────
  const passM = q.match(/(\d+)\s*(?:passenger|pax|person|people|adult)/i)
  const passengers = passM ? parseInt(passM[1]) : 1

  // ── flexible days ────────────────────────────────────────────────────────
  const flexM = q.match(/(?:±|plus.minus|flex(?:ible)?)\s*(\d+)\s*day/)
  const flexible_days = flexM ? parseInt(flexM[1]) : 0

  // ── stops ─────────────────────────────────────────────────────────────────
  let max_stops = 2
  if (q.includes('direct') || q.includes('non-stop') || q.includes('nonstop')) max_stops = 0
  if (q.includes('1 stop') || q.includes('one stop')) max_stops = 1

  // ── currency ──────────────────────────────────────────────────────────────
  let currency: Currency = 'USD'
  if (q.includes('eur') || q.includes('euro')) currency = 'EUR'
  if (q.includes('gbp') || q.includes('pound')) currency = 'GBP'
  if (q.includes('jpy') || q.includes('yen')) currency = 'JPY'

  // ── origin / destination ──────────────────────────────────────────────────
  // Try "FROM X to Y" pattern
  let origin = ''
  let destination = ''

  const fromToM = raw.match(/(?:from\s+)?([A-Za-z\s]+?)\s+(?:to|→|-)\s+([A-Za-z\s]+?)(?:\s+|$)/i)
  if (fromToM) {
    origin = resolveIATA(fromToM[1].trim()) || fromToM[1].trim().toUpperCase().slice(0, 3)
    destination = resolveIATA(fromToM[2].trim()) || fromToM[2].trim().toUpperCase().slice(0, 3)
  } else {
    // scan words for IATA codes
    const iatas: string[] = []
    for (const w of words) {
      const resolved = resolveIATA(w)
      if (resolved) iatas.push(resolved)
    }
    origin = iatas[0] || 'JFK'
    destination = iatas[1] || 'LHR'
  }

  const { date_out, date_back } = resolveDate(raw)

  return {
    raw_query: raw,
    origin,
    destination,
    date_out,
    date_back,
    passengers,
    deal_types,
    max_stops,
    flexible_days,
    currency,
  }
}

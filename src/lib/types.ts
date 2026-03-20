// ─── Deal Types ────────────────────────────────────────────────────────────────
export type DealType = 'fuel_dump' | 'hidden_city' | 'throwaway' | 'yq_free' | 'best_fare'
export type Confidence = 'HIGH' | 'MEDIUM' | 'LOW'
export type Source = 'kiwi' | 'serpapi'
export type FlightType = 'oneway' | 'round' | 'multicity'
export type Currency = 'USD' | 'EUR' | 'GBP' | 'JPY' | 'AUD'
export type SortBy = 'savings_pct' | 'price' | 'departure_time'

// ─── Raw Flight Data ──────────────────────────────────────────────────────────
export interface Segment {
  origin: string           // IATA code e.g. "JFK"
  destination: string      // IATA code e.g. "FCO"
  airline: string          // IATA carrier code e.g. "UA"
  airline_name?: string
  flight_number: string
  departure_time: string   // ISO 8601
  arrival_time: string     // ISO 8601
  duration_minutes: number
  stops: number
  is_throwaway?: boolean   // true if this leg should be discarded (fuel dump)
}

export interface FlightOffer {
  id: string
  source: Source
  segments: Segment[]
  total_price_usd: number
  currency: string
  booking_url: string
  fetched_at: string
}

// ─── Search Spec ──────────────────────────────────────────────────────────────
export interface SearchSpec {
  raw_query: string
  origin: string           // IATA
  destination: string      // IATA
  date_out: string         // YYYY-MM-DD
  date_back?: string       // YYYY-MM-DD
  passengers: number
  deal_types: DealType[]
  max_stops: number
  flexible_days: number
  currency: Currency
}

// ─── Deal Result ──────────────────────────────────────────────────────────────
export interface DealResult {
  id?: string
  offer: FlightOffer
  deal_type: DealType
  normal_fare_usd: number
  savings_usd: number
  savings_pct: number
  explanation: string
  confidence: Confidence
  caveats: string[]
  booking_url: string
  is_saved?: boolean
}

// ─── YQ Carrier Table ─────────────────────────────────────────────────────────
export interface YQCarrierTable {
  yq_imposing: Record<string, string>
  yq_free: Record<string, string>
  yq_exempt_departure_airports: Record<string, string>
}

// ─── Filter State ─────────────────────────────────────────────────────────────
export interface FilterState {
  deal_types: DealType[]
  max_price_usd: number
  airlines: string[]
  max_stops: 0 | 1 | 2
  sort_by: SortBy
  sort_dir: 'asc' | 'desc'
}

// ─── Settings ─────────────────────────────────────────────────────────────────
export interface AppSettings {
  kiwi_api_key: string
  serpapi_key: string
  home_airport: string
  default_passengers: number
  currency: Currency
}

// ─── API Response ─────────────────────────────────────────────────────────────
export interface SearchResponse {
  spec: SearchSpec
  deals: DealResult[]
  meta: {
    total_fetched: number
    deals_found: number
    sources_checked: string[]
    source_errors: string[]
    duration_ms: number
  }
}

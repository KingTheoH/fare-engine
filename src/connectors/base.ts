import type { FlightOffer, SearchSpec } from '../lib/types'

export interface FlightConnector {
  name: string
  search(spec: SearchSpec, apiKey: string): Promise<FlightOffer[]>
}

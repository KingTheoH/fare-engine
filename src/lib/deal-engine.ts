import type { FlightOffer, DealResult, DealType, SearchSpec, YQCarrierTable } from './types'

// ─── YQ Carrier Table (static) ────────────────────────────────────────────────
export const YQ_TABLE: YQCarrierTable = {
  yq_imposing: {
    BA: 'British Airways', LH: 'Lufthansa', AF: 'Air France',
    KL: 'KLM', LX: 'Swiss International', OS: 'Austrian Airlines',
    SN: 'Brussels Airlines', VS: 'Virgin Atlantic', EI: 'Aer Lingus',
    IB: 'Iberia', AZ: 'ITA Airways', SK: 'SAS', AY: 'Finnair',
    TP: 'TAP Air Portugal', CX: 'Cathay Pacific', SQ: 'Singapore Airlines',
    QF: 'Qantas', EK: 'Emirates', EY: 'Etihad', QR: 'Qatar Airways',
    TK: 'Turkish Airlines',
  },
  yq_free: {
    UA: 'United Airlines', AA: 'American Airlines', DL: 'Delta Air Lines',
    AS: 'Alaska Airlines', WN: 'Southwest Airlines', B6: 'JetBlue',
    NK: 'Spirit Airlines', F9: 'Frontier Airlines', G4: 'Allegiant Air',
  },
  yq_exempt_departure_airports: {
    NRT: 'Tokyo Narita — Japan prohibits fuel surcharges',
    HND: 'Tokyo Haneda — Japan prohibits fuel surcharges',
    KIX: 'Osaka Kansai — Japan prohibits fuel surcharges',
    ITM: 'Osaka Itami — Japan prohibits fuel surcharges',
    GRU: 'São Paulo Guarulhos — Brazil caps fuel surcharges',
    GIG: 'Rio de Janeiro — Brazil caps fuel surcharges',
    HKG: 'Hong Kong — Low/zero YQ environment',
  },
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function buildPriceIndex(offers: FlightOffer[]): Map<string, number> {
  const idx = new Map<string, number>()
  for (const offer of offers) {
    if (offer.segments.length === 1) {
      const key = `${offer.segments[0].origin}-${offer.segments[0].destination}`
      const existing = idx.get(key)
      if (!existing || offer.total_price_usd < existing) {
        idx.set(key, offer.total_price_usd)
      }
    }
  }
  return idx
}

function primaryCarrier(offer: FlightOffer): string {
  return offer.segments[0]?.airline || ''
}

function carrierName(code: string, table: YQCarrierTable): string {
  return table.yq_imposing[code] || table.yq_free[code] || code
}

// ─── Detector 1: Fuel Dump ────────────────────────────────────────────────────
export function detectFuelDump(
  offers: FlightOffer[],
  spec: SearchSpec,
  table: YQCarrierTable
): DealResult[] {
  const results: DealResult[] = []
  const priceIndex = buildPriceIndex(offers)

  for (const offer of offers) {
    if (offer.segments.length < 2) continue
    const finalDest = offer.segments[offer.segments.length - 1].destination
    if (finalDest === spec.destination) continue // not a throwaway

    // Check it passes through user's destination
    const primaryLeg = offer.segments.find(s => s.destination === spec.destination)
    if (!primaryLeg) continue

    const baselineKey = `${spec.origin}-${spec.destination}`
    const baseline = priceIndex.get(baselineKey)
    if (!baseline) continue

    const savings = baseline - offer.total_price_usd
    const savingsPct = savings / baseline

    if (savings < 50 || savingsPct < 0.20) continue

    const carrier = primaryCarrier(offer)
    const isYQCarrier = !!table.yq_imposing[carrier]
    const confidence = isYQCarrier ? 'HIGH' : 'MEDIUM'
    const throwawayDest = finalDest
    const throwawayLeg = offer.segments[offer.segments.length - 1]

    const explanation = isYQCarrier
      ? `Appending ${throwawayDest} as a throwaway leg eliminates ${carrierName(carrier, table)}'s YQ fuel surcharge on the ${spec.origin}→${spec.destination} primary legs, saving $${savings.toFixed(0)}.`
      : `Multi-city routing via ${throwawayDest} prices $${savings.toFixed(0)} cheaper than a direct ${spec.origin}→${spec.destination} ticket. Likely YQ or pricing rule interaction.`

    // Mark the throwaway leg
    const enrichedOffer: FlightOffer = {
      ...offer,
      segments: offer.segments.map((s, i) =>
        i === offer.segments.length - 1 ? { ...s, is_throwaway: true } : s
      ),
    }

    results.push({
      offer: enrichedOffer,
      deal_type: 'fuel_dump',
      normal_fare_usd: baseline,
      savings_usd: savings,
      savings_pct: savingsPct * 100,
      explanation,
      confidence,
      caveats: [
        'Violates airline Terms of Service',
        'Book as multi-city — do not modify the itinerary after ticketing',
        `You do not need to fly the ${throwawayDest} leg`,
      ],
      booking_url: offer.booking_url,
    })
  }

  return results
}

// ─── Detector 2: Hidden City (Skiplagging) ────────────────────────────────────
export function detectHiddenCity(
  offers: FlightOffer[],
  spec: SearchSpec
): DealResult[] {
  const results: DealResult[] = []

  // Find cheapest direct A→B
  const directOffers = offers.filter(o =>
    o.segments.length >= 1 &&
    o.segments[0].origin === spec.origin &&
    o.segments[o.segments.length - 1].destination === spec.destination
  )
  if (directOffers.length === 0) return []
  const cheapestDirect = Math.min(...directOffers.map(o => o.total_price_usd))

  // Find offers that route THROUGH spec.destination but end elsewhere
  for (const offer of offers) {
    if (offer.segments[0].origin !== spec.origin) continue
    const finalDest = offer.segments[offer.segments.length - 1].destination
    if (finalDest === spec.destination) continue // this is the direct route

    const hasConnectionAtDest = offer.segments.some(
      (s, i) => i < offer.segments.length - 1 && s.destination === spec.destination
    )
    if (!hasConnectionAtDest) continue

    const savings = cheapestDirect - offer.total_price_usd
    if (savings < 30) continue

    const savingsPct = savings / cheapestDirect
    const confidence = savings > 100 ? 'HIGH' : 'MEDIUM'

    results.push({
      offer,
      deal_type: 'hidden_city',
      normal_fare_usd: cheapestDirect,
      savings_usd: savings,
      savings_pct: savingsPct * 100,
      explanation: `Booking ${spec.origin}→${spec.destination}→${finalDest} and exiting at ${spec.destination} costs $${savings.toFixed(0)} less than the cheapest direct ${spec.origin}→${spec.destination} ticket.`,
      confidence,
      caveats: [
        'CARRY-ON ONLY — checked bags will travel to the final destination',
        'Do not use a return leg if booked as round-trip on the same ticket',
        'Airline may cancel remaining legs if you deboard early',
        'Violates airline Terms of Service',
        'Legally permissible per 2024 US federal court ruling',
      ],
      booking_url: offer.booking_url,
    })
  }

  return results
}

// ─── Detector 3: Throwaway Ticketing ─────────────────────────────────────────
export function detectThrowaway(
  onewayOffers: FlightOffer[],
  roundtripOffers: FlightOffer[],
  spec: SearchSpec
): DealResult[] {
  if (onewayOffers.length === 0 || roundtripOffers.length === 0) return []

  const cheapestOneway = Math.min(...onewayOffers.map(o => o.total_price_usd))
  const cheapestRoundtrip = roundtripOffers.reduce((best, o) =>
    o.total_price_usd < best.total_price_usd ? o : best
  , roundtripOffers[0])

  if (!cheapestRoundtrip) return []
  const savings = cheapestOneway - cheapestRoundtrip.total_price_usd
  if (savings < 20) return []

  return [{
    offer: cheapestRoundtrip,
    deal_type: 'throwaway',
    normal_fare_usd: cheapestOneway,
    savings_usd: savings,
    savings_pct: (savings / cheapestOneway) * 100,
    explanation: `A round-trip ${spec.origin}→${spec.destination} costs $${savings.toFixed(0)} less than the cheapest one-way. Buy the round-trip and simply don't use the return leg.`,
    confidence: 'HIGH',
    caveats: [
      'Use the outbound leg only — no-show the return',
      'Most carriers allow no-show on return without penalty for revenue fares',
      'Do not check bags if skipping the return leg',
      'Violates airline Terms of Service',
    ],
    booking_url: cheapestRoundtrip.booking_url,
  }]
}

// ─── Detector 4: YQ-Free Carrier ─────────────────────────────────────────────
export function detectYQFreeCarrier(
  offers: FlightOffer[],
  spec: SearchSpec,
  table: YQCarrierTable
): DealResult[] {
  const results: DealResult[] = []

  // Group by (origin, destination, stops_bucket)
  type Group = { yqFree: FlightOffer[]; yqImposing: FlightOffer[] }
  const groups = new Map<string, Group>()

  for (const offer of offers) {
    const firstSeg = offer.segments[0]
    const lastSeg = offer.segments[offer.segments.length - 1]
    // Group by route only — compare across stop levels so a 1-stop YQ-free
    // carrier (e.g. JetBlue via JFK) is compared against a direct YQ-imposing fare (BA)
    const key = `${firstSeg.origin}-${lastSeg.destination}`

    if (!groups.has(key)) groups.set(key, { yqFree: [], yqImposing: [] })
    const g = groups.get(key)!

    const carrier = primaryCarrier(offer)
    const isExemptDeparture = !!table.yq_exempt_departure_airports[firstSeg.origin]

    if (table.yq_free[carrier] || isExemptDeparture) {
      g.yqFree.push(offer)
    } else if (table.yq_imposing[carrier]) {
      g.yqImposing.push(offer)
    }
  }

  for (const [, group] of groups) {
    if (group.yqFree.length === 0 || group.yqImposing.length === 0) continue

    const bestFree = group.yqFree.reduce((best, o) =>
      o.total_price_usd < best.total_price_usd ? o : best
    , group.yqFree[0])
    const cheapestImposing = Math.min(...group.yqImposing.map(o => o.total_price_usd))

    if (bestFree.total_price_usd > cheapestImposing * 0.90) continue

    const savings = cheapestImposing - bestFree.total_price_usd
    const savingsPct = savings / cheapestImposing

    const carrier = primaryCarrier(bestFree)
    const carrierFullName = carrierName(carrier, table)
    const isExemptDeparture = !!table.yq_exempt_departure_airports[bestFree.segments[0].origin]

    const explanation = isExemptDeparture
      ? `Departing from ${bestFree.segments[0].origin} (${table.yq_exempt_departure_airports[bestFree.segments[0].origin]}) saves $${savings.toFixed(0)} vs. equivalent YQ-imposing carrier routes.`
      : `${carrierFullName} does not impose YQ/YR fuel surcharges — this $${savings.toFixed(0)} saving is structural, not a sale. YQ-imposing carriers charge this as a permanent surcharge regardless of fuel prices.`

    results.push({
      offer: bestFree,
      deal_type: 'yq_free',
      normal_fare_usd: cheapestImposing,
      savings_usd: savings,
      savings_pct: savingsPct * 100,
      explanation,
      confidence: 'MEDIUM',
      caveats: [], // No ToS caveats — fully legitimate
      booking_url: bestFree.booking_url,
    })
  }

  return results
}

// ─── Main Entry Point ─────────────────────────────────────────────────────────
// ─── Detector 5: Best Fare (fallback for live data with no loopholes) ─────────
export function detectBestFares(offers: FlightOffer[], spec: SearchSpec): DealResult[] {
  // Only kick in when there are real offers but no loopholes detected
  const realOffers = offers.filter(o => o.source !== 'demo')
  if (realOffers.length === 0) return []

  // Sort by price and return top 5 as "Best Fare" cards
  const sorted = [...realOffers].sort((a, b) => a.total_price_usd - b.total_price_usd)
  const priciest = Math.max(...realOffers.map(o => o.total_price_usd))

  return sorted.slice(0, 5).map(offer => {
    const savings = priciest - offer.total_price_usd
    const carrier = offer.segments[0]?.airline || ''
    const carrierName = YQ_TABLE.yq_imposing[carrier] || YQ_TABLE.yq_free[carrier] || carrier
    const isYQFree = !!YQ_TABLE.yq_free[carrier]
    return {
      offer,
      deal_type: 'best_fare' as const,
      normal_fare_usd: priciest,
      savings_usd: savings,
      savings_pct: savings > 0 ? (savings / priciest) * 100 : 0,
      explanation: isYQFree
        ? `${carrierName} is a YQ-free carrier — no fuel surcharge baked into this fare.`
        : `Cheapest available fare on this route via live search.`,
      confidence: 'MEDIUM' as const,
      caveats: ['Book directly through the airline or Google Flights'],
      booking_url: offer.booking_url,
    }
  })
}

export function detectDeals(
  offers: FlightOffer[],
  onewayOffers: FlightOffer[],
  roundtripOffers: FlightOffer[],
  spec: SearchSpec
): DealResult[] {
  const loopholeDeals: DealResult[] = [
    ...detectFuelDump(offers, spec, YQ_TABLE),
    ...detectHiddenCity(offers, spec),
    ...detectThrowaway(onewayOffers, roundtripOffers, spec),
    ...detectYQFreeCarrier(offers, spec, YQ_TABLE),
  ].filter(d => spec.deal_types.includes(d.deal_type)).filter(d => d.savings_pct > 0)

  // If no loopholes found from live data, show the best real fares so the UI isn't empty
  if (loopholeDeals.length === 0) {
    return detectBestFares(offers, spec)
  }

  return loopholeDeals
}

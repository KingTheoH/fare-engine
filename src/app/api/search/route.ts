import { NextRequest, NextResponse } from 'next/server'
import { parseQuery } from '@/lib/query-interpreter'
import { detectDeals } from '@/lib/deal-engine'
import { rankDeals } from '@/lib/ranking'
import { skyScrapperConnector, serpapiConnector } from '@/connectors'
import { demoConnector } from '@/connectors/demo'
import prisma from '@/lib/db'
import type { FlightOffer, SearchSpec } from '@/lib/types'

export async function POST(req: NextRequest) {
  const start = Date.now()

  try {
    const body = await req.json()
    const spec: SearchSpec = body.spec
      ? body.spec
      : parseQuery(body.query || '')

    // ── Load settings ───────────────────────────────────────────────────────
    let settings = await prisma.settings.findFirst({ where: { id: 'singleton' } })
    if (!settings) {
      settings = await prisma.settings.create({
        data: { id: 'singleton', kiwi_api_key: '', serpapi_key: '', home_airport: '', default_passengers: 1, currency: 'USD' },
      })
    }

    const rapidApiKey = settings.kiwi_api_key || process.env.RAPIDAPI_KEY || ''
    const serpapiKey  = settings.serpapi_key  || process.env.SERPAPI_KEY  || ''
    const hasAnyKey   = !!(rapidApiKey || serpapiKey)

    // ── Fetch from connectors ───────────────────────────────────────────────
    const sourceErrors: string[] = []
    const sources: string[] = []
    let allOffers: FlightOffer[] = []

    if (hasAnyKey) {
      // ── Cache helpers ─────────────────────────────────────────────────────
      const CACHE_TTL_HOURS = 24
      const cacheKey = { origin: spec.origin, destination: spec.destination, date_out: spec.date_out }

      async function loadFromCache(source: string): Promise<FlightOffer[] | null> {
        const row = await prisma.offerCache.findUnique({
          where: { origin_destination_date_out_source: { ...cacheKey, source } },
        })
        if (!row) return null
        const ageHours = (Date.now() - new Date(row.fetched_at).getTime()) / 3_600_000
        if (ageHours > CACHE_TTL_HOURS) return null
        try { return JSON.parse(row.payload) as FlightOffer[] } catch { return null }
      }

      async function saveToCache(source: string, offers: FlightOffer[]) {
        await prisma.offerCache.upsert({
          where: { origin_destination_date_out_source: { ...cacheKey, source } },
          update: { payload: JSON.stringify(offers), fetched_at: new Date() },
          create: { ...cacheKey, source, payload: JSON.stringify(offers) },
        })
      }

      // ── Fetch with cache-first strategy ──────────────────────────────────
      async function fetchWithCache(
        source: string,
        fetcher: () => Promise<FlightOffer[]>
      ): Promise<{ offers: FlightOffer[]; fromCache: boolean }> {
        const cached = await loadFromCache(source)
        if (cached) return { offers: cached, fromCache: true }
        const fresh = await fetcher()
        if (fresh.length > 0) await saveToCache(source, fresh)
        return { offers: fresh, fromCache: false }
      }

      // Live mode — real APIs only, cache-first to preserve free-tier quota
      const [skyResult, serpapiResult] = await Promise.allSettled([
        rapidApiKey
          ? fetchWithCache('skyscrapper', () => skyScrapperConnector.search(spec, rapidApiKey))
          : Promise.resolve({ offers: [] as FlightOffer[], fromCache: false }),
        serpapiKey
          ? fetchWithCache('serpapi', () => serpapiConnector.search(spec, serpapiKey))
          : Promise.resolve({ offers: [] as FlightOffer[], fromCache: false }),
      ])

      if (skyResult.status === 'fulfilled' && skyResult.value.offers.length > 0) {
        allOffers.push(...skyResult.value.offers)
        sources.push(skyResult.value.fromCache ? 'skyscrapper (cached)' : 'skyscrapper')
      } else if (skyResult.status === 'rejected') {
        sourceErrors.push(`SkyScrapper: ${skyResult.reason?.message || 'unknown error'}`)
      }

      if (serpapiResult.status === 'fulfilled' && serpapiResult.value.offers.length > 0) {
        allOffers.push(...serpapiResult.value.offers)
        sources.push(serpapiResult.value.fromCache ? 'serpapi (cached)' : 'serpapi')
      } else if (serpapiResult.status === 'rejected') {
        sourceErrors.push(`SerpApi: ${serpapiResult.reason?.message || 'unknown error'}`)
      }

      // If real APIs returned nothing, fall back to demo so UI isn't empty
      if (allOffers.length === 0) {
        const demoOffers = await demoConnector.search(spec, '')
        allOffers.push(...demoOffers)
        sources.push('demo')
        sourceErrors.push('⚠️ Live APIs returned no results — showing demo data')
      }
    } else {
      // No API keys — pure demo mode
      const demoOffers = await demoConnector.search(spec, '')
      allOffers.push(...demoOffers)
      sources.push('demo')
      sourceErrors.push('⚠️ Demo mode — add a RapidAPI key in Settings for live prices')
    }

    // ── Separate one-way vs round-trip for throwaway detection ─────────────
    const onewayOffers = allOffers.filter(o => o.segments.length <= 2)
    const roundtripOffers = allOffers.filter(o => {
      const last = o.segments[o.segments.length - 1]
      return last?.destination === o.segments[0]?.origin
    })

    // ── Deduplicate by composite key (not just booking_url which can repeat) ──
    const seen = new Set<string>()
    allOffers = allOffers.filter(o => {
      const firstSeg = o.segments[0]
      const key = `${o.source}|${firstSeg?.airline}|${firstSeg?.origin}|${firstSeg?.destination}|${firstSeg?.departure_time}|${o.total_price_usd}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })

    // ── Detect deals ────────────────────────────────────────────────────────
    const rawDeals = detectDeals(allOffers, onewayOffers, roundtripOffers, spec)
    const deals = rankDeals(rawDeals)

    // ── Persist search + deals ──────────────────────────────────────────────
    const search = await prisma.search.create({
      data: {
        raw_query: spec.raw_query,
        origin: spec.origin,
        destination: spec.destination,
        date_out: spec.date_out,
        date_back: spec.date_back,
        passengers: spec.passengers,
        deal_types: spec.deal_types.join(','),
        deal_count: deals.length,
      },
    })

    const savedDeals = await Promise.all(
      deals.map(d =>
        prisma.deal.create({
          data: {
            search_id: search.id,
            source: d.offer.source,
            deal_type: d.deal_type,
            origin: d.offer.segments[0]?.origin || spec.origin,
            destination: d.offer.segments[d.offer.segments.length - 1]?.destination || spec.destination,
            airline_codes: [...new Set(d.offer.segments.map(s => s.airline))].join(','),
            segments_json: JSON.stringify(d.offer.segments),
            total_price_usd: d.offer.total_price_usd,
            normal_fare_usd: d.normal_fare_usd,
            savings_usd: d.savings_usd,
            savings_pct: d.savings_pct,
            explanation: d.explanation,
            confidence: d.confidence,
            caveats_json: JSON.stringify(d.caveats),
            booking_url: d.booking_url,
            fetched_at: new Date(d.offer.fetched_at),
          },
        })
      )
    )

    const dealsWithIds = deals.map((d, i) => ({ ...d, id: savedDeals[i].id }))

    return NextResponse.json({
      spec,
      deals: dealsWithIds,
      meta: {
        total_fetched: allOffers.length,
        deals_found: deals.length,
        sources_checked: sources,
        source_errors: sourceErrors,
        duration_ms: Date.now() - start,
      },
    })
  } catch (err) {
    console.error('[search] error:', err)
    return NextResponse.json(
      { error: 'Search failed', detail: String(err) },
      { status: 500 }
    )
  }
}

import { NextResponse } from 'next/server'
import prisma from '@/lib/db'

export async function GET() {
  const savedDeals = await prisma.deal.findMany({
    where: { is_saved: true },
    orderBy: { created_at: 'desc' },
    take: 100,
  })

  const deals = savedDeals.map(d => ({
    id: d.id,
    deal_type: d.deal_type,
    is_saved: true,
    offer: {
      id: d.id,
      source: d.source,
      segments: JSON.parse(d.segments_json),
      total_price_usd: d.total_price_usd,
      currency: 'USD',
      booking_url: d.booking_url,
      fetched_at: d.fetched_at.toISOString(),
    },
    normal_fare_usd: d.normal_fare_usd,
    savings_usd: d.savings_usd,
    savings_pct: d.savings_pct,
    explanation: d.explanation,
    confidence: d.confidence,
    caveats: JSON.parse(d.caveats_json),
    booking_url: d.booking_url,
  }))

  return NextResponse.json({ deals })
}

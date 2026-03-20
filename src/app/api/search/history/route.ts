import { NextResponse } from 'next/server'
import prisma from '@/lib/db'

export async function GET() {
  const searches = await prisma.search.findMany({
    orderBy: { created_at: 'desc' },
    take: 50,
    select: {
      id: true,
      raw_query: true,
      origin: true,
      destination: true,
      date_out: true,
      deal_count: true,
      created_at: true,
    },
  })
  return NextResponse.json({ searches })
}

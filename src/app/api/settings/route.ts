import { NextRequest, NextResponse } from 'next/server'
import prisma from '@/lib/db'

export async function GET() {
  let settings = await prisma.settings.findFirst({ where: { id: 'singleton' } })
  if (!settings) {
    settings = await prisma.settings.create({
      data: { id: 'singleton', kiwi_api_key: '', serpapi_key: '', home_airport: '', default_passengers: 1, currency: 'USD' },
    })
  }
  return NextResponse.json(settings)
}

export async function POST(req: NextRequest) {
  const body = await req.json()
  const settings = await prisma.settings.upsert({
    where: { id: 'singleton' },
    update: {
      kiwi_api_key:       body.kiwi_api_key       ?? undefined,
      serpapi_key:        body.serpapi_key         ?? undefined,
      home_airport:       body.home_airport        ?? undefined,
      default_passengers: body.default_passengers  ?? undefined,
      currency:           body.currency            ?? undefined,
    },
    create: {
      id: 'singleton',
      kiwi_api_key:       body.kiwi_api_key       || '',
      serpapi_key:        body.serpapi_key         || '',
      home_airport:       body.home_airport        || '',
      default_passengers: body.default_passengers  || 1,
      currency:           body.currency            || 'USD',
    },
  })
  return NextResponse.json(settings)
}

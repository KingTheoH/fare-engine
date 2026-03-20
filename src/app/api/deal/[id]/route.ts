import { NextRequest, NextResponse } from 'next/server'
import prisma from '@/lib/db'

export async function GET(_: NextRequest, { params }: { params: { id: string } }) {
  const deal = await prisma.deal.findUnique({ where: { id: params.id } })
  if (!deal) return NextResponse.json({ error: 'Not found' }, { status: 404 })
  return NextResponse.json(deal)
}

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const { is_saved } = await req.json()
  const deal = await prisma.deal.update({ where: { id: params.id }, data: { is_saved } })
  return NextResponse.json(deal)
}

'use client'
import { useState } from 'react'
import type { DealResult } from '@/lib/types'
import DealTypeBadge from './DealTypeBadge'

interface Props {
  deal: DealResult
  onSaveToggle?: (id: string, saved: boolean) => void
}

function formatTime(iso: string) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch { return iso.slice(11, 16) || '—' }
}

function formatDate(iso: string) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })
  } catch { return iso.slice(0, 10) || '—' }
}

function savingsPrefix(pct: number) {
  if (pct >= 80) return '🔥 '
  if (pct >= 60) return '⚡ '
  return ''
}

const CONF_COLOUR: Record<string, string> = {
  HIGH:   'text-emerald-400',
  MEDIUM: 'text-amber-400',
  LOW:    'text-zinc-400',
}

export default function DealCard({ deal, onSaveToggle }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [saved, setSaved] = useState(deal.is_saved || false)
  const [saving, setSaving] = useState(false)

  const firstSeg = deal.offer.segments[0]
  const lastSeg  = deal.offer.segments[deal.offer.segments.length - 1]
  const airline  = [...new Set(deal.offer.segments.map(s => s.airline))].join('/')
  const viaSegs  = deal.offer.segments.slice(1, -1).map(s => s.origin)
  const viaStr   = viaSegs.length ? ` via ${viaSegs.join(',')}` : ''

  async function toggleSave() {
    if (!deal.id) return
    setSaving(true)
    try {
      await fetch(`/api/deal/${deal.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_saved: !saved }),
      })
      setSaved(!saved)
      onSaveToggle?.(deal.id, !saved)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="border border-zinc-800 rounded-xl bg-zinc-900 overflow-hidden">
      {/* ── Collapsed row ─────────────────────────────────────────────────── */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full text-left px-5 py-4 hover:bg-zinc-800/60 transition-colors"
      >
        <div className="flex items-center gap-3 flex-wrap">
          <DealTypeBadge type={deal.deal_type} />

          <span className="font-medium text-sm text-zinc-100">
            {firstSeg?.origin} → {lastSeg?.destination}
            {viaStr && <span className="text-zinc-500 text-xs">{viaStr}</span>}
          </span>

          <span className="text-xs text-zinc-400 font-mono">{airline}</span>

          <span className="text-xs text-zinc-400">
            {formatDate(firstSeg?.departure_time)}
          </span>

          <span className="font-mono text-white text-lg ml-auto">
            ${deal.offer.total_price_usd.toFixed(0)}
          </span>

          <span className="text-emerald-400 text-sm font-medium whitespace-nowrap">
            {savingsPrefix(deal.savings_pct)}Save ${deal.savings_usd.toFixed(0)} ({deal.savings_pct.toFixed(0)}%)
          </span>

          <a
            href={deal.booking_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            className="px-3 py-1.5 rounded-lg bg-zinc-700 hover:bg-zinc-600 text-white text-xs font-medium transition-colors"
          >
            Book ↗
          </a>

          <button
            onClick={e => { e.stopPropagation(); toggleSave() }}
            disabled={saving}
            className="text-lg"
            title={saved ? 'Unsave' : 'Save'}
          >
            {saved ? '🔖' : '🤍'}
          </button>

          <span className="text-zinc-500 text-xs">{expanded ? '▲' : '▼'}</span>
        </div>
      </button>

      {/* ── Expanded panel ─────────────────────────────────────────────────── */}
      {expanded && (
        <div className="px-5 pb-5 border-t border-zinc-800 pt-4 space-y-4">
          {/* Segment timeline */}
          <div className="space-y-2">
            {deal.offer.segments.map((seg, i) => (
              <div key={i} className={`flex items-center gap-4 text-sm ${seg.is_throwaway ? 'opacity-40' : ''}`}>
                <span className="font-mono text-zinc-300 w-24">{seg.origin} → {seg.destination}</span>
                <span className="text-zinc-400 text-xs">{seg.airline}{seg.flight_number ? ` ${seg.flight_number}` : ''}</span>
                <span className="text-zinc-400 text-xs">
                  {formatDate(seg.departure_time)} · {formatTime(seg.departure_time)} → {formatTime(seg.arrival_time)}
                </span>
                {seg.is_throwaway && (
                  <span className="text-xs text-amber-500/70 bg-amber-500/10 px-2 py-0.5 rounded">throwaway leg</span>
                )}
              </div>
            ))}
          </div>

          {/* Explanation */}
          <div className="flex gap-2 text-sm text-zinc-300 bg-zinc-800/50 rounded-lg px-3 py-2">
            <span>💡</span>
            <span>{deal.explanation}</span>
          </div>

          {/* Normal vs deal price */}
          <div className="text-xs text-zinc-500">
            Normal {firstSeg?.origin}→{lastSeg?.destination}: <span className="line-through">${deal.normal_fare_usd.toFixed(0)}</span>
            {' · '}This deal: <span className="text-emerald-400">${deal.offer.total_price_usd.toFixed(0)}</span>
          </div>

          {/* Confidence */}
          <div className="text-xs">
            Confidence: <span className={`font-medium ${CONF_COLOUR[deal.confidence]}`}>{deal.confidence}</span>
          </div>

          {/* Caveats */}
          {deal.caveats.length > 0 && (
            <div className="space-y-1">
              {deal.caveats.map((c, i) => (
                <div key={i} className="flex gap-2 text-xs text-amber-400/80">
                  <span>⚠️</span><span>{c}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

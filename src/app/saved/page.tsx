'use client'
import { useEffect, useState } from 'react'
import DealCard from '@/components/DealCard'
import type { DealResult } from '@/lib/types'

export default function SavedPage() {
  const [deals, setDeals] = useState<DealResult[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/search/saved')
      .then(r => r.json())
      .then(d => { setDeals(d.deals || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  function handleUnsave(id: string) {
    setDeals(prev => prev.filter(d => d.id !== id))
  }

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold text-white mb-6">🔖 Saved Deals</h1>
      {loading && <div className="text-zinc-500 text-sm">Loading…</div>}
      {!loading && deals.length === 0 && (
        <div className="text-center py-20 text-zinc-600">
          <div className="text-4xl mb-3">🤍</div>
          <div className="text-sm">No saved deals yet. Click 🤍 on a result to save it.</div>
        </div>
      )}
      <div className="space-y-3">
        {deals.map((d, i) => (
          <DealCard
            key={d.id || i}
            deal={{ ...d, is_saved: true }}
            onSaveToggle={(id, saved) => { if (!saved) handleUnsave(id) }}
          />
        ))}
      </div>
    </div>
  )
}

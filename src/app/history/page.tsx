'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

interface SearchRecord {
  id: string
  raw_query: string
  origin: string
  destination: string
  date_out: string
  deal_count: number
  created_at: string
}

export default function HistoryPage() {
  const [searches, setSearches] = useState<SearchRecord[]>([])
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    fetch('/api/search/history')
      .then(r => r.json())
      .then(d => { setSearches(d.searches || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-white mb-6">🕐 Search History</h1>
      {loading && <div className="text-zinc-500 text-sm">Loading…</div>}
      {!loading && searches.length === 0 && (
        <div className="text-center py-20 text-zinc-600">
          <div className="text-4xl mb-3">🕐</div>
          <div className="text-sm">No searches yet. Run your first search to see history.</div>
        </div>
      )}
      <div className="space-y-2">
        {searches.map(s => (
          <button
            key={s.id}
            onClick={() => router.push(`/?q=${encodeURIComponent(s.raw_query)}`)}
            className="w-full text-left border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 rounded-xl px-5 py-4 transition-colors"
          >
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-medium text-zinc-100">{s.raw_query}</span>
                <div className="text-xs text-zinc-500 mt-0.5">
                  {s.origin} → {s.destination} · {s.date_out}
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm text-emerald-400">{s.deal_count} deals</div>
                <div className="text-xs text-zinc-600">
                  {new Date(s.created_at).toLocaleDateString()}
                </div>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

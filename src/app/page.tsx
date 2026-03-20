'use client'
import { useState } from 'react'
import type { DealResult, SearchResponse, FilterState, DealType } from '@/lib/types'
import DealCard from '@/components/DealCard'
import FilterSidebar from '@/components/FilterSidebar'
import { sortDeals, applyFilters } from '@/lib/ranking'

const EXAMPLES = [
  'JFK to Rome June',
  'LAX to London one-way',
  'NYC to Tokyo direct',
  'Chicago to Paris July 15',
  'SFO to Amsterdam one-way',
]

const DEFAULT_FILTERS: FilterState = {
  deal_types: ['fuel_dump', 'hidden_city', 'throwaway', 'yq_free', 'best_fare'],
  max_price_usd: 5000,
  airlines: [],
  max_stops: 2,
  sort_by: 'savings_pct',
  sort_dir: 'desc',
}

function SkeletonCard() {
  return (
    <div className="border border-zinc-800 rounded-xl bg-zinc-900 px-5 py-4 animate-pulse">
      <div className="flex items-center gap-3">
        <div className="h-5 w-20 bg-zinc-800 rounded" />
        <div className="h-4 w-40 bg-zinc-800 rounded" />
        <div className="ml-auto h-6 w-16 bg-zinc-800 rounded" />
        <div className="h-4 w-24 bg-zinc-800 rounded" />
      </div>
    </div>
  )
}

export default function HomePage() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState<SearchResponse | null>(null)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS)

  async function runSearch(q: string) {
    if (!q.trim()) return
    setLoading(true)
    setError('')
    setResponse(null)
    try {
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q }),
      })
      if (!res.ok) throw new Error(await res.text())
      const data: SearchResponse = await res.json()
      setResponse(data)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  const allDeals = response?.deals || []
  const filtered = sortDeals(
    applyFilters(allDeals, filters),
    filters.sort_by,
    filters.sort_dir
  )

  return (
    <div className="max-w-5xl">
      <h1 className="text-2xl font-bold text-white mb-1">Cheap Flight Finder</h1>
      <p className="text-sm text-zinc-500 mb-6">
        Detects fuel dump, hidden city, throwaway & YQ-free pricing loopholes.
      </p>

      {/* Search form */}
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && runSearch(query)}
          placeholder="e.g. JFK to Rome June one-way"
          className="flex-1 bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-zinc-500 text-sm"
        />
        <button
          onClick={() => runSearch(query)}
          disabled={loading || !query.trim()}
          className="px-6 py-3 bg-white text-zinc-900 rounded-xl font-medium text-sm hover:bg-zinc-100 disabled:opacity-40 transition-colors"
        >
          {loading ? 'Searching…' : 'Search'}
        </button>
      </div>

      {/* Example chips */}
      <div className="flex flex-wrap gap-2 mb-8">
        {EXAMPLES.map(ex => (
          <button
            key={ex}
            onClick={() => { setQuery(ex); runSearch(ex) }}
            className="px-3 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-full text-xs transition-colors"
          >
            {ex}
          </button>
        ))}
      </div>

      {/* Parsed spec pill */}
      {response?.spec && (
        <div className="mb-5 text-xs text-zinc-400 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 inline-block">
          <span className="font-mono">{response.spec.origin} → {response.spec.destination}</span>
          {' · '}{response.spec.date_out}
          {' · '}{response.spec.deal_types.map(t => t.replace('_', ' ')).join(', ')}
        </div>
      )}

      {error && (
        <div className="mb-4 text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {/* Results */}
      {(loading || allDeals.length > 0) && (
        <div className="flex gap-6">
          <FilterSidebar
            filters={filters}
            onChange={setFilters}
            totalDeals={allDeals.length}
            visibleDeals={filtered.length}
          />

          <div className="flex-1 space-y-3">
            {/* Meta */}
            {response && !loading && (
              <div className="text-xs text-zinc-500 mb-4 flex items-center gap-2 flex-wrap">
                {response.meta.deals_found} deals found
                {' · '}{response.meta.total_fetched} offers scanned
                {' · '}{(response.meta.duration_ms / 1000).toFixed(1)}s
                {/* LIVE vs DEMO badge */}
                {response.meta.sources_checked.includes('demo') && !response.meta.sources_checked.some(s => s !== 'demo') ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-500/15 text-amber-400 font-medium">
                    ⚠ DEMO — flights are fictional
                  </span>
                ) : response.meta.sources_checked.some(s => s !== 'demo') ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 font-medium">
                    ● LIVE
                  </span>
                ) : null}
                {response.meta.source_errors.length > 0 && (
                  <span className="text-amber-500/70"> · {response.meta.source_errors.join(', ')}</span>
                )}
              </div>
            )}

            {/* Skeletons */}
            {loading && Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)}

            {/* Deal cards */}
            {!loading && filtered.map((deal, i) => (
              <DealCard key={deal.id || i} deal={deal} />
            ))}

            {!loading && response && filtered.length === 0 && (
              <div className="text-center py-16 text-zinc-500">
                <div className="text-4xl mb-3">🔍</div>
                <div>No deals found for this route.</div>
                <div className="text-xs mt-2">
                  {!response.meta.sources_checked.length
                    ? 'Add API keys in Settings to enable live search.'
                    : 'Try a different route or date.'}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && !response && !error && (
        <div className="text-center py-20 text-zinc-600">
          <div className="text-5xl mb-4">✈️</div>
          <div className="text-sm">Enter a route above to start finding deals</div>
          <div className="text-xs mt-2 max-w-sm mx-auto leading-relaxed">
            Add your Kiwi and SerpApi keys in Settings to enable live results. Free tiers available — no credit card needed.
          </div>
        </div>
      )}
    </div>
  )
}

'use client'
import type { FilterState, DealType } from '@/lib/types'

const DEAL_TYPES: { value: DealType; label: string }[] = [
  { value: 'fuel_dump',   label: '🔶 Fuel Dump' },
  { value: 'hidden_city', label: '🔵 Hidden City' },
  { value: 'throwaway',   label: '🟣 Throwaway' },
  { value: 'yq_free',     label: '🟢 YQ-Free' },
  { value: 'best_fare',   label: '🔷 Best Fare' },
]

interface Props {
  filters: FilterState
  onChange: (f: FilterState) => void
  totalDeals: number
  visibleDeals: number
}

export default function FilterSidebar({ filters, onChange, totalDeals, visibleDeals }: Props) {
  function toggleDealType(t: DealType) {
    const next = filters.deal_types.includes(t)
      ? filters.deal_types.filter(x => x !== t)
      : [...filters.deal_types, t]
    onChange({ ...filters, deal_types: next })
  }

  return (
    <aside className="w-52 shrink-0 space-y-6">
      <div className="text-xs text-zinc-500">
        {visibleDeals} of {totalDeals} deals
      </div>

      {/* Deal type */}
      <div>
        <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-2">Deal Type</div>
        <div className="space-y-1.5">
          {DEAL_TYPES.map(({ value, label }) => (
            <label key={value} className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={filters.deal_types.includes(value)}
                onChange={() => toggleDealType(value)}
                className="accent-zinc-400"
              />
              <span className="text-zinc-300">{label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Max stops */}
      <div>
        <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-2">Max Stops</div>
        <div className="space-y-1.5">
          {([0, 1, 2] as const).map(n => (
            <label key={n} className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="radio"
                name="max_stops"
                checked={filters.max_stops === n}
                onChange={() => onChange({ ...filters, max_stops: n })}
                className="accent-zinc-400"
              />
              <span className="text-zinc-300">{n === 0 ? 'Direct only' : n === 1 ? '1 stop' : 'Any'}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Max price */}
      <div>
        <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-2">
          Max Price: <span className="text-zinc-200">${filters.max_price_usd}</span>
        </div>
        <input
          type="range"
          min={50}
          max={5000}
          step={50}
          value={filters.max_price_usd}
          onChange={e => onChange({ ...filters, max_price_usd: Number(e.target.value) })}
          className="w-full accent-zinc-400"
        />
      </div>

      {/* Sort */}
      <div>
        <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-2">Sort By</div>
        <select
          value={filters.sort_by}
          onChange={e => onChange({ ...filters, sort_by: e.target.value as FilterState['sort_by'] })}
          className="w-full bg-zinc-800 text-zinc-200 text-sm rounded-lg px-2 py-1.5 border border-zinc-700"
        >
          <option value="savings_pct">Savings %</option>
          <option value="price">Price</option>
          <option value="departure_time">Departure</option>
        </select>
      </div>
    </aside>
  )
}

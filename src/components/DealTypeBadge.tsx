import type { DealType } from '@/lib/types'

const COLOURS: Record<DealType, string> = {
  fuel_dump:   'bg-amber-500/20 text-amber-300 border border-amber-500/30',
  hidden_city: 'bg-blue-500/20  text-blue-300  border border-blue-500/30',
  throwaway:   'bg-purple-500/20 text-purple-300 border border-purple-500/30',
  yq_free:     'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30',
  best_fare:   'bg-sky-500/20 text-sky-300 border border-sky-500/30',
}

const LABELS: Record<DealType, string> = {
  fuel_dump:   'Fuel Dump',
  hidden_city: 'Hidden City',
  throwaway:   'Throwaway',
  yq_free:     'YQ-Free',
  best_fare:   'Best Fare',
}

export default function DealTypeBadge({ type }: { type: DealType }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${COLOURS[type]}`}>
      {LABELS[type]}
    </span>
  )
}

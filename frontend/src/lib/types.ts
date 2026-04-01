// Types matching backend Pydantic schemas

export interface MultiCitySegment {
  from: string;
  to: string;
  carrier: string | null;
  via: string | null;
  notes: string | null;
}

export interface DumpSegment {
  from: string;
  to: string;
  carrier: string | null;
  notes: string | null;
}

export interface StrikeSegment {
  origin: string;
  destination: string;
  carrier: string;
  note?: string | null;
}

export interface ManualInputBundle {
  routing_code_string: string;
  human_description: string;
  ita_matrix_steps: string[];
  expected_yq_savings_usd: number;
  expected_yq_carrier: string;
  validation_timestamp: string;
  confidence_score: number;
  backup_routing_code: string | null;
  notes: string | null;
  // Scan engine fields — present when no validated bundle exists yet.
  // When these are set, ManualInputBundle renders the staged query view.
  multi_city_segments?: MultiCitySegment[] | null;
  dump_segment?: DumpSegment | null;
  baseline_routing?: string | null;
  optimized_routing?: string | null;
  is_scan_engine_bundle?: boolean;
  // Tier 1 fields — ITA Matrix URL generation & fare class guidance
  origin_iata?: string;
  destination_iata?: string;
  fare_basis_hint?: string | null;
  // Strike segment — throwaway leg appended to zero YQ
  strike_segment?: StrikeSegment | null;
}

export interface DumpPatternSummary {
  id: string;
  dump_type: string;
  lifecycle_state: string;
  origin_iata: string;
  destination_iata: string;
  ticketing_carrier_iata: string;
  operating_carriers: string[];
  routing_points: string[];
  expected_yq_savings_usd: number | null;
  // Price delta from scanner — null until first scan run
  baseline_price_usd: number | null;
  optimized_price_usd: number | null;
  confidence_score: number;
  freshness_tier: number;
  source: string;
  source_url: string | null;
  last_scan_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DumpPatternResponse extends DumpPatternSummary {
  fare_basis_hint: string | null;
  ita_routing_code: string | null;  // nullable — new patterns use baseline/optimized_routing
  manual_input_bundle: ManualInputBundle | null;
  // Scan engine fields
  baseline_routing: string | null;
  optimized_routing: string | null;
  multi_city_segments: MultiCitySegment[] | null;
  dump_segment: DumpSegment | null;
  strike_segment: StrikeSegment | null;
  source_post_weight: number;
  backup_pattern_id: string | null;
}

export interface CarrierResponse {
  iata_code: string;
  name: string;
  alliance: string;
  charges_yq: boolean | null;
  typical_yq_usd: number | null;
  last_yq_updated: string | null;
  yq_scrape_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface ValidationRunResponse {
  id: string;
  pattern_id: string;
  ran_at: string;
  success: boolean;
  yq_charged_usd: number | null;
  yq_expected_usd: number | null;
  base_fare_usd: number | null;
  raw_ita_response: Record<string, unknown> | null;
  manual_input_snapshot: Record<string, unknown> | null;
  error_message: string | null;
  proxy_used: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface PatternFilters {
  origin?: string;
  destination?: string;
  dump_type?: string;
  carrier?: string;
  min_confidence?: number;
  min_savings_usd?: number;
  page?: number;
  page_size?: number;
}

export interface ScanTargetResponse {
  id: string;
  origin_iata: string;
  destination_iata: string;
  carrier_iata: string | null;
  tier: number;
  last_scanned_at: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface DumpCandidateResponse {
  id: string;
  from_iata: string;
  to_iata: string;
  carrier_iata: string | null;
  notes: string | null;
  success_count: number;
  test_count: number;
  success_rate: number | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ScanTargetFilters {
  tier?: number;
  enabled?: boolean;
  page?: number;
  page_size?: number;
}

export interface DumpCandidateFilters {
  enabled?: boolean;
  page?: number;
  page_size?: number;
}

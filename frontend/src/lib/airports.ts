/**
 * airports.ts — Airport opportunity scoring for the /airports page.
 *
 * Pure functions only — no React, no side effects. All inputs come from
 * the patterns and carriers API responses.
 *
 * Scoring formula (0–100 composite):
 *   opportunityScore =
 *     yqCoverageScore  * 0.40   (which high-YQ carriers serve this origin?)
 *   + patternDensity   * 0.30   (known working pattern count)
 *   + maxSavingsScore  * 0.20   (ceiling of available savings)
 *   + anchorBonus      * 0.10   (QR/EK/NH enables carrier-switch dumps)
 */

import type { DumpPatternSummary, CarrierResponse } from "./types";

// ─── Static data ─────────────────────────────────────────────────────────────

export type CarrierRole = "hub" | "focus" | "partner" | "codeshare";

export interface AirportCarrierEntry {
  carrier: string;
  role: CarrierRole;
}

/** Which carriers meaningfully serve each airport. */
export const AIRPORT_CARRIER_MAP: Record<string, AirportCarrierEntry[]> = {
  // North America — prime origins
  YVR: [
    { carrier: "AC", role: "hub" },
    { carrier: "LH", role: "partner" },
    { carrier: "BA", role: "partner" },
    { carrier: "QR", role: "partner" },
  ],
  SEA: [
    { carrier: "AS", role: "hub" },
    { carrier: "BA", role: "partner" },
    { carrier: "QR", role: "partner" },
    { carrier: "LH", role: "partner" },
  ],
  YYZ: [
    { carrier: "AC", role: "hub" },
    { carrier: "LH", role: "partner" },
    { carrier: "BA", role: "partner" },
    { carrier: "QR", role: "partner" },
  ],
  JFK: [
    { carrier: "BA", role: "focus" },
    { carrier: "AA", role: "hub" },
    { carrier: "QR", role: "partner" },
    { carrier: "LH", role: "focus" },
    { carrier: "AF", role: "focus" },
  ],
  LAX: [
    { carrier: "BA", role: "focus" },
    { carrier: "QR", role: "partner" },
    { carrier: "CX", role: "focus" },
    { carrier: "LH", role: "focus" },
  ],
  // UK / Europe — high-YQ hubs (great dump origins)
  LHR: [
    { carrier: "BA", role: "hub" },
    { carrier: "VS", role: "focus" },
    { carrier: "QR", role: "partner" },
    { carrier: "EK", role: "partner" },
  ],
  FRA: [
    { carrier: "LH", role: "hub" },
    { carrier: "LX", role: "codeshare" },
  ],
  CDG: [
    { carrier: "AF", role: "hub" },
    { carrier: "KL", role: "codeshare" },
  ],
  AMS: [
    { carrier: "KL", role: "hub" },
    { carrier: "AF", role: "codeshare" },
  ],
  ZRH: [{ carrier: "LX", role: "hub" }],
  VIE: [{ carrier: "OS", role: "hub" }],
  MAD: [
    { carrier: "IB", role: "hub" },
    { carrier: "BA", role: "partner" },
  ],
  BCN: [
    { carrier: "VY", role: "focus" },
    { carrier: "BA", role: "partner" },
    { carrier: "IB", role: "focus" },
  ],
  // Asia / Pacific
  ICN: [
    { carrier: "KE", role: "hub" },
    { carrier: "OZ", role: "focus" },
  ],
  NRT: [
    { carrier: "NH", role: "hub" },
    { carrier: "JL", role: "focus" },
  ],
  HND: [
    { carrier: "NH", role: "focus" },
    { carrier: "JL", role: "focus" },
  ],
  TPE: [
    { carrier: "BR", role: "hub" },
    { carrier: "CI", role: "hub" },
  ],
  MNL: [
    { carrier: "PR", role: "hub" },
    { carrier: "CX", role: "partner" },
  ],
  BKK: [
    { carrier: "TG", role: "hub" },
    { carrier: "QR", role: "partner" },
    { carrier: "EK", role: "partner" },
  ],
  SIN: [
    { carrier: "SQ", role: "hub" },
    { carrier: "QR", role: "partner" },
    { carrier: "EK", role: "partner" },
  ],
  HKG: [
    { carrier: "CX", role: "hub" },
    { carrier: "QR", role: "partner" },
    { carrier: "EK", role: "partner" },
  ],
  // Middle East — dump anchor hubs
  DOH: [{ carrier: "QR", role: "hub" }],
  DXB: [{ carrier: "EK", role: "hub" }],
  AUH: [{ carrier: "EY", role: "hub" }],
};

/** City/region display names for airports. */
export const AIRPORT_NAMES: Record<string, { city: string; region: string }> = {
  YVR: { city: "Vancouver", region: "North America" },
  SEA: { city: "Seattle", region: "North America" },
  YYZ: { city: "Toronto", region: "North America" },
  JFK: { city: "New York", region: "North America" },
  LAX: { city: "Los Angeles", region: "North America" },
  LHR: { city: "London", region: "Europe" },
  FRA: { city: "Frankfurt", region: "Europe" },
  CDG: { city: "Paris", region: "Europe" },
  AMS: { city: "Amsterdam", region: "Europe" },
  ZRH: { city: "Zurich", region: "Europe" },
  VIE: { city: "Vienna", region: "Europe" },
  MAD: { city: "Madrid", region: "Europe" },
  BCN: { city: "Barcelona", region: "Europe" },
  ICN: { city: "Seoul", region: "Asia" },
  NRT: { city: "Tokyo Narita", region: "Asia" },
  HND: { city: "Tokyo Haneda", region: "Asia" },
  TPE: { city: "Taipei", region: "Asia" },
  MNL: { city: "Manila", region: "Asia" },
  BKK: { city: "Bangkok", region: "Asia" },
  SIN: { city: "Singapore", region: "Asia" },
  HKG: { city: "Hong Kong", region: "Asia" },
  DOH: { city: "Doha", region: "Middle East" },
  DXB: { city: "Dubai", region: "Middle East" },
  AUH: { city: "Abu Dhabi", region: "Middle East" },
};

/** High-YQ carriers with their tier and typical YQ (fallback if carrier API is unavailable). */
export const HIGH_YQ_CARRIERS: Record<string, { tier: 1 | 2 | 3; typicalYqUsd: number }> = {
  LH: { tier: 1, typicalYqUsd: 580 },
  BA: { tier: 1, typicalYqUsd: 550 },
  LX: { tier: 2, typicalYqUsd: 450 },
  OS: { tier: 2, typicalYqUsd: 430 },
  AF: { tier: 2, typicalYqUsd: 400 },
  KL: { tier: 2, typicalYqUsd: 380 },
  CX: { tier: 2, typicalYqUsd: 350 },
  TG: { tier: 3, typicalYqUsd: 200 },
  SQ: { tier: 3, typicalYqUsd: 180 },
  KE: { tier: 3, typicalYqUsd: 170 },
  NH: { tier: 3, typicalYqUsd: 150 },
};

/** No-YQ carriers that enable carrier-switch dumps (anchors). */
export const DUMP_ANCHORS = new Set(["QR", "EK", "EY", "TK", "AC", "AS", "UA", "DL"]);

// ─── Computed view-model ──────────────────────────────────────────────────────

export interface YqCarrierInfo {
  carrier: string;
  role: CarrierRole;
  typicalYqUsd: number;
  tier: 1 | 2 | 3;
}

export interface AnchorCarrierInfo {
  carrier: string;
  role: CarrierRole;
}

export interface AirportOpportunity {
  iata: string;
  city: string;
  region: string;
  yqCarriers: YqCarrierInfo[];       // High-YQ carriers serving this airport
  anchors: AnchorCarrierInfo[];      // No-YQ dump-anchor carriers
  patternCount: number;
  maxSavingsUsd: number;
  avgConfidence: number;
  opportunityScore: number;          // 0–100
  strategy: string;
  samplePatterns: DumpPatternSummary[];  // Top patterns by savings (max 3)
}

// ─── Scoring ──────────────────────────────────────────────────────────────────

const ROLE_WEIGHT: Record<CarrierRole, number> = {
  hub: 1.0,
  focus: 0.8,
  partner: 0.6,
  codeshare: 0.4,
};

const TIER_BASE: Record<1 | 2 | 3, number> = { 1: 35, 2: 20, 3: 10 };

function yqCoverageScore(entries: AirportCarrierEntry[], liveCarriers: Map<string, CarrierResponse>): number {
  let score = 0;
  for (const entry of entries) {
    const live = liveCarriers.get(entry.carrier);
    const isHighYq =
      (live && live.charges_yq === true) ||
      (!live && entry.carrier in HIGH_YQ_CARRIERS);

    if (!isHighYq) continue;

    const tier = HIGH_YQ_CARRIERS[entry.carrier]?.tier ?? 3;
    const base = TIER_BASE[tier];
    score += base * ROLE_WEIGHT[entry.role];
  }
  return Math.min(score, 100);
}

function patternDensityScore(count: number): number {
  if (count === 0) return 0;
  return Math.min((Math.log2(count + 1) / Math.log2(21)) * 100, 100);
}

function maxSavingsScore(maxSavings: number): number {
  return Math.min((maxSavings / 600) * 100, 100);
}

function anchorScore(entries: AirportCarrierEntry[]): number {
  return entries.some((e) => DUMP_ANCHORS.has(e.carrier)) ? 100 : 0;
}

// ─── Strategy text ────────────────────────────────────────────────────────────

function getStrategy(
  iata: string,
  yqCarriers: YqCarrierInfo[],
  anchors: AnchorCarrierInfo[]
): string {
  const topYq = yqCarriers.sort((a, b) => b.typicalYqUsd - a.typicalYqUsd)[0];
  const topAnchor = anchors[0];

  if (!topYq && !topAnchor) {
    return "Limited dump potential — monitor for new patterns";
  }

  if (topYq?.tier === 1 && topYq.role === "hub") {
    // Prime case: carrier is a hub carrier here (e.g., LH at FRA, BA at LHR)
    const hub = iata;
    const carrier = topYq.carrier;
    const savings = topYq.typicalYqUsd;
    return `Prime TP dump hub — ${carrier} based here, ~$${savings} YQ avoidable via multi-city + intra-${hub === "LHR" || hub === "MAD" || hub === "BCN" ? "European" : "regional"} dump leg`;
  }

  if (topYq && topAnchor) {
    // Both high-YQ and anchor available — carrier switch opportunity
    return `Carrier-switch opportunity — book ${topYq.carrier} sectors on ${topAnchor.carrier} metal to drop ~$${topYq.typicalYqUsd} YQ`;
  }

  if (topYq && topYq.tier === 1) {
    return `Tier 1 target — ${topYq.carrier} serves this route with ~$${topYq.typicalYqUsd} YQ; use multi-city + short dump leg`;
  }

  if (topYq) {
    return `${topYq.carrier} YQ target (~$${topYq.typicalYqUsd}) — use multi-city construction with regional dump segment`;
  }

  if (topAnchor) {
    return `${topAnchor.carrier} anchor available — useful for carrier-switch dumps on connecting high-YQ metal`;
  }

  return "Monitor for emerging patterns on this route";
}

// ─── Main export ──────────────────────────────────────────────────────────────

/**
 * Compute an AirportOpportunity record for every airport in AIRPORT_CARRIER_MAP,
 * enriched with live pattern counts and carrier YQ data.
 */
export function computeAirportOpportunities(
  patterns: DumpPatternSummary[],
  carriers: CarrierResponse[]
): AirportOpportunity[] {
  // Index carriers by IATA for O(1) lookup
  const liveCarriers = new Map<string, CarrierResponse>(
    carriers.map((c) => [c.iata_code, c])
  );

  // Aggregate pattern stats by origin_iata
  const patternStats = new Map<string, { count: number; maxSavings: number; totalConf: number }>();
  const patternsByOrigin = new Map<string, DumpPatternSummary[]>();
  for (const p of patterns) {
    const existing = patternStats.get(p.origin_iata) ?? { count: 0, maxSavings: 0, totalConf: 0 };
    patternStats.set(p.origin_iata, {
      count: existing.count + 1,
      maxSavings: Math.max(existing.maxSavings, p.expected_yq_savings_usd ?? 0),
      totalConf: existing.totalConf + p.confidence_score,
    });
    const list = patternsByOrigin.get(p.origin_iata) ?? [];
    list.push(p);
    patternsByOrigin.set(p.origin_iata, list);
  }

  return Object.entries(AIRPORT_CARRIER_MAP).map(([iata, entries]) => {
    const meta = AIRPORT_NAMES[iata] ?? { city: iata, region: "Unknown" };
    const stats = patternStats.get(iata) ?? { count: 0, maxSavings: 0, totalConf: 0 };
    const avgConfidence = stats.count > 0 ? stats.totalConf / stats.count : 0;

    // Split carriers into high-YQ and anchor categories
    const yqCarriers: YqCarrierInfo[] = [];
    const anchors: AnchorCarrierInfo[] = [];

    for (const entry of entries) {
      const live = liveCarriers.get(entry.carrier);
      const isHighYq =
        (live?.charges_yq === true) ||
        (!live && entry.carrier in HIGH_YQ_CARRIERS);
      const isAnchor = DUMP_ANCHORS.has(entry.carrier);

      if (isHighYq) {
        const fallback = HIGH_YQ_CARRIERS[entry.carrier];
        const typicalYqUsd =
          live?.typical_yq_usd ?? fallback?.typicalYqUsd ?? 0;
        const tier = fallback?.tier ?? 3;
        yqCarriers.push({ carrier: entry.carrier, role: entry.role, typicalYqUsd, tier });
      } else if (isAnchor) {
        anchors.push({ carrier: entry.carrier, role: entry.role });
      }
    }

    // Compute component scores
    const yCoverage = yqCoverageScore(entries, liveCarriers);
    const pDensity = patternDensityScore(stats.count);
    const mSavings = maxSavingsScore(stats.maxSavings);
    const aBonus = anchorScore(entries);

    const opportunityScore = Math.round(
      yCoverage * 0.40 +
      pDensity  * 0.30 +
      mSavings  * 0.20 +
      aBonus    * 0.10
    );

    // Top 3 patterns by savings for the expanded detail view
    const samplePatterns = (patternsByOrigin.get(iata) ?? [])
      .sort((a, b) => (b.expected_yq_savings_usd ?? 0) - (a.expected_yq_savings_usd ?? 0))
      .slice(0, 3);

    return {
      iata,
      city: meta.city,
      region: meta.region,
      yqCarriers: yqCarriers.sort((a, b) => b.typicalYqUsd - a.typicalYqUsd),
      anchors,
      patternCount: stats.count,
      maxSavingsUsd: stats.maxSavings,
      avgConfidence,
      opportunityScore,
      strategy: getStrategy(iata, [...yqCarriers], [...anchors]),
      samplePatterns,
    };
  }).sort((a, b) => b.opportunityScore - a.opportunityScore);
}

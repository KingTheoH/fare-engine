"use client";

import { useState, useMemo, useEffect } from "react";
import { getPatterns, getCarriers } from "@/lib/api";
import { MOCK_PATTERNS, MOCK_CARRIERS } from "@/lib/mock-data";
import {
  computeAirportOpportunities,
  type AirportOpportunity,
  type CarrierRole,
} from "@/lib/airports";
import type { DumpPatternSummary, CarrierResponse } from "@/lib/types";

// ─── Badge helpers ────────────────────────────────────────────────────────────

const TIER_COLORS: Record<1 | 2 | 3, string> = {
  1: "bg-[#fce8e6] text-[#c5221f] border border-[#f5c6c2]",
  2: "bg-[#fef7e0] text-[#e37400] border border-[#fad56c]",
  3: "bg-[#f1f3f4] text-[#5f6368] border border-[#dadce0]",
};

const ROLE_OPACITY: Record<CarrierRole, string> = {
  hub: "opacity-100",
  focus: "opacity-90",
  partner: "opacity-70",
  codeshare: "opacity-50",
};

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 70
      ? "bg-[#e6f4ea] text-[#0d904f] border border-[#b7dfbf]"
      : score >= 45
      ? "bg-[#fef7e0] text-[#e37400] border border-[#fad56c]"
      : "bg-[#f1f3f4] text-[#5f6368] border border-[#dadce0]";
  return (
    <span
      className={`inline-flex items-center justify-center w-10 h-10 rounded-full text-[15px] font-bold tabular-nums ${color}`}
    >
      {score}
    </span>
  );
}

function RankBadge({ rank }: { rank: number }) {
  if (rank === 1) return <span className="text-[16px]" title="Top airport">🥇</span>;
  if (rank === 2) return <span className="text-[16px]" title="Second">🥈</span>;
  if (rank === 3) return <span className="text-[16px]" title="Third">🥉</span>;
  return (
    <span className="text-[13px] font-medium text-[#80868b] tabular-nums w-5 text-center">
      {rank}
    </span>
  );
}

// ─── Region filter values ─────────────────────────────────────────────────────

const ALL_REGIONS = ["All", "North America", "Europe", "Asia", "Middle East"];

// ─── Main page ────────────────────────────────────────────────────────────────

export default function AirportsPage() {
  const [patterns, setPatterns] = useState<DumpPatternSummary[]>([]);
  const [carriers, setCarriers] = useState<CarrierResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [usingMock, setUsingMock] = useState(false);
  const [regionFilter, setRegionFilter] = useState("All");
  const [minScore, setMinScore] = useState(0);
  const [expandedIata, setExpandedIata] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      getPatterns({ page_size: 100 }).then((r) => r.items),
      getCarriers({ page_size: 100 }).then((r) => r.items),
    ])
      .then(([p, c]) => {
        setPatterns(p.length > 0 ? p : MOCK_PATTERNS);
        setCarriers(c.length > 0 ? c : MOCK_CARRIERS);
        if (p.length === 0) setUsingMock(true);
      })
      .catch(() => {
        setPatterns(MOCK_PATTERNS);
        setCarriers(MOCK_CARRIERS);
        setUsingMock(true);
      })
      .finally(() => setLoading(false));
  }, []);

  const opportunities = useMemo(
    () => computeAirportOpportunities(patterns, carriers),
    [patterns, carriers]
  );

  const filtered = useMemo(() => {
    return opportunities.filter(
      (a) =>
        (regionFilter === "All" || a.region === regionFilter) &&
        a.opportunityScore >= minScore
    );
  }, [opportunities, regionFilter, minScore]);

  // ─── Loading / error states ─────────────────────────────────────────

  if (loading) {
    return (
      <div className="animate-fade-in flex items-center justify-center py-20">
        <span className="text-[14px] text-[#5f6368]">
          Scoring airports…
        </span>
      </div>
    );
  }

  const topScore = filtered[0]?.opportunityScore ?? 0;

  return (
    <div className="animate-fade-in">
      {/* ── Header ── */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-[22px] font-normal text-[#202124]">
            Origin Airport Opportunities
          </h1>
          <p className="text-[13px] text-[#5f6368] mt-1">
            Airports ranked by fuel-dump potential — combines YQ carrier
            presence, working pattern density, and available savings.
          </p>
        </div>
        <div className="text-right">
          <p className="text-[12px] text-[#80868b]">
            {filtered.length} airports
            {regionFilter !== "All" ? ` in ${regionFilter}` : ""}
          </p>
        </div>
      </div>

      {/* ── Mock banner ── */}
      {usingMock && (
        <div className="mb-4 px-3 py-2 bg-[#fef7e0] border border-[#fad56c] rounded-lg text-[12px] text-[#e37400]">
          ⚠ Backend not reachable — showing mock patterns. Scores reflect
          carrier-presence heuristics only, not live validation data.
        </div>
      )}

      {/* ── Filters ── */}
      <div className="flex flex-wrap items-center gap-4 mb-5 p-3 bg-[#f8f9fa] border border-[#e8eaed] rounded-lg">
        {/* Region tabs */}
        <div className="flex gap-1">
          {ALL_REGIONS.map((r) => (
            <button
              key={r}
              onClick={() => setRegionFilter(r)}
              className={`px-3 py-1.5 text-[12px] font-medium rounded-full transition-colors ${
                regionFilter === r
                  ? "bg-[#1a73e8] text-white"
                  : "bg-white border border-[#dadce0] text-[#5f6368] hover:border-[#1a73e8] hover:text-[#1a73e8]"
              }`}
            >
              {r}
            </button>
          ))}
        </div>

        {/* Min score slider */}
        <label className="flex items-center gap-2 ml-auto">
          <span className="text-[12px] text-[#5f6368]">Min score</span>
          <input
            type="range"
            min={0}
            max={90}
            step={5}
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="w-24 accent-[#1a73e8]"
          />
          <span className="text-[12px] font-medium text-[#202124] tabular-nums w-5">
            {minScore}
          </span>
        </label>
      </div>

      {/* ── Table ── */}
      <div className="border border-[#dadce0] rounded-lg overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-[#f8f9fa] border-b border-[#dadce0]">
              <th className="text-left px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider w-10">
                #
              </th>
              <th className="text-left px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">
                Score
              </th>
              <th className="text-left px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">
                Airport
              </th>
              <th className="text-left px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">
                High-YQ Carriers
              </th>
              <th className="text-left px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">
                Dump Anchors
              </th>
              <th className="text-right px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">
                Patterns
              </th>
              <th className="text-right px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">
                Max Savings
              </th>
              <th className="text-left px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">
                Strategy
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#e8eaed]">
            {filtered.length === 0 ? (
              <tr>
                <td
                  colSpan={8}
                  className="px-4 py-12 text-center text-[14px] text-[#5f6368]"
                >
                  No airports match the current filters.
                </td>
              </tr>
            ) : (
              filtered.map((airport, idx) => (
                <AirportRow
                  key={airport.iata}
                  airport={airport}
                  rank={idx + 1}
                  topScore={topScore}
                  expanded={expandedIata === airport.iata}
                  onToggle={() =>
                    setExpandedIata(
                      expandedIata === airport.iata ? null : airport.iata
                    )
                  }
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* ── Legend ── */}
      <div className="mt-4 flex flex-wrap gap-4 text-[11px] text-[#80868b]">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm bg-[#fce8e6] border border-[#f5c6c2]" />
          Tier 1 YQ carrier (LH/BA, ~$550+)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm bg-[#fef7e0] border border-[#fad56c]" />
          Tier 2 YQ carrier ($200–500)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm bg-[#f1f3f4] border border-[#dadce0]" />
          Tier 3 YQ carrier (under $200)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm bg-[#e8f0fe] border border-[#c5d9f7]" />
          Dump anchor (no-YQ carrier)
        </span>
        <span className="ml-auto">
          Faded badges = partner/codeshare presence (lower frequency)
        </span>
      </div>
    </div>
  );
}

// ─── Row component ─────────────────────────────────────────────────────────────

interface AirportRowProps {
  airport: AirportOpportunity;
  rank: number;
  topScore: number;
  expanded: boolean;
  onToggle: () => void;
}

function AirportRow({ airport, rank, topScore, expanded, onToggle }: AirportRowProps) {
  const hasPatterns = airport.patternCount > 0;
  const scoreBarWidth = topScore > 0 ? (airport.opportunityScore / topScore) * 100 : 0;

  return (
    <>
      <tr
        className="hover:bg-[#f8f9fa] transition-colors cursor-pointer"
        onClick={onToggle}
      >
        {/* Rank */}
        <td className="px-4 py-3">
          <div className="flex items-center justify-center">
            <RankBadge rank={rank} />
          </div>
        </td>

        {/* Score */}
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            <ScoreBadge score={airport.opportunityScore} />
            <div className="w-16 h-1.5 bg-[#e8eaed] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-[#1a73e8]"
                style={{ width: `${scoreBarWidth}%` }}
              />
            </div>
          </div>
        </td>

        {/* Airport */}
        <td className="px-4 py-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[15px] font-semibold font-mono text-[#202124]">
                {airport.iata}
              </span>
              <span className="text-[13px] text-[#5f6368]">
                {airport.city}
              </span>
            </div>
            <span className="text-[11px] text-[#80868b]">{airport.region}</span>
          </div>
        </td>

        {/* High-YQ carriers */}
        <td className="px-4 py-3">
          <div className="flex flex-wrap gap-1">
            {airport.yqCarriers.length === 0 ? (
              <span className="text-[12px] text-[#80868b]">—</span>
            ) : (
              airport.yqCarriers.map((c) => (
                <span
                  key={c.carrier}
                  title={`${c.carrier} · Tier ${c.tier} · ~$${c.typicalYqUsd} YQ · ${c.role}`}
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium tabular-nums ${
                    TIER_COLORS[c.tier]
                  } ${ROLE_OPACITY[c.role]}`}
                >
                  {c.carrier}
                  <span className="font-normal opacity-70">
                    ${c.typicalYqUsd}
                  </span>
                </span>
              ))
            )}
          </div>
        </td>

        {/* Dump anchors */}
        <td className="px-4 py-3">
          <div className="flex flex-wrap gap-1">
            {airport.anchors.length === 0 ? (
              <span className="text-[12px] text-[#80868b]">—</span>
            ) : (
              airport.anchors.map((a) => (
                <span
                  key={a.carrier}
                  title={`${a.carrier} · No-YQ anchor · ${a.role}`}
                  className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-[#e8f0fe] text-[#1a73e8] border border-[#c5d9f7] ${ROLE_OPACITY[a.role]}`}
                >
                  {a.carrier}
                </span>
              ))
            )}
          </div>
        </td>

        {/* Pattern count */}
        <td className="px-4 py-3 text-right">
          {hasPatterns ? (
            <span className="text-[14px] font-semibold text-[#202124] tabular-nums">
              {airport.patternCount}
            </span>
          ) : (
            <span className="text-[13px] text-[#80868b]">0</span>
          )}
        </td>

        {/* Max savings */}
        <td className="px-4 py-3 text-right">
          {airport.maxSavingsUsd > 0 ? (
            <span className="text-[14px] font-semibold text-[#0d904f] tabular-nums">
              ${airport.maxSavingsUsd.toFixed(0)}
            </span>
          ) : (
            <span className="text-[13px] text-[#80868b]">—</span>
          )}
        </td>

        {/* Strategy */}
        <td className="px-4 py-3 max-w-[300px]">
          <p className="text-[12px] text-[#5f6368] leading-snug line-clamp-2">
            {airport.strategy}
          </p>
          <span className="text-[10px] text-[#1a73e8] mt-0.5 inline-block">
            {expanded ? "▲ less" : "▼ details"}
          </span>
        </td>
      </tr>

      {/* ── Expanded detail row ── */}
      {expanded && (
        <tr className="bg-[#f8f9fa]">
          <td colSpan={8} className="px-6 py-4">
            <ExpandedDetail airport={airport} />
          </td>
        </tr>
      )}
    </>
  );
}

// ─── Expanded detail ──────────────────────────────────────────────────────────

const DUMP_TYPE_LABELS: Record<string, string> = {
  TP_DUMP: "TP",
  CARRIER_SWITCH: "CS",
  FARE_BASIS: "FB",
  ALLIANCE_RULE: "AR",
};

const DUMP_TYPE_COLORS: Record<string, string> = {
  TP_DUMP: "bg-[#e8f0fe] text-[#1a73e8] border-[#c5d9f7]",
  CARRIER_SWITCH: "bg-[#fce8e6] text-[#c5221f] border-[#f5c6c2]",
  FARE_BASIS: "bg-[#e6f4ea] text-[#0d904f] border-[#b7dfbf]",
  ALLIANCE_RULE: "bg-[#fef7e0] text-[#e37400] border-[#fad56c]",
};

function ExpandedDetail({ airport }: { airport: AirportOpportunity }) {
  return (
    <div className="grid grid-cols-4 gap-6 text-[13px]">
      {/* Score breakdown */}
      <div>
        <p className="text-[11px] font-medium text-[#5f6368] uppercase tracking-wider mb-2">
          Score breakdown
        </p>
        <div className="space-y-1.5">
          <ScoreRow
            label="YQ carrier coverage (40%)"
            value={airport.opportunityScore}
            note="Weighted by tier and route role"
          />
          {airport.patternCount > 0 && (
            <ScoreRow
              label="Pattern density (30%)"
              value={airport.patternCount}
              note={`${airport.patternCount} known pattern${airport.patternCount !== 1 ? "s" : ""}`}
              raw
            />
          )}
          {airport.maxSavingsUsd > 0 && (
            <ScoreRow
              label="Max savings (20%)"
              value={airport.maxSavingsUsd}
              note={`up to $${airport.maxSavingsUsd.toFixed(0)} YQ avoided`}
              raw
            />
          )}
          {airport.anchors.length > 0 && (
            <p className="text-[12px] text-[#5f6368]">
              <span className="font-medium text-[#202124]">
                Anchor bonus (10%)
              </span>{" "}
              — {airport.anchors.map((a) => a.carrier).join(", ")} enables
              carrier-switch construction
            </p>
          )}
        </div>
      </div>

      {/* All carriers */}
      <div>
        <p className="text-[11px] font-medium text-[#5f6368] uppercase tracking-wider mb-2">
          Carrier detail
        </p>
        <div className="space-y-1">
          {airport.yqCarriers.map((c) => (
            <div key={c.carrier} className="flex items-center gap-2">
              <span
                className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium ${
                  TIER_COLORS[c.tier]
                }`}
              >
                {c.carrier}
              </span>
              <span className="text-[12px] text-[#5f6368]">
                Tier {c.tier} · ~${c.typicalYqUsd} YQ ·{" "}
                <span className="italic">{c.role}</span>
              </span>
            </div>
          ))}
          {airport.anchors.map((a) => (
            <div key={a.carrier} className="flex items-center gap-2">
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium bg-[#e8f0fe] text-[#1a73e8] border border-[#c5d9f7]">
                {a.carrier}
              </span>
              <span className="text-[12px] text-[#5f6368]">
                No-YQ anchor ·{" "}
                <span className="italic">{a.role}</span>
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Strategy + stats */}
      <div>
        <p className="text-[11px] font-medium text-[#5f6368] uppercase tracking-wider mb-2">
          Agent tip
        </p>
        <p className="text-[12px] text-[#202124] leading-relaxed">
          {airport.strategy}
        </p>
        {airport.avgConfidence > 0 && (
          <p className="mt-2 text-[11px] text-[#80868b]">
            Avg pattern confidence:{" "}
            <span className="font-medium text-[#202124]">
              {(airport.avgConfidence * 100).toFixed(0)}%
            </span>
          </p>
        )}
        {airport.patternCount === 0 && (
          <p className="mt-2 text-[11px] text-[#e37400]">
            No validated patterns yet — score is based on carrier presence only.
            Try manual ITA Matrix search.
          </p>
        )}
      </div>

      {/* Sample routings */}
      <div>
        <p className="text-[11px] font-medium text-[#5f6368] uppercase tracking-wider mb-2">
          Sample routings
        </p>
        {airport.samplePatterns.length === 0 ? (
          <p className="text-[12px] text-[#80868b] italic">
            No validated patterns yet
          </p>
        ) : (
          <div className="space-y-2">
            {airport.samplePatterns.map((p) => {
              const dumpLabel = DUMP_TYPE_LABELS[p.dump_type] ?? p.dump_type;
              const dumpColor =
                DUMP_TYPE_COLORS[p.dump_type] ??
                "bg-[#f1f3f4] text-[#5f6368] border-[#dadce0]";
              const via = p.routing_points.length > 0
                ? ` via ${p.routing_points.join(", ")}`
                : "";
              return (
                <a
                  key={p.id}
                  href={`/patterns/${p.id}`}
                  className="block border border-[#e8eaed] rounded-lg px-3 py-2 bg-white hover:border-[#1a73e8] hover:bg-[#f8f9fa] transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[12px] font-semibold text-[#202124]">
                      {p.origin_iata} → {p.destination_iata}
                    </span>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <span
                        className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border ${dumpColor}`}
                      >
                        {dumpLabel}
                      </span>
                      {p.expected_yq_savings_usd != null && (
                        <span className="text-[11px] font-semibold text-[#0d904f] tabular-nums">
                          ${p.expected_yq_savings_usd.toFixed(0)}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="mt-0.5 flex items-center gap-2">
                    <span className="text-[11px] text-[#5f6368]">
                      {p.ticketing_carrier_iata}{via}
                    </span>
                    <span className="text-[10px] text-[#80868b] tabular-nums">
                      {(p.confidence_score * 100).toFixed(0)}% conf
                    </span>
                  </div>
                </a>
              );
            })}
            {airport.patternCount > 3 && (
              <p className="text-[11px] text-[#1a73e8] mt-1">
                +{airport.patternCount - 3} more → see Patterns tab
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ScoreRow({
  label,
  value,
  note,
  raw,
}: {
  label: string;
  value: number;
  note: string;
  raw?: boolean;
}) {
  return (
    <p className="text-[12px] text-[#5f6368]">
      <span className="font-medium text-[#202124]">{label}</span>
      {raw ? null : (
        <span className="ml-1 tabular-nums text-[#1a73e8]">{value}</span>
      )}{" "}
      — {note}
    </p>
  );
}

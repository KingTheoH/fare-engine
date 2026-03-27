"use client";

import { useMemo } from "react";
import Link from "next/link";
import { MOCK_PATTERN_DETAIL, MOCK_VALIDATION_RUNS } from "@/lib/mock-data";
import ManualInputBundle from "@/components/ManualInputBundle";
import LifecycleBadge from "@/components/LifecycleBadge";
import DumpTypeBadge from "@/components/DumpTypeBadge";
import ConfidenceBar from "@/components/ConfidenceBar";

export default function PatternDetailPage() {
  // Use mock data — swap to API call when backend is connected
  const pattern = MOCK_PATTERN_DETAIL;
  const runs = MOCK_VALIDATION_RUNS;

  const successRate = useMemo(() => {
    if (runs.length === 0) return 0;
    return runs.filter((r) => r.success).length / runs.length;
  }, [runs]);

  // Derive last successful run and recent failure count for LastWorkingBadge
  const lastSuccessfulRun = useMemo(() => {
    const sorted = [...runs].sort((a, b) => new Date(b.ran_at).getTime() - new Date(a.ran_at).getTime());
    const success = sorted.find((r) => r.success);
    if (!success) return null;
    return {
      date: success.ran_at,
      basePrice: success.base_fare_usd ?? 0,
      yqCharged: success.yq_charged_usd ?? 0,
    };
  }, [runs]);

  const recentFailureCount = useMemo(() => {
    const sorted = [...runs].sort((a, b) => new Date(b.ran_at).getTime() - new Date(a.ran_at).getTime());
    let count = 0;
    for (const run of sorted) {
      if (!run.success) count++;
      else break;
    }
    return count;
  }, [runs]);

  return (
    <div className="animate-fade-in">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 mb-5 text-[13px]">
        <Link href="/patterns" className="text-[#1a73e8] hover:underline">
          Patterns
        </Link>
        <span className="text-[#80868b]">/</span>
        <span className="text-[#5f6368]">
          {pattern.origin_iata} &rarr; {pattern.destination_iata}
        </span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-[24px] font-normal text-[#202124]">
            {pattern.origin_iata}
            <span className="text-[#5f6368] mx-2">&rarr;</span>
            {pattern.destination_iata}
          </h1>
          <div className="flex items-center gap-3 mt-2">
            <DumpTypeBadge type={pattern.dump_type} />
            <LifecycleBadge state={pattern.lifecycle_state} />
            <span className="text-[13px] text-[#5f6368]">
              via {pattern.ticketing_carrier_iata}
              {pattern.routing_points.length > 0 &&
                ` / ${pattern.routing_points.join(", ")}`}
            </span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[32px] font-semibold text-[#0d904f] tabular-nums">
            ${pattern.expected_yq_savings_usd?.toFixed(0) ?? "—"}
          </div>
          <div className="text-[12px] text-[#5f6368]">YQ savings/RT</div>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-[1fr_420px] gap-6">
        {/* Left: metadata + validation history */}
        <div className="space-y-6">
          {/* Pattern info */}
          <div className="border border-[#dadce0] rounded-lg overflow-hidden">
            <div className="px-5 py-3 bg-[#f8f9fa] border-b border-[#dadce0]">
              <h2 className="text-[14px] font-medium text-[#202124]">
                Pattern Details
              </h2>
            </div>
            <div className="px-5 py-4 grid grid-cols-2 gap-4">
              <InfoRow label="Routing Code" value={pattern.ita_routing_code ?? pattern.baseline_routing ?? "—"} mono />
              <InfoRow label="Ticketing Carrier" value={pattern.ticketing_carrier_iata} />
              <InfoRow label="Operating Carriers" value={pattern.operating_carriers.join(", ")} />
              <InfoRow label="Routing Points" value={pattern.routing_points.join(", ") || "Direct"} />
              <InfoRow label="Fare Basis Hint" value={pattern.fare_basis_hint || "—"} />
              <InfoRow label="Source" value={pattern.source} />
              <InfoRow label="Freshness Tier" value={pattern.freshness_tier === 1 ? "Tier 1 (Daily)" : pattern.freshness_tier === 2 ? "Tier 2 (Weekly)" : "Tier 3 (Monthly)"} />
              <div>
                <span className="text-[11px] text-[#80868b] uppercase tracking-wider">
                  Confidence
                </span>
                <div className="mt-1">
                  <ConfidenceBar score={pattern.confidence_score} />
                </div>
              </div>
            </div>
          </div>

          {/* Validation history */}
          <div className="border border-[#dadce0] rounded-lg overflow-hidden">
            <div className="px-5 py-3 bg-[#f8f9fa] border-b border-[#dadce0] flex items-center justify-between">
              <h2 className="text-[14px] font-medium text-[#202124]">
                Validation History
              </h2>
              <span className="text-[12px] text-[#5f6368]">
                {Math.round(successRate * 100)}% success rate
              </span>
            </div>

            {/* Mini validation bar */}
            <div className="px-5 py-3 border-b border-[#e8eaed] flex items-center gap-1">
              {runs.map((run) => (
                <div
                  key={run.id}
                  title={`${new Date(run.ran_at).toLocaleDateString()} — ${run.success ? "Success" : "Failed"}`}
                  className={`h-6 flex-1 rounded-sm ${
                    run.success ? "bg-[#0d904f]" : "bg-[#c5221f]"
                  }`}
                />
              ))}
            </div>

            <table className="w-full">
              <thead>
                <tr className="border-b border-[#e8eaed]">
                  <th className="text-left px-4 py-2 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">Date</th>
                  <th className="text-left px-4 py-2 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">Result</th>
                  <th className="text-right px-4 py-2 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">YQ Charged</th>
                  <th className="text-right px-4 py-2 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">Base Fare</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e8eaed]">
                {runs.map((run) => (
                  <tr key={run.id} className="hover:bg-[#f8f9fa]">
                    <td className="px-4 py-2 text-[13px] text-[#202124]">
                      {new Date(run.ran_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="px-4 py-2">
                      {run.success ? (
                        <span className="inline-flex items-center gap-1 text-[12px] font-medium text-[#0d904f]">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                          Pass
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[12px] font-medium text-[#c5221f]">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                            <line x1="18" y1="6" x2="6" y2="18" />
                            <line x1="6" y1="6" x2="18" y2="18" />
                          </svg>
                          Fail
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-right text-[13px] tabular-nums">
                      {run.yq_charged_usd !== null ? (
                        <span className={run.yq_charged_usd === 0 ? "text-[#0d904f]" : "text-[#c5221f]"}>
                          ${run.yq_charged_usd.toFixed(0)}
                        </span>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-2 text-right text-[13px] text-[#5f6368] tabular-nums">
                      {run.base_fare_usd !== null ? `$${run.base_fare_usd.toFixed(0)}` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right: Manual Input Bundle */}
        <div className="no-print-hide">
          {pattern.manual_input_bundle ? (
            <ManualInputBundle
              bundle={pattern.manual_input_bundle}
              lastSuccessfulRun={lastSuccessfulRun}
              recentFailureCount={recentFailureCount}
            />
          ) : (
            <div className="border border-[#dadce0] rounded-lg p-8 text-center">
              <p className="text-[14px] text-[#5f6368]">
                No manual input bundle yet
              </p>
              <p className="text-[12px] text-[#80868b] mt-1">
                Awaiting first successful validation
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function InfoRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <span className="text-[11px] text-[#80868b] uppercase tracking-wider">
        {label}
      </span>
      <p
        className={`text-[13px] text-[#202124] mt-0.5 ${
          mono ? "routing-code" : ""
        }`}
      >
        {value}
      </p>
    </div>
  );
}

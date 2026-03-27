"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { getRecentValidations } from "@/lib/api";
import type { ValidationRunResponse } from "@/lib/types";

type Period = "24h" | "7d" | "30d";

export default function ValidationsPage() {
  const [period, setPeriod] = useState<Period>("7d");
  const [validations, setValidations] = useState<ValidationRunResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getRecentValidations(period)
      .then((res) => {
        setValidations(res.items);
        setError(null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [period]);

  const sorted = useMemo(() => {
    return [...validations].sort(
      (a, b) => new Date(b.ran_at).getTime() - new Date(a.ran_at).getTime()
    );
  }, [validations]);

  const successCount = sorted.filter((v) => v.success).length;
  const failCount = sorted.length - successCount;

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-[22px] font-normal text-[#202124]">
            Validation History
          </h1>
          <p className="text-[13px] text-[#5f6368] mt-1">
            {sorted.length} runs &middot;{" "}
            <span className="text-[#0d904f]">{successCount} passed</span>
            {failCount > 0 && (
              <> &middot; <span className="text-[#c5221f]">{failCount} failed</span></>
            )}
          </p>
        </div>
        <div className="flex items-center gap-1 bg-[#f1f3f4] rounded-lg p-0.5">
          {(["24h", "7d", "30d"] as Period[]).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1.5 text-[12px] font-medium rounded-md transition-colors ${
                period === p
                  ? "bg-white text-[#202124] shadow-sm"
                  : "text-[#5f6368] hover:text-[#202124]"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <span className="text-[14px] text-[#5f6368]">Loading validations...</span>
        </div>
      ) : error ? (
        <div className="flex items-center justify-center py-20">
          <span className="text-[14px] text-[#c5221f]">Error: {error}</span>
        </div>
      ) : (
        <div className="border border-[#dadce0] rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-[#f8f9fa] border-b border-[#dadce0]">
                <th className="text-left px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">Pattern</th>
                <th className="text-left px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">Run Time</th>
                <th className="text-left px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">Result</th>
                <th className="text-right px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">YQ Charged</th>
                <th className="text-right px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">YQ Expected</th>
                <th className="text-right px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">Base Fare</th>
                <th className="text-left px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">Error</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e8eaed]">
              {sorted.map((run) => (
                <tr key={run.id} className="hover:bg-[#f8f9fa] transition-colors">
                  <td className="px-4 py-3">
                    <Link
                      href={`/patterns/${run.pattern_id}`}
                      className="text-[14px] font-medium text-[#1a73e8] hover:underline"
                    >
                      {run.pattern_id.slice(0, 8)}...
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-[13px] text-[#202124]">
                    {new Date(run.ran_at).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                  <td className="px-4 py-3">
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
                  <td className="px-4 py-3 text-right text-[13px] tabular-nums">
                    {run.yq_charged_usd !== null ? (
                      <span className={run.yq_charged_usd === 0 ? "text-[#0d904f] font-medium" : "text-[#c5221f]"}>
                        ${run.yq_charged_usd.toFixed(0)}
                      </span>
                    ) : "—"}
                  </td>
                  <td className="px-4 py-3 text-right text-[13px] text-[#5f6368] tabular-nums">
                    {run.yq_expected_usd !== null ? `$${run.yq_expected_usd.toFixed(0)}` : "—"}
                  </td>
                  <td className="px-4 py-3 text-right text-[13px] text-[#5f6368] tabular-nums">
                    {run.base_fare_usd !== null ? `$${run.base_fare_usd.toFixed(0)}` : "—"}
                  </td>
                  <td className="px-4 py-3 text-[12px] text-[#c5221f] max-w-[200px] truncate">
                    {run.error_message || ""}
                  </td>
                </tr>
              ))}
              {sorted.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-[14px] text-[#5f6368]">
                    No validation runs in this period
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

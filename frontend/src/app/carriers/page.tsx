"use client";

import { useState, useMemo, useEffect } from "react";
import { getCarriers } from "@/lib/api";
import type { CarrierResponse } from "@/lib/types";

const ALLIANCE_COLORS: Record<string, string> = {
  STAR: "bg-[#e8f0fe] text-[#1a73e8]",
  ONEWORLD: "bg-[#fce8e6] text-[#c5221f]",
  SKYTEAM: "bg-[#e6f4ea] text-[#0d904f]",
  NONE: "bg-[#f1f3f4] text-[#80868b]",
};

export default function CarriersPage() {
  const [showYqOnly, setShowYqOnly] = useState(false);
  const [allCarriers, setAllCarriers] = useState<CarrierResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCarriers({ page_size: 100 })
      .then((res) => setAllCarriers(res.items))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const carriers = useMemo(() => {
    let result = [...allCarriers];
    if (showYqOnly) result = result.filter((c) => c.charges_yq === true);
    return result.sort(
      (a, b) => (b.typical_yq_usd ?? 0) - (a.typical_yq_usd ?? 0)
    );
  }, [allCarriers, showYqOnly]);

  const maxYq = Math.max(...allCarriers.map((c) => c.typical_yq_usd ?? 0), 1);

  if (loading) {
    return (
      <div className="animate-fade-in flex items-center justify-center py-20">
        <span className="text-[14px] text-[#5f6368]">Loading carriers...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="animate-fade-in flex items-center justify-center py-20">
        <span className="text-[14px] text-[#c5221f]">Error: {error}</span>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-[22px] font-normal text-[#202124]">
            YQ Tracker
          </h1>
          <p className="text-[13px] text-[#5f6368] mt-1">
            {allCarriers.length} carriers — target the highest YQ carriers
          </p>
        </div>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showYqOnly}
            onChange={(e) => setShowYqOnly(e.target.checked)}
            className="w-4 h-4 rounded border-[#dadce0] text-[#1a73e8] focus:ring-[#1a73e8]"
          />
          <span className="text-[13px] text-[#5f6368]">
            YQ carriers only
          </span>
        </label>
      </div>

      <div className="border border-[#dadce0] rounded-lg overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-[#f8f9fa] border-b border-[#dadce0]">
              <th className="text-left px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">Carrier</th>
              <th className="text-left px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">Alliance</th>
              <th className="text-left px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">Charges YQ</th>
              <th className="text-right px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">Typical YQ</th>
              <th className="text-left px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider w-[200px]"></th>
              <th className="text-left px-4 py-3 text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">Last Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#e8eaed]">
            {carriers.map((c) => (
              <tr key={c.iata_code} className="hover:bg-[#f8f9fa] transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-[14px] font-medium text-[#202124]">
                      {c.iata_code}
                    </span>
                    <span className="text-[13px] text-[#5f6368]">
                      {c.name}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${
                      ALLIANCE_COLORS[c.alliance] || ALLIANCE_COLORS.NONE
                    }`}
                  >
                    {c.alliance === "NONE" ? "—" : c.alliance}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {c.charges_yq === true ? (
                    <span className="text-[12px] font-medium text-[#c5221f]">Yes</span>
                  ) : c.charges_yq === false ? (
                    <span className="text-[12px] font-medium text-[#0d904f]">No</span>
                  ) : (
                    <span className="text-[12px] text-[#80868b]">Unknown</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  <span className={`text-[15px] font-semibold tabular-nums ${
                    (c.typical_yq_usd ?? 0) > 0 ? "text-[#c5221f]" : "text-[#0d904f]"
                  }`}>
                    ${c.typical_yq_usd?.toFixed(0) ?? "—"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="w-full h-2 bg-[#e8eaed] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        (c.typical_yq_usd ?? 0) > 300
                          ? "bg-[#c5221f]"
                          : (c.typical_yq_usd ?? 0) > 100
                          ? "bg-[#e37400]"
                          : "bg-[#0d904f]"
                      }`}
                      style={{
                        width: `${maxYq > 0 ? ((c.typical_yq_usd ?? 0) / maxYq) * 100 : 0}%`,
                      }}
                    />
                  </div>
                </td>
                <td className="px-4 py-3 text-[12px] text-[#80868b]">
                  {c.last_yq_updated
                    ? new Date(c.last_yq_updated).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                      })
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

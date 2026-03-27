"use client";

import { useState } from "react";
import {
  DUMPABLE_CLASSES,
  NON_DUMPABLE_CLASSES,
  FARE_CLASS_EXPLAINER,
  EXTENSION_CODE_INSTRUCTION,
} from "@/lib/fare-classes";

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export default function FareClassGuidance(_props: {
  fareBasisHint?: string | null;
}) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="border border-[#e8eaed] rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full px-4 py-3 flex items-center justify-between bg-[#fef7e0] border-b border-[#f9d67a] hover:bg-[#fef0c7] transition-colors"
      >
        <div className="flex items-center gap-2">
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#5f3400"
            strokeWidth="2"
          >
            <path d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-[13px] font-medium text-[#5f3400]">
            Fare Class Guidance
          </span>
        </div>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="#5f3400"
          strokeWidth="2.5"
          className={`transition-transform ${expanded ? "rotate-180" : ""}`}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {expanded && (
        <div className="px-4 py-3 space-y-3 bg-white">
          {/* Explainer */}
          <p className="text-[12px] text-[#5f6368] leading-relaxed">
            {FARE_CLASS_EXPLAINER}
          </p>

          {/* Class badges */}
          <div className="space-y-2">
            <div>
              <span className="text-[11px] font-medium text-[#0d904f] uppercase tracking-wider">
                Dumpable (cheap economy)
              </span>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {DUMPABLE_CLASSES.map((cls) => (
                  <span
                    key={cls}
                    className="px-2 py-0.5 bg-[#e6f4ea] text-[#0d904f] text-[12px] font-mono font-semibold rounded"
                  >
                    {cls}
                  </span>
                ))}
              </div>
            </div>
            <div>
              <span className="text-[11px] font-medium text-[#c5221f] uppercase tracking-wider">
                Not dumpable (full fare / premium)
              </span>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {NON_DUMPABLE_CLASSES.map((cls) => (
                  <span
                    key={cls}
                    className="px-2 py-0.5 bg-[#fce8e6] text-[#c5221f] text-[12px] font-mono font-semibold rounded"
                  >
                    {cls}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Result filtering guidance */}
          <div className="border-t border-[#e8eaed] pt-3">
            <p className="text-[11px] text-[#80868b] leading-relaxed">
              {EXTENSION_CODE_INSTRUCTION}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

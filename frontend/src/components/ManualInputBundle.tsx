"use client";

import { useState, useMemo } from "react";
import type { ManualInputBundle as ManualInputBundleType, MultiCitySegment } from "@/lib/types";
import { buildDumpSearchUrl, buildBaselineSearchUrl } from "@/lib/ita-matrix-url";
import CopyButton from "./CopyButton";
import ConfidenceBar from "./ConfidenceBar";
import FareClassGuidance from "./FareClassGuidance";
import LastWorkingBadge, { type LastWorkingInfo } from "./LastWorkingBadge";

export default function ManualInputBundle({
  bundle,
  lastSuccessfulRun,
  recentFailureCount,
}: {
  bundle: ManualInputBundleType;
  lastSuccessfulRun?: LastWorkingInfo | null;
  recentFailureCount?: number;
}) {
  // Render the scan-engine view when multi_city_segments are present
  if (bundle.is_scan_engine_bundle && bundle.multi_city_segments) {
    return (
      <ScanEngineView
        bundle={bundle}
        lastSuccessfulRun={lastSuccessfulRun}
        recentFailureCount={recentFailureCount}
      />
    );
  }
  return (
    <ValidatedView
      bundle={bundle}
      lastSuccessfulRun={lastSuccessfulRun}
      recentFailureCount={recentFailureCount}
    />
  );
}

// ─────────────────────────────────────────────────────────────
// ITA Matrix Buttons — shared between both views
// ─────────────────────────────────────────────────────────────

function ItaMatrixButtons({ bundle, departureDate }: { bundle: ManualInputBundleType; departureDate?: Date }) {
  const dumpUrl = useMemo(() => buildDumpSearchUrl(bundle, departureDate), [bundle, departureDate]);
  const baselineUrl = useMemo(() => buildBaselineSearchUrl(bundle, departureDate), [bundle, departureDate]);

  return (
    <div className="flex flex-col gap-2">
      {dumpUrl && (
        <a
          href={dumpUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-2 px-4 py-2.5 bg-[#1a73e8] hover:bg-[#1765cc] text-white text-[13px] font-medium rounded-lg transition-colors"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
          Open Dump Search in ITA Matrix
        </a>
      )}
      {baselineUrl && (
        <a
          href={baselineUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-2 px-4 py-2 bg-white hover:bg-[#f8f9fa] text-[#1a73e8] text-[12px] font-medium rounded-lg border border-[#dadce0] transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
          Baseline (roundtrip for comparison)
        </a>
      )}
      {!dumpUrl && !baselineUrl && (
        <p className="text-[11px] text-[#80868b]">
          Missing origin/destination or dump segment — cannot generate ITA Matrix URL.
        </p>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Date Picker Row — departure date for ITA Matrix URL
// ─────────────────────────────────────────────────────────────

function DatePickerRow({
  departureDate,
  setDepartureDate,
}: {
  departureDate: string;
  setDepartureDate: (d: string) => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <label className="text-[11px] font-medium text-[#5f6368] uppercase tracking-wider whitespace-nowrap">
        Departure
      </label>
      <input
        type="date"
        value={departureDate}
        onChange={(e) => setDepartureDate(e.target.value)}
        className="px-2 py-1.5 text-[13px] text-[#202124] bg-white border border-[#dadce0] rounded-md focus:outline-none focus:ring-2 focus:ring-[#1a73e8] focus:border-transparent"
      />
      <span className="text-[11px] text-[#80868b]">
        ITA Matrix will search +/- 2 days
      </span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Scan Engine View — for patterns with multi_city_segments
// Shows: itinerary diagram, two routing codes, staged steps
// ─────────────────────────────────────────────────────────────

function ScanEngineView({
  bundle,
  lastSuccessfulRun,
  recentFailureCount,
}: {
  bundle: ManualInputBundleType;
  lastSuccessfulRun?: LastWorkingInfo | null;
  recentFailureCount?: number;
}) {
  const [checkedSteps, setCheckedSteps] = useState<Set<number>>(new Set());
  const segments = bundle.multi_city_segments!;
  const dumpSeg = bundle.dump_segment;

  // Date state for ITA Matrix URL builder
  const defaultDate = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() + 21);
    return d.toISOString().split("T")[0];
  }, []);
  const [departureDate, setDepartureDate] = useState(defaultDate);
  const departureDateObj = useMemo(() => new Date(departureDate + "T12:00:00"), [departureDate]);

  const toggleStep = (i: number) =>
    setCheckedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(i)) { next.delete(i); } else { next.add(i); }
      return next;
    });

  // Identify which segments are the dump leg
  const isDump = (seg: MultiCitySegment) =>
    dumpSeg &&
    seg.from === dumpSeg.from &&
    seg.to === dumpSeg.to;

  const steps = buildScanEngineSteps(bundle);

  return (
    <div className="bg-white border border-[#dadce0] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 bg-[#fef7e0] border-b border-[#f9d67a] flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-[15px] font-medium text-[#202124]">
              Manual Input Guide
            </h3>
            <span className="px-2 py-0.5 bg-[#f9d67a] text-[#5f3400] text-[11px] font-medium rounded">
              Not yet validated
            </span>
          </div>
          <p className="text-[12px] text-[#5f6368] mt-0.5">
            Scanner-generated — verify YQ savings manually
          </p>
        </div>
        <button
          onClick={() => window.print()}
          className="px-3 py-1.5 text-[12px] font-medium text-[#5f6368] hover:text-[#202124] hover:bg-[#e8eaed] rounded-md transition-colors no-print"
        >
          Print
        </button>
      </div>

      {/* Last Working Badge */}
      <div className="px-5 py-3 border-b border-[#e8eaed]">
        <LastWorkingBadge
          lastSuccessfulRun={lastSuccessfulRun}
          recentFailureCount={recentFailureCount}
        />
      </div>

      {/* Savings estimate */}
      <div className="px-5 py-4 bg-[#e6f4ea] border-b border-[#ceead6]">
        <div className="flex items-baseline gap-2">
          <span className="text-[28px] font-semibold text-[#0d904f] tabular-nums">
            ~${bundle.expected_yq_savings_usd.toFixed(0)}
          </span>
          <span className="text-[13px] text-[#0d904f]">
            estimated YQ savings per trip
          </span>
        </div>
        <p className="text-[12px] text-[#137333] mt-1">
          {bundle.human_description}
        </p>
      </div>

      {/* ITA Matrix one-click buttons + date picker */}
      <div className="px-5 py-4 border-b border-[#e8eaed] space-y-3">
        <span className="text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">
          Quick Search
        </span>
        <DatePickerRow departureDate={departureDate} setDepartureDate={setDepartureDate} />
        <ItaMatrixButtons bundle={bundle} departureDate={departureDateObj} />
      </div>

      {/* Fare Class Guidance */}
      <div className="px-5 py-4 border-b border-[#e8eaed]">
        <FareClassGuidance fareBasisHint={bundle.fare_basis_hint} />
      </div>

      {/* Multi-city itinerary diagram */}
      <div className="px-5 py-4 border-b border-[#e8eaed]">
        <span className="text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">
          Multi-City Itinerary
        </span>
        <div className="mt-3 space-y-2">
          {segments.map((seg, i) => {
            const dump = isDump(seg);
            return (
              <div
                key={i}
                className={`flex items-start gap-3 px-3 py-2.5 rounded-lg border ${
                  dump
                    ? "bg-[#fff8e1] border-[#fdd663]"
                    : "bg-[#f8f9fa] border-[#e8eaed]"
                }`}
              >
                {/* Leg number */}
                <div
                  className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 text-[11px] font-semibold ${
                    dump
                      ? "bg-[#f9d67a] text-[#5f3400]"
                      : "bg-[#e8eaed] text-[#5f6368]"
                  }`}
                >
                  {i + 1}
                </div>

                {/* Route */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[14px] font-semibold text-[#202124] font-mono">
                      {seg.from}
                    </span>
                    <span className="text-[#80868b]">&rarr;</span>
                    <span className="text-[14px] font-semibold text-[#202124] font-mono">
                      {seg.to}
                    </span>
                    {seg.via && (
                      <span className="text-[11px] text-[#80868b]">
                        via {seg.via}
                      </span>
                    )}
                    {seg.carrier ? (
                      <span className="px-1.5 py-0.5 bg-[#e8f0fe] text-[#1a73e8] text-[11px] font-medium rounded">
                        {seg.carrier}
                      </span>
                    ) : (
                      <span className="px-1.5 py-0.5 bg-[#f1f3f4] text-[#80868b] text-[11px] rounded">
                        any carrier
                      </span>
                    )}
                    {dump && (
                      <span className="px-1.5 py-0.5 bg-[#f9d67a] text-[#5f3400] text-[11px] font-semibold rounded">
                        DUMP LEG
                      </span>
                    )}
                  </div>
                  {seg.notes && (
                    <p className="text-[11px] text-[#80868b] mt-0.5 leading-snug">
                      {seg.notes}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Dump explanation */}
        {dumpSeg?.notes && (
          <div className="mt-3 px-3 py-2.5 bg-[#fff8e1] border border-[#fdd663] rounded-lg">
            <p className="text-[12px] text-[#5f3400]">
              <span className="font-semibold">Why this works: </span>
              {dumpSeg.notes}
            </p>
          </div>
        )}
      </div>

      {/* Routing codes — two-step */}
      <div className="px-5 py-4 border-b border-[#e8eaed] space-y-4">
        <div>
          <span className="text-[11px] font-medium text-[#5f6368] uppercase tracking-wider block">
            ITA Matrix Routing Codes
          </span>
          <p className="text-[11px] text-[#80868b] mt-1">
            Paste into each leg&apos;s routing codes field — not the itinerary itself.
            Dump leg has <strong>no routing code</strong> — enter it as a plain city pair.
          </p>
          {/* Syntax legend */}
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-[#80868b]">
            <span><code className="bg-[#f1f3f4] px-1 rounded font-mono">LH+</code> = 1 or more LH segments</span>
            <span><code className="bg-[#f1f3f4] px-1 rounded font-mono">FRA,MUC</code> = Frankfurt <em>or</em> Munich</span>
            <span><code className="bg-[#f1f3f4] px-1 rounded font-mono">F?</code> = any carrier (fallback)</span>
          </div>
        </div>

        {/* Baseline */}
        {bundle.baseline_routing && (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-[#e8eaed] text-[#5f6368] text-[11px] font-semibold flex items-center justify-center">1</span>
                <span className="text-[12px] font-medium text-[#5f6368]">
                  Baseline — paste into both slices of a roundtrip search
                </span>
              </div>
              <CopyButton text={bundle.baseline_routing} label="Copy" />
            </div>
            <div className="font-mono bg-[#f8f9fa] border border-[#e8eaed] rounded-md px-4 py-2.5 text-[14px] text-[#202124] select-all">
              {bundle.baseline_routing}
            </div>
            <p className="text-[11px] text-[#80868b] mt-1">
              Run as a roundtrip first to get your reference price.
            </p>
            <FallbackCode primary={bundle.baseline_routing} />
          </div>
        )}

        {/* Multi-city Leg 1 routing code */}
        {bundle.optimized_routing && (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-[#f9d67a] text-[#5f3400] text-[11px] font-semibold flex items-center justify-center">2</span>
                <span className="text-[12px] font-medium text-[#5f3400]">
                  Multi-city: Leg 1 routing code
                </span>
              </div>
              <CopyButton text={bundle.optimized_routing} label="Copy" />
            </div>
            <div className="font-mono bg-[#fff8e1] border border-[#fdd663] rounded-md px-4 py-2.5 text-[14px] text-[#202124] select-all">
              {bundle.optimized_routing}
            </div>
            <p className="text-[11px] text-[#80868b] mt-1">
              Switch ITA Matrix to Multi-city. Paste into Leg 1 only.
              Leg 2 (dump) is a plain city pair — leave routing codes blank.
            </p>
            <FallbackCode primary={bundle.optimized_routing} />
          </div>
        )}
      </div>

      {/* Strike Segment callout */}
      {bundle.strike_segment && (
        <div className="mx-5 mb-4 border border-amber-200 bg-amber-50 rounded-md px-4 py-3">
          <div className="text-[11px] font-semibold text-amber-700 uppercase tracking-wider mb-1.5">
            ⚡ Strike Segment Required
          </div>
          <p className="text-[13px] text-amber-900">
            Append{" "}
            <span className="font-mono font-semibold">
              {bundle.strike_segment.origin}→{bundle.strike_segment.destination}
            </span>{" "}
            on{" "}
            <span className="font-semibold">{bundle.strike_segment.carrier}</span>{" "}
            as a throwaway final leg — do not fly it.
          </p>
          {bundle.strike_segment.note && (
            <p className="text-[11px] text-amber-700 mt-1.5 leading-relaxed">
              {bundle.strike_segment.note}
            </p>
          )}
        </div>
      )}

      {/* Steps checklist */}
      <div className="px-5 py-4 border-b border-[#e8eaed]">
        <span className="text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">
          Steps
        </span>
        <ol className="mt-3 space-y-1.5">
          {steps.map((step, i) => (
            <li
              key={i}
              onClick={() => toggleStep(i)}
              className={`flex items-start gap-3 px-3 py-2 rounded-md cursor-pointer transition-colors ${
                checkedSteps.has(i)
                  ? "bg-[#e6f4ea] text-[#5f6368]"
                  : "hover:bg-[#f8f9fa]"
              }`}
            >
              <div
                className={`mt-0.5 w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 transition-all ${
                  checkedSteps.has(i)
                    ? "bg-[#0d904f] border-[#0d904f]"
                    : "border-[#dadce0]"
                }`}
              >
                {checkedSteps.has(i) && (
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
              </div>
              <span
                className={`text-[13px] leading-relaxed ${
                  checkedSteps.has(i) ? "line-through" : "text-[#202124]"
                }`}
              >
                {step}
              </span>
            </li>
          ))}
        </ol>
      </div>

      {/* Confidence */}
      <div className="px-5 py-3">
        <div className="flex items-center gap-4">
          <div>
            <span className="text-[11px] text-[#80868b] uppercase tracking-wider">
              Confidence
            </span>
            <div className="mt-1">
              <ConfidenceBar score={bundle.confidence_score} />
            </div>
          </div>
          <div>
            <span className="text-[11px] text-[#80868b] uppercase tracking-wider">
              Status
            </span>
            <p className="text-[12px] text-[#e37400] mt-1 font-medium">
              Awaiting first scan
            </p>
          </div>
        </div>
        {bundle.notes && (
          <p className="mt-3 text-[12px] text-[#80868b] leading-relaxed border-t border-[#f1f3f4] pt-3">
            {bundle.notes}
          </p>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Validated View — original view for confirmed bundles
// ─────────────────────────────────────────────────────────────

function ValidatedView({
  bundle,
  lastSuccessfulRun,
  recentFailureCount,
}: {
  bundle: ManualInputBundleType;
  lastSuccessfulRun?: LastWorkingInfo | null;
  recentFailureCount?: number;
}) {
  const [checkedSteps, setCheckedSteps] = useState<Set<number>>(new Set());
  const [showBackup, setShowBackup] = useState(false);

  // Date state for ITA Matrix URL builder
  const defaultDate = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() + 21);
    return d.toISOString().split("T")[0];
  }, []);
  const [departureDate, setDepartureDate] = useState(defaultDate);
  const departureDateObj = useMemo(() => new Date(departureDate + "T12:00:00"), [departureDate]);

  const toggleStep = (i: number) => {
    setCheckedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(i)) { next.delete(i); } else { next.add(i); }
      return next;
    });
  };

  const validatedAt = new Date(bundle.validation_timestamp);
  const timeAgo = getTimeAgo(validatedAt);

  return (
    <div className="bg-white border border-[#dadce0] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 bg-[#f8f9fa] border-b border-[#dadce0] flex items-center justify-between">
        <div>
          <h3 className="text-[15px] font-medium text-[#202124]">
            Manual Input Bundle
          </h3>
          <p className="text-[12px] text-[#5f6368] mt-0.5">
            Paste directly into ITA Matrix
          </p>
        </div>
        <div className="flex items-center gap-2 no-print">
          <button
            onClick={() => window.print()}
            className="px-3 py-1.5 text-[12px] font-medium text-[#5f6368] hover:text-[#202124] hover:bg-[#e8eaed] rounded-md transition-colors"
          >
            Print
          </button>
        </div>
      </div>

      {/* Last Working Badge */}
      <div className="px-5 py-3 border-b border-[#e8eaed]">
        <LastWorkingBadge
          lastSuccessfulRun={lastSuccessfulRun}
          recentFailureCount={recentFailureCount}
        />
      </div>

      {/* Savings callout */}
      <div className="px-5 py-4 bg-[#e6f4ea] border-b border-[#ceead6]">
        <div className="flex items-baseline gap-2">
          <span className="text-[28px] font-semibold text-[#0d904f] tabular-nums">
            ${bundle.expected_yq_savings_usd.toFixed(0)}
          </span>
          <span className="text-[13px] text-[#0d904f]">
            YQ savings per roundtrip
          </span>
        </div>
        <p className="text-[12px] text-[#137333] mt-1">
          Avoiding {bundle.expected_yq_carrier} fuel surcharge
        </p>
      </div>

      {/* ITA Matrix one-click buttons + date picker */}
      <div className="px-5 py-4 border-b border-[#e8eaed] space-y-3">
        <span className="text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">
          Quick Search
        </span>
        <DatePickerRow departureDate={departureDate} setDepartureDate={setDepartureDate} />
        <ItaMatrixButtons bundle={bundle} departureDate={departureDateObj} />
      </div>

      {/* Fare Class Guidance */}
      <div className="px-5 py-4 border-b border-[#e8eaed]">
        <FareClassGuidance fareBasisHint={bundle.fare_basis_hint} />
      </div>

      {/* Routing code */}
      <div className="px-5 py-4 border-b border-[#e8eaed]">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">
            Routing Code
          </span>
          <CopyButton text={bundle.routing_code_string} label="Copy code" />
        </div>
        <div className="font-mono bg-[#f8f9fa] border border-[#e8eaed] rounded-md px-4 py-3 text-[15px] text-[#202124] select-all">
          {bundle.routing_code_string}
        </div>
        <p className="text-[13px] text-[#5f6368] mt-2">
          {bundle.human_description}
        </p>
      </div>

      {/* Strike Segment callout */}
      {bundle.strike_segment && (
        <div className="mx-5 mb-4 border border-amber-200 bg-amber-50 rounded-md px-4 py-3">
          <div className="text-[11px] font-semibold text-amber-700 uppercase tracking-wider mb-1.5">
            ⚡ Strike Segment Required
          </div>
          <p className="text-[13px] text-amber-900">
            Append{" "}
            <span className="font-mono font-semibold">
              {bundle.strike_segment.origin}→{bundle.strike_segment.destination}
            </span>{" "}
            on{" "}
            <span className="font-semibold">{bundle.strike_segment.carrier}</span>{" "}
            as a throwaway final leg — do not fly it.
          </p>
          {bundle.strike_segment.note && (
            <p className="text-[11px] text-amber-700 mt-1.5 leading-relaxed">
              {bundle.strike_segment.note}
            </p>
          )}
        </div>
      )}

      {/* Steps checklist */}
      <div className="px-5 py-4 border-b border-[#e8eaed]">
        <span className="text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">
          Steps
        </span>
        <ol className="mt-3 space-y-2">
          {bundle.ita_matrix_steps.map((step, i) => (
            <li
              key={i}
              onClick={() => toggleStep(i)}
              className={`flex items-start gap-3 px-3 py-2 rounded-md cursor-pointer transition-colors ${
                checkedSteps.has(i)
                  ? "bg-[#e6f4ea] text-[#5f6368]"
                  : "hover:bg-[#f8f9fa]"
              }`}
            >
              <div
                className={`mt-0.5 w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 transition-all ${
                  checkedSteps.has(i)
                    ? "bg-[#0d904f] border-[#0d904f]"
                    : "border-[#dadce0]"
                }`}
              >
                {checkedSteps.has(i) && (
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
              </div>
              <span
                className={`text-[13px] leading-relaxed ${
                  checkedSteps.has(i) ? "line-through" : "text-[#202124]"
                }`}
              >
                {step}
              </span>
            </li>
          ))}
        </ol>
      </div>

      {/* Validation info */}
      <div className="px-5 py-3 border-b border-[#e8eaed] flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <span className="text-[11px] text-[#80868b] uppercase tracking-wider">
              Confidence
            </span>
            <div className="mt-1">
              <ConfidenceBar score={bundle.confidence_score} />
            </div>
          </div>
          <div>
            <span className="text-[11px] text-[#80868b] uppercase tracking-wider">
              Validated
            </span>
            <p className="text-[13px] text-[#202124] mt-1">{timeAgo}</p>
          </div>
        </div>
      </div>

      {/* Backup routing */}
      {bundle.backup_routing_code && (
        <div className="px-5 py-3 border-b border-[#e8eaed]">
          <button
            onClick={() => setShowBackup(!showBackup)}
            className="flex items-center gap-2 text-[13px] text-[#e37400] hover:text-[#c56200] font-medium"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className={`transition-transform ${showBackup ? "rotate-90" : ""}`}
            >
              <polyline points="9 18 15 12 9 6" />
            </svg>
            If this fails... (backup routing)
          </button>
          {showBackup && (
            <div className="mt-3 animate-fade-in">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">
                  Backup Routing Code
                </span>
                <CopyButton text={bundle.backup_routing_code} label="Copy backup" />
              </div>
              <div className="font-mono bg-[#fef7e0] border border-[#fdd663] rounded-md px-4 py-3 text-[14px] text-[#202124] select-all">
                {bundle.backup_routing_code}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Notes */}
      {bundle.notes && (
        <div className="px-5 py-3">
          <span className="text-[11px] font-medium text-[#5f6368] uppercase tracking-wider">
            Notes
          </span>
          <p className="text-[13px] text-[#5f6368] mt-1 leading-relaxed">
            {bundle.notes}
          </p>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────

function buildScanEngineSteps(bundle: ManualInputBundleType): string[] {
  const segs = bundle.multi_city_segments ?? [];
  const dumpSeg = bundle.dump_segment;

  const steps: string[] = [
    "Go to matrix.itasoftware.com",
    'Click "Multi-city" at the top of the search form',
  ];

  segs.forEach((seg, i) => {
    const isDump = dumpSeg && seg.from === dumpSeg.from && seg.to === dumpSeg.to;
    const carrier = seg.carrier ? ` — constrain carrier to ${seg.carrier}` : "";
    const via = seg.via ? ` via ${seg.via}` : "";
    const tag = isDump ? " (DUMP leg — the key to triggering YQ drop)" : "";
    steps.push(`Leg ${i + 1}: ${seg.from} \u2192 ${seg.to}${via}${carrier}${tag}`);
  });

  if (bundle.baseline_routing) {
    steps.push(
      `Optional — first run as a roundtrip to get a baseline price. Routing code: ${bundle.baseline_routing}`
    );
  }

  if (bundle.optimized_routing) {
    steps.push(
      `In the routing codes field for the main leg, paste: ${bundle.optimized_routing}`
    );
  }

  steps.push(
    "Set cabin to Economy, choose flexible dates (+/- 3 days), then click Search",
    "In results, open the fare breakdown and look for YQ = $0 or significantly reduced",
    "If YQ still appears: try removing the routing code constraint and re-run (progressive constraint removal)",
    "Note the total price with and without the dump leg — the difference is your savings"
  );

  return steps;
}

/**
 * Derives and shows a fallback routing code by replacing "XX+" with "F?" (any carrier).
 * Only shown when the primary code contains a carrier+ constraint.
 * e.g. "LH+ FRA,MUC LH+" -> "F? FRA,MUC F?"
 *      "QR+ DOH QR+"     -> "F? DOH F?"
 */
function FallbackCode({ primary }: { primary: string }) {
  const [open, setOpen] = useState(false);

  // Only applicable if primary contains a carrier+ pattern
  if (!/[A-Z]{2}\+/.test(primary)) return null;

  const fallback = primary.replace(/[A-Z]{2}\+/g, "F?");
  if (fallback === primary) return null;

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-[11px] text-[#e37400] hover:text-[#c56200] font-medium flex items-center gap-1"
      >
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
          className={`transition-transform ${open ? "rotate-90" : ""}`}>
          <polyline points="9 18 15 12 9 6" />
        </svg>
        Zero results? Try fallback (any carrier, hub-constrained)
      </button>
      {open && (
        <div className="mt-1.5 flex items-center gap-2">
          <div className="font-mono bg-[#fef7e0] border border-[#fad56c] rounded-md px-3 py-2 text-[13px] text-[#5f3400] select-all flex-1">
            {fallback}
          </div>
          <CopyButton text={fallback} label="Copy" />
        </div>
      )}
    </div>
  );
}

function getTimeAgo(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

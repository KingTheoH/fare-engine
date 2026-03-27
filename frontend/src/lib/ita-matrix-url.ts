/**
 * ITA Matrix deep-link URL builder.
 *
 * Generates base64-encoded JSON URLs that pre-fill the ITA Matrix search form
 * with routing codes, extension codes, multi-city segments, and date flexibility.
 *
 * URL format: https://matrix.itasoftware.com/flights?search={base64_json}
 */

import type { ManualInputBundle } from "./types";

const ITA_BASE = "https://matrix.itasoftware.com/flights";

interface ItaSlice {
  origin: string[];
  dest: string[];
  routing: string;
  ext: string;
  dates: {
    departureDate: string;
    departureDateModifier?: string;
  };
}

interface ItaSearchPayload {
  type: string;
  slices: ItaSlice[];
  options: {
    cabin: string;
    stops: string;
    extraStops: string;
    allowAirportChanges: string;
    showOnlyAvailable: string;
    currency: { displayName: string; code: string };
  };
  pax: { adults: string };
  solution: { sessionId: null; td: boolean; nh: null; Oi: null };
}

const DEFAULT_OPTIONS: ItaSearchPayload["options"] = {
  cabin: "COACH",
  stops: "-1",
  extraStops: "1",
  allowAirportChanges: "true",
  showOnlyAvailable: "true",
  currency: { displayName: "United States Dollar (USD)", code: "USD" },
};

const DEFAULT_SOLUTION: ItaSearchPayload["solution"] = {
  sessionId: null,
  td: true,
  nh: null,
  Oi: null,
};

function encodePayload(payload: ItaSearchPayload): string {
  const json = JSON.stringify(payload);
  // btoa works in browser; for SSR we'd need Buffer but this is client-only
  const encoded = btoa(json);
  return `${ITA_BASE}?search=${encodeURIComponent(encoded)}`;
}

/** Format a Date as YYYY-MM-DD */
function formatDate(d: Date): string {
  return d.toISOString().split("T")[0];
}

/** Get a default departure date ~3 weeks from now */
function getDefaultDepartureDate(): Date {
  const d = new Date();
  d.setDate(d.getDate() + 21);
  return d;
}

/** Get dump segment date (departure + offset days) */
function getDumpDate(departureDate: Date, offsetDays: number = 5): Date {
  const d = new Date(departureDate);
  d.setDate(d.getDate() + offsetDays);
  return d;
}

/**
 * Build a multi-city dump search URL for ITA Matrix.
 *
 * Creates a multi-city search with:
 * - Leg 1: origin → destination with routing code + ±2 day flex
 * - Leg 2: dump segment (no routing code)
 *
 * Note: ext is always "" — ITA Matrix rejects all command-line prefix syntax
 * (/f, +f, bc=). Booking class filtering is handled in the app pipeline.
 */
export function buildDumpSearchUrl(
  bundle: ManualInputBundle,
  departureDate?: Date,
  dumpOffsetDays: number = 5
): string | null {
  const segments = bundle.multi_city_segments;
  const origin = bundle.origin_iata ?? segments?.[0]?.from;
  const destination = bundle.origin_iata ? bundle.destination_iata : segments?.[0]?.to;
  const dumpSeg = bundle.dump_segment;

  if (!origin || !destination || !dumpSeg) return null;

  const depDate = departureDate ?? getDefaultDepartureDate();
  const dmpDate = getDumpDate(depDate, dumpOffsetDays);

  const routingCode = bundle.optimized_routing ?? bundle.baseline_routing ?? "";

  const slices: ItaSlice[] = [
    {
      origin: [origin],
      dest: [destination],
      routing: routingCode,
      ext: "",
      dates: {
        departureDate: formatDate(depDate),
        departureDateModifier: "22", // ±2 days
      },
    },
    {
      origin: [dumpSeg.from],
      dest: [dumpSeg.to],
      routing: "",
      ext: "",
      dates: {
        departureDate: formatDate(dmpDate),
      },
    },
  ];

  const payload: ItaSearchPayload = {
    type: "multi-city",
    slices,
    options: DEFAULT_OPTIONS,
    pax: { adults: "1" },
    solution: DEFAULT_SOLUTION,
  };

  return encodePayload(payload);
}

/**
 * Build a round-trip baseline search URL for price comparison.
 *
 * Uses the baseline routing code on both slices so users can see
 * the "normal" price before applying the dump.
 */
export function buildBaselineSearchUrl(
  bundle: ManualInputBundle,
  departureDate?: Date,
  returnOffsetDays: number = 10
): string | null {
  const origin = bundle.origin_iata ?? bundle.multi_city_segments?.[0]?.from;
  const destination = bundle.destination_iata ?? bundle.multi_city_segments?.[0]?.to;

  if (!origin || !destination) return null;

  const depDate = departureDate ?? getDefaultDepartureDate();
  const retDate = getDumpDate(depDate, returnOffsetDays);

  const routingCode = bundle.baseline_routing ?? bundle.optimized_routing ?? bundle.routing_code_string ?? "";

  const slices: ItaSlice[] = [
    {
      origin: [origin],
      dest: [destination],
      routing: routingCode,
      ext: "",
      dates: {
        departureDate: formatDate(depDate),
        departureDateModifier: "22",
      },
    },
    {
      origin: [destination],
      dest: [origin],
      routing: routingCode,
      ext: "",
      dates: {
        departureDate: formatDate(retDate),
      },
    },
  ];

  const payload: ItaSearchPayload = {
    type: "multi-city",
    slices,
    options: DEFAULT_OPTIONS,
    pax: { adults: "1" },
    solution: DEFAULT_SOLUTION,
  };

  return encodePayload(payload);
}

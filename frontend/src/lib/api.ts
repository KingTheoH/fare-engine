/**
 * Typed API client for the Fare Construction Engine backend.
 *
 * All calls go to /api/v1/* (proxied to FastAPI backend via Next.js rewrites).
 * X-API-Key header from NEXT_PUBLIC_API_KEY env var.
 */

import type {
  CarrierResponse,
  DumpPatternResponse,
  DumpPatternSummary,
  ManualInputBundle,
  PaginatedResponse,
  PatternFilters,
  ValidationRunResponse,
} from "./types";

const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "dev_key_change_in_production";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || body.message || `API error: ${res.status}`);
  }

  return res.json();
}

function buildQuery(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== ""
  );
  if (entries.length === 0) return "";
  return "?" + entries.map(([k, v]) => `${k}=${encodeURIComponent(v!)}`).join("&");
}

// ─── Patterns ───────────────────────────────────────────────────────────

export async function getPatterns(
  filters: PatternFilters = {}
): Promise<PaginatedResponse<DumpPatternSummary>> {
  const query = buildQuery({
    origin: filters.origin,
    destination: filters.destination,
    dump_type: filters.dump_type,
    carrier: filters.carrier,
    min_confidence: filters.min_confidence,
    min_savings_usd: filters.min_savings_usd,
    page: filters.page,
    page_size: filters.page_size,
  });
  return apiFetch(`/api/v1/patterns${query}`);
}

export async function getPattern(id: string): Promise<DumpPatternResponse> {
  return apiFetch(`/api/v1/patterns/${id}`);
}

export async function getManualInput(id: string): Promise<ManualInputBundle> {
  return apiFetch(`/api/v1/patterns/${id}/manual-input`);
}

// ─── Carriers ───────────────────────────────────────────────────────────

export async function getCarriers(
  params: { charges_yq?: boolean; page?: number; page_size?: number } = {}
): Promise<PaginatedResponse<CarrierResponse>> {
  const query = buildQuery({
    charges_yq: params.charges_yq?.toString(),
    page: params.page,
    page_size: params.page_size,
  });
  return apiFetch(`/api/v1/carriers${query}`);
}

// ─── Validations ────────────────────────────────────────────────────────

export async function getValidationHistory(
  patternId: string,
  params: { page?: number; page_size?: number } = {}
): Promise<PaginatedResponse<ValidationRunResponse>> {
  const query = buildQuery({ page: params.page, page_size: params.page_size });
  return apiFetch(`/api/v1/validations/${patternId}/history${query}`);
}

export async function getRecentValidations(
  period: "24h" | "7d" | "30d" = "7d"
): Promise<PaginatedResponse<ValidationRunResponse>> {
  return apiFetch(`/api/v1/validations?period=${period}&page_size=100`);
}

export async function triggerValidation(
  patternId: string
): Promise<{ status: string; task_id: string; pattern_id: string }> {
  return apiFetch(`/api/v1/validations/trigger/${patternId}`, {
    method: "POST",
  });
}

// ─── Scan Targets ────────────────────────────────────────────────────────

export async function getScanTargets(
  params: { tier?: number; enabled?: boolean; page?: number; page_size?: number } = {}
): Promise<import("./types").PaginatedResponse<import("./types").ScanTargetResponse>> {
  const query = buildQuery({
    tier: params.tier,
    enabled: params.enabled?.toString(),
    page: params.page,
    page_size: params.page_size,
  });
  return apiFetch(`/api/v1/scan-targets${query}`);
}

// ─── Dump Candidates ─────────────────────────────────────────────────────

export async function getDumpCandidates(
  params: { enabled?: boolean; page?: number; page_size?: number } = {}
): Promise<import("./types").PaginatedResponse<import("./types").DumpCandidateResponse>> {
  const query = buildQuery({
    enabled: params.enabled?.toString(),
    page: params.page,
    page_size: params.page_size,
  });
  return apiFetch(`/api/v1/dump-candidates${query}`);
}

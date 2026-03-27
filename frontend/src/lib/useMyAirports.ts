"use client";

import { useState, useEffect, useCallback } from "react";
import { DEFAULT_MY_AIRPORTS } from "./mock-data";

const STORAGE_KEY = "fare-engine-my-airports";

function load(): string[] {
  if (typeof window === "undefined") return DEFAULT_MY_AIRPORTS;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch {}
  return DEFAULT_MY_AIRPORTS;
}

export function useMyAirports() {
  const [airports, setAirports] = useState<string[]>(DEFAULT_MY_AIRPORTS);

  useEffect(() => {
    setAirports(load());
  }, []);

  const save = useCallback((next: string[]) => {
    setAirports(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }, []);

  const add = useCallback(
    (code: string) => {
      const upper = code.toUpperCase().trim();
      if (!upper || airports.includes(upper)) return;
      save([...airports, upper]);
    },
    [airports, save]
  );

  const remove = useCallback(
    (code: string) => {
      save(airports.filter((a) => a !== code.toUpperCase()));
    },
    [airports, save]
  );

  const reset = useCallback(() => {
    save(DEFAULT_MY_AIRPORTS);
  }, [save]);

  return { airports, add, remove, reset };
}

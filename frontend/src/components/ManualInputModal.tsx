"use client";

import { useEffect } from "react";
import type { ManualInputBundle as ManualInputBundleType } from "@/lib/types";
import ManualInputBundle from "./ManualInputBundle";

export default function ManualInputModal({
  bundle,
  route,
  onClose,
}: {
  bundle: ManualInputBundleType;
  route: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-12 bg-black/40"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-[520px] max-h-[calc(100vh-96px)] overflow-y-auto rounded-xl shadow-2xl animate-fade-in">
        <div className="bg-white rounded-t-xl px-5 py-3 border-b border-[#dadce0] flex items-center justify-between sticky top-0 z-10">
          <span className="text-[14px] font-medium text-[#202124]">
            {route}
          </span>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-[#f1f3f4] transition-colors text-[#5f6368]"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <ManualInputBundle bundle={bundle} />
      </div>
    </div>
  );
}

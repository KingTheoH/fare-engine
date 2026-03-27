"use client";

export interface LastWorkingInfo {
  date: string;
  basePrice: number;
  yqCharged: number;
}

export default function LastWorkingBadge({
  lastSuccessfulRun,
  recentFailureCount = 0,
}: {
  lastSuccessfulRun?: LastWorkingInfo | null;
  recentFailureCount?: number;
}) {
  // No history at all
  if (!lastSuccessfulRun) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 bg-[#f1f3f4] border border-[#dadce0] rounded-lg">
        <div className="w-2 h-2 rounded-full bg-[#80868b]" />
        <span className="text-[12px] text-[#5f6368]">Not yet validated</span>
      </div>
    );
  }

  const date = new Date(lastSuccessfulRun.date);
  const dateStr = date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
  const daysSince = Math.floor(
    (Date.now() - date.getTime()) / (1000 * 60 * 60 * 24)
  );

  // Warning state: 3+ consecutive failures
  if (recentFailureCount >= 3) {
    return (
      <div className="space-y-1.5">
        <div className="flex items-center gap-2 px-3 py-2 bg-[#e6f4ea] border border-[#ceead6] rounded-lg">
          <div className="w-2 h-2 rounded-full bg-[#0d904f]" />
          <span className="text-[12px] text-[#137333]">
            Last success: {dateStr} &mdash; ${lastSuccessfulRun.basePrice} base,
            ${lastSuccessfulRun.yqCharged} YQ
          </span>
        </div>
        <div className="flex items-center gap-2 px-3 py-2 bg-[#fef7e0] border border-[#f9d67a] rounded-lg">
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#e37400"
            strokeWidth="2"
          >
            <path d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span className="text-[12px] text-[#e37400] font-medium">
            {recentFailureCount} consecutive failures &mdash; try different
            dates or check fare availability
          </span>
        </div>
      </div>
    );
  }

  // Healthy state
  const freshness =
    daysSince <= 3 ? "text-[#0d904f]" : daysSince <= 7 ? "text-[#e37400]" : "text-[#5f6368]";

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-[#e6f4ea] border border-[#ceead6] rounded-lg">
      <div className="w-2 h-2 rounded-full bg-[#0d904f]" />
      <span className={`text-[12px] ${freshness}`}>
        Last success: {dateStr} &mdash; ${lastSuccessfulRun.basePrice} base, $
        {lastSuccessfulRun.yqCharged} YQ
      </span>
      {daysSince <= 3 && (
        <span className="px-1.5 py-0.5 bg-[#ceead6] text-[#0d904f] text-[10px] font-medium rounded">
          Fresh
        </span>
      )}
    </div>
  );
}

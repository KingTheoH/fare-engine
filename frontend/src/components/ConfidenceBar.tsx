export default function ConfidenceBar({
  score,
  showLabel = true,
}: {
  score: number;
  showLabel?: boolean;
}) {
  const pct = Math.round(score * 100);
  const color =
    score >= 0.75
      ? "bg-[#0d904f]"
      : score >= 0.4
      ? "bg-[#e37400]"
      : "bg-[#c5221f]";

  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-[#e8eaed] rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-[12px] text-[#5f6368] tabular-nums">{pct}%</span>
      )}
    </div>
  );
}

const LABELS: Record<string, string> = {
  TP_DUMP: "TP Dump",
  CARRIER_SWITCH: "Carrier Switch",
  FARE_BASIS: "Fare Basis",
  ALLIANCE_RULE: "Alliance Rule",
};

const COLORS: Record<string, string> = {
  TP_DUMP: "bg-[#e8f0fe] text-[#1a73e8]",
  CARRIER_SWITCH: "bg-[#fce8e6] text-[#c5221f]",
  FARE_BASIS: "bg-[#fef7e0] text-[#e37400]",
  ALLIANCE_RULE: "bg-[#e6f4ea] text-[#0d904f]",
};

export default function DumpTypeBadge({ type }: { type: string }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium tracking-wide ${
        COLORS[type] || "bg-[#f1f3f4] text-[#5f6368]"
      }`}
    >
      {LABELS[type] || type}
    </span>
  );
}

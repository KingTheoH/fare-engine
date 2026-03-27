const STYLES: Record<string, string> = {
  active: "bg-[#e6f4ea] text-[#0d904f]",
  degrading: "bg-[#fef7e0] text-[#e37400]",
  deprecated: "bg-[#fce8e6] text-[#c5221f]",
  archived: "bg-[#f1f3f4] text-[#80868b]",
  discovered: "bg-[#e8f0fe] text-[#1a73e8]",
};

export default function LifecycleBadge({ state }: { state: string }) {
  const style = STYLES[state] || STYLES.archived;
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium uppercase tracking-wider ${style}`}
    >
      {state}
    </span>
  );
}

const STYLES: Record<string, string> = {
  SUPPORTED: "bg-emerald-100 text-emerald-800 border-emerald-300",
  REFUTED: "bg-red-100 text-red-800 border-red-300",
  NOT_ENOUGH_INFORMATION: "bg-amber-100 text-amber-800 border-amber-300",
};

const LABELS: Record<string, string> = {
  SUPPORTED: "SUPPORTED",
  REFUTED: "REFUTED",
  NOT_ENOUGH_INFORMATION: "NOT ENOUGH INFO",
};

export default function VerdictBadge({ verdict, large }: { verdict: string; large?: boolean }) {
  const cls = STYLES[verdict] ?? "bg-slate-100 text-slate-700 border-slate-300";
  return (
    <span
      className={`inline-flex items-center rounded-full border font-semibold tracking-wide ${
        large ? "px-4 py-1.5 text-sm" : "px-2.5 py-0.5 text-xs"
      } ${cls}`}
    >
      {LABELS[verdict] ?? verdict}
    </span>
  );
}

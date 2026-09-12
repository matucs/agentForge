const STATUS_STYLES: Record<string, string> = {
  completed: "bg-emerald-950 text-emerald-300 border-emerald-800",
  approved: "bg-emerald-950 text-emerald-300 border-emerald-800",
  running: "bg-sky-950 text-sky-300 border-sky-800",
  pending: "bg-slate-800 text-slate-300 border-slate-700",
  awaiting_approval: "bg-amber-950 text-amber-300 border-amber-800",
  failed: "bg-rose-950 text-rose-300 border-rose-800",
  blocked: "bg-rose-950 text-rose-300 border-rose-800",
  rejected: "bg-rose-950 text-rose-300 border-rose-800",
  cancelled: "bg-slate-800 text-slate-400 border-slate-700",
  stopped_by_timeout: "bg-rose-950 text-rose-300 border-rose-800",
  stopped_by_budget: "bg-rose-950 text-rose-300 border-rose-800",
};

export function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? "bg-slate-800 text-slate-300 border-slate-700";
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${style}`}
    >
      {status.replaceAll("_", " ")}
    </span>
  );
}

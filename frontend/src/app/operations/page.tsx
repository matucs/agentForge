"use client";

import { useEffect, useState } from "react";
import { fetchOperationsSummary, type OperationsSummary } from "@/lib/api";

export default function OperationsPage() {
  const [summary, setSummary] = useState<OperationsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await fetchOperationsSummary();
        if (!cancelled) {
          setSummary(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load");
      }
    }
    load();
    const interval = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Operations</h1>
      <p className="mt-1 text-sm text-slate-400">
        Every figure below is computed live from the database — see also{" "}
        <code className="text-slate-300">GET /api/metrics</code> (Prometheus
        format) for scraping.
      </p>

      {error && <p className="mt-4 text-sm text-rose-400">{error}</p>}

      {summary && (
        <>
          <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
            <Stat label="Runs today" value={summary.runs_today} />
            <Stat label="Runs total" value={summary.runs_total} />
            <Stat
              label="Success rate"
              value={
                summary.success_rate != null
                  ? `${(summary.success_rate * 100).toFixed(1)}%`
                  : "—"
              }
            />
            <Stat
              label="Avg duration"
              value={
                summary.avg_duration_seconds != null
                  ? `${summary.avg_duration_seconds.toFixed(1)}s`
                  : "—"
              }
            />
            <Stat
              label="Avg cost"
              value={
                summary.avg_estimated_cost_usd != null
                  ? `$${summary.avg_estimated_cost_usd.toFixed(4)}`
                  : "—"
              }
            />
            <Stat label="Verification failures" value={summary.verification_failures} />
            <Stat label="Approvals pending" value={summary.human_approvals_pending} />
            <Stat label="Approvals total" value={summary.human_approvals_total} />
          </div>

          <div className="mt-6 rounded-xl border border-slate-800 bg-slate-900 p-5">
            <h2 className="text-sm font-medium text-slate-300">Runs by status</h2>
            <div className="mt-3 space-y-2">
              {Object.entries(summary.runs_by_status).map(([status, count]) => (
                <div key={status} className="flex items-center gap-3">
                  <span className="w-40 shrink-0 text-xs text-slate-400">
                    {status.replaceAll("_", " ")}
                  </span>
                  <div className="h-2 flex-1 rounded-full bg-slate-800">
                    <div
                      className="h-2 rounded-full bg-sky-600"
                      style={{
                        width: summary.runs_total
                          ? `${(count / summary.runs_total) * 100}%`
                          : "0%",
                      }}
                    />
                  </div>
                  <span className="w-8 text-right text-xs text-slate-400">{count}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-100">{value}</p>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  fetchOperationsSummary,
  listRuns,
  type OperationsSummary,
  type Run,
} from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";

export function OverviewPanel() {
  const [summary, setSummary] = useState<OperationsSummary | null>(null);
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [summaryData, runsData] = await Promise.all([
          fetchOperationsSummary(),
          listRuns(),
        ]);
        if (!cancelled) {
          setSummary(summaryData);
          setRuns(runsData.slice(0, 8));
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Backend unreachable");
        }
      }
    }

    load();
    const interval = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (error) {
    return (
      <div className="rounded-xl border border-rose-900 bg-rose-950/40 p-6 text-rose-300">
        Integration unavailable — the backend is not reachable at{" "}
        {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}.
        <p className="mt-2 text-xs text-rose-400">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Runs today" value={summary?.runs_today ?? "—"} />
        <Stat
          label="Success rate"
          value={
            summary?.success_rate != null
              ? `${(summary.success_rate * 100).toFixed(0)}%`
              : "—"
          }
        />
        <Stat
          label="Avg duration"
          value={
            summary?.avg_duration_seconds != null
              ? `${summary.avg_duration_seconds.toFixed(1)}s`
              : "—"
          }
        />
        <Stat
          label="Avg cost"
          value={
            summary?.avg_estimated_cost_usd != null
              ? `$${summary.avg_estimated_cost_usd.toFixed(3)}`
              : "—"
          }
        />
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900">
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-3">
          <h2 className="text-sm font-medium text-slate-300">Recent runs</h2>
          <Link href="/runs" className="text-xs text-slate-400 hover:text-slate-200">
            View all →
          </Link>
        </div>
        {runs === null ? (
          <p className="px-5 py-6 text-sm text-slate-500">Loading…</p>
        ) : runs.length === 0 ? (
          <p className="px-5 py-6 text-sm text-slate-500">
            No runs yet — create a task and start one from the Tasks page.
          </p>
        ) : (
          <ul className="divide-y divide-slate-800">
            {runs.map((run) => (
              <li key={run.id} className="flex items-center justify-between px-5 py-3">
                <Link
                  href={`/runs/${run.id}`}
                  className="font-mono text-xs text-slate-400 hover:text-slate-200"
                >
                  {run.id.slice(0, 8)}
                </Link>
                <StatusBadge status={run.status} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
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

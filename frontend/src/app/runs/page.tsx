"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listRuns, listTasks, type Run, type Task } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";

const STATUS_OPTIONS = [
  "",
  "pending",
  "running",
  "completed",
  "failed",
  "blocked",
  "awaiting_approval",
  "rejected",
  "cancelled",
  "stopped_by_timeout",
  "stopped_by_budget",
];

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [status, setStatus] = useState("");
  const [taskId, setTaskId] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listTasks().then(setTasks).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setRuns(null);
    listRuns({ status: status || undefined, task_id: taskId || undefined })
      .then((data) => {
        if (!cancelled) setRuns(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load runs");
      });
    return () => {
      cancelled = true;
    };
  }, [status, taskId]);

  const taskTitleById = Object.fromEntries(tasks.map((t) => [t.id, t.title]));

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Runs</h1>

      <div className="mt-6 flex flex-wrap gap-3">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-200"
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s === "" ? "All statuses" : s.replaceAll("_", " ")}
            </option>
          ))}
        </select>
        <select
          value={taskId}
          onChange={(e) => setTaskId(e.target.value)}
          className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm text-slate-200"
        >
          <option value="">All tasks</option>
          {tasks.map((t) => (
            <option key={t.id} value={t.id}>
              {t.title}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="mt-4 text-sm text-rose-400">{error}</p>}

      <div className="mt-6 overflow-x-auto rounded-xl border border-slate-800 bg-slate-900">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Run</th>
              <th className="px-4 py-3">Task</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Cost</th>
              <th className="px-4 py-3">Iterations</th>
              <th className="px-4 py-3">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {runs === null ? (
              <tr>
                <td className="px-4 py-6 text-slate-500" colSpan={6}>
                  Loading…
                </td>
              </tr>
            ) : runs.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-slate-500" colSpan={6}>
                  No runs match these filters.
                </td>
              </tr>
            ) : (
              runs.map((run) => (
                <tr key={run.id} className="hover:bg-slate-800/40">
                  <td className="px-4 py-3">
                    <Link
                      href={`/runs/${run.id}`}
                      className="font-mono text-xs text-sky-400 hover:underline"
                    >
                      {run.id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-300">
                    {taskTitleById[run.task_id] ?? run.task_id.slice(0, 8)}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-3 text-slate-400">
                    ${run.estimated_cost_usd.toFixed(4)}
                  </td>
                  <td className="px-4 py-3 text-slate-400">{run.iteration_count}</td>
                  <td className="px-4 py-3 text-slate-500">
                    {new Date(run.created_at).toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}

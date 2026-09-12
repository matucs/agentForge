"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createRun, getTask, listRuns, startRun, type Run, type Task } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";

export function TaskDetail({ taskId }: { taskId: string }) {
  const [task, setTask] = useState<Task | null>(null);
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  async function refresh() {
    const [taskData, runsData] = await Promise.all([
      getTask(taskId),
      listRuns({ task_id: taskId }),
    ]);
    setTask(taskData);
    setRuns(runsData);
  }

  useEffect(() => {
    refresh().catch((err) =>
      setError(err instanceof Error ? err.message : "Failed to load task"),
    );
  }, [taskId]);

  async function handleNewRun() {
    setCreating(true);
    setError(null);
    try {
      const run = await createRun(taskId);
      await startRun(run.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start a new run");
    } finally {
      setCreating(false);
    }
  }

  if (error && !task) {
    return (
      <main className="mx-auto max-w-6xl px-6 py-10">
        <p className="text-rose-400">{error}</p>
      </main>
    );
  }

  if (!task) {
    return (
      <main className="mx-auto max-w-6xl px-6 py-10">
        <p className="text-slate-500">Loading…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <Link href="/tasks" className="text-xs text-slate-500 hover:text-slate-300">
        ← Tasks
      </Link>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-xl font-semibold text-slate-100">{task.title}</h1>
        <button
          onClick={handleNewRun}
          disabled={creating}
          className="rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
        >
          {creating ? "Starting…" : "Start new run"}
        </button>
      </div>

      <div className="mt-4 rounded-xl border border-slate-800 bg-slate-900 p-4">
        <p className="text-xs uppercase tracking-wide text-slate-500">Requirement</p>
        <p className="mt-1 whitespace-pre-wrap text-sm text-slate-300">{task.requirement_text}</p>
      </div>

      {error && <p className="mt-4 text-sm text-rose-400">{error}</p>}

      <h2 className="mt-6 text-sm font-medium text-slate-300">Runs</h2>
      <div className="mt-2 overflow-x-auto rounded-xl border border-slate-800 bg-slate-900">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Run</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Cost</th>
              <th className="px-4 py-3">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {runs === null ? (
              <tr>
                <td className="px-4 py-6 text-slate-500" colSpan={4}>
                  Loading…
                </td>
              </tr>
            ) : runs.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-slate-500" colSpan={4}>
                  No runs for this task yet.
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
                  <td className="px-4 py-3">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-3 text-slate-400">
                    ${run.estimated_cost_usd.toFixed(4)}
                  </td>
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

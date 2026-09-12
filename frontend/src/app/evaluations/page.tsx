"use client";

import { useEffect, useState } from "react";
import { listEvaluations, type Evaluation } from "@/lib/api";

export default function EvaluationsPage() {
  const [evaluations, setEvaluations] = useState<Evaluation[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listEvaluations()
      .then(setEvaluations)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load evaluations"),
      );
  }, []);

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Evaluations</h1>
      <p className="mt-1 text-sm text-slate-400">
        Results from <code className="text-slate-300">make eval</code> — real
        pipeline runs against the task definitions in{" "}
        <code className="text-slate-300">evals/tasks/</code>.
      </p>

      {error && <p className="mt-4 text-sm text-rose-400">{error}</p>}

      <div className="mt-6 overflow-x-auto rounded-xl border border-slate-800 bg-slate-900">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Task</th>
              <th className="px-4 py-3">Runs</th>
              <th className="px-4 py-3">Success</th>
              <th className="px-4 py-3">Avg duration</th>
              <th className="px-4 py-3">Avg cost</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {evaluations === null ? (
              <tr>
                <td className="px-4 py-6 text-slate-500" colSpan={5}>
                  Loading…
                </td>
              </tr>
            ) : evaluations.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-slate-500" colSpan={5}>
                  No evaluation runs yet — run{" "}
                  <code className="text-slate-400">make eval</code> (requires an
                  ANTHROPIC_API_KEY or OPENAI_API_KEY configured on the backend).
                </td>
              </tr>
            ) : (
              evaluations.map((evaluation) => (
                <tr key={evaluation.id} className="hover:bg-slate-800/40">
                  <td className="px-4 py-3 text-slate-200">{evaluation.name}</td>
                  <td className="px-4 py-3 text-slate-400">{evaluation.run_count}</td>
                  <td className="px-4 py-3 text-slate-400">
                    {evaluation.run_count > 0
                      ? `${evaluation.success_count}/${evaluation.run_count}`
                      : "—"}
                  </td>
                  <td className="px-4 py-3 text-slate-400">
                    {evaluation.avg_duration_seconds != null
                      ? `${evaluation.avg_duration_seconds.toFixed(1)}s`
                      : "—"}
                  </td>
                  <td className="px-4 py-3 text-slate-400">
                    {evaluation.avg_estimated_cost_usd != null
                      ? `$${evaluation.avg_estimated_cost_usd.toFixed(4)}`
                      : "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <p className="mt-4 text-xs text-slate-500">
        Reviewer/QA/Security detection-rate accuracy is not shown here yet —
        computing it honestly requires a task with a known injected bug to
        check detection against (Phase 10's failure-injection harness), not
        invented percentages.
      </p>
    </main>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  cancelRun,
  listRunArtifacts,
  listRunEvents,
  listRunReviews,
  listRunSecurityFindings,
  listRunTestResults,
  listRunToolCalls,
  listRunVerificationResults,
  getRun,
  startRun,
  type AgentMessage,
  type Artifact,
  type Review,
  type Run,
  type SecurityFinding,
  type TestResult,
  type ToolCall,
  type VerificationResult,
} from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";

const ACTIVE_STATUSES = new Set(["pending", "running"]);

interface RunData {
  run: Run;
  events: AgentMessage[];
  artifacts: Artifact[];
  reviews: Review[];
  testResults: TestResult[];
  securityFindings: SecurityFinding[];
  verificationResults: VerificationResult[];
  toolCalls: ToolCall[];
}

export function RunDetail({ runId }: { runId: string }) {
  const [data, setData] = useState<RunData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [run, events, artifacts, reviews, testResults, securityFindings, verificationResults, toolCalls] =
        await Promise.all([
          getRun(runId),
          listRunEvents(runId),
          listRunArtifacts(runId),
          listRunReviews(runId),
          listRunTestResults(runId),
          listRunSecurityFindings(runId),
          listRunVerificationResults(runId),
          listRunToolCalls(runId),
        ]);
      setData({ run, events, artifacts, reviews, testResults, securityFindings, verificationResults, toolCalls });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load run");
    }
  }, [runId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!data || !ACTIVE_STATUSES.has(data.run.status)) return;
    const interval = setInterval(load, 2000);
    return () => clearInterval(interval);
  }, [data, load]);

  if (error) {
    return (
      <main className="mx-auto max-w-6xl px-6 py-10">
        <p className="text-rose-400">{error}</p>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="mx-auto max-w-6xl px-6 py-10">
        <p className="text-slate-500">Loading…</p>
      </main>
    );
  }

  const { run, events, artifacts, reviews, testResults, securityFindings, verificationResults, toolCalls } = data;

  async function handleStart() {
    setActionError(null);
    try {
      await startRun(runId);
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to start run");
    }
  }

  async function handleCancel() {
    setActionError(null);
    try {
      await cancelRun(runId);
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to cancel run");
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <Link href="/runs" className="text-xs text-slate-500 hover:text-slate-300">
        ← Runs
      </Link>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-mono text-lg text-slate-100">{run.id}</h1>
          <Link href={`/tasks/${run.task_id}`} className="text-xs text-slate-500 hover:text-slate-300">
            Task {run.task_id.slice(0, 8)}
          </Link>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={run.status} />
          {run.status === "pending" && (
            <button
              onClick={handleStart}
              className="rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-500"
            >
              Start
            </button>
          )}
          {run.status === "running" && (
            <button
              onClick={handleCancel}
              className="rounded-md bg-rose-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-rose-600"
            >
              Cancel
            </button>
          )}
        </div>
      </div>
      {actionError && <p className="mt-2 text-sm text-rose-400">{actionError}</p>}

      <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Iterations" value={run.iteration_count} />
        <Stat label="Cost" value={`$${run.estimated_cost_usd.toFixed(4)}`} />
        <Stat label="Input tokens" value={run.total_input_tokens} />
        <Stat label="Output tokens" value={run.total_output_tokens} />
      </div>

      <Section title="Agent timeline">
        {events.length === 0 ? (
          <Empty text="No agent events yet." />
        ) : (
          <ul className="divide-y divide-slate-800">
            {events.map((event) => (
              <li key={event.id} className="px-4 py-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-slate-500">
                    {new Date(event.created_at).toLocaleTimeString()}
                  </span>
                  <span className="text-xs text-slate-400">
                    {event.from_agent} → {event.to_agent}
                  </span>
                </div>
                <p className="mt-1 font-medium text-slate-200">{event.type}</p>
                <pre className="mt-1 overflow-x-auto rounded bg-slate-950 p-2 text-xs text-slate-500">
                  {JSON.stringify(event.payload, null, 2)}
                </pre>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Artifacts">
        {artifacts.length === 0 ? (
          <Empty text="No artifacts yet." />
        ) : (
          <ul className="divide-y divide-slate-800">
            {artifacts.map((a) => (
              <li key={a.id} className="px-4 py-3 text-sm">
                <p className="font-medium text-slate-200">
                  {a.type} <span className="text-slate-500">by {a.produced_by}</span>
                </p>
                <pre className="mt-1 max-h-64 overflow-auto rounded bg-slate-950 p-2 text-xs text-slate-500">
                  {JSON.stringify(a.content, null, 2)}
                </pre>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Reviewer findings">
        {reviews.length === 0 ? (
          <Empty text="No review findings." />
        ) : (
          <ul className="divide-y divide-slate-800">
            {reviews.map((r) => (
              <li key={r.id} className="px-4 py-3 text-sm">
                <span
                  className={`mr-2 rounded px-1.5 py-0.5 text-xs ${
                    r.severity === "high"
                      ? "bg-rose-950 text-rose-300"
                      : r.severity === "medium"
                        ? "bg-amber-950 text-amber-300"
                        : "bg-slate-800 text-slate-400"
                  }`}
                >
                  {r.severity}
                </span>
                {r.file && <span className="text-slate-500">{r.file}:{r.line ?? "?"} — </span>}
                {r.finding}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Test results">
        {testResults.length === 0 ? (
          <Empty text="No test results." />
        ) : (
          <ul className="divide-y divide-slate-800">
            {testResults.map((t) => (
              <li key={t.id} className="px-4 py-3 text-sm">
                <span className={t.passed ? "text-emerald-400" : "text-rose-400"}>
                  {t.passed ? "PASSED" : "FAILED"}
                </span>{" "}
                <span className="text-slate-400">
                  {t.suite} ({t.duration_seconds.toFixed(2)}s)
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Security findings">
        {securityFindings.length === 0 ? (
          <Empty text="No security findings." />
        ) : (
          <ul className="divide-y divide-slate-800">
            {securityFindings.map((s) => (
              <li key={s.id} className="px-4 py-3 text-sm">
                <span
                  className={`mr-2 rounded px-1.5 py-0.5 text-xs ${
                    s.blocking ? "bg-rose-950 text-rose-300" : "bg-slate-800 text-slate-400"
                  }`}
                >
                  {s.severity}
                </span>
                {s.category} — {s.detail}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Verification gate">
        {verificationResults.length === 0 ? (
          <Empty text="No verification results." />
        ) : (
          <ul className="divide-y divide-slate-800">
            {verificationResults.map((v) => (
              <li key={v.id} className="flex items-center justify-between px-4 py-3 text-sm">
                <span className="text-slate-300">{v.gate}</span>
                <span className={v.passed ? "text-emerald-400" : "text-rose-400"}>
                  {v.passed ? "PASS" : "BLOCK"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Tool calls (agent duration)">
        {toolCalls.length === 0 ? (
          <Empty text="No tool calls recorded." />
        ) : (
          <ul className="divide-y divide-slate-800">
            {toolCalls.map((tc) => (
              <li key={tc.id} className="flex items-center justify-between px-4 py-3 text-sm">
                <span className="text-slate-300">{tc.agent}</span>
                <span className={tc.succeeded ? "text-emerald-400" : "text-rose-400"}>
                  {tc.duration_seconds.toFixed(3)}s {tc.succeeded ? "ok" : "failed"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-100">{value}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-6 rounded-xl border border-slate-800 bg-slate-900">
      <h2 className="border-b border-slate-800 px-4 py-3 text-sm font-medium text-slate-300">
        {title}
      </h2>
      {children}
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="px-4 py-6 text-sm text-slate-500">{text}</p>;
}

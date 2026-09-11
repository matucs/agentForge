"use client";

import { useEffect, useState } from "react";
import { fetchHealth, type HealthResponse } from "@/lib/api";

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; data: HealthResponse };

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${
        ok ? "bg-emerald-400" : "bg-rose-500"
      }`}
    />
  );
}

export function HealthPanel() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await fetchHealth();
        if (!cancelled) setState({ kind: "ready", data });
      } catch (err) {
        if (!cancelled) {
          setState({
            kind: "error",
            message:
              err instanceof Error
                ? err.message
                : "Backend unreachable at " +
                  (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"),
          });
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

  return (
    <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-lg">
      <h2 className="text-sm font-medium uppercase tracking-wide text-slate-400">
        System status
      </h2>

      {state.kind === "loading" && (
        <p className="mt-4 text-slate-500">Checking backend…</p>
      )}

      {state.kind === "error" && (
        <div className="mt-4 space-y-1">
          <p className="flex items-center gap-2 text-rose-400">
            <StatusDot ok={false} /> Integration unavailable
          </p>
          <p className="text-xs text-slate-500">{state.message}</p>
        </div>
      )}

      {state.kind === "ready" && (
        <dl className="mt-4 space-y-3 text-sm">
          <div className="flex items-center justify-between">
            <dt className="text-slate-400">Overall</dt>
            <dd className="flex items-center gap-2 font-medium">
              <StatusDot ok={state.data.status === "healthy"} />
              {state.data.status}
            </dd>
          </div>
          <div className="flex items-center justify-between">
            <dt className="text-slate-400">Database</dt>
            <dd className="flex items-center gap-2">
              <StatusDot ok={state.data.database === "connected"} />
              {state.data.database}
            </dd>
          </div>
          <div className="flex items-center justify-between">
            <dt className="text-slate-400">Redis</dt>
            <dd className="flex items-center gap-2">
              <StatusDot ok={state.data.redis === "connected"} />
              {state.data.redis}
            </dd>
          </div>
          <div className="flex items-center justify-between">
            <dt className="text-slate-400">LLM provider</dt>
            <dd className="text-right">
              {state.data.llm_provider.default}
              {!state.data.llm_provider.anthropic_configured &&
                !state.data.llm_provider.openai_configured && (
                  <span className="block text-xs text-amber-400">
                    No API key configured
                  </span>
                )}
            </dd>
          </div>
        </dl>
      )}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { listAgents, type AgentInfo } from "@/lib/api";

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAgents()
      .then(setAgents)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load agents"));
  }, []);

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Agent registry</h1>
      <p className="mt-1 text-sm text-slate-400">
        The seven agents and their permission set — seeded by an Alembic
        migration, not hard-coded here.
      </p>

      {error && <p className="mt-4 text-sm text-rose-400">{error}</p>}

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {agents === null ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : (
          agents.map((agent) => (
            <div key={agent.id} className="rounded-xl border border-slate-800 bg-slate-900 p-5">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-100">{agent.role}</h2>
                <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
                  {agent.name}
                </span>
              </div>
              {agent.responsibilities && (
                <p className="mt-2 text-sm text-slate-400">{agent.responsibilities}</p>
              )}
              <div className="mt-3 flex flex-wrap gap-1.5">
                {agent.allowed_tools.map((tool) => (
                  <span
                    key={tool}
                    className="rounded-full border border-slate-700 px-2 py-0.5 text-xs text-slate-400"
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </main>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { approveApproval, listApprovals, rejectApproval, type Approval } from "@/lib/api";

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function refresh() {
    const data = await listApprovals("pending");
    setApprovals(data);
  }

  useEffect(() => {
    refresh().catch((err) =>
      setError(err instanceof Error ? err.message : "Failed to load approvals"),
    );
    const interval = setInterval(() => refresh().catch(() => {}), 5000);
    return () => clearInterval(interval);
  }, []);

  async function handleDecision(id: string, decision: "approve" | "reject") {
    setBusyId(id);
    setError(null);
    try {
      if (decision === "approve") {
        await approveApproval(id);
      } else {
        await rejectApproval(id);
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record decision");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Approvals</h1>
      <p className="mt-1 text-sm text-slate-400">
        High-risk changes the policy engine paused for human sign-off (spec
        §11/ADR-004) — enforced in the backend, not just this queue.
      </p>

      {error && <p className="mt-4 text-sm text-rose-400">{error}</p>}

      <div className="mt-6 space-y-3">
        {approvals === null ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : approvals.length === 0 ? (
          <p className="text-sm text-slate-500">No pending approvals.</p>
        ) : (
          approvals.map((approval) => (
            <div
              key={approval.id}
              className="flex items-center justify-between rounded-xl border border-amber-900 bg-amber-950/20 p-4"
            >
              <div>
                <p className="text-sm font-medium text-slate-100">{approval.action}</p>
                <p className="mt-1 text-xs text-slate-400">{approval.requested_reason}</p>
                <div className="mt-2 flex items-center gap-3 text-xs text-slate-500">
                  <span className="rounded bg-amber-900/40 px-2 py-0.5 text-amber-300">
                    risk: {approval.risk_level}
                  </span>
                  <Link href={`/runs/${approval.run_id}`} className="hover:text-slate-300">
                    View run →
                  </Link>
                </div>
              </div>
              <div className="flex shrink-0 gap-2">
                <button
                  onClick={() => handleDecision(approval.id, "approve")}
                  disabled={busyId === approval.id}
                  className="rounded-md bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
                >
                  Approve
                </button>
                <button
                  onClick={() => handleDecision(approval.id, "reject")}
                  disabled={busyId === approval.id}
                  className="rounded-md bg-rose-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-50"
                >
                  Reject
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </main>
  );
}

import { HealthPanel } from "@/components/health-panel";
import { OverviewPanel } from "@/components/overview-panel";

export default function Home() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
        <p className="mt-1 text-sm text-slate-400">
          Governed autonomous software engineering platform. LLMs propose;
          deterministic systems verify.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <OverviewPanel />
        <div className="lg:pt-0">
          <HealthPanel />
        </div>
      </div>
    </main>
  );
}

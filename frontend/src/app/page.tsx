import { HealthPanel } from "@/components/health-panel";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 bg-slate-950 px-6 py-16 text-slate-100">
      <div className="max-w-xl text-center">
        <h1 className="text-3xl font-semibold tracking-tight">AgentForge</h1>
        <p className="mt-2 text-slate-400">
          Governed autonomous software engineering platform. LLMs propose;
          deterministic systems verify.
        </p>
      </div>
      <HealthPanel />
    </main>
  );
}

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface HealthResponse {
  status: "healthy" | "degraded";
  database: "connected" | "unavailable";
  redis: "connected" | "unavailable";
  llm_provider: {
    default: string;
    anthropic_configured: boolean;
    openai_configured: boolean;
  };
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/api/health`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Health check failed with status ${res.status}`);
  }
  return res.json();
}

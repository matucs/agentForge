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

export interface Project {
  id: string;
  name: string;
  repo_path: string;
  description: string | null;
  created_at: string;
}

export interface Task {
  id: string;
  project_id: string;
  title: string;
  requirement_text: string;
  status: string;
  risk_level: string | null;
  created_at: string;
}

export interface Run {
  id: string;
  task_id: string;
  status: string;
  branch_name: string | null;
  started_at: string | null;
  finished_at: string | null;
  total_input_tokens: number;
  total_output_tokens: number;
  estimated_cost_usd: number;
  iteration_count: number;
  final_decision: string | null;
  created_at: string;
}

export interface AgentMessage {
  id: string;
  run_id: string;
  from_agent: string;
  to_agent: string;
  type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface Artifact {
  id: string;
  run_id: string;
  type: string;
  produced_by: string;
  content: Record<string, unknown>;
  created_at: string;
}

export interface Review {
  id: string;
  run_id: string;
  severity: string;
  file: string | null;
  line: number | null;
  finding: string;
  reason: string | null;
  recommendation: string | null;
  resolved: boolean;
  created_at: string;
}

export interface TestResult {
  id: string;
  run_id: string;
  suite: string;
  passed: boolean;
  total: number;
  failed: number;
  duration_seconds: number;
  output: string | null;
  created_at: string;
}

export interface SecurityFinding {
  id: string;
  run_id: string;
  severity: string;
  category: string;
  file: string | null;
  detail: string;
  blocking: boolean;
  created_at: string;
}

export interface VerificationResult {
  id: string;
  run_id: string;
  gate: string;
  passed: boolean;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface ToolCall {
  id: string;
  run_id: string;
  agent: string;
  tool_name: string;
  duration_seconds: number;
  succeeded: boolean;
  result_summary: string | null;
  created_at: string;
}

export interface Approval {
  id: string;
  run_id: string;
  action: string;
  risk_level: string;
  status: string;
  requested_reason: string | null;
  decided_by: string | null;
  decided_at: string | null;
  created_at: string;
}

export interface AgentInfo {
  id: string;
  name: string;
  role: string;
  responsibilities: string | null;
  allowed_tools: string[];
}

export interface Evaluation {
  id: string;
  name: string;
  task_file: string;
  description: string | null;
  created_at: string;
  run_count: number;
  success_count: number;
  avg_duration_seconds: number | null;
  avg_estimated_cost_usd: number | null;
}

export interface EvaluationRun {
  id: string;
  evaluation_id: string;
  run_id: string | null;
  success: boolean;
  reviewer_correct: boolean | null;
  qa_detected: boolean | null;
  security_detected: boolean | null;
  duration_seconds: number;
  estimated_cost_usd: number;
  created_at: string;
}

export interface OperationsSummary {
  runs_total: number;
  runs_today: number;
  success_rate: number | null;
  avg_duration_seconds: number | null;
  avg_estimated_cost_usd: number | null;
  verification_failures: number;
  human_approvals_pending: number;
  human_approvals_total: number;
  runs_by_status: Record<string, number>;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${init?.method ?? "GET"} ${path} failed (${res.status}): ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const fetchHealth = () => apiFetch<HealthResponse>("/api/health");

export const listProjects = () => apiFetch<Project[]>("/api/projects");
export const createProject = (data: { name: string; repo_path: string; description?: string | null }) =>
  apiFetch<Project>("/api/projects", { method: "POST", body: JSON.stringify(data) });

export const listTasks = (projectId?: string) =>
  apiFetch<Task[]>(`/api/tasks${projectId ? `?project_id=${projectId}` : ""}`);
export const getTask = (id: string) => apiFetch<Task>(`/api/tasks/${id}`);
export const createTask = (data: { project_id: string; title: string; requirement_text: string }) =>
  apiFetch<Task>("/api/tasks", { method: "POST", body: JSON.stringify(data) });

export const listRuns = (params?: { task_id?: string; status?: string }) => {
  const query = new URLSearchParams();
  if (params?.task_id) query.set("task_id", params.task_id);
  if (params?.status) query.set("status", params.status);
  const qs = query.toString();
  return apiFetch<Run[]>(`/api/runs${qs ? `?${qs}` : ""}`);
};
export const getRun = (id: string) => apiFetch<Run>(`/api/runs/${id}`);
export const createRun = (taskId: string) =>
  apiFetch<Run>("/api/runs", { method: "POST", body: JSON.stringify({ task_id: taskId }) });
export const startRun = (id: string) => apiFetch<Run>(`/api/runs/${id}/start`, { method: "POST" });
export const cancelRun = (id: string) => apiFetch<Run>(`/api/runs/${id}/cancel`, { method: "POST" });

export const listRunEvents = (id: string) => apiFetch<AgentMessage[]>(`/api/runs/${id}/events`);
export const listRunArtifacts = (id: string) => apiFetch<Artifact[]>(`/api/runs/${id}/artifacts`);
export const listRunReviews = (id: string) => apiFetch<Review[]>(`/api/runs/${id}/reviews`);
export const listRunTestResults = (id: string) => apiFetch<TestResult[]>(`/api/runs/${id}/test-results`);
export const listRunSecurityFindings = (id: string) =>
  apiFetch<SecurityFinding[]>(`/api/runs/${id}/security-findings`);
export const listRunVerificationResults = (id: string) =>
  apiFetch<VerificationResult[]>(`/api/runs/${id}/verification-results`);
export const listRunToolCalls = (id: string) => apiFetch<ToolCall[]>(`/api/runs/${id}/tool-calls`);

export const listApprovals = (status?: string) =>
  apiFetch<Approval[]>(`/api/approvals${status ? `?status=${status}` : ""}`);
export const approveApproval = (id: string, decidedBy = "operator") =>
  apiFetch<Approval>(`/api/approvals/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ decided_by: decidedBy }),
  });
export const rejectApproval = (id: string, decidedBy = "operator") =>
  apiFetch<Approval>(`/api/approvals/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ decided_by: decidedBy }),
  });

export const listAgents = () => apiFetch<AgentInfo[]>("/api/agents");

export const listEvaluations = () => apiFetch<Evaluation[]>("/api/evaluations");
export const listEvaluationRuns = (id: string) =>
  apiFetch<EvaluationRun[]>(`/api/evaluations/${id}/runs`);

export const fetchOperationsSummary = () =>
  apiFetch<OperationsSummary>("/api/operations/summary");

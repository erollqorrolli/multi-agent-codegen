// Thin typed client for the backend API.

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface RunSummary {
  id: string;
  issue_title: string;
  status: string;
  repo: string | null;
  pr_url: string | null;
  total_input_tokens: number;
  total_output_tokens: number;
  created_at: string;
}

export interface AgentStep {
  sequence: number;
  agent: string;
  model: string | null;
  output: Record<string, unknown>;
  input_tokens: number | null;
  output_tokens: number | null;
  duration_ms: number | null;
}

export interface RunDetail extends RunSummary {
  issue_body: string;
  error: string | null;
  generated_files: Record<string, string>;
  steps: AgentStep[];
}

export interface Lesson {
  agent: string;
  lesson: string;
  weight: number;
  times_applied: number;
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  listRuns: () => http<RunSummary[]>("/api/runs"),
  getRun: (id: string) => http<RunDetail>(`/api/runs/${id}`),
  listLessons: () => http<Lesson[]>("/api/lessons"),
  generate: (issue_title: string, issue_body: string) =>
    http<{ run_id: string }>("/api/pipeline/generate", {
      method: "POST",
      body: JSON.stringify({ issue_title, issue_body }),
    }),
  feedback: (runId: string, verdict: string, comment: string) =>
    http(`/api/runs/${runId}/feedback`, {
      method: "POST",
      body: JSON.stringify({ verdict, comment }),
    }),
};

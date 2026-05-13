// Plain fetch wrappers for non-SSE backend endpoints.
//
// All paths are relative; Next.js `rewrites` (see next.config.mjs) proxy
// `/api/*` to the FastAPI backend.

import type { JobRecord, JobsListResponse, ModelsResponse } from "@/lib/types";

async function getJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    headers: { Accept: "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    throw new Error(`${resp.status} ${resp.statusText}: ${body}`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  models: () => getJSON<ModelsResponse>("/api/models"),
  jobs: (limit = 50) =>
    getJSON<JobsListResponse>(`/api/jobs?limit=${encodeURIComponent(limit)}`),
  job: (id: string) =>
    getJSON<JobRecord>(`/api/jobs/${encodeURIComponent(id)}`),
};

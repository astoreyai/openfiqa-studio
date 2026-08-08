/**
 * Backend client.
 *
 * ADR-0001: this file fetches and nothing else. It does not compute, rescale, aggregate, or
 * normalise any scientific quantity — every number rendered by this app arrives from the control
 * plane already carrying its engine and semantics.
 */

const BASE = import.meta.env.VITE_OFS_API ?? "http://127.0.0.1:8790";

export interface Health {
  status: string;
  api_version: string;
  workspace: string;
  plugins: number;
  executable_plugins: string[];
}

export type AvailabilityState = "AVAILABLE" | "DEGRADED" | "BLOCKED" | "UNVERIFIED";

export interface PluginSummary {
  plugin_id: string;
  name: string;
  version: string;
  kind: string;
  mode: string;
  inputs: string[];
  outputs: string[];
  capabilities: { batch: boolean | "unknown"; gpu: boolean | "unknown"; deterministic: boolean | "unknown" };
  availability: {
    state: AvailabilityState;
    blocker_id: string | null;
    reason: string | null;
    verified_by: { corpus: string; rc: number; n_components: number | null } | null;
  };
  executable: boolean;
  provenance: { source_repository: string | null; commit: string | null; license: string | null; public: boolean };
}

export interface PluginList {
  plugins: PluginSummary[];
  counts: { total: number; executable: number; blocked: number; unverified: number };
}

export interface Project {
  id: string;
  name: string;
  root: string;
  created_at: string;
}

export interface RunSummary {
  run_id: string;
  label: string;
  status: string;
  exit_code: number | null;
  created_at: string;
  finished_at: string | null;
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`);
  if (!response.ok) throw new Error(`${path} -> ${response.status}`);
  return (await response.json()) as T;
}

export const api = {
  health: () => get<Health>("/api/health"),
  plugins: () => get<PluginList>("/api/plugins"),
  projects: () => get<{ projects: Project[] }>("/api/projects"),
  runs: () => get<{ runs: RunSummary[] }>("/api/runs"),
  base: BASE,
};

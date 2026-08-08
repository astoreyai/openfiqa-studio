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

export interface NodeKind {
  kind: string;
  inputs: string[];
  outputs: string[];
  blocked_by: string | null;
}

export interface WorkflowValidation {
  name: string;
  valid: boolean;
  problems: string[];
  workflow_sha256: string;
  nodes: number;
  edges: number;
}

export interface ManifestNode {
  node_id: string;
  kind: string;
  status: string;
  detail: string | null;
  blocker_id: string | null;
  outputs: string[];
  upstream: string[];
}

export interface RunManifest {
  workflow_name: string;
  workflow_sha256: string;
  status: string;
  nodes: ManifestNode[];
  artifacts: Record<string, unknown>;
}

export interface SampleEntry {
  path: string;
  name: string;
  subject_id: string;
}

export interface ComponentView {
  name: string;
  raw: number | null;
  scalar: number | null;
  computed: boolean;
  failure_sentinel?: number | null;
  raw_polarity: string;
}

export interface QualityVectorView {
  sample_id: string;
  engine: { engine_id: string; version: string | null; commit: string | null; config_digest?: string | null };
  components: ComponentView[];
  unified: { value: number | null; semantics: { definition_id: string } } | null;
  state: string;
}

export interface TransformRecordView {
  transform_id: string;
  implementation: string;
  parameters: Record<string, unknown>;
  seed: number | null;
  deterministic: boolean;
  input_sha256: string;
  output_sha256: string;
}

export interface DegradeResult {
  path: string;
  transform: TransformRecordView;
  source_path: string;
}

export interface Detection {
  bbox: [number, number, number, number];
  det_score: number;
  keypoints: [number, number][];
  landmarks_106?: [number, number][];
  pose_pitch_yaw_roll?: [number, number, number];
}

export interface DetectResult {
  image_width: number;
  image_height: number;
  n_faces: number;
  detections: Detection[];
  geometry_consistent: boolean;
  geometry_problems: string[];
  duration_s: number;
}

export interface RunSummary {
  run_id: string;
  label: string;
  status: string;
  exit_code: number | null;
  created_at: string;
  finished_at: string | null;
}

export interface RunEvent {
  run_id: string;
  type: "queued" | "started" | "stdout" | "stderr" | "completed" | "failed" | "cancelled" | "error";
  at?: string;
  line?: string;
  exit_code?: number;
  pid?: number;
  detail?: string;
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`);
  if (!response.ok) throw new Error(`${path} -> ${response.status}`);
  return (await response.json()) as T;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    // Preserve the backend's structured refusal. A blocked engine answers with its blocker id,
    // and flattening that to "request failed" would discard the only useful part.
    const detail = (payload as { detail?: unknown }).detail;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail ?? response.status));
  }
  return payload as T;
}

/** Live run events. The URL mirrors the HTTP base so both follow VITE_OFS_API. */
export function runEventSocket(runId: string): WebSocket {
  const wsBase = BASE.replace(/^http/, "ws");
  return new WebSocket(`${wsBase}/ws/runs/${runId}`);
}

export const api = {
  health: () => get<Health>("/api/health"),
  plugins: () => get<PluginList>("/api/plugins"),
  projects: () => get<{ projects: Project[] }>("/api/projects"),
  runs: () => get<{ runs: RunSummary[] }>("/api/runs"),
  createProject: (name: string) => post<Project>("/api/projects", { name }),
  createRun: (label: string, argv: string[]) =>
    post<RunSummary>("/api/runs", { label, argv }),
  cancelRun: (runId: string) => post<{ run_id: string; status: string }>(`/api/runs/${runId}/cancel`),
  runPlugin: (pluginId: string) => post<RunSummary>(`/api/runs/plugin/${pluginId}`),
  nodeKinds: () => get<{ kinds: NodeKind[] }>("/api/workflows/node-kinds"),
  validateWorkflow: (yaml: string) => post<WorkflowValidation>("/api/workflows/validate", { yaml }),
  runWorkflow: (yaml: string) => post<RunManifest>("/api/workflows/run", { yaml }),
  samples: (limit = 200) => get<{ samples: SampleEntry[] }>(`/api/samples?limit=${limit}`),
  imageUrl: (path: string) => `${BASE}/api/samples/image?path=${encodeURIComponent(path)}`,
  degrade: (imagePath: string, operator: string, parameters: Record<string, unknown>) =>
    post<DegradeResult>("/api/samples/degrade", { image_path: imagePath, operator, parameters }),
  detect: (imagePath: string) =>
    post<DetectResult>("/api/samples/detect", { image_path: imagePath }),
  assess: (pluginId: string, imagePath: string) =>
    post<{ quality_vector: QualityVectorView; provenance: Record<string, unknown>; raw_output: string }>(
      `/api/engines/${pluginId}/assess`, { image_path: imagePath }),
  base: BASE,
};

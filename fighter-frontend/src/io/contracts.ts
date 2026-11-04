/**
 * Exact wire contracts for the existing Python backend.
 *
 * Only src/io/ files should import these interfaces. Keep backend JSON names
 * here so changes in server.py do not leak into UI components or the viewer.
 */

export interface HealthWireResponse {
  ok: boolean;
}

export interface RunSummaryWire {
  n: number;
  created: string;
  result: string | null;
  frames: number;
  info: Record<string, unknown>;
  replay_status?: 'not_compiled' | 'queued' | 'compiling' | 'validating' | 'ready' | 'failed';
  replay_progress?: Record<string, unknown>;
}

export interface RunsWireResponse {
  runs: RunSummaryWire[];
}

export interface StartPracticeWireInput {
  ai: 'A' | 'B';
  preset: 'meta' | 'meta_contrib' | 'baseten';
  interval: number;
  effort: 'minimal' | 'low' | 'medium' | 'high' | 'xhigh' | 'max';
  duration_minutes?: number;
}

export interface StartFightWireInput {
  presetA: 'meta' | 'meta_contrib' | 'baseten';
  presetB: 'meta' | 'meta_contrib' | 'baseten';
  interval: number;
  effortA: 'minimal' | 'low' | 'medium' | 'high' | 'xhigh' | 'max';
  effortB: 'minimal' | 'low' | 'medium' | 'high' | 'xhigh' | 'max';
  duration_minutes?: number;
}

export interface StartJobWireResponse {
  job: string;
}

export interface JobWireResponse {
  id: string;
  kind: 'practice' | 'fight';
  status: string;
  stage?: string;
  params?: Record<string, unknown>;
  started?: number;
  elapsed_ms?: number;
  run?: number;
  result?: string | null;
  percent?: number;
  decision?: number;
  target_decisions?: number;
  frame?: number;
  max_frame?: number;
  usage?: Record<string, number>;
  error?: string;
  latest_thinking?: { fighter?: string; text?: string; raw_text?: string; is_fallback?: boolean; word_count?: number; frame?: number; time_sec?: number; valid_20_words?: boolean; interval_index?: number; decision?: number };
  latest_thinking_A?: { fighter?: string; text?: string; raw_text?: string; is_fallback?: boolean; word_count?: number; frame?: number; time_sec?: number; valid_20_words?: boolean; interval_index?: number; decision?: number };
  latest_thinking_B?: { fighter?: string; text?: string; raw_text?: string; is_fallback?: boolean; word_count?: number; frame?: number; time_sec?: number; valid_20_words?: boolean; interval_index?: number; decision?: number };
  thinking_history?: Array<{ fighter?: string; text?: string; raw_text?: string; is_fallback?: boolean; word_count?: number; frame?: number; time_sec?: number; valid_20_words?: boolean; interval_index?: number; decision?: number }>;
  round_summary?: string;
  round_summaries?: string[];
}

export interface JobAuditWire {
  id: string;
  kind: 'practice' | 'fight';
  status: string;
  stage: string;
  created: string;
  started: number;
  elapsed_ms: number;
  run?: number;
  result?: string | null;
  params?: Record<string, unknown>;
  usage?: Record<string, number>;
  error?: string | null;
}

export interface JobsListWireResponse {
  jobs: JobAuditWire[];
}

export interface JobEventWire {
  id: number;
  job_id: string;
  created: string;
  severity: 'info' | 'warn' | 'error';
  stage: string;
  message: string;
  metadata?: Record<string, unknown>;
}

export interface EventsListWireResponse {
  events: JobEventWire[];
}

export interface CatalogFieldWire {
  key: string;
  label: string;
  type: string;
  primary?: boolean;
}

export interface CatalogResourceWire {
  key: string;
  label: string;
  description: string;
  count: number;
  primary_key: string;
  operations: string[];
  reversible: boolean;
  fields: CatalogFieldWire[];
}

export interface DbCatalogWireResponse {
  catalog: CatalogResourceWire[];
}

export interface DbResourceListWireResponse {
  items: Record<string, unknown>[];
  total: number;
  limit: number;
  offset: number;
}

export interface DbRecordWireResponse {
  item: Record<string, unknown>;
}

export interface DbDeleteWireResponse {
  ok: boolean;
  deleted: number;
  error?: string;
}

export interface DbResetMemoryWireResponse {
  ok: boolean;
  reset_libraries: number;
  target: string;
  error?: string;
}

export interface ReplayStatusWireResponse {
  status: 'not_compiled' | 'queued' | 'compiling' | 'validating' | 'ready' | 'failed';
  run: number;
  progress?: Record<string, unknown>;
  error?: string;
}

export interface ReplayCompileWireResponse {
  ok: boolean;
  status: 'not_compiled' | 'queued' | 'compiling' | 'validating' | 'ready' | 'failed';
  progress?: Record<string, unknown>;
  error?: string;
}

export interface ProviderConfigWire {
  base: string;
  model: string;
  key_env: string;
  effort: boolean;
  role: string;
  overridden?: boolean;
}

export interface EffectiveConfigWireResponse {
  providers: Record<string, ProviderConfigWire>;
}

export interface ApiCheckWireResponse {
  ok: boolean;
  text?: string;
  model: string;
  elapsed_ms?: number;
  error?: string;
}


export interface BackendShapeWire {
  k: string;
  p?: number;
  a?: number;
  b?: number;
  r: number;
  n?: string;
}

export interface ReplayInitWire {
  points: number;
  shapes: BackendShapeWire[];
  world: {
    ring: number;
    wall_h: number;
    wall_t: number;
  };
  fps: number;
  nf: number;
}

export interface ReplayFrameWire {
  t: number;
  p: number[];
  x: number[];
}

export interface ReplayComputingWireResponse {
  status: 'computing';
}

export interface ReplayReadyWireResponse {
  status: 'ready';
  result: string | null;
  init: ReplayInitWire;
  frames: ReplayFrameWire[];
}

export type ReplayWireResponse = ReplayComputingWireResponse | ReplayReadyWireResponse;

export interface MemoryWireResponse {
  ai: 'A' | 'B';
  moves: string[];
  chains: Record<string, unknown>;
}

export interface ServerLogEntryWire {
  id: number;
  timestamp: number;
  iso: string;
  level: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR' | string;
  subsystem: 'HTTP' | 'SIMULATION' | 'AI_ENGINE' | 'PHYSICS' | 'DATABASE' | 'CACHE' | 'SYSTEM' | 'RULES' | string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ServerStatusWire {
  uptime_seconds: number;
  total_logs: number;
  buffer_size: number;
  activity: string;
  detail?: string;
  active_job?: string;
  status: string;
}

export interface LiveLogsWireResponse {
  logs: ServerLogEntryWire[];
  status: ServerStatusWire;
  max_id: number;
}


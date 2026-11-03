/**
 * HTTP-only adapter for the Python backend.
 *
 * This is the ONLY place in the frontend that calls fetch(). It receives app-
 * level commands, translates them into backend JSON, and maps responses back
 * into app-level models. UI components never build URLs or backend payloads.
 */

import type {
  ActivityEvent,
  CatalogResource,
  FightCommand,
  PracticeCommand,
  ReplayLoadResult,
  SavedRun,
  SimulationJob,
  SimulationKind,
} from '../core/commands';
import type {
  ApiCheckWireResponse,
  DbCatalogWireResponse,
  DbDeleteWireResponse,
  DbRecordWireResponse,
  DbResetMemoryWireResponse,
  DbResourceListWireResponse,
  EffectiveConfigWireResponse,
  EventsListWireResponse,
  HealthWireResponse,
  JobWireResponse,
  JobsListWireResponse,
  LiveLogsWireResponse,
  MemoryWireResponse,
  ProviderConfigWire,
  ReplayStatusWireResponse,
  ReplayWireResponse,
  RunsWireResponse,
  ServerLogEntryWire,
  StartFightWireInput,
  StartJobWireResponse,
  StartPracticeWireInput,
} from './contracts';
import {
  mapActivityEvent,
  mapCatalogResource,
  mapJob,
  mapJobAudit,
  mapReplayResponse,
  mapRunSummary,
} from './mapper';

const configuredBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';
const API_BASE_URL = configuredBaseUrl.trim().replace(/\/+$/, '');

export class ApiClientError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
  }
}

function makeUrl(path: string): string {
  if (!API_BASE_URL) {
    throw new Error('VITE_API_BASE_URL is not configured. Copy .env.example to .env and set your backend URL.');
  }
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

async function request<T>(
  path: string,
  options: { method?: 'GET' | 'POST' | 'DELETE'; body?: unknown; adminToken?: string } = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';

  // The operator token is supplied at runtime. It is never compiled into Vite.
  if (options.adminToken) headers['X-Token'] = options.adminToken;

  let response: Response;
  try {
    response = await fetch(makeUrl(path), {
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : 'Network request failed';
    throw new Error(`Cannot reach the backend. Check its URL, CORS settings, and Render service status. (${detail})`);
  }

  const rawText = await response.text();
  let payload: unknown = {};
  if (rawText) {
    try {
      payload = JSON.parse(rawText) as unknown;
    } catch {
      throw new ApiClientError(`Backend returned non-JSON data (HTTP ${response.status}).`, response.status);
    }
  }

  if (!response.ok) {
    const message =
      typeof payload === 'object' && payload !== null && 'error' in payload
        ? String((payload as { error: unknown }).error)
        : `Request failed with HTTP ${response.status}`;
    throw new ApiClientError(message, response.status);
  }

  return payload as T;
}

export const api = {
  /** Health check. The app only needs to know whether it completed. */
  health: async (): Promise<void> => {
    await request<HealthWireResponse>('/health');
  },

  /** Returns UI-ready run items, not backend database field names. */
  listRuns: async (kind: SimulationKind): Promise<SavedRun[]> => {
    const response = await request<RunsWireResponse>(`/runs/${kind}`);
    return response.runs.map(mapRunSummary);
  },

  /** Translate app vocabulary into the exact POST /practice payload including duration. */
  startPractice: async (command: PracticeCommand, adminToken: string): Promise<string> => {
    const body: StartPracticeWireInput = {
      ai: command.memorySlot,
      preset: command.provider,
      interval: command.thinkingIntervalSeconds,
      effort: command.reasoning,
      duration_minutes: command.durationMinutes,
    };
    const response = await request<StartJobWireResponse>('/practice', { method: 'POST', body, adminToken });
    return response.job;
  },

  /** Translate app vocabulary into the exact POST /fight payload including duration. */
  startFight: async (command: FightCommand, adminToken: string): Promise<string> => {
    const body: StartFightWireInput = {
      presetA: command.fighterA.provider,
      presetB: command.fighterB.provider,
      interval: command.thinkingIntervalSeconds,
      effortA: command.fighterA.reasoning,
      effortB: command.fighterB.reasoning,
      duration_minutes: command.durationMinutes,
    };
    const response = await request<StartJobWireResponse>('/fight', { method: 'POST', body, adminToken });
    return response.job;
  },

  /** Normalize the server's transient job object for the app controller. */
  getJob: async (jobId: string): Promise<SimulationJob> => {
    const response = await request<JobWireResponse>(`/jobs/${encodeURIComponent(jobId)}`);
    return mapJob(response);
  },

  /** Return either a preparation state or a fully normalized scene. */
  getReplay: async (kind: SimulationKind, runNumber: number): Promise<ReplayLoadResult> => {
    const response = await request<ReplayWireResponse>(`/replay/${kind}/${encodeURIComponent(String(runNumber))}`);
    if (response.status !== 'ready') return { status: 'computing' };
    return { status: 'ready', scene: mapReplayResponse(response) };
  },

  compileReplay: async (
    kind: SimulationKind,
    runNumber: number,
    adminToken?: string,
  ): Promise<ReplayCompileWireResponse> => {
    return request<ReplayCompileWireResponse>(
      `/replay/${kind}/${encodeURIComponent(String(runNumber))}/compile`,
      { method: 'POST', adminToken },
    );
  },

  /** Fast status check for replay readiness without loading full frame payload. */
  getReplayStatus: async (kind: SimulationKind, runNumber: number): Promise<ReplayStatusWireResponse> => {
    return request<ReplayStatusWireResponse>(`/replay/${kind}/${encodeURIComponent(String(runNumber))}/status`);
  },

  /** Optional read-only memory data. */
  getMemory: (ai: 'A' | 'B') => request<MemoryWireResponse>(`/memory/${ai}`),

  // ---- Admin Monitoring Endpoints ----
  listJobs: async (adminToken: string, limit = 50): Promise<SimulationJob[]> => {
    const response = await request<JobsListWireResponse>(`/admin/jobs?limit=${limit}`, { adminToken });
    return response.jobs.map(mapJobAudit);
  },

  listEvents: async (adminToken: string, limit = 100, sinceId?: number): Promise<ActivityEvent[]> => {
    const path = sinceId ? `/admin/events?limit=${limit}&since_id=${sinceId}` : `/admin/events?limit=${limit}`;
    const response = await request<EventsListWireResponse>(path, { adminToken });
    return response.events.map(mapActivityEvent);
  },

  // ---- Dynamic Database Management Endpoints ----
  getDbCatalog: async (adminToken: string): Promise<CatalogResource[]> => {
    const response = await request<DbCatalogWireResponse>('/admin/db/catalog', { adminToken });
    return response.catalog.map(mapCatalogResource);
  },

  listDbResource: async (
    adminToken: string,
    resourceKey: string,
    limit = 50,
    offset = 0,
  ): Promise<{ items: Record<string, unknown>[]; total: number; limit: number; offset: number }> => {
    return request<DbResourceListWireResponse>(
      `/admin/db/${encodeURIComponent(resourceKey)}?limit=${limit}&offset=${offset}`,
      { adminToken },
    );
  },

  getDbRecord: async (
    adminToken: string,
    resourceKey: string,
    id: string | number,
  ): Promise<Record<string, unknown>> => {
    const response = await request<DbRecordWireResponse>(
      `/admin/db/${encodeURIComponent(resourceKey)}/${encodeURIComponent(String(id))}`,
      { adminToken },
    );
    return response.item;
  },

  deleteDbRecord: async (
    adminToken: string,
    resourceKey: string,
    id: string | number,
  ): Promise<{ ok: boolean; deleted: number }> => {
    return request<DbDeleteWireResponse>(
      `/admin/db/${encodeURIComponent(resourceKey)}/${encodeURIComponent(String(id))}`,
      { method: 'DELETE', adminToken },
    );
  },

  deleteDbBatch: async (
    adminToken: string,
    resourceKey: string,
    ids: (string | number)[],
  ): Promise<{ ok: boolean; deleted: number }> => {
    return request<DbDeleteWireResponse>(
      `/admin/db/${encodeURIComponent(resourceKey)}/delete-batch`,
      { method: 'POST', body: { ids }, adminToken },
    );
  },

  resetMemory: async (
    adminToken: string,
    target: 'A' | 'B' | 'all' = 'all',
  ): Promise<{ ok: boolean; deleted_notes: number; reset_libraries: number; target: string }> => {
    return request<DbResetMemoryWireResponse>('/admin/db/reset-memory', {
      method: 'POST',
      body: { target },
      adminToken,
    });
  },

  // ---- Diagnostic & Configuration Endpoints ----
  getConfig: async (adminToken: string): Promise<Record<string, ProviderConfigWire>> => {
    const response = await request<EffectiveConfigWireResponse>('/admin/config', { adminToken });
    return response.providers;
  },

  setModelOverride: async (
    adminToken: string,
    preset: string,
    model: string,
  ): Promise<{ ok: boolean }> => {
    return request<{ ok: boolean }>('/admin/config/set-model', {
      method: 'POST',
      body: { preset, model },
      adminToken,
    });
  },

  checkApi: async (adminToken: string, preset: string): Promise<ApiCheckWireResponse> => {
    return request<ApiCheckWireResponse>('/admin/diagnostic/check-api', {
      method: 'POST',
      body: { preset },
      adminToken,
    });
  },

  // ---- Real-Time Live Server Logs Endpoints ----
  getLiveLogs: async (
    adminToken?: string,
    params?: {
      sinceId?: number;
      limit?: number;
      level?: string;
      subsystem?: string;
      search?: string;
    },
  ): Promise<LiveLogsWireResponse> => {
    const q = new URLSearchParams();
    if (params?.sinceId !== undefined) q.set('since_id', String(params.sinceId));
    if (params?.limit !== undefined) q.set('limit', String(params.limit));
    if (params?.level && params.level !== 'ALL') q.set('level', params.level);
    if (params?.subsystem && params.subsystem !== 'ALL') q.set('subsystem', params.subsystem);
    if (params?.search && params.search.trim()) q.set('search', params.search.trim());

    const qs = q.toString() ? `?${q.toString()}` : '';
    // Prefer /admin/logs if adminToken is available, otherwise /logs
    const path = adminToken?.trim() ? `/admin/logs${qs}` : `/logs${qs}`;
    return request<LiveLogsWireResponse>(path, { adminToken: adminToken?.trim() || undefined });
  },

  clearLiveLogs: async (adminToken?: string): Promise<{ ok: boolean }> => {
    const path = adminToken?.trim() ? '/admin/logs/clear' : '/logs/clear';
    return request<{ ok: boolean }>(path, {
      method: 'POST',
      adminToken: adminToken?.trim() || undefined,
    });
  },

  emitTestLog: async (
    adminToken?: string,
    message?: string,
  ): Promise<{ ok: boolean; log?: ServerLogEntryWire }> => {
    const path = adminToken?.trim() ? '/admin/logs/test' : '/logs/test';
    return request<{ ok: boolean; log?: ServerLogEntryWire }>(path, {
      method: 'POST',
      body: { message: message || 'Operator diagnostic ping' },
      adminToken: adminToken?.trim() || undefined,
    });
  },
};


export function getConfiguredApiUrl(): string {
  return API_BASE_URL;
}


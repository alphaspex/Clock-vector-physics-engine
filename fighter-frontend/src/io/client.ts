/**
 * HTTP-only adapter for the Python backend.
 *
 * This is the ONLY place in the frontend that calls fetch(). It receives app-
 * level commands, translates them into backend JSON, and maps responses back
 * into app-level models. UI components never build URLs or backend payloads.
 */

import type {
  FightCommand,
  PracticeCommand,
  ReplayLoadResult,
  SavedRun,
  SimulationKind,
  SimulationJob,
} from '../core/commands';
import type {
  HealthWireResponse,
  JobWireResponse,
  MemoryWireResponse,
  ReplayWireResponse,
  RunsWireResponse,
  StartFightWireInput,
  StartJobWireResponse,
  StartPracticeWireInput,
} from './contracts';
import { mapJob, mapReplayResponse, mapRunSummary } from './mapper';

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
  options: { method?: 'GET' | 'POST'; body?: unknown; adminToken?: string } = {},
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

  /** Translate app vocabulary into the exact POST /practice payload. */
  startPractice: async (command: PracticeCommand, adminToken: string): Promise<string> => {
    const body: StartPracticeWireInput = {
      ai: command.memorySlot,
      preset: command.provider,
      interval: command.thinkingIntervalSeconds,
      effort: command.reasoning,
    };
    const response = await request<StartJobWireResponse>('/practice', { method: 'POST', body, adminToken });
    return response.job;
  },

  /** Translate app vocabulary into the exact POST /fight payload. */
  startFight: async (command: FightCommand, adminToken: string): Promise<string> => {
    const body: StartFightWireInput = {
      presetA: command.fighterA.provider,
      presetB: command.fighterB.provider,
      interval: command.thinkingIntervalSeconds,
      effortA: command.fighterA.reasoning,
      effortB: command.fighterB.reasoning,
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
    if (response.status === 'computing') return { status: 'computing' };
    return { status: 'ready', scene: mapReplayResponse(response) };
  },

  /** Optional read-only memory data, normalized later if it is exposed in UI. */
  getMemory: (ai: 'A' | 'B') => request<MemoryWireResponse>(`/memory/${ai}`),
};

export function getConfiguredApiUrl(): string {
  return API_BASE_URL;
}

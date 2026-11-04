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
}

export interface RunsWireResponse {
  runs: RunSummaryWire[];
}

export interface StartPracticeWireInput {
  ai: 'A' | 'B';
  preset: 'meta' | 'meta_contrib' | 'baseten';
  interval: number;
  effort: 'minimal' | 'low' | 'medium' | 'high' | 'xhigh' | 'max';
}

export interface StartFightWireInput {
  presetA: 'meta' | 'meta_contrib' | 'baseten';
  presetB: 'meta' | 'meta_contrib' | 'baseten';
  interval: number;
  effortA: 'minimal' | 'low' | 'medium' | 'high' | 'xhigh' | 'max';
  effortB: 'minimal' | 'low' | 'medium' | 'high' | 'xhigh' | 'max';
}

export interface StartJobWireResponse {
  job: string;
}

export interface JobWireResponse {
  id: string;
  kind: 'practice' | 'fight';
  status: string;
  params?: Record<string, unknown>;
  started?: number;
  run?: number;
  result?: string | null;
  usage?: Record<string, number>;
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
  notes: string[];
  moves: string[];
  chains: Record<string, unknown>;
}

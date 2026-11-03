/**
 * App-facing commands and view models.
 *
 * These types describe what the application means, not how the Python API
 * spells JSON keys. UI components and the app controller depend on these;
 * src/io/ translates them to/from the backend wire contract.
 */

export type SimulationKind = 'practice' | 'fight';
export type MemorySlot = 'A' | 'B';
export type ModelProvider = 'meta' | 'meta_contrib' | 'baseten';
export type ReasoningMode = 'minimal' | 'low' | 'medium' | 'high' | 'xhigh' | 'max';

export interface PracticeCommand {
  memorySlot: MemorySlot;
  provider: ModelProvider;
  thinkingIntervalSeconds: number;
  reasoning: ReasoningMode;
  durationMinutes: number;
}

export interface FighterCommand {
  provider: ModelProvider;
  reasoning: ReasoningMode;
}

export interface FightCommand {
  fighterA: FighterCommand;
  fighterB: FighterCommand;
  thinkingIntervalSeconds: number;
  durationMinutes: number;
}

/** Stable app-facing run item; server fields are mapped before UI receives it. */
export interface SavedRun {
  number: number;
  createdAt: string;
  result: string | null;
  frameCount: number;
}

/** Normalized job state; the UI/controller do not read backend job JSON keys. */
export interface SimulationJob {
  id: string;
  kind: SimulationKind;
  state: 'running' | 'done' | 'error';
  stage: string;
  runNumber?: number;
  result?: string | null;
  percent?: number;
  decision?: number;
  targetDecisions?: number;
  frame?: number;
  maxFrame?: number;
  elapsedMs?: number;
  startedAt?: number;
  createdAt?: string;
  params?: Record<string, unknown>;
  usage?: { prompt: number; completion: number; reasoning: number };
  errorMessage?: string;
}

export interface ActivityEvent {
  id: number;
  jobId: string;
  createdAt: string;
  severity: 'info' | 'warn' | 'error';
  stage: string;
  message: string;
  metadata?: Record<string, unknown>;
}

export interface CatalogField {
  key: string;
  label: string;
  type: string;
  primary?: boolean;
}

export interface CatalogResource {
  key: string;
  label: string;
  description: string;
  count: number;
  primaryKey: string;
  operations: string[];
  reversible: boolean;
  fields: CatalogField[];
}

export interface UnifiedHistoryItem {
  key: string;
  kind: SimulationKind;
  jobId?: string;
  runNumber?: number;
  status: 'running' | 'saving' | 'preparing_replay' | 'ready' | 'failed';
  stageLabel: string;
  createdAt: string;
  result?: string | null;
  frameCount?: number;
  errorMessage?: string;
}

export type ReplayLoadResult =
  | { status: 'computing' }
  | { status: 'ready'; scene: import('./scene').ReplayScene };


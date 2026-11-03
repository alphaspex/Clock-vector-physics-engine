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
}

export interface FighterCommand {
  provider: ModelProvider;
  reasoning: ReasoningMode;
}

export interface FightCommand {
  fighterA: FighterCommand;
  fighterB: FighterCommand;
  thinkingIntervalSeconds: number;
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
  state: 'running' | 'done' | 'error';
  runNumber?: number;
  errorMessage?: string;
}

export type ReplayLoadResult =
  | { status: 'computing' }
  | { status: 'ready'; scene: import('./scene').ReplayScene };

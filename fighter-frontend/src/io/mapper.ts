/**
 * Backend-to-app boundary mappings.
 *
 * Keep backend-specific fields in this folder. The UI and renderer receive
 * normalized app models and never need to understand the backend's JSON keys.
 */

import type {
  CatalogResourceWire,
  JobAuditWire,
  JobEventWire,
  JobWireResponse,
  ReplayReadyWireResponse,
  RunSummaryWire,
} from './contracts';
import type { ReplayScene, SceneBlueprint, SceneFrame, ScenePrimitive } from '../core/scene';
import type { ActivityEvent, CatalogResource, SavedRun, SimulationJob, SimulationKind } from '../core/commands';

function finiteNumber(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

export function mapRunSummary(wire: RunSummaryWire): SavedRun {
  return {
    number: wire.n,
    createdAt: wire.created,
    result: wire.result ?? null,
    frameCount: wire.frames,
  };
}

export function mapJob(wire: JobWireResponse): SimulationJob {
  const isDone = wire.status === 'done';
  const isError = wire.status === 'error';
  const state: 'running' | 'done' | 'error' = isDone ? 'done' : isError ? 'error' : 'running';

  return {
    id: wire.id || '',
    kind: (wire.kind as SimulationKind) || 'practice',
    state,
    stage: wire.stage || (isDone ? 'ready' : isError ? 'failed' : 'simulation'),
    runNumber: typeof wire.run === 'number' ? wire.run : undefined,
    result: wire.result ?? null,
    percent: typeof wire.percent === 'number' ? wire.percent : undefined,
    decision: typeof wire.decision === 'number' ? wire.decision : undefined,
    targetDecisions: typeof wire.target_decisions === 'number' ? wire.target_decisions : undefined,
    frame: typeof wire.frame === 'number' ? wire.frame : undefined,
    maxFrame: typeof wire.max_frame === 'number' ? wire.max_frame : undefined,
    elapsedMs: typeof wire.elapsed_ms === 'number' ? wire.elapsed_ms : undefined,
    startedAt: typeof wire.started === 'number' ? wire.started : undefined,
    params: wire.params,
    usage: wire.usage ? {
      prompt: wire.usage.prompt || 0,
      completion: wire.usage.completion || 0,
      reasoning: wire.usage.reasoning || 0,
    } : undefined,
    errorMessage: wire.error,
  };
}

export function mapJobAudit(wire: JobAuditWire): SimulationJob {
  const isDone = wire.status === 'done';
  const isError = wire.status === 'error';
  const state: 'running' | 'done' | 'error' = isDone ? 'done' : isError ? 'error' : 'running';

  return {
    id: wire.id,
    kind: wire.kind,
    state,
    stage: wire.stage || (isDone ? 'ready' : isError ? 'failed' : 'simulation'),
    runNumber: wire.run,
    result: wire.result ?? null,
    elapsedMs: wire.elapsed_ms,
    startedAt: wire.started,
    createdAt: wire.created,
    params: wire.params,
    usage: wire.usage ? {
      prompt: wire.usage.prompt || 0,
      completion: wire.usage.completion || 0,
      reasoning: wire.usage.reasoning || 0,
    } : undefined,
    errorMessage: wire.error ?? undefined,
  };
}

export function mapActivityEvent(wire: JobEventWire): ActivityEvent {
  return {
    id: wire.id,
    jobId: wire.job_id,
    createdAt: wire.created,
    severity: wire.severity,
    stage: wire.stage,
    message: wire.message,
    metadata: wire.metadata,
  };
}

export function mapCatalogResource(wire: CatalogResourceWire): CatalogResource {
  return {
    key: wire.key,
    label: wire.label,
    description: wire.description,
    count: wire.count,
    primaryKey: wire.primary_key,
    operations: wire.operations,
    reversible: wire.reversible,
    fields: wire.fields.map((f) => ({
      key: f.key,
      label: f.label,
      type: f.type,
      primary: f.primary,
    })),
  };
}


export function mapReplayResponse(payload: ReplayReadyWireResponse): ReplayScene {
  const init = payload.init;
  const pointCount = Math.max(0, Math.floor(finiteNumber(init.points, 0)));
  const primitives: ScenePrimitive[] = [];

  init.shapes.forEach((shape, id) => {
    const radius = finiteNumber(shape.r, 0);
    if (radius <= 0) return;

    // This switch maps the backend's primitive names to generic scene types.
    if (shape.k === 'ball' && Number.isInteger(shape.p) && (shape.p ?? -1) >= 0 && (shape.p ?? 0) < pointCount) {
      primitives.push({ id, kind: 'sphere', point: shape.p!, radius, label: shape.n });
      return;
    }

    if (
      shape.k === 'cap' &&
      Number.isInteger(shape.a) && Number.isInteger(shape.b) &&
      (shape.a ?? -1) >= 0 && (shape.b ?? -1) >= 0 &&
      (shape.a ?? pointCount) < pointCount && (shape.b ?? pointCount) < pointCount
    ) {
      primitives.push({ id, kind: 'capsule', from: shape.a!, to: shape.b!, radius, label: shape.n });
      return;
    }

    // Unknown future geometry is skipped rather than crashing the TV renderer.
    console.warn(`[replay adapter] Skipped unsupported or invalid primitive: ${shape.k}`, shape);
  });

  const blueprint: SceneBlueprint = {
    pointCount,
    primitives,
    arena: {
      radius: Math.max(0.1, finiteNumber(init.world?.ring, 5)),
      wallHeight: Math.max(0, finiteNumber(init.world?.wall_h, 0.5)),
      wallThickness: Math.max(0, finiteNumber(init.world?.wall_t, 0.2)),
    },
    framesPerSecond: Math.max(1, finiteNumber(init.fps, 30)),
    fighterCount: Math.max(1, Math.floor(finiteNumber(init.nf, 1))),
  };

  const frames: SceneFrame[] = [];
  for (const frame of payload.frames) {
    if (!Array.isArray(frame.p) || frame.p.length !== pointCount * 3) {
      console.warn('[replay adapter] Skipped frame with an invalid position array.', frame);
      continue;
    }
    if (!frame.p.every((value) => Number.isFinite(value))) {
      console.warn('[replay adapter] Skipped frame containing non-finite positions.', frame);
      continue;
    }
    frames.push({
      time: Math.max(0, finiteNumber(frame.t, 0)),
      positions: frame.p,
      hiddenPrimitiveIds: Array.isArray(frame.x) ? frame.x.filter(Number.isInteger) : [],
    });
  }

  if (frames.length === 0) {
    throw new Error('The replay is ready, but it contains no valid position frames.');
  }

  return { blueprint, frames, result: payload.result ?? null };
}

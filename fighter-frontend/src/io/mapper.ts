/**
 * Backend-to-app boundary mappings.
 *
 * Keep backend-specific fields in this folder. The UI and renderer receive
 * normalized app models and never need to understand the backend's JSON keys.
 */

import type {
  JobWireResponse,
  ReplayReadyWireResponse,
  RunSummaryWire,
} from './contracts';
import type { ReplayScene, SceneBlueprint, SceneFrame, ScenePrimitive } from '../core/scene';
import type { SavedRun, SimulationJob } from '../core/commands';

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
  if (wire.status === 'done') {
    return { state: 'done', runNumber: typeof wire.run === 'number' ? wire.run : undefined };
  }
  if (wire.status === 'error') {
    return { state: 'error', errorMessage: wire.error || 'The backend job failed.' };
  }
  return { state: 'running' };
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

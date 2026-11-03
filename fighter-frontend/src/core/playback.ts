/**
 * Pure playback math. No React, timers, HTTP, or Three.js dependencies.
 * The renderer receives a sampled frame and does not know about time controls.
 */

import type { DisplayFrame, SceneFrame } from './scene';

export function getReplayDuration(frames: readonly SceneFrame[]): number {
  return frames.length > 0 ? frames[frames.length - 1].time : 0;
}

/** Find two adjacent frames and interpolate every XYZ coordinate. */
export function sampleAtTime(frames: readonly SceneFrame[], time: number): DisplayFrame | null {
  if (frames.length === 0) return null;
  if (frames.length === 1 || time <= frames[0].time) {
    const first = frames[0];
    return { time: first.time, positions: first.positions, hiddenPrimitiveIds: first.hiddenPrimitiveIds };
  }

  const last = frames[frames.length - 1];
  if (time >= last.time) {
    return { time: last.time, positions: last.positions, hiddenPrimitiveIds: last.hiddenPrimitiveIds };
  }

  // Binary search keeps seeking efficient even for long replays.
  let low = 0;
  let high = frames.length - 1;
  while (low + 1 < high) {
    const middle = Math.floor((low + high) / 2);
    if (frames[middle].time <= time) low = middle;
    else high = middle;
  }

  const from = frames[low];
  const to = frames[high];
  const span = Math.max(0.000001, to.time - from.time);
  const alpha = Math.min(1, Math.max(0, (time - from.time) / span));
  const positions = new Array<number>(from.positions.length);

  for (let index = 0; index < positions.length; index += 1) {
    positions[index] = from.positions[index] + (to.positions[index] - from.positions[index]) * alpha;
  }

  return {
    time,
    positions,
    // Destruction changes are discrete events: keep the earlier state during
    // interpolation and switch only when the playhead reaches the next frame.
    hiddenPrimitiveIds: from.hiddenPrimitiveIds,
  };
}

export function formatTime(seconds: number): string {
  const safe = Math.max(0, Number.isFinite(seconds) ? seconds : 0);
  const minutes = Math.floor(safe / 60);
  const remainder = Math.floor(safe % 60);
  const tenths = Math.floor((safe % 1) * 10);
  return `${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}.${tenths}`;
}

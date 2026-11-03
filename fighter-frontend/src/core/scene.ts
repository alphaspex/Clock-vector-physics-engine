/**
 * Renderer-facing scene model.
 *
 * This file intentionally has no backend, HTTP, React, or fighter-anatomy
 * dependencies. The renderer only understands generic points and primitives.
 */

export type ScenePrimitive =
  | {
      id: number;
      kind: 'sphere';
      point: number;
      radius: number;
      label?: string;
    }
  | {
      id: number;
      kind: 'capsule';
      from: number;
      to: number;
      radius: number;
      label?: string;
    };

export interface SceneBlueprint {
  pointCount: number;
  primitives: ScenePrimitive[];
  arena: {
    radius: number;
    wallHeight: number;
    wallThickness: number;
  };
  framesPerSecond: number;
  fighterCount: number;
}

/** A single normalized position update. Positions are flat XYZ triples. */
export interface SceneFrame {
  time: number;
  positions: number[];
  hiddenPrimitiveIds: number[];
}

export interface ReplayScene {
  blueprint: SceneBlueprint;
  frames: SceneFrame[];
  result: string | null;
}

/** Interpolated display frame produced by the playback engine. */
export interface DisplayFrame {
  time: number;
  positions: number[];
  hiddenPrimitiveIds: readonly number[];
}

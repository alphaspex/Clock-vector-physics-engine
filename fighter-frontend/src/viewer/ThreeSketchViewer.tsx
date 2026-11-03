import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { DisplayFrame, SceneBlueprint, ScenePrimitive } from '../core/scene';

interface Props {
  blueprint: SceneBlueprint | null;
  frame: DisplayFrame | null;
  cameraResetKey: number;
}

type PartMode = 'point' | 'cylinder' | 'end-a' | 'end-b';

interface GeometryPart {
  mode: PartMode;
  /** Local vertices; each pair of XYZ triples describes one line segment. */
  vertices: number[];
  /** Offset into the combined Float32Array for this line layer. */
  offset: number;
}

interface PrimitiveBinding {
  primitive: ScenePrimitive;
  inkParts: GeometryPart[];
  sketchParts: GeometryPart[];
}

interface ViewerRuntime {
  camera: THREE.PerspectiveCamera;
  controls: OrbitControls;
  bindings: PrimitiveBinding[];
  inkPositions: Float32Array;
  sketchPositions: Float32Array;
  inkAttribute: THREE.BufferAttribute;
  sketchAttribute: THREE.BufferAttribute;
  initialCameraPosition: THREE.Vector3;
  initialTarget: THREE.Vector3;
}

const UP = new THREE.Vector3(0, 1, 0);

/** Generate sphere latitude/longitude line vertices without triangle diagonals. */
function sphereGridVertices(radius: number, longitudeCount = 10, latitudeCount = 7): number[] {
  const coordinates: number[] = [];
  const addSegment = (a: THREE.Vector3, b: THREE.Vector3) => {
    coordinates.push(a.x, a.y, a.z, b.x, b.y, b.z);
  };

  const pointAt = (phi: number, theta: number) => new THREE.Vector3(
    radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  );

  for (let latitude = 1; latitude < latitudeCount; latitude += 1) {
    const phi = (Math.PI * latitude) / latitudeCount;
    for (let longitude = 0; longitude < longitudeCount; longitude += 1) {
      const a = (Math.PI * 2 * longitude) / longitudeCount;
      const b = (Math.PI * 2 * (longitude + 1)) / longitudeCount;
      addSegment(pointAt(phi, a), pointAt(phi, b));
    }
  }

  for (let longitude = 0; longitude < longitudeCount; longitude += 1) {
    const theta = (Math.PI * 2 * longitude) / longitudeCount;
    for (let latitude = 0; latitude < latitudeCount; latitude += 1) {
      const phiA = (Math.PI * latitude) / latitudeCount;
      const phiB = (Math.PI * (latitude + 1)) / latitudeCount;
      addSegment(pointAt(phiA, theta), pointAt(phiB, theta));
    }
  }
  return coordinates;
}

/** Open cylindrical sleeve: two circular rims and longitudinal guide lines. */
function cylinderGridVertices(radius: number, radialSegments = 10): number[] {
  const coordinates: number[] = [];
  const addSegment = (ax: number, ay: number, az: number, bx: number, by: number, bz: number) => {
    coordinates.push(ax, ay, az, bx, by, bz);
  };

  for (let segment = 0; segment < radialSegments; segment += 1) {
    const a = (Math.PI * 2 * segment) / radialSegments;
    const b = (Math.PI * 2 * (segment + 1)) / radialSegments;
    const ax = Math.cos(a) * radius;
    const az = Math.sin(a) * radius;
    const bx = Math.cos(b) * radius;
    const bz = Math.sin(b) * radius;
    addSegment(ax, -0.5, az, bx, -0.5, bz);
    addSegment(ax, 0.5, az, bx, 0.5, bz);
    addSegment(ax, -0.5, az, ax, 0.5, az);
  }
  return coordinates;
}

/** Static arena boundary. Both wall contours are lines, never a shaded mesh. */
function makeArenaGeometry(radius: number, wallHeight: number, wallThickness: number): THREE.BufferGeometry {
  const coordinates: number[] = [];
  const addSegment = (ax: number, ay: number, az: number, bx: number, by: number, bz: number) => {
    coordinates.push(ax, ay, az, bx, by, bz);
  };
  const radii = wallThickness > 0 ? [radius, Math.max(0.1, radius - wallThickness)] : [radius];

  for (const ringRadius of radii) {
    for (let segment = 0; segment < 72; segment += 1) {
      const a = (Math.PI * 2 * segment) / 72;
      const b = (Math.PI * 2 * (segment + 1)) / 72;
      const ax = Math.cos(a) * ringRadius;
      const az = Math.sin(a) * ringRadius;
      const bx = Math.cos(b) * ringRadius;
      const bz = Math.sin(b) * ringRadius;
      addSegment(ax, 0.01, az, bx, 0.01, bz);
      if (wallHeight > 0) {
        addSegment(ax, wallHeight, az, bx, wallHeight, bz);
        if (segment % 3 === 0) addSegment(ax, 0.01, az, ax, wallHeight, az);
      }
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(coordinates, 3));
  return geometry;
}

function offsetVertices(vertices: number[], x: number, z: number): number[] {
  const result = vertices.slice();
  for (let index = 0; index < result.length; index += 3) {
    result[index] += x;
    result[index + 2] += z;
  }
  return result;
}

/**
 * TV-only 3D renderer.
 *
 * It receives a generic scene description and sampled XYZ data. It has no API,
 * form, fighter-anatomy, physics, or simulation dependencies. All primitives
 * are merged into two dynamic line buffers plus one static arena buffer, so a
 * whole scene is rendered in three draw calls rather than one per body part.
 */
export default function ThreeSketchViewer({ blueprint, frame, cameraResetKey }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<ViewerRuntime | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !blueprint) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#fbfbf8');

    const width = Math.max(1, host.clientWidth);
    const height = Math.max(1, host.clientHeight);
    const camera = new THREE.PerspectiveCamera(38, width / height, 0.01, 200);
    const initialCameraPosition = new THREE.Vector3(
      blueprint.arena.radius * 1.55,
      blueprint.arena.radius * 1.1,
      blueprint.arena.radius * 2.05,
    );
    const initialTarget = new THREE.Vector3(0, 0.9, 0);
    camera.position.copy(initialCameraPosition);
    camera.lookAt(initialTarget);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'low-power' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
    renderer.setSize(width, height);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setClearColor('#fbfbf8', 1);
    renderer.domElement.setAttribute('aria-label', 'Interactive 3D wireframe simulation replay');
    renderer.domElement.className = 'three-sketch-canvas';
    host.appendChild(renderer.domElement);

    // Lines are unlit by design. No surfaces, lighting model, or shadows exist.
    const ink = new THREE.LineBasicMaterial({ color: '#171717', transparent: true, opacity: 0.94 });
    const sketchInk = new THREE.LineBasicMaterial({ color: '#777771', transparent: true, opacity: 0.24 });
    const arenaInk = new THREE.LineBasicMaterial({ color: '#5b5b56', transparent: true, opacity: 0.38 });
    const arenaGeometry = makeArenaGeometry(
      blueprint.arena.radius,
      blueprint.arena.wallHeight,
      blueprint.arena.wallThickness,
    );
    const arenaLines = new THREE.LineSegments(arenaGeometry, arenaInk);
    scene.add(arenaLines);

    const bindings: PrimitiveBinding[] = [];
    let inkLength = 0;
    let sketchLength = 0;

    const addPart = (parts: GeometryPart[], vertices: number[], mode: PartMode, layer: 'ink' | 'sketch') => {
      const offset = layer === 'ink' ? inkLength : sketchLength;
      parts.push({ mode, vertices, offset });
      if (layer === 'ink') inkLength += vertices.length;
      else sketchLength += vertices.length;
    };

    for (const primitive of blueprint.primitives) {
      const binding: PrimitiveBinding = { primitive, inkParts: [], sketchParts: [] };

      if (primitive.kind === 'sphere') {
        addPart(binding.inkParts, sphereGridVertices(primitive.radius), 'point', 'ink');
        addPart(
          binding.sketchParts,
          offsetVertices(sphereGridVertices(primitive.radius * 1.025), primitive.radius * 0.012, -primitive.radius * 0.01),
          'point',
          'sketch',
        );
      } else {
        addPart(binding.inkParts, cylinderGridVertices(primitive.radius), 'cylinder', 'ink');
        addPart(binding.inkParts, sphereGridVertices(primitive.radius), 'end-a', 'ink');
        addPart(binding.inkParts, sphereGridVertices(primitive.radius), 'end-b', 'ink');
        addPart(
          binding.sketchParts,
          offsetVertices(cylinderGridVertices(primitive.radius * 1.035), primitive.radius * 0.012, -primitive.radius * 0.01),
          'cylinder',
          'sketch',
        );
        addPart(
          binding.sketchParts,
          offsetVertices(sphereGridVertices(primitive.radius * 1.025), primitive.radius * 0.012, -primitive.radius * 0.01),
          'end-a',
          'sketch',
        );
        addPart(
          binding.sketchParts,
          offsetVertices(sphereGridVertices(primitive.radius * 1.025), primitive.radius * 0.012, -primitive.radius * 0.01),
          'end-b',
          'sketch',
        );
      }
      bindings.push(binding);
    }

    const inkPositions = new Float32Array(inkLength);
    const sketchPositions = new Float32Array(sketchLength);
    const inkGeometry = new THREE.BufferGeometry();
    const sketchGeometry = new THREE.BufferGeometry();
    const inkAttribute = new THREE.BufferAttribute(inkPositions, 3);
    const sketchAttribute = new THREE.BufferAttribute(sketchPositions, 3);
    inkAttribute.setUsage(THREE.DynamicDrawUsage);
    sketchAttribute.setUsage(THREE.DynamicDrawUsage);
    inkGeometry.setAttribute('position', inkAttribute);
    sketchGeometry.setAttribute('position', sketchAttribute);
    const inkLines = new THREE.LineSegments(inkGeometry, ink);
    const sketchLines = new THREE.LineSegments(sketchGeometry, sketchInk);
    // These buffers move after every replay snapshot. Disable automatic frustum
    // culling so Three.js never reuses a stale bounding sphere from old positions.
    inkLines.frustumCulled = false;
    sketchLines.frustumCulled = false;
    scene.add(inkLines, sketchLines);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.075;
    controls.target.copy(initialTarget);
    controls.minDistance = 1.5;
    controls.maxDistance = blueprint.arena.radius * 9;
    controls.maxPolarAngle = Math.PI * 0.49;
    controls.update();

    const resize = () => {
      const nextWidth = Math.max(1, host.clientWidth);
      const nextHeight = Math.max(1, host.clientHeight);
      camera.aspect = nextWidth / nextHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(nextWidth, nextHeight);
    };
    let resizeObserver: ResizeObserver | undefined;
    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(resize);
      resizeObserver.observe(host);
    } else {
      window.addEventListener('resize', resize);
    }

    let animationId = 0;
    const renderLoop = () => {
      controls.update();
      renderer.render(scene, camera);
      animationId = window.requestAnimationFrame(renderLoop);
    };
    renderLoop();

    runtimeRef.current = {
      camera,
      controls,
      bindings,
      inkPositions,
      sketchPositions,
      inkAttribute,
      sketchAttribute,
      initialCameraPosition,
      initialTarget,
    };

    return () => {
      window.cancelAnimationFrame(animationId);
      resizeObserver?.disconnect();
      window.removeEventListener('resize', resize);
      controls.dispose();
      renderer.dispose();
      if (host.contains(renderer.domElement)) host.removeChild(renderer.domElement);
      arenaGeometry.dispose();
      inkGeometry.dispose();
      sketchGeometry.dispose();
      ink.dispose();
      sketchInk.dispose();
      arenaInk.dispose();
      runtimeRef.current = null;
    };
  }, [blueprint]);

  // Update merged line buffers in-place: no objects or geometry are recreated
  // during playback, even when the backend changes the point positions.
  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!runtime || !blueprint || !frame) return;

    const hidden = new Set(frame.hiddenPrimitiveIds);
    const anchor = new THREE.Vector3();
    const output = new THREE.Vector3();
    const first = new THREE.Vector3();
    const second = new THREE.Vector3();
    const direction = new THREE.Vector3();
    const center = new THREE.Vector3();
    const rotation = new THREE.Quaternion();
    const local = new THREE.Vector3();

    const writeParts = (
      parts: GeometryPart[],
      target: Float32Array,
      isVisible: boolean,
      anchor: THREE.Vector3,
      quaternion: THREE.Quaternion | null,
      length: number,
    ) => {
      for (const part of parts) {
        for (let index = 0; index < part.vertices.length; index += 3) {
          const outputIndex = part.offset + index;
          if (!isVisible) {
            target[outputIndex] = 0;
            target[outputIndex + 1] = 0;
            target[outputIndex + 2] = 0;
            continue;
          }

          local.set(part.vertices[index], part.vertices[index + 1], part.vertices[index + 2]);
          if (part.mode === 'point') {
            output.copy(local).add(anchor);
          } else {
            if (part.mode === 'cylinder') local.y *= length;
            if (part.mode === 'end-a') local.y -= length / 2;
            if (part.mode === 'end-b') local.y += length / 2;
            output.copy(local).applyQuaternion(quaternion!).add(anchor);
          }
          target[outputIndex] = output.x;
          target[outputIndex + 1] = output.y;
          target[outputIndex + 2] = output.z;
        }
      }
    };

    for (const binding of runtime.bindings) {
      const primitive = binding.primitive;
      const visible = !hidden.has(primitive.id);

      if (primitive.kind === 'sphere') {
        const offset = primitive.point * 3;
        const valid = offset + 2 < frame.positions.length;
        if (valid) anchor.set(frame.positions[offset], frame.positions[offset + 1], frame.positions[offset + 2]);
        else anchor.set(0, 0, 0);
        writeParts(binding.inkParts, runtime.inkPositions, visible && valid, anchor, null, 0);
        writeParts(binding.sketchParts, runtime.sketchPositions, visible && valid, anchor, null, 0);
        continue;
      }

      const fromOffset = primitive.from * 3;
      const toOffset = primitive.to * 3;
      const valid = fromOffset + 2 < frame.positions.length && toOffset + 2 < frame.positions.length;
      if (valid) {
        first.set(frame.positions[fromOffset], frame.positions[fromOffset + 1], frame.positions[fromOffset + 2]);
        second.set(frame.positions[toOffset], frame.positions[toOffset + 1], frame.positions[toOffset + 2]);
        direction.subVectors(second, first);
      } else {
        first.set(0, 0, 0);
        second.set(0, 0, 0);
        direction.set(0, 1, 0);
      }
      const distance = direction.length();
      const length = Math.max(distance, 0.00001);
      if (distance > 0.00000001) direction.multiplyScalar(1 / distance);
      else direction.copy(UP);
      center.copy(first).add(second).multiplyScalar(0.5);
      rotation.setFromUnitVectors(UP, direction);
      writeParts(binding.inkParts, runtime.inkPositions, visible && valid, center, rotation, length);
      writeParts(binding.sketchParts, runtime.sketchPositions, visible && valid, center, rotation, length);
    }

    runtime.inkAttribute.needsUpdate = true;
    runtime.sketchAttribute.needsUpdate = true;
  }, [blueprint, frame]);

  // Camera reset is an independent UI action; it never changes replay data.
  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!runtime) return;
    // The position is restored relative to the loaded arena's original view.
    runtime.camera.position.copy(runtime.initialCameraPosition);
    runtime.controls.target.copy(runtime.initialTarget);
    runtime.controls.update();
  }, [cameraResetKey]);

  return <div className="three-sketch-host" ref={hostRef} />;
}

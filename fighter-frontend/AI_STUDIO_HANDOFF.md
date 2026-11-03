# AI Studio handoff instructions

This file describes the intended architecture for anyone (including an AI coding assistant) who edits this repository.

## Non-negotiable design intent

The frontend is a **TV-only renderer**. The Python backend owns the simulation and sends the scene description and frame positions. Do not recreate fighter bodies, joints, movement rules, damage, or physics in JavaScript.

The renderer must stay generic:

- Iterate over the scene primitives returned by the backend.
- Use the point indices and radii supplied by the backend.
- Read all XYZ positions from the current replay frame.
- Hide primitive IDs listed in the frame's destroyed-shape array.
- Never hardcode 44 points, 102 shapes, fighter names, or body-part locations.
- Keep the visual style as black line-only 3D sketch geometry: no surface fills, color materials, realistic lighting, or shadows.

## File ownership

- UI forms/buttons/labels: `src/features/launcher/LauncherPanel.tsx`
- Replay history UI: `src/features/history/RunHistory.tsx`
- Playback controls UI: `src/features/playback/PlaybackBar.tsx`
- Page composition: `src/app/App.tsx`
- UI-level command/view-model vocabulary: `src/core/commands.ts`
- Exact backend JSON/wire contracts: `src/io/contracts.ts` (only `src/io/` imports these)
- HTTP calls and wire-to-app translation: `src/io/client.ts` and `src/io/mapper.ts`
- Generic replay scene and interpolation: `src/core/scene.ts` and `src/core/playback.ts`
- Generic 3D renderer: `src/viewer/ThreeSketchViewer.tsx`

A purely visual UI change should not edit `src/io/`, `src/core/`, or `src/viewer/`. For a control's behavior, keep using the existing app command shape if its meaning is unchanged.

A change to server API field names or routes belongs in `src/io/`; translate it there so UI components do not learn the server's JSON vocabulary. Do not import `src/io/contracts.ts` from UI or viewer files.

A new backend geometry kind needs both a mapper in `src/io/mapper.ts` and a generic primitive renderer in `src/viewer/ThreeSketchViewer.tsx`. Do not add fighter-specific checks to the renderer.

## Existing backend API

The frontend targets the API in the accompanying backend archive:

- `GET /health`
- `GET /runs/practice`
- `GET /runs/fight`
- `POST /practice` with `{ ai, preset, interval, effort }`
- `POST /fight` with `{ presetA, presetB, interval, effortA, effortB }`
- `GET /jobs/{id}`
- `GET /replay/{kind}/{n}`

The supported provider IDs are `meta`, `meta_contrib`, and `baseten`. Efforts are `minimal`, `low`, `medium`, `high`, `xhigh`, and `max`. `interval` is an integer from 1 to 10.

The replay endpoint responds with `status: "computing"` before `status: "ready"`. The ready response contains `init` and `frames`.

## Deployment

Set `VITE_API_BASE_URL` to the existing Render web-service URL. Do not put `ADMIN_TOKEN` in Vite variables, source files, or Git. The console accepts a trusted operator's token at runtime for the two POST actions.

Before browser POST requests can work cross-origin, apply the CORS OPTIONS patch documented in `FRONTEND_PLAN_AND_AUDIT.md` to the Python server.

## Instructions for AI-assisted code edits

Preserve the boundary above. Do not combine the I/O adapter with React components. Do not hardcode scene point counts, shape counts, body-part labels, or point layouts. Keep all `fetch()` calls inside `src/io/client.ts`. If a user requests a UI-only change, make the smallest edit in the relevant `src/features/` file and keep its app-level command output stable. Update the tests and documentation when changing a contract.

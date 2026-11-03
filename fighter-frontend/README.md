# Fighter Simulation — Replay Console

A lightweight React + TypeScript + Three.js frontend for the supplied Python simulation backend.

## Core idea

The browser is a **TV, not a second simulation engine**. It requests a saved replay, reads the server's scene description, constructs generic wireframe primitives, and moves them with the supplied XYZ snapshots. It does not know what a shoulder, head, knee, fighter, or joint is.

The 3D view uses black line geometry on an off-white background. It does not use filled surfaces, material colors, realistic lighting, or shadows. A faint second contour creates a restrained technical-sketch quality.

## Architecture

```text
src/
  app/                  App composition and simulation workflow controller
  components/           Small shared UI components
  core/                 Generic scene model and pure playback math
  features/
    history/             Saved replay list UI
    launcher/            Practice/fight forms and operator token field
    playback/            Timeline controls and playback hook
  io/                   Only HTTP and backend contract mapping
  styles/               Page and component styles
  viewer/                Three.js generic wireframe renderer
```

### The important separation

- `src/io/` is the input/output boundary. It knows exact URLs, headers, JSON request bodies and backend response names. It is the only folder that calls `fetch()`.
- `src/core/commands.ts` defines app-facing commands and view models (for example, `provider`, `memorySlot`, and `createdAt`). UI components use these names, not Python JSON field names.
- `src/io/contracts.ts` defines the exact backend wire format (for example, `presetA`, `ai`, `n`, and `created`). Only files inside `src/io/` should import these wire types.
- `src/core/scene.ts` and `src/core/playback.ts` define generic geometry and replay timing, not fighter anatomy or the backend.
- `src/viewer/` only draws a generic `SceneBlueprint` and a sampled `DisplayFrame`.
- `src/features/` contains UI controls. UI-only changes belong here. The app controller in `src/app/` connects UI actions to the I/O adapter without making the controls understand HTTP.

Read `FRONTEND_PLAN_AND_AUDIT.md` before changing the contract or adding a new geometry primitive. For Google AI Studio, use the ready-to-paste project instructions in `AI_STUDIO_PROMPT.md` and also follow `AI_STUDIO_HANDOFF.md`.

## Run locally

Requirements: Node.js 20 or newer and npm.

```bash
cp .env.example .env
# Edit .env and set your backend URL.
npm install
npm run dev
```

Build and type-check:

```bash
npm run typecheck
npm run build
```

## Deploy to Render Static Site

- Build command: `npm install && npm run build`
- Publish directory: `dist`
- Environment variable: `VITE_API_BASE_URL` = your existing Python web-service URL

The frontend and Python web service remain separate. See `BACKEND_COMPATIBILITY.md` for the one required CORS adjustment and deployment checklist.

## Operator access

GET endpoints are used for health, run history and replay retrieval. The existing backend requires `X-Token` for new practice/fight POST requests. Enter the backend's `ADMIN_TOKEN` in the UI's admin-token field to launch a run. The value remains in component memory and is not stored in project files or browser storage.

This is an operator convenience, not multi-user authentication. Do not distribute the backend admin token to untrusted users. For a public multi-user app, add server-side login/session authentication.

## Extending the renderer

Current backend primitives:

- `ball` → generic sphere wireframe
- `cap` → generic capsule/link wireframe

Position values are flat XYZ triples. The renderer iterates every primitive returned in the scene description and every point index is read from the current frame. Changing the number or arrangement of points and links does not require a frontend update as long as those primitive contracts remain supported.

If the backend adds a new primitive kind, update the mapper in `src/io/mapper.ts` and add a generic drawing implementation in `src/viewer/ThreeSketchViewer.tsx`. Avoid introducing fighter-specific rules.

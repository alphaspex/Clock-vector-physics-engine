# Frontend plan and backend contract audit

## Product decision

Build a **TV-only, server-driven replay viewer**. The browser is not the source of truth for anatomy, physics, joint layout, or fighter positions. It draws generic geometric primitives described by the backend and moves them using the backend's position snapshots.

The frontend is intentionally split into four boundaries:

1. **`src/features/` — UI controls.** Forms, buttons, tabs, history and playback controls. This is where UI-only edits belong. The controls emit app-level command objects and do not build URLs or backend JSON.
2. **`src/app/` — orchestration.** Owns screen state and workflows (health checks, job polling, replay selection). It passes app-level commands to the I/O gateway; it does not call `fetch()`.
3. **`src/core/` — app models and playback math.** `commands.ts` defines app-facing command/view-model vocabulary; `scene.ts` and `playback.ts` define generic geometry and interpolation. No backend JSON naming, React, HTTP, or fighter anatomy.
4. **`src/io/` — input/output boundary.** `contracts.ts` describes exact backend JSON; `client.ts` owns URLs, headers and HTTP; `mapper.ts` translates between backend wire objects and app-level models. This is the only folder that calls `fetch()`.
5. **`src/viewer/` — TV renderer.** Three.js wireframe geometry only. It receives a generic blueprint and one sampled position frame. It never calls the API and never reads UI state.

This means a UI-only change (for example, changing a provider dropdown into a text box, adding a button, or reorganizing the control panel) should stay inside `src/features/` or `src/app/`. It should not require edits to the renderer. A backend wire-protocol change should be localized to `src/io/contracts.ts`, `src/io/client.ts`, and `src/io/mapper.ts`.

## Audited backend contract

The audit is based on the supplied `backend.zip`, not an assumed API design.

| Purpose | Existing route | Method | Frontend use |
|---|---|---:|---|
| Health | `/health` | GET | Initial connection check |
| Saved practice runs | `/runs/practice` | GET | History list |
| Saved fights | `/runs/fight` | GET | History list |
| Start practice | `/practice` | POST | Practice form |
| Start fight | `/fight` | POST | Fight form |
| Job status | `/jobs/{id}` | GET | Poll until done/error |
| Replay | `/replay/{kind}/{n}` | GET | Load a saved scene and frames |
| AI memory | `/memory/A` or `/memory/B` | GET | Contract typed for future UI use; not currently displayed |

### Exact request bodies

Practice:

```json
{
  "ai": "A",
  "preset": "meta_contrib",
  "interval": 3,
  "effort": "high"
}
```

Fight:

```json
{
  "presetA": "meta_contrib",
  "presetB": "baseten",
  "interval": 3,
  "effortA": "minimal",
  "effortB": "minimal"
}
```

Supported providers in `config.py`: `meta`, `meta_contrib`, `baseten`.

Supported efforts in `config.py`: `minimal`, `low`, `medium`, `high`, `xhigh`, `max`.

The server validates `interval` as an integer from 1 through 10 seconds. The frontend offers the same range. The current API does **not** accept custom simulation duration, so the frontend intentionally does not send one.

### Replay contract

`GET /replay/{kind}/{n}` initially returns:

```json
{ "status": "computing" }
```

When ready, it returns:

```json
{
  "status": "ready",
  "result": "A",
  "init": {
    "points": 44,
    "shapes": [
      { "k": "ball", "p": 0, "r": 0.092, "n": "A.core" },
      { "k": "cap", "a": 0, "b": 1, "r": 0.007, "n": "A.neck" }
    ],
    "world": { "ring": 5, "wall_h": 0.5, "wall_t": 0.2 },
    "fps": 30,
    "nf": 2
  },
  "frames": [
    { "t": 0, "p": [0, 0, 0], "x": [] }
  ]
}
```

The example is abbreviated; a real frame has three numbers (`x`, `y`, `z`) for every point. `x` contains shape indices to hide after destruction. Current `frames.py` emits `ball` and `cap` primitives. The mapper converts those wire types into generic `sphere` and `capsule` primitives for the viewer.

The current two-fighter shape description has 44 points and 102 shapes: 44 balls and 58 capsule links. The viewer loops over the server's list; it does not have 44 hardcoded points or a hardcoded body diagram.

### What “does not need frontend changes” means

- Changing positions, dimensions, radius, endpoints, point count, primitive count, or fighter arrangement: **no viewer changes** as long as the backend continues to emit supported `ball` and `cap` instructions.
- Reordering the points or changing the fighter template: **no viewer changes** because it follows the indices and links in `init.shapes`.
- Adding a new primitive kind (for example, `box` or arbitrary mesh): requires adding support in the small I/O mapper and adding a generic renderer for that primitive. Unknown types are skipped with a warning instead of crashing the scene.
- Changing a form control's appearance or interaction: UI files only, provided the same typed API command is still emitted.
- Changing an API route or request/response field: I/O files only, plus the UI adapter if the user-facing action itself changes.

## Audit findings and integration blockers

### 1. CORS preflight needs one backend patch

`server.py` currently returns `Access-Control-Allow-Origin` and `Access-Control-Allow-Headers`, but it does not return `Access-Control-Allow-Methods`. The frontend sends JSON POST requests and an `X-Token` header. A browser can therefore send an OPTIONS preflight and reject the POST before it reaches `api.py`.

Recommended minimal backend change: advertise the methods in both normal responses and the OPTIONS response. A clean `do_OPTIONS` implementation is:

```python
def do_OPTIONS(self):
    self.send_response(204)
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Token")
    self.send_header("Access-Control-Max-Age", "600")
    self.end_headers()
```

Also add `("Access-Control-Allow-Methods", "GET, POST, OPTIONS")` to the headers emitted by `_send()` if desired. For a public deployment, replace `*` with the exact static-site origin after the domain is known. Do not use cookie credentials with wildcard origin.

### 2. Admin token handling

The existing backend requires `X-Token` for `POST /practice` and `POST /fight`. The frontend includes a password field where the operator enters the token at runtime. It is held in component memory only; it is not placed in `.env`, source code, localStorage, sessionStorage, or the ZIP.

This is suitable for a single trusted operator using the console, but it is **not a secure multi-user authentication system**: a browser operator can inspect their own network requests and memory. For a public multi-user product, put a login/session layer or server-side proxy in front of these admin endpoints and do not give browser users the backend admin token.

### 3. Replay is post-run, not live streaming

`server.py` queues simulation work in a background thread. After a job is done, the frontend asks for a replay; replay generation can itself return `computing` before it returns `ready`. The viewer therefore displays a preparation state and then plays the saved result. No live physics stream or WebSocket is present in the supplied backend, and this frontend does not pretend otherwise.

### 4. Render Free cold starts

The static frontend can call the existing Render web service using `VITE_API_BASE_URL`. A free web service may be asleep after inactivity, so first requests can take longer. The UI surfaces connection errors and has a service-check action. The user should not interpret a cold start as a renderer failure.

## Validation performed on the supplied backend

The following scripts were run from the extracted backend folder:

- `python test_physics.py` — passed all reported physics checks.
- `python test_backend.py` — passed all reported API, frame-contract, deterministic replay, database, job, and real-HTTP checks.

`test_backend.py` explicitly confirmed the frame payload contains 102 shapes and the replay API eventually returns `status: ready` with frames. The frontend was designed around that tested contract. The frontend source was also checked with TypeScript transpilation, isolated contract typing, and focused mapper/playback tests. A full dependency-backed Vite production build was not run in the authoring environment because npm dependency installation timed out; run `npm install`, `npm run typecheck`, and `npm run build` in the deployment/authoring environment before publishing.

## Files to edit by task

| Desired change | First place to edit |
|---|---|
| Change select into text input, rearrange controls, add buttons | `src/features/launcher/LauncherPanel.tsx` |
| Change how replay history looks | `src/features/history/RunHistory.tsx` |
| Change play/pause, speed or timeline UI | `src/features/playback/PlaybackBar.tsx` |
| Change the 3D sketch line style | `src/viewer/ThreeSketchViewer.tsx` |
| Change frame interpolation or timing | `src/core/playback.ts` |
| Change backend routes, headers or JSON fields | `src/io/contracts.ts`, `src/io/client.ts`, and/or `src/io/mapper.ts` |
| Change the frontend's app-level command vocabulary | `src/core/commands.ts`, then update the UI and I/O adapter at that deliberate boundary |
| Change overall page layout and composition | `src/app/App.tsx` and `src/styles/global.css` |

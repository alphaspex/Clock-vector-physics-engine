# Fighter Simulation Control Room — Monorepo

Complete AI-driven stick fighter simulation system containing both the Python backend and the React + Three.js TV replay viewer, live monitoring control room, and database manager.

```text
.
├── backend/            Python physics engine, LLM integration & HTTP server
├── fighter-frontend/   React 18 + Three.js TV replay viewer & operator console
├── docker-compose.yml  Local Docker setup with PostgreSQL
└── README.md
```

---

## 1. Architecture Overview

- **Backend (`/backend`)**: Authoritative simulation engine. Computes kinematics, physics collisions, damage, AI reasoning, and outputs JSON frames with 3D coordinates.
  - Exposes RESTful API with CORS preflight for `GET`, `POST`, `DELETE`, and `OPTIONS`.
  - Authenticates administrative actions using the `X-Token` header matching the backend-only `ADMIN_TOKEN`.
  - Manages thread-safe job tracking, live activity event auditing, and eager replay generation.
- **Frontend (`/fighter-frontend`)**: TV-only wireframe renderer, live monitoring control room, and dynamic database management console.
  - Consumes backend scene definitions (`init.shapes`) and position snapshots (`frames`).
  - Maintains clean architectural boundaries: `src/io/` for network communication, `src/core/` for app-facing models, `src/features/` for UI controls, and `src/viewer/` for the generic Three.js renderer.

---

## 2. Deploying to Render

This monorepo deploys as two interconnected services on Render:

### A. Backend (Render Web Service)
1. In the Render Dashboard, click **New +** → **Web Service**.
2. Connect your GitHub repository.
3. Configure the service:
   - **Root Directory**: `backend`
   - **Environment**: `Docker` (or `Python 3`)
   - **Build Command** (if Python): `pip install -r requirements.txt`
   - **Start Command** (if Python): `python server.py`
4. **Environment Variables**:
   - `PORT`: `8000` (Render default is 10000 or custom)
   - `DATABASE_URL`: Connection string from your Render PostgreSQL database (`postgres://...`)
   - `ADMIN_TOKEN`: Secure secret string for authenticating run starts and admin operations
   - `MODEL_API_KEY`: API key for Meta AI providers (`api.meta.ai`)
   - `BASETEN_API_KEY`: API key for Baseten provider (`inference.baseten.co`)
5. Note your backend URL (e.g., `https://fighter-backend.onrender.com`).

### B. Frontend (Render Static Site)
1. In the Render Dashboard, click **New +** → **Static Site**.
2. Connect the same GitHub repository.
3. Configure the static site:
   - **Root Directory**: `fighter-frontend` (or `fighter frontend`)
   - **Build Command**: `npm install && npm run build`
   - **Publish Directory**: `dist`
4. **Environment Variables**:
   - `VITE_API_BASE_URL`: The full URL of your deployed backend service (e.g., `https://fighter-backend.onrender.com`).
5. Click **Create Static Site**.

---

## 3. Environment Variables Reference

| Variable | Service | Required | Purpose |
|---|---|---|---|
| `DATABASE_URL` | Backend | Optional | PostgreSQL connection string (`postgres://...`). Defaults to SQLite file `fighter.db` if unset. |
| `ADMIN_TOKEN` | Backend | Required for launch/admin | Secret authentication token verified against the `X-Token` request header. |
| `MODEL_API_KEY` | Backend | Required for Meta | Bearer token for `https://api.meta.ai/v1`. |
| `BASETEN_API_KEY` | Backend | Required for Baseten | Bearer token for `https://inference.baseten.co/v1`. |
| `PORT` | Backend | Optional | HTTP listen port (default `8000`). |
| `VITE_API_BASE_URL` | Frontend | Required | Base URL of the backend web service (baked into the frontend bundle at build time). |

---

## 4. AI Provider & Model Configuration

The application strictly supports two provider families:

### Meta
- **Muse Spark 1.3 Contributor** (Preset: `meta_contrib`, Model ID: `muse-spark-1.3-contributor`)
- **Muse Spark 1.3** (Preset: `meta`, Model ID: `muse-spark-1.3`)
- Uses `MODEL_API_KEY`, sends `system` role prompt messages, and supports reasoning effort levels (`minimal`, `low`, `medium`, `high`, `xhigh`, `max`).

### Baseten
- **Fixed Model**: `meta-models/muse-spark-open-1026` (Preset: `baseten`)
- Uses `BASETEN_API_KEY`, sends `developer` role prompt messages.
- Read-only in the UI without arbitrary model selection or silent fallback.

---

## 5. API Endpoints

### Public Endpoints
- `GET /health` — Service health check (`{"ok": true}`)
- `GET /runs/practice` — List completed practice runs
- `GET /runs/fight` — List completed fight runs
- `GET /jobs/<id>` — Query transient or completed job status
- `GET /replay/<kind>/<n>` — Load full deterministic replay scene & frames
- `GET /replay/<kind>/<n>/status` — Lightweight status check (`ready` vs `computing`)
- `GET /memory/<A|B>` — Read stored fighter memory notes and learned moves

### Authenticated Admin Endpoints (Require `X-Token` Header)
- `POST /practice` — Start practice simulation with `{ ai, preset, interval, effort, duration_minutes }`
- `POST /fight` — Start match with `{ presetA, presetB, interval, effortA, effortB, duration_minutes }`
- `GET /admin/jobs?limit=50` — Query recent and active jobs with progress and stage information
- `GET /admin/events?limit=100&since_id=N` — Chronological operational activity event feed
- `GET /admin/db/catalog` — Dynamic database catalog describing all manageable resources
- `GET /admin/db/<resource>?limit=50&offset=0` — Paginated list of records in a catalog resource
- `GET /admin/db/<resource>/<id>` — Detailed single record JSON payload
- `DELETE /admin/db/<resource>/<id>` — Delete a single record (active running jobs protected)
- `POST /admin/db/<resource>/delete-batch` — Bulk delete records by array of IDs: `{"ids": [...]}`
- `POST /admin/db/reset-memory` — Clear reflection notes & reset libraries (`{"target": "all" | "A" | "B"}`) while preserving run history

---

## 6. Verification & Test Commands

From repository root:
```bash
# Verify backend Python files compile cleanly
npm run build:backend

# Run automated tests for API, DB catalog, duration, and Baseten model identifier
npm run test:backend

# Verify frontend TypeScript types
npm run typecheck:frontend

# Verify frontend production bundle build
npm run build:frontend
```

# Fighter Simulation — Monorepo

Complete AI-driven stick fighter simulation system containing both the Python backend and the React + Three.js replay frontend.

```text
.
├── backend/            Python physics engine, LLM integration & HTTP server
├── frontend/           React 18 + Three.js TV replay viewer & operator console
├── docker-compose.yml  Local Docker setup with PostgreSQL
└── README.md
```

---

## 1. Architecture Overview

- **Backend (`/backend`)**: Authoritative simulation engine. Computes kinematics, physics collisions, damage, AI reasoning, and outputs JSON frames with 3D coordinates.
- **Frontend (`/frontend`)**: TV-only wireframe renderer. Consumes backend scene definitions (`init.shapes`) and position snapshots (`frames`). Never hardcodes fighter anatomy, joints, or physics.

---

## 2. Deploying to Render

This monorepo is set up to deploy as two interconnected services on Render:

### A. Backend (Render Web Service)
1. In Render Dashboard, click **New +** → **Web Service**.
2. Connect your GitHub repository.
3. Configure the service:
   - **Root Directory**: `backend` (or leave root and set Dockerfile path)
   - **Environment**: `Docker` (or `Python 3`)
   - **Build Command** (if Python): `pip install -r requirements.txt`
   - **Start Command** (if Python): `python server.py`
4. **Environment Variables**:
   - `PORT`: `8000` (Render default is 10000 or custom)
   - `DATABASE_URL`: Connection string from your Render PostgreSQL database (`postgres://...`)
   - `ADMIN_TOKEN`: Secure secret string for authenticating run starts
   - `MODEL_API_KEY`: API key for Meta / Baseten AI providers
5. Note your backend URL (e.g., `https://fighter-backend.onrender.com`).

### B. Frontend (Render Static Site)
1. In Render Dashboard, click **New +** → **Static Site**.
2. Connect the same GitHub repository.
3. Configure the static site:
   - **Root Directory**: `frontend`
   - **Build Command**: `npm install && npm run build`
   - **Publish Directory**: `dist`
4. **Environment Variables**:
   - `VITE_API_BASE_URL`: The full URL of your deployed backend service (e.g., `https://fighter-backend.onrender.com`).
5. Click **Create Static Site**.

---

## 3. CORS & Preflight

`backend/server.py` is pre-configured with complete CORS headers including `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Methods: GET, POST, OPTIONS`, and `Access-Control-Allow-Headers: Content-Type, X-Token` with HTTP 204 OPTIONS preflight support. Browser POST requests with the operator token work cross-origin out of the box.

---

## 4. Local Development

### Option 1: Docker Compose (Backend + PostgreSQL)
```bash
# Starts Postgres and Backend on port 8000
docker-compose up -d

# Start Frontend
cd frontend
cp .env.example .env
# Set VITE_API_BASE_URL=http://localhost:8000 in frontend/.env
npm install
npm run dev
```

### Option 2: Running directly
```bash
# 1. Backend
cd backend
pip install -r requirements.txt
python server.py

# 2. Frontend (in another terminal)
cd frontend
cp .env.example .env
npm install
npm run dev
```

---

## 5. Verification Commands

From repository root:
```bash
# Verify backend Python files compile
npm run build:backend

# Verify frontend types and production build
npm run typecheck:frontend
npm run build:frontend
```

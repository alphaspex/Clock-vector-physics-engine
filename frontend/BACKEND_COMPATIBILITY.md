# Backend compatibility checklist

The frontend is configured for the supplied Python API. Before deployment:

- [x] Apply the CORS OPTIONS patch in `FRONTEND_PLAN_AND_AUDIT.md` to `backend/server.py` (applied).
- [ ] Set `VITE_API_BASE_URL` to the full HTTPS URL of the existing Render web service (no trailing slash required).
- [ ] Keep `ADMIN_TOKEN` on the backend. Do not add it to a Vite environment variable or commit it.
- [ ] Enter the admin token in the frontend control panel when a trusted operator launches a simulation.
- [ ] Confirm `GET /health` returns `{ "ok": true }` from the deployed API.
- [ ] Confirm browser requests to `GET /runs/fight` and `GET /runs/practice` succeed.
- [ ] Confirm browser OPTIONS preflight and authenticated POST requests succeed.

## Render Static Site settings

- Root Directory: `frontend`
- Build command: `npm install && npm run build`
- Publish directory: `dist`
- Environment variable: `VITE_API_BASE_URL=https://YOUR-WEB-SERVICE.onrender.com`

For local development:

```bash
cp .env.example .env
# Edit .env and set VITE_API_BASE_URL to your backend URL.
npm install
npm run dev
```

## Notes

The UI is a static client and does not host or proxy the Python backend. The replay view is loaded after a job has been saved. The frontend is not responsible for physics, AI requests, simulation duration, or fighter construction.

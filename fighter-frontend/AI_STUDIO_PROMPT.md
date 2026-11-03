# Prompt for Google AI Studio

Use this repository as the complete starting frontend for the existing Fighter Simulation Python backend.

Read these files before making any edits:

1. `README.md`
2. `FRONTEND_PLAN_AND_AUDIT.md`
3. `AI_STUDIO_HANDOFF.md`
4. `BACKEND_COMPATIBILITY.md`

## Preserve the architecture

- Keep the application as a **TV-only replay viewer**. The Python backend owns simulation logic, fighter structure, physics, positions, and replay generation.
- Keep all HTTP requests inside `src/io/client.ts`.
- Keep exact Python API JSON names and response interfaces inside `src/io/contracts.ts`.
- Keep backend-to-app translation inside `src/io/mapper.ts`.
- Keep app-level commands in `src/core/commands.ts`; UI components must not import backend wire contracts.
- Keep generic scene types and interpolation in `src/core/scene.ts` and `src/core/playback.ts`.
- Keep all 3D drawing inside `src/viewer/ThreeSketchViewer.tsx`.
- Keep form controls, labels, buttons, and visual layout inside `src/features/` and `src/styles/`.
- Keep `src/app/` for composition and UI workflow coordination only.

## Non-negotiable renderer rules

- Never hardcode point counts, shape counts, fighter anatomy, body-part positions, joint layouts, or movement rules.
- Build the scene from the backend's `init` description and update it from replay snapshots.
- Keep the visual style as black/grey line-only geometry on a light background. No filled 3D surfaces, material shading, lights, or shadows.
- Preserve generic support for the current `ball` and `cap` primitives.
- If a new geometry type is added, implement it generically in the adapter and renderer; do not add fighter-specific conditionals.

## Change policy

When asked to change a textbox, dropdown, label, button, or panel arrangement, edit the smallest relevant UI file. Do not rewrite or merge the I/O layer, core model, or renderer just to change the interface. If the meaning of a UI action changes, update the app-level command type and translate it in `src/io/` deliberately.

Do not add `ADMIN_TOKEN` to `.env`, Vite variables, client source, GitHub, or any generated bundle. It is entered at runtime by the trusted operator. Keep `VITE_API_BASE_URL` as the only public build-time API configuration.

## Verify before finishing

Run:

```bash
npm install
npm run typecheck
npm run build
```

Fix errors without weakening TypeScript checks or removing the architectural boundaries. Verify the CORS OPTIONS patch described in `FRONTEND_PLAN_AND_AUDIT.md` has been applied to the backend before testing browser POST actions. Do not claim the browser can stream live positions; the supplied backend currently generates replays after a job completes.

When the requested changes are complete, summarize changed files and checks. Only publish/push the repository after confirming no secrets, `.env` files, `node_modules`, or `dist` output have been added to Git.

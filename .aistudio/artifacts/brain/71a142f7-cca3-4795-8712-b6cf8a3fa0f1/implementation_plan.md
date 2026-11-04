# Implementation Plan: AI Thinking Stream Tab (Live Running Rounds)

## User Requirements & Clarifications
- Add a new tab on the UI dedicated to the **AI Thinking Stream** during live running rounds.
- Capture interval descriptions/thoughts from AI answers for both **Practice** and **Fight** modes without modifying prompt structures.
- If `[THINKING]` tags are not present, fallback gracefully to displaying the complete interval answer.
- Only for current live running rounds (not post-match replays).
- During Fight mode, display Fighter A and Fighter B in **stacked vertical cards**.
- Display mode: **Show only latest interval with history drawer** (highlight latest active interval per fighter, with an expandable chronological drawer for previous intervals).

---

## 1. Backend Enhancements (`backend/server.py`, `backend/rounds.py`)
- **Robust Thinking & Fallback Extraction**:
  - In `backend/rounds.py` (`practice` and `fight` loops):
    - When an AI response is received, extract `[THINKING]` description.
    - If `thinking_text` is empty or missing, fallback to using the sanitized/full answer text (`clean_text.strip()`).
    - Pass both `thinking` and `raw_answer` in the `on_progress` dict with `decision` index, `fighter`, `frame`, `word_count`, and `time_sec`.
  - In `backend/server.py`:
    - Track both `latest_thinking_A` and `latest_thinking_B` in `JOBS[jid]` so that concurrent or alternating fight decisions don't overwrite each other.
    - Ensure `thinking_history` collects entries with `{ fighter, text, raw_text, decision, frame, time_sec, word_count }`.
    - Expose `latest_thinking_A` and `latest_thinking_B` in the `GET /jobs/<id>` response payload.

---

## 2. Frontend Contract & Mapper Updates (`fighter-frontend/src/io/`)
- **`src/io/contracts.ts`**:
  - Update `JobWireResponse` to include `latest_thinking_A`, `latest_thinking_B`, and enhanced `thinking_history` items.
- **`src/io/mapper.ts`**:
  - Map `latest_thinking_A` and `latest_thinking_B` into `SimulationJob` model in `src/core/commands.ts`.

---

## 3. UI Component: `LiveThinkingPanel.tsx` (`fighter-frontend/src/features/thinking/`)
- **Stacked Vertical Cards**:
  - **Fight Mode**: Card 1 for Fighter A (Blue theme), Card 2 for Fighter B (Red/Amber theme).
  - **Practice Mode**: Single prominent Card for Fighter A.
- **Latest Interval Hero View**:
  - Displays decision index (e.g., `Interval #4 (Frame 120 / ~4.0s)`), word count badge, and clean text.
  - Live typing/pulse animation when the AI is currently in the `decision` stage.
  - Fallback indicator if the response was captured as raw text vs structured thinking.
- **Expandable History Drawer**:
  - Collapsible timeline drawer listing all earlier intervals from the current live round.
  - Filterable by fighter (All / Fighter A / Fighter B).
  - Copy thought button for debugging or inspection.
- **Empty / Idle State**:
  - When no simulation is actively running, displays an "Awaiting Active Match" state with quick launcher shortcut buttons to start Practice or Fight.

---

## 4. App Shell & Navigation Integration (`fighter-frontend/src/app/App.tsx`)
- Add `'thinking'` tab to `AppTab` union type.
- Add `<Brain>` / `<Sparkles>` nav button titled `"AI Thinking"` with a live pulsing indicator when a job is in progress.
- Route tab selection to `<LiveThinkingPanel />`.

---

## 5. Verification Plan
- Run backend test suite (`python test_api_extensions.py`, `python test_backend.py`, `python test_official_spec.py`).
- Run frontend typecheck (`npm run typecheck` in `fighter-frontend`).
- Test both Practice and Fight live running progress with and without `[THINKING]` tags to verify fallback mechanism.

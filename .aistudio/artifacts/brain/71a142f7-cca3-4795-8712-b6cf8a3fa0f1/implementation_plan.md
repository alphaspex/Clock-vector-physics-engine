# Robot Fighter AI Decision Priorities & Database Purge Integration

Implementation plan for integrating high-level decision priorities and physical observation feedback loop rules into `backend/prompts.py`, alongside adding a dedicated "Delete All DB Data" feature in `DatabaseManager.tsx` backed by backend purge API endpoints.

## User Review & Critical Decisions

> [!IMPORTANT]
> The following design choices guide this revision:

- **Confirmed Decision 1 (Prompt Location)**: Integrated as a dedicated `DECISION PRIORITIES & STRATEGY EVALUATION RULES` section added to both Practice Mode (`practice_system`) and Fight Mode (`fight_system`) prompts in `backend/prompts.py`.
- **Confirmed Decision 2 (Simulation Scope)**: Enforced across both Practice Mode and Fight Mode for consistent physics behavior during both motor training and arena combat.
- **Confirmed Decision 3 (Thinking Alignment)**: The mandatory 20-word `[THINKING]` tag directive is guided to reflect current priority level (e.g. Protect/Recover/Support) and evaluate physical movement obstructions in every interval.
- **Confirmed Decision 4 (Database Clear Feature)**: Added a "Delete All DB Data" button in `DatabaseManager.tsx` with a dual-confirmation modal to allow operators to wipe all database tables (runs, replays, notes, libraries, summaries, interval descriptions, jobs, and events) cleanly in one click.

---

## 1. Overview & Core Concept

- **Decision Hierarchy & Physical Feedback**:
  1. **Protect**: Keep head and neck away from dangerous ground contact or strikes at all times.
  2. **Recover**: If chest is grounded, prioritize lifting it off the floor above all aggressive actions.
  3. **Establish Support**: Use fist contact and arm positioning to form a stable physical base.
  4. **Stabilize**: Halt unwanted sliding and regain posture control before launching attacks.
  5. **Move**: Only after recovery and support are established, attempt crawling and rotation.
  6. **Fight**: When an opponent is present, balance recovery, defense, and attack strategy.
  - *Physical Observation Feedback Loop*: Never repeat failed physical strategies without a meaningful parameter change. Analyze physical observations post-action to identify movement blockers and adapt motor rotations or support positions when recovery fails repeatedly.

- **Database Purge Management**:
  - Adds a prominent, red "Delete All DB Data" button in `DatabaseManager.tsx`.
  - Sends a secure request to `POST /admin/db/purge-all` requiring admin token authentication.
  - Truncates/deletes records across all tables (`runs`, `replays`, `round_summaries`, `interval_descriptions`, `notes`, `library`, `jobs`, `job_events`) and resets active state safely.

---

## 2. User Experience & Visual Design

- **Database Manager UI Extensions**:
  - In `DatabaseManager.tsx`, alongside the existing "Reset Memory" button, a red `<Trash2 /> Delete All DB Data` button will be placed in the header action toolbar.
  - Clicking "Delete All DB Data" opens a red warning modal explicitly listing that all saved fights, practices, memories, move libraries, jobs, and event feeds will be deleted permanently.
  - Upon confirmation, a success toast confirms database truncation and refreshes the catalog tab counts to 0.

- **Live Reasoning & Physical Behavior**:
  - In `LiveThinkingPanel` and `ControlRoomPanel`, AI interval thinking will reflect priority awareness and physical blockage diagnoses.
  - In `ThreeSketchViewer`, stick-fighters will demonstrate safer head clearance and immediate chest lifting when grounded.

---

## 3. Key Product Decisions & Trade-Offs

- **Decision 1: Prompt Extension in `backend/prompts.py`**
  - *Chosen Approach*: Embed `_DECISION_PRIORITIES` in `backend/prompts.py` for `practice_system()` and `fight_system()`.
  - *Why*: Preserves 100% compatibility with motor syntax rules (exact 15° rotation multiples), 20-word thinking parser, and automated test suites (`test_official_spec.py`, `test_backend.py`, `test_physics.py`).

- **Decision 2: Comprehensive Database Purge in `backend/db.py` & `backend/api.py`**
  - *Chosen Approach*: Implement `purge_all_database_data(conn)` in `backend/db.py` and route it through `POST /admin/db/purge-all` in `backend/api.py`.
  - *Why*: Provides a clean, complete database reset capability for developers and operators without requiring raw database shell access.

---

## 4. Technical Architecture & Data Strategy

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Fighter AI & Database System                    │
└────────────────────────────────────────────────────────────────────────┘
                                    │
         ┌──────────────────────────┴──────────────────────────┐
         ▼                                                     ▼
┌─────────────────────────┐                           ┌─────────────────────────┐
│  AI System Prompts      │                           │  Database Management    │
│  (backend/prompts.py)   │                           │  (DatabaseManager.tsx)  │
└────────────┬────────────┘                           └────────────┬────────────┘
             │                                                     │
             ▼                                                     ▼
┌─────────────────────────┐                           ┌─────────────────────────┐
│ _DECISION_PRIORITIES    │                           │  "Delete All DB Data"   │
│ - 6 Priority Tiers      │                           │  Confirmation Modal     │
│ - Feedback Evaluation   │                           └────────────┬────────────┘
│ - 20-Word Thinking      │                                        │
└────────────┬────────────┘                                        ▼
             │                                        ┌─────────────────────────┐
             ▼                                        │ POST /admin/db/purge-all│
┌─────────────────────────┐                           └────────────┬────────────┘
│ AI Model Execution      │                                        │
│ (backend/ai_call.py)    │                                        ▼
└─────────────────────────┘                           ┌─────────────────────────┐
                                                      │ purge_all_db_data(conn) │
                                                      │ (backend/db.py)         │
                                                      └─────────────────────────┘
```

### Proposed Code Additions:

1. **`backend/prompts.py`**:
```python
_DECISION_PRIORITIES = (
    "DECISION PRIORITIES & STRATEGY EVALUATION RULES:\n"
    "1. PROTECT: Keep head and neck away from dangerous ground contact or strikes at all times.\n"
    "2. RECOVER: If chest is grounded, prioritize lifting it off the floor above all aggressive actions.\n"
    "3. ESTABLISH SUPPORT: Use fist contact and arm positioning to form a stable physical base.\n"
    "4. STABILIZE: Stop unwanted sliding and regain posture control before launching attacks.\n"
    "5. MOVE: Only after recovery and support are established, attempt crawling and rotation.\n"
    "6. FIGHT: When an opponent is present, balance recovery, defense, and attack strategy.\n\n"
    "STRATEGY EVALUATION & FEEDBACK LOOP:\n"
    "- Never repeat a failed physical strategy without a meaningful change in motor angles or timing.\n"
    "- After issuing motor rotations, examine the next physical observation. If expected movement did not happen, identify what physically prevented it and choose a different motor action.\n"
    "- Do not assume that issuing a movement command means it succeeded physically.\n"
    "- When recovery fails repeatedly, stop experimenting with unrelated movements. Adjust support position, motor rotations, or recovery approach based on contact and movement data.\n"
    "- In your mandatory 20-word [THINKING] block, explicitly diagnose your current priority state and any physical movement obstructions.\n"
)
```

2. **`backend/db.py`**:
```python
def purge_all_database_data(conn, active_jobs=()):
    """Clears all records from every database table safely."""
    _x(conn, "DELETE FROM notes")
    _x(conn, "DELETE FROM round_summaries")
    _x(conn, "DELETE FROM interval_descriptions")
    _x(conn, "DELETE FROM replays")
    _x(conn, "DELETE FROM runs")
    _x(conn, "DELETE FROM library")
    _x(conn, "DELETE FROM job_events")
    _x(conn, "DELETE FROM jobs WHERE id NOT IN %s", (tuple(active_jobs) if active_jobs else ('__none__',),))
    conn.commit()
    return dict(ok=True, message="All database tables successfully purged.")
```

3. **`backend/api.py`**: Add route handler for `POST /admin/db/purge-all` calling `ctx["db_purge_all"]()`.
4. **`fighter-frontend/src/io/client.ts`**: Expose `purgeAllDatabase(adminToken: string)`.
5. **`fighter-frontend/src/features/database/DatabaseManager.tsx`**: Add "Delete All DB Data" button & confirmation modal handler.

---

## Verification Plan

- Run `python3 backend/test_official_spec.py` to ensure all 8 specification test sections pass 100%.
- Run `python3 backend/test_backend.py` and `python3 backend/test_all.py` to verify full backend, API, and database test suites.
- Verify in `DatabaseManager.tsx` that deleting all DB data purges records and resets all catalog counters to 0.

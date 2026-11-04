# Dual Robot AI Synchronization, Concurrent Summaries & Chest Weight Update (7kg)

Ensure dual robot fight rounds wait for both AI calls, execute end-of-round summaries concurrently, and update the robot chest mass from 4.0kg to 7.0kg with full verification across the physics engine and test suite.

## User Review & Critical Decisions

> [!IMPORTANT]
> Key revisions included in this plan per user feedback:

- **Chest Mass Update**: Increase chest ball mass in `backend/body.py` from 4.0 kg to 7.0 kg for improved physical stability, ensuring mass matrix `m`, inverse mass `w = 1/m`, drag coefficients, and motor effective mass (`meff`) adjust dynamically.
- **Dual AI Synchronization**: Guarantee that in `fight(...)` (`backend/rounds.py`), the server dispatches AI calls for Fighter A and Fighter B concurrently and blocks until both complete before applying orders or ticking physics.
- **Concurrent Summaries**: Execute Fighter A and Fighter B end-of-round AI summary generation concurrently using `ThreadPoolExecutor`.
- **Automated Verification**: Implement dedicated unit tests in `backend/test_backend.py` with artificial timing delays to verify timing barriers and mass stability.

---

## 1. Overview & Technical Goal

1. **Body Spec Mass Update (`backend/body.py`)**:
   - Update chest template entry from `("chest", 0.0, 0.35, 0.0, 0.092, IRON, 4.0)` to `("chest", 0.0, 0.35, 0.0, 0.092, IRON, 7.0)`.
   - Ensure all dependent physics parameters (`w`, `kdrag`, motor effective mass `meff`, forces) compute correctly.
2. **AI Call Synchronization & Summaries (`backend/rounds.py`)**:
   - Verify concurrent dispatch and synchronization barrier for Fighter A & B in decision loops.
   - Refactor end-of-round summaries to execute in parallel threads for both fighters.
3. **Automated Verification (`backend/test_backend.py` & `backend/test_official_spec.py`)**:
   - Test chest mass property and physics stability with 7.0 kg chest mass.
   - Add asynchronous delay test to verify simulation wait behavior in dual robot fight rounds.

---

## 2. Technical Architecture & Data Strategy

```
┌─────────────────────────────────────────────────────────┐
│                    Fight Round Loop                     │
│                                                         │
│  ┌────────────────────┐         ┌────────────────────┐  │
│  │  AI Call Fighter A │         │  AI Call Fighter B │  │
│  │ (e.g., fast 5ms)   │         │ (e.g., slow 100ms) │  │
│  └─────────┬──────────┘         └─────────┬──────────┘  │
│            │                              │             │
│            └──────────────┬───────────────┘             │
│                           │                             │
│                           ▼                             │
│           ┌────────────────────────────────┐            │
│           │   Synchronization Barrier     │            │
│           │ [f.result() for f in futures]  │            │
│           └───────────────┬────────────────┘            │
│                           │                             │
│                           ▼                             │
│           ┌────────────────────────────────┐            │
│           │ Apply Orders & Tick Physics    │            │
│           │ (Chest Mass = 7.0 kg)          │            │
│           └────────────────────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Step-by-Step Implementation Strategy

1. **`backend/body.py`**:
   - Change chest mass template line to `7.0` kg.
2. **`backend/rounds.py`**:
   - Verify `fight` decision loop submits both `asks` to `ThreadPoolExecutor(2)` and blocks on `[x.result() for x in futs]`.
   - Update end-of-round summary generation in `fight` to run both summary calls concurrently using `ThreadPoolExecutor(2)`.
3. **`backend/test_backend.py` & `backend/test_all.py`**:
   - Add unit tests verifying 7.0kg chest mass and synchronization behavior.
   - Run full test suite (`test_all.py`, `test_backend.py`, `test_official_spec.py`) to confirm 100% pass rate.

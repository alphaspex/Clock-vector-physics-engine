# Practice System: One-Move Learning and Mastery Architecture

Architectural blueprint for transitioning the robot fighter from open-ended, multi-move generation to a disciplined, goal-driven motor learning system where the AI refines, tests, and masters one physical movement at a time.

## User Review & Critical Decisions

> [!IMPORTANT]
> The following parameters and operational decisions were confirmed for this implementation:

- **Confirmed Decision 1 (Mastery Threshold)**: A movement is marked as `mastered` only after achieving **3 consecutive successful practice test rounds** meeting all physical success criteria.
- **Confirmed Decision 2 (Version History Storage)**: Explicit version history is attached directly to the active move in the library structure (`move_history` and `mastered_moves` dictionaries), preserving step rotations, timestamps, and physical outcome logs across revisions.
- **Confirmed Decision 3 (Chain Construction Rule)**: **Chains can ONLY be created using moves that have already achieved `mastered` status.** The AI is forbidden from chaining unverified or training moves.
- **Confirmed Decision 4 (Combo Practice Phase)**: Chain creation is treated as a separate "Combo Mastery" goal in practice. This goal only becomes available after at least two individual moves are mastered.
- **Confirmed Decision 5 (Fight Mode Separation)**: In Fight Mode, the AI strictly uses existing moves and chains using `do`, prioritizing mastered movements and verified chains. It does not create new moves or chains during combat.
- **Confirmed Decision 6 (Initial Recovery Benchmark)**: The initial movement goal is **Recovery**: moving from a chest-grounded prone position to a stable four-point base with both fists supporting the body and the chest lifted clear of the ground.

---

## 1. Overview & Core Concept: The Two-Phase Mastery System

Currently, the practice mode prompts the AI to freely generate arbitrary moves and chains. The new system enforces a strict hierarchical progression:

### Phase 1: Individual Move Mastery
- **One Goal per Session**: Target a single physical task (e.g., `recovery`).
- **One Move Sequence**: Refine a single motor sequence.
- **Physical Evaluation**: AI edits the move version based on telemetry until success criteria are met.
- **Certification**: 3 consecutive successes mark the move as `mastered`.

### Phase 2: Combo Chain Construction
- **Pre-requisite**: Multiple mastered moves must exist.
- **The Combo Goal**: A practice session focused on sequencing (e.g., "Chain `recovery` + `jab`").
- **Constraint**: Only `mastered` moves can be used as components in a `chain`.
- **Mastery Certification**: 3 consecutive successful executions of the chain (meeting the combo goal's specific physical success conditions) mark the chain as `mastered`.

### Core Rules
1. **No Clutter**: Do not create multiple moves for the same goal. Edit the existing one.
2. **Physical Evaluation & Iteration**: After each round, physics evaluation identifies failure points (e.g., inadequate arm extension). The AI edits the existing move rather than renaming or proliferating new moves.
3. **Fight Mode Execution**: Strictly uses saved `mastered` moves and chains. Tactical decisions only.

---

## 2. User Experience & Visual Design

- **Live Thinking & Practice Feedback**:
  - In practice mode, the AI's mandatory 20-word `[THINKING]` diagnosis explicitly evaluates the active goal (Individual or Combo), the performance of the current version, and the specific joint angle or timing adjustments required.
- **Control Room & Move Library Inspection**:
  - The move library displays a clear badge indicating `MASTERED (3/3 successes)` or `TRAINING (v{N}, streak: {X}/3)`.
  - Chains are visibly locked or disabled in the UI unless all component moves are `mastered`.
- **Fight Mode Execution**:
  - Fight mode decisions clearly demonstrate tactical execution: issuing `do recovery`, `do jab`, or combos assembled from mastered movements.

---

## 3. Key Product Decisions & Trade-Offs

- **Decision 1: Pure Physical Verification (Anti-Hallucination)**
  - *Chosen Approach*: Mastery and success are computed directly from the numerical physics simulation state, never from the AI's textual self-report.
  - *Why*: Ensures moves are physically functional.

- **Decision 2: Locked Chain Creation**
  - *Chosen Approach*: The system rejects any `chain` definition if its components are not found in the `mastered_moves` registry.
  - *Why*: Prevents "unstable stacks" of unverified moves that degrade combat reliability.

- **Decision 3: Dedicated Physical Goal Evaluator Module (`backend/practice_eval.py`)**
  - *Chosen Approach*: Encapsulate goal definitions, initial poses, and success condition checkers (Individual vs. Combo) in a dedicated evaluation module.
  - *Why*: Maintains modularity and keeps `sim.py` focused on the core simulation loop.

---

## 4. Technical Architecture & Data Strategy

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    ONE-MOVE LEARNING & MASTERY ARCHITECTURE                  │
└──────────────────────────────────────────────────────────────────────────────┘
                                       │
        ┌──────────────────────────────┴──────────────────────────────┐
        ▼                                                             ▼
┌──────────────────────────────┐              ┌──────────────────────────────┐
│     PRACTICE MODE            │              │          FIGHT MODE          │
│  (Experiment, Edit, Master)  │              │    (Execute Saved Moves)     │
└──────────────┬───────────────┘              └──────────────┬───────────────┘
               │                                             │
      ┌────────┴─────────────────────┐                       │
      ▼                              ▼                       ▼
┌───────────────────────┐    ┌───────────────────────┐  ┌──────────────────────┐
│ PHASE 1: INDIVIDUAL   │    │ PHASE 2: COMBO        │  │ Tactical Selector    │
│ Goal: Master 1 Move   │    │ Goal: Sequence Moves  │  │ - Mastered Only      │
│ - Phys Evaluation     │    │ - Mastered-Only Rule  │  │ - No AI Creation     │
└──────────────┬────────┘    └──────────────┬────────┘  └──────────────────────┘
               │                            │
               └─────────────┬──────────────┘
                             ▼
┌────────────────────────────────────────────────────────────┐
│ Physical Evaluator (backend/practice_eval.py)              │
│ - Success: 3/3 Streak -> Mark MASTERED                     │
│ - Failure: Reset Streak -> Provide Physics Diagnostics     │
└────────────────────────────────────────────────────────────┘
```

### Data Structures & State Management

1. **Move Library Schema Extension (`library` table in `backend/db.py`)**:
```json
{
  "moves": { ... },
  "chains": {
    "recovery_guard": ["recovery", "high_guard"]
  },
  "mastered_moves": {
    "recovery": { "streak": 3, "goal": "recovery", ... },
    "high_guard": { "streak": 3, "goal": "guard", ... }
  },
  "mastered_chains": {
    "recovery_guard": { "streak": 3, "components": ["recovery", "high_guard"] }
  },
  "move_history": { ... }
}
```

2. **Core Components to Modify / Implement**:
- **`backend/practice_eval.py` (New Module)**:
  - Defines goal specifications and success criteria for both Individual and Combo goals.
- **`backend/prompts.py`**:
  - Updates `practice_system()` to guide the AI through the two-phase progression.
  - Enforces the rule: "You cannot create chains unless the moves used are MASTERED."
- **`backend/moves.py`**:
  - Enhances `parse()` and `merge()` to validate chain components against `mastered_moves`.
- **`backend/rounds.py`**:
  - Tracks success streaks and updates mastery registries in the DB.

- **`backend/test_practice_mastery.py` (New Automated Test Suite)**:
  - Comprehensive unit and integration tests verifying single-goal practice, move versioning, physical evaluation rules, mastery threshold (3 consecutive successes), and fight mode move usage.

---

## 5. Verification Plan

### Automated Backend Tests
- Run `python3 backend/test_practice_mastery.py` to verify:
  1. Initial chest-grounded state setup for recovery practice.
  2. Physical evaluation functions correctly identify success vs. failure based on physics data.
  3. Single-move editing preserves version history without creating duplicate move names.
  4. Mastery status triggers precisely upon 3 consecutive successes.
  5. Fight mode prompt correctly exposes mastered moves and forbids move creation.
- Run `python3 backend/test_all.py` to ensure existing motor limits, 15° multiples, damage calculations, and 20-word thinking extractions continue to pass with 0 regressions.

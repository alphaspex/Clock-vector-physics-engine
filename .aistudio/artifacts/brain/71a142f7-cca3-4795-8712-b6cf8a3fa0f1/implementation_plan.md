# Practice System: AI-Self-Approved Mastery Architecture

Revised architectural plan to transition mastery verification from deterministic backend math to AI-driven self-assessment. The AI now evaluates its own performance based on physical telemetry and determines if it has achieved its goal.

## User Review & Critical Decisions

> [!IMPORTANT]
> The following parameters were updated to move the "Judge" role from the system to the AI:

- **Confirmed Decision 1 (AI as Judge)**: Mastery is determined by the AI's self-evaluation. The backend will parse the AI-generated `round_summary` for a specific status tag (e.g., `RESULT: SUCCESS`).
- **Confirmed Decision 2 (Telemetry for Evaluation)**: To ensure the AI makes informed judgments, the system provides a detailed **Physical Final State Report** (chest height, ground contacts, stability) to the AI during the summary generation phase.
- **Confirmed Decision 3 (Mastery Threshold)**: A single AI-declared success (`RESULT: SUCCESS`) is sufficient to mark a move or chain as `mastered`.
- **Confirmed Decision 4 (History & Separations)**: All previous rules regarding version history, separation of practice and fighting, and chain construction (mastered-only) remain in effect.

---

## 1. Overview & Core Concept: AI Self-Assessment

The "One-Move Learning and Mastery" system now relies on the AI's ability to reflect on its physical results:

1. **Practice Execution**: The AI performs a trial round with a specific goal (e.g., Recovery).
2. **Telemetry Collection**: The system records the final physical state (coordinates, contacts, velocities).
3. **Reflective Summary & Judgment**:
   - The AI is asked to write its 3-part round summary.
   - It is provided with all interval thoughts AND the final physical state data.
   - The AI must conclude with either `RESULT: SUCCESS` or `RESULT: FAILED`.
4. **Mastery Update**:
   - The backend parses the summary text.
   - If `RESULT: SUCCESS` is found, the active move is marked as `mastered`.
   - If `RESULT: FAILED` is found (or no tag), the move remains in training.

---

## 2. Technical Architecture & Data Strategy

### Summary Prompt Update (`backend/prompts.py`)
The `round_summary_system` is updated to include:
- A requirement to evaluate the physical evidence provided.
- A mandatory format for the final judgment line.

### Logic Update (`backend/rounds.py`)
- **Success Extraction**: A new parser looks for the `RESULT:` tag in the AI's summary.
- **Goal Evaluation Removal**: The `practice_eval.evaluate_goal` function is no longer used to determine mastery. It is now only used to generate a "Physical Report" that is passed to the AI as context for its summary.

### Data Model
- No changes to the database schema are required. The mastery status remains in the `library` table.

---

## 3. Implementation Steps

1. **`backend/prompts.py`**:
   - Modify `round_summary_system` to include the `RESULT: SUCCESS/FAILED` instruction.
   - Update `round_summary_user` to accept a `physical_report` string.
2. **`backend/rounds.py`**:
   - In `practice()`, generate the physical report using `practice_eval`.
   - Pass this report to the summary AI call.
   - Parse the resulting summary for the mastery status.
3. **`backend/practice_eval.py`**:
   - Keep the evaluation logic but rename/refactor it to return a natural-language report string for the AI's consumption.
4. **`backend/test_practice_mastery.py`**:
   - Update tests to verify that mastery is granted only when the AI summary contains the success tag.

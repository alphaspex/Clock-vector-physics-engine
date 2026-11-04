# Implementation Plan - AI Chest Rotation, Body Part Destruction Display, and Move Deletion

## Summary
This plan addresses three core engine requirements:
1. **Chest Rotation & Arena Locomotion**: Clarify in system prompt rules and physics guidance how differential arm ground forces drive chest rotation and arena movement.
2. **Destroyed Body Parts & Motor Status**: Update prompt tree formatting so destroyed body balls show `STATUS: DESTROYED` explicitly and associated motors display `STATUS: DESTROYED (DISABLED)` so the AI refrains from attempting to control destroyed limbs.
3. **Move & Chain Deletion (`forget NAME`)**: Extend the move parser and library merger to support `forget NAME` (or `forget NAME1, NAME2`), allowing the AI in practice mode to delete obsolete or ineffective moves and chains.

---

## Target Changes

### 1. Prompt Body Tree & Motor Status (`/backend/observe.py`)
- **Body Part Destruction Status**:
  - Update `build_fighter_tree()` to check `palive[ball_idx]` for `CHEST`, `HEAD`, `RIGHT_SHOULDER`, `RIGHT_ELBOW`, `RIGHT_FIST`, `LEFT_SHOULDER`, `LEFT_ELBOW`, `LEFT_FIST`.
  - Display `STATUS: INTACT` or `STATUS: DESTROYED` under every physical body part heading.
  - In `build_enemy_tree()`, include `STATUS: INTACT` or `STATUS: DESTROYED` for enemy body parts.
- **Motor Destruction Status**:
  - Update `format_motor_state()` to check if the motor's pivot or joint is destroyed (`not palive[mo['pv']]` or `not lalive[mo['lid']]`).
  - If destroyed, format as `STATUS: DESTROYED (DISABLED)` instead of reporting target rotations.

### 2. Move & Chain Deletion Engine (`/backend/moves.py` & `/backend/prompts.py`)
- **Parser Extension (`/backend/moves.py`)**:
  - Add parsing for `forget NAME` or `delete NAME` (handling comma-separated lists of move/chain names).
  - Return `forget` list in `parse()` results.
- **Library Merger (`/backend/moves.py`)**:
  - In `merge()`, remove any names present in `parsed["forget"]` from `library["moves"]`, `library["chains"]`, `library["move_descriptions"]`, and `library["chain_descriptions"]`.
- **System Prompt Rules (`/backend/prompts.py`)**:
  - Update `_MOTOR_RULES` and `practice_system()` to document `forget NAME` syntax for removing saved moves/chains.

### 3. Chest Rotation & Arena Locomotion Guidance (`/backend/prompts.py`)
- Clarify in `_WORLD_RULES` and `_MOTOR_RULES` how arm pushes against the ground produce reaction torques that rotate the central chest ball and propel the fighter across the arena.

---

## Verification Plan
1. Validate Python modules using `py_compile`.
2. Test move parser with `forget` command syntax.
3. Run `compile_applet` to confirm overall applet build state.

## Progress Tracking & Status Reporting
For all completed changes, we will explicitly detail:
1. What was done and working 100%.
2. What was done and might not work 100%.
3. What was not done.

# Chest Ball Rotation & Floating Neck Decoupling Plan

Fix the chest ball center rotation behavior so that rotating the chest ball rotates only the chest ball itself around its center, while keeping the neck, head, shoulder joints, and arm linkages fixed in floating space relative to the chest center (unaffected by the rotational spin of the chest ball).

## User Review & Critical Decisions

> [!IMPORTANT]
> Confirmed user selections from Phase 1 clarification:
> 1. **Chest Ball & Joint Interaction**: Rotate chest ball around its center without rotating neck and shoulder positions.
> 2. **Arm Motor Reference Frame**: Keep arm motor reference frames (`torso_frame`) anchored to floating neck and shoulder position vectors, completely unaffected by chest ball rotation.
> 3. **Link Physics Constraints**: Decouple chest rotation from link physics constraint forces so zero rotational torque is transmitted from chest ball rotation to the neck and shoulder links.

---

## 1. Overview & Core Concept

Currently, the fighter body hierarchy couples chest orientation/rotation to the neck link and shoulder joints. When the chest center rotates or receives rotational motor torque, the attached neck, head, and shoulder joints spin along with it.

This plan isolates the chest ball's rotational degree of freedom:
- **Chest Center Translation**: The chest ball center remains the structural anchor point. Translating the chest center moves the neck, head, and arms in space.
- **Chest Ball Rotation Decoupling**: Rotating the chest ball around its center rotates the chest ball's visual/internal orientation, but leaves the neck and shoulder joint positional offsets in "floating space" (anchored to the chest center position, not its orientation angle).
- **Arm Reference Frame Independence**: The `torso_frame` used to target shoulder/elbow motor angles continues to evaluate position vectors (`head - chest` and `shR - shL`), maintaining stable target coordinates regardless of chest ball rotation.

---

## 2. User Experience & Visual Design

- **Visual Wireframe & Sketch Rendering**: In the 3D replay viewer (`ThreeSketchViewer`), the chest ball displays its orientation rotation, while the neck capsule and shoulder-to-elbow links maintain their relative position vectors above and beside the chest center.
- **Physics Fidelity**: In the simulation engine, motor forces acting on arms compute their local torque relative to the position-derived torso frame, ensuring strikes and blocks perform predictably without rotational drift caused by chest spinning.

---

## 3. Key Product Decisions & Trade-Offs

- **Decision 1: Floating Neck & Shoulder Position Anchoring**
  - *Chosen Approach*: Anchor neck and shoulder initial relative offsets to the chest center point in translation only.
  - *Why*: Direct compliance with user requirement where the neck behaves as if "floating in its own space following the ball center movement, not following ball rotation".
  - *Alternatives Considered*: Rotating neck and shoulders rigidly with chest orientation (rejected as it causes joint twisting and unintended limb spinning).

- **Decision 2: Torso Frame Computation (`torso_frame`)**
  - *Chosen Approach*: Compute `torso_frame` (right, up, front) using position differences between head, chest, and shoulder points (`p_head - p_chest` and `p_shR - p_shL`).
  - *Why*: Ensures arm joint motors target exact world-relative and body-relative angles without being distorted when the chest ball spins.

---

## 4. Technical Architecture & Data Strategy

```
┌───────────────────────────────────────────────────────────┐
│                      Physical World                       │
│                                                           │
│                  ┌──────────────────┐                     │
│                  │  Head Ball (p1)  │                     │
│                  └────────┬─────────┘                     │
│                           │ (Floating Neck Link)          │
│                           ▼                               │
│  ┌───────────┐   ┌──────────────────┐   ┌───────────┐     │
│  │ shL (p5)  │───│ Chest Center(p0) │───│ shR (p2)  │     │
│  └───────────┘   └──────────────────┘   └───────────┘     │
│                   ▲ Rotates around                        │
│                   │ its own center                        │
│                   │ (No torque to                         │
│                   │  neck/shoulders)                      │
└───────────────────────────────────────────────────────────┘
```

### Affected System Components

1. **`backend/geometry.py` (`torso_frame`)**:
   - Verify and guarantee `torso_frame` relies strictly on positional deltas (`p_head - p_chest` and `p_shR - p_shL`) so chest ball rotation does not rotate arm motor targets.

2. **`backend/muscles.py` (`drive`)**:
   - Ensure motor forces applied to arm joints treat the chest as a pure point pivot position for shoulder links without transmitting chest angular velocity/rotation to child joints.

3. **`backend/body.py` & `backend/physics.py`**:
   - Isolate chest rotation logic so chest ball center rotation affects chest ball orientation state only.
   - Maintain rigid distance constraints (`cL`) between chest center position and shoulder/neck positions without angular constraint coupling.

4. **Frontend Verification**:
   - Ensure `fighter-frontend/src/viewer/ThreeSketchViewer.tsx` renders chest sphere and link capsules based on point snapshot positions, maintaining independent visual representation.

---

## 5. Verification & Test Strategy

1. **Automated Backend Tests (`backend/test_all.py` / `backend/test_physics.py`)**:
   - Add/run unit test verifying that applying rotational torque/commands to the chest center alters chest ball orientation while keeping head, neck, and shoulder joint coordinates unchanged.
   - Run full test suite (`python backend/test_all.py`) to confirm no regressions in 8-ball body physics, 15° motor rules, or 42-word observations.
2. **Frontend Replay Verification**:
   - Verify replay rendering in `ThreeSketchViewer` accurately shows floating neck position following chest center movement while chest ball rotates independently.

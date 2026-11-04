# Implementation Plan - Physics Contact Collision & Friction Audit

## Objective
Audit and verify the physical realism of contact collision responses, restitution (bounce), and friction coefficients in `backend/contacts.py` and `backend/config.py` to ensure bipedal robots interact logically with ground and body-to-body impacts (no unnatural sliding or unphysical bouncing).

## Analysis & Plan
1. **Friction & Restitution Review (`backend/config.py`)**:
   - `MU = (0.5, 0.4)` (Iron, Wood friction)
   - `REST = (0.5, 0.4)` (Iron, Wood restitution/bounce)
   - `GROUND = (0.6, 0.4)` (Ground friction and bounce)
   - These values provide realistic damping (semi-inelastic collisions, preventing excessive or infinite bouncing) and stable traction.

2. **Contact Response Logic (`backend/contacts.py`)**:
   - Normal impulses use coefficient of restitution (`e`) with velocity threshold (`BOUNCE_MIN_SPEED = 0.5`).
   - Tangential friction impulses apply Coulomb friction limiting (`jt <= mu * normal_force`), correctly preventing excessive tangential sliding during impact.
   - Positional correction (`push_out`) cleanly resolves penetration overlaps without adding artificial velocity energy.

3. **Testing & Verification**:
   - Review physics test suite (`backend/test_physics.py`) to confirm collision and constraint tests pass successfully.

"""PRACTICE_EVAL: Defines physical goals, starting poses, and success criteria for mastery.
"""
import numpy as np
from config import ARENA_R

GOALS = {
    "recovery": {
        "name": "Recovery: Chest Grounded to Four-Point Base",
        "description": "Lift chest from the ground and establish a stable base with both fists.",
        "initial_pose": "grounded",
        "min_chest_y": 0.15,  # Radius 0.092, so 0.15 means ~0.06m clearance
        "require_fists": True,
        "max_velocity": 0.2,
    },
    "jab": {
        "name": "Jab: Quick Forward Strike",
        "description": "Extend one arm forward quickly and retract.",
        "initial_pose": "standing",
        "min_fist_z": 0.4,
        "max_fist_y_dev": 0.1,
    }
}

def evaluate_recovery(state, spec, f=0):
    """Evaluates if the fighter is in a stable four-point base."""
    i = f * spec.n
    ix = spec.idx
    
    chest_y = state.p[i + ix["chest"], 1]
    r_chest = spec.r[i + ix["chest"]]
    clearance = chest_y - r_chest
    
    # Check if fists are on ground
    fistR_y = state.p[i + ix["fistR"], 1]
    fistL_y = state.p[i + ix["fistL"], 1]
    r_fistR = spec.r[i + ix["fistR"]]
    r_fistL = spec.r[i + ix["fistL"]]
    
    fistR_ground = (fistR_y - r_fistR) < 0.05
    fistL_ground = (fistL_y - r_fistL) < 0.05
    
    # Head safety
    head_y = state.p[i + ix["head"], 1]
    r_head = spec.r[i + ix["head"]]
    head_clearance = head_y - r_head
    head_safe = head_clearance > 0.1
    
    # Stability (low velocity)
    vel = np.linalg.norm(state.v[i + ix["chest"]])
    stable = vel < 0.2
    
    success = (clearance > 0.05) and fistR_ground and fistL_ground and head_safe and stable
    
    diagnostics = []
    if clearance <= 0.05: diagnostics.append(f"Chest too low ({clearance:.3f}m). Push harder with arms.")
    if not fistR_ground: diagnostics.append("Right fist lost ground contact.")
    if not fistL_ground: diagnostics.append("Left fist lost ground contact.")
    if not head_safe: diagnostics.append("Head is dangerously close to the ground.")
    if not stable: diagnostics.append(f"Fighter is sliding or falling (vel={vel:.2f}m/s).")
    
    return {
        "success": success,
        "metrics": {
            "chest_clearance": float(clearance),
            "fistR_ground": bool(fistR_ground),
            "fistL_ground": bool(fistL_ground),
            "head_safe": bool(head_safe),
            "velocity": float(vel)
        },
        "diagnostics": " ".join(diagnostics) if diagnostics else "Stable four-point base achieved."
    }

def evaluate_goal(goal_id, state, spec, f=0):
    if goal_id == "recovery":
        return evaluate_recovery(state, spec, f)
    return {"success": False, "diagnostics": f"Unknown goal: {goal_id}", "metrics": {}}

def get_initial_pose(goal_id, spec):
    """Returns a modified initial state for specific practice goals."""
    import body
    st = body.initial_state(spec)
    if goal_id == "recovery":
        # Force chest to ground
        for f in range(spec.nf):
            i = f * spec.n
            st.p[i + spec.idx["chest"], 1] = spec.r[i + spec.idx["chest"]] + 0.01
            # Lower everything else too
            offset = 0.3
            st.p[i:] -= [0, offset, 0]
            # Ensure no ball is below ground
            for b in range(spec.n):
                idx = i + b
                st.p[idx, 1] = max(st.p[idx, 1], spec.r[idx])
    return st

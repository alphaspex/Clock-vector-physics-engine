"""PRACTICE_EVAL: Generates physical final state reports for AI self-assessment.
"""
import numpy as np

def get_physical_report(goal_id, state, spec, f=0):
    """Generates a detailed natural-language report of the fighter's final state."""
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
    
    # Stability (low velocity)
    vel = np.linalg.norm(state.v[i + ix["chest"]])
    
    lines = [f"FINAL PHYSICAL STATE REPORT (GOAL: {goal_id.upper()}):"]
    lines.append(f"- Chest Ground Clearance: {clearance:.3f} meters")
    lines.append(f"- Right Fist Status: {'TOUCHING GROUND' if fistR_ground else 'OFF GROUND'}")
    lines.append(f"- Left Fist Status: {'TOUCHING GROUND' if fistL_ground else 'OFF GROUND'}")
    lines.append(f"- Head Ground Clearance: {head_clearance:.3f} meters")
    lines.append(f"- Chest Velocity: {vel:.2f} m/s")
    
    if goal_id == "recovery":
        lines.append("\nSUCCESS CRITERIA FOR RECOVERY:")
        lines.append("- Chest must be lifted clear of the ground (>0.05m).")
        lines.append("- Both fists must be grounded for support.")
        lines.append("- Head must be safe and lifted.")
        lines.append("- Body must be stable (low velocity).")
        
    return "\n".join(lines)

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

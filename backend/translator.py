import math
import numpy as np
from observe import H_DIR_WORDS, V_DIR_WORDS, CHEST_BALL_RADIUS
from geometry import unit, rot, torso_frame

# --- VOCABULARY MAPPINGS ---

H_WORD_TO_DEG = {v: k for k, v in H_DIR_WORDS.items()}
V_WORD_TO_DEG = {v: k for k, v in V_DIR_WORDS.items()}

# Distance thresholds from observe.py: 0.10, 0.25, 0.45, 0.70
# We use the midpoint of each band as the numerical representative.
DIST_BANDS = {
    "VERY-CLOSE": (0.0, 0.10, 0.05),
    "CLOSE": (0.10, 0.25, 0.175),
    "MID": (0.25, 0.45, 0.35),
    "FAR": (0.45, 0.70, 0.575),
    "VERY-FAR": (0.70, 1.20, 0.95),
    "GROUND": (0.0, 0.0, 0.0), # Handled separately
}

def parse_position_to_point(words_str, fr, p_chest):
    """
    Translates position words into a local (chest-relative) 3D point.
    Syntax: DISTANCE [HORIZONTAL] VERTICAL
    """
    tok = words_str.upper().split()
    if not tok:
        return None
    
    dist_word = tok[0]
    if dist_word not in DIST_BANDS:
        return None
    
    # Distance r (add chest radius back as coordinate origin is center)
    r_val = DIST_BANDS[dist_word][2] + CHEST_BALL_RADIUS
    
    # Identify Vertical word (usually last)
    # Identify Horizontal word (optional, if vertical is not STRAIGHT UP/DOWN)
    
    v_word = None
    h_word = None
    
    # V_DIR_WORDS includes multi-word entries like "STRAIGHT UP"
    # We check from the end for vertical
    found_v = None
    for i in range(len(tok), 0, -1):
        candidate = " ".join(tok[i-1:])
        if candidate in V_WORD_TO_DEG:
            found_v = candidate
            v_word = candidate
            # horizontal is what remains in the middle
            if i > 1:
                h_candidate = " ".join(tok[1:i-1])
                if h_candidate in H_WORD_TO_DEG:
                    h_word = h_candidate
            break
            
    if v_word is None:
        return None
        
    v_deg = V_WORD_TO_DEG[v_word]
    h_deg = H_WORD_TO_DEG.get(h_word, 0) if h_word else 0
    
    v_rad = math.radians(v_deg)
    h_rad = math.radians(h_deg)
    
    # Spherical to Cartesian (as defined in observe.py and prompt)
    # X = r * cos(V) * sin(H)
    # Y = r * sin(V)
    # Z = r * cos(V) * cos(H)
    
    dx = r_val * math.cos(v_rad) * math.sin(h_rad)
    dy = r_val * math.sin(v_rad)
    dz = r_val * math.cos(v_rad) * math.cos(h_rad)
    
    # Return as local vector (Right, Up, Front)
    return np.array([dx, dy, dz])

def forward_kinematics(shoulder_angles, elbow_angle, shoulder_pivot, fr, spec, arm_side):
    """
    Calculates elbow and fist positions from motor angles.
    shoulder_angles: (pitch_deg, out_deg)
    elbow_angle: (bend_deg,)
    """
    right, up, fwd = fr
    s_sg = 1 if arm_side == "R" else -1
    e_sg = -1 # From body.py
    
    # Motor names to get lengths
    m_sh = f"{arm_side}_shoulder"
    m_el = f"{arm_side}_elbow"
    
    # We need the spec to find motor info (lengths)
    # Actually, we can pre-calculate or pass them.
    # Let's assume we find the motor dicts.
    mo_sh = next(m for m in spec.motors if m["name"] == m_sh)
    mo_el = next(m for m in spec.motors if m["name"] == m_el)
    
    L1 = mo_sh["L"][0] # Upper arm length
    L2 = mo_el["L"][0] # Forearm length
    
    # Shoulder FK (replicates muscles._targets)
    a, b = np.radians(shoulder_angles)
    d1 = s_sg * np.sin(b) * right - np.cos(b) * np.cos(a) * up + np.cos(b) * np.sin(a) * fwd
    elbow_pos = shoulder_pivot + L1 * d1
    
    # Elbow FK (replicates muscles._targets)
    u = unit(elbow_pos - shoulder_pivot)
    # Note: elbow_angle is a single value, but muscles expects cmd[0]
    bend_rad = np.radians(elbow_angle[0])
    d2 = rot(u, right, e_sg * bend_rad)
    fist_pos = elbow_pos + L2 * d2
    
    return elbow_pos, fist_pos

def inverse_kinematics(elbow_target, fist_target, shoulder_pivot, fr, spec, arm_side, initial_angles=None):
    """
    Solves for shoulder and elbow angles using damped least squares.
    elbow_target, fist_target: local vectors relative to chest center.
    """
    # We work in local torso space
    local_right = np.array([1.0, 0.0, 0.0])
    local_up = np.array([0.0, 1.0, 0.0])
    local_fwd = np.array([0.0, 0.0, 1.0])
    
    # Get current motor angles for initial guess if provided
    # initial_angles: (sh_pitch, sh_out, el_bend)
    if initial_angles is None:
        cur_q = np.array([0.0, 0.0, 0.0]) 
    else:
        cur_q = np.array(initial_angles, dtype=float)
    
    # We need lengths
    m_sh = f"{arm_side}_shoulder"
    m_el = f"{arm_side}_elbow"
    mo_sh = next(m for m in spec.motors if m["name"] == m_sh)
    mo_el = next(m for m in spec.motors if m["name"] == m_el)
    L1 = mo_sh["L"][0]
    L2 = mo_el["L"][0]
    
    s_sg = 1 if arm_side == "R" else -1
    e_sg = -1
    
    # Limits
    sh_lim = mo_sh["lim"] # ((-180, 180), (0, 180))
    el_lim = mo_el["lim"] # ((0, 150),)
    
    def fk(q):
        # q = [pitch, out, bend]
        a, b, c = np.radians(q)
        # Shoulder
        d1 = s_sg * np.sin(b) * local_right - np.cos(b) * np.cos(a) * local_up + np.cos(b) * np.sin(a) * local_fwd
        el_pos = shoulder_pivot + L1 * d1
        # Elbow
        u = unit(el_pos - shoulder_pivot)
        d2 = rot(u, local_right, e_sg * c)
        fi_pos = el_pos + L2 * d2
        return el_pos, fi_pos

    # Solver parameters
    max_iters = 20
    damp = 0.01
    step_size = 0.5
    
    for _ in range(max_iters):
        el_curr, fi_curr = fk(cur_q)
        
        # Error vector (6 components: 3 for elbow, 3 for fist)
        err_el = elbow_target - el_curr
        err_fi = fist_target - fi_curr
        
        # Prioritize elbow: weigh it more? Or just solve.
        # User: "Prioritize satisfying the elbow target while also minimizing fist-target error."
        # We can weigh the elbow error higher.
        weight_el = 2.0
        weight_fi = 1.0
        
        full_err = np.concatenate([err_el * weight_el, err_fi * weight_fi])
        
        if np.linalg.norm(full_err) < 1e-4:
            break
            
        # Numerical Jacobian (3x6)
        J = np.zeros((6, 3))
        eps = 1e-3
        for i in range(3):
            q_plus = cur_q.copy()
            q_plus[i] += eps
            el_p, fi_p = fk(q_plus)
            
            J[0:3, i] = (el_p - el_curr) * weight_el / eps
            J[3:6, i] = (fi_p - fi_curr) * weight_fi / eps
            
        # Damped Least Squares
        # delta_q = (J^T J + lambda^2 I)^-1 J^T err
        JTJ = J.T @ J
        delta_q = np.linalg.inv(JTJ + (damp**2) * np.eye(3)) @ J.T @ full_err
        
        cur_q += delta_q * step_size
        
        # Clamp to limits
        cur_q[0] = np.clip(cur_q[0], sh_lim[0][0], sh_lim[0][1])
        cur_q[1] = np.clip(cur_q[1], sh_lim[1][0], sh_lim[1][1])
        cur_q[2] = np.clip(cur_q[2], el_lim[0][0], el_lim[0][1])

    # Round to nearest 15 degrees as per rules
    def round15(x):
        return round(x / 15.0) * 15.0
        
    final_q = [round15(cur_q[0]), round15(cur_q[1]), round15(cur_q[2])]
    
    # Re-verify final pose
    final_el, final_fi = fk(final_q)
    err_dist = np.linalg.norm(elbow_target - final_el) + np.linalg.norm(fist_target - final_fi)
    
    return (final_q[0], final_q[1]), (final_q[2],), err_dist

def translate_step(step_dict, p, spec, f, fr):
    """
    Translates a step dictionary containing position words into motor angles.
    step_dict: { 'RIGHT_FIST': 'CLOSE FRONT LEVEL', 'R_shoulder': '60,0 1.0' }
    Returns: new step_dict with only motor names.
    """
    new_step = {}
    
    # Identify body parts requested
    parts = ["RIGHT_ELBOW", "RIGHT_FIST", "LEFT_ELBOW", "LEFT_FIST"]
    requested = {p: step_dict[p] for p in parts if p in step_dict}
    
    # Get torso frame info
    right, up, fwd = fr
    p_chest = p[f * spec.n + spec.idx["chest"]]
    
    # Process arms independently
    for side in ("R", "L"):
        side_name = "RIGHT" if side == "R" else "LEFT"
        el_key = f"{side_name}_ELBOW"
        fi_key = f"{side_name}_FIST"
        
        if el_key in requested or fi_key in requested:
            # We need targets
            # If one is missing, use current position as target
            # Get current local shoulder pivot
            sh_idx = spec.idx["sh" + side]
            p_sh = p[f * spec.n + sh_idx]
            
            # Localize shoulder pivot
            d_sh = p_sh - p_chest
            local_sh_pivot = np.array([
                np.dot(d_sh, right),
                np.dot(d_sh, up),
                np.dot(d_sh, fwd)
            ])
            
            # Get current targets
            if el_key in requested:
                el_target = parse_position_to_point(requested[el_key], fr, p_chest)
            else:
                # Use current elbow pos as target
                el_idx = spec.idx["el" + side]
                d_el = p[f * spec.n + el_idx] - p_chest
                el_target = np.array([np.dot(d_el, right), np.dot(d_el, up), np.dot(d_el, fwd)])
                
            if fi_key in requested:
                fi_target = parse_position_to_point(requested[fi_key], fr, p_chest)
            else:
                # Use current fist pos as target
                fi_idx = spec.idx["fist" + side]
                d_fi = p[f * spec.n + fi_idx] - p_chest
                fi_target = np.array([np.dot(d_fi, right), np.dot(d_fi, up), np.dot(d_fi, fwd)])
            
            if el_target is None or fi_target is None:
                continue
                
            # Get current motor angles for initial guess
            # Find motor indices
            m_sh_idx = spec.mix[(f, f"{side}_shoulder")]
            m_el_idx = spec.mix[(f, f"{side}_elbow")]
            
            # Wait, current state cmd might not be angles?
            # Actually, State.cmd stores the targets.
            # We need to know what the motors are currently DOING.
            # But the prompt says "Read the measured current body pose and current motor angles."
            # Since we are in the translation step, let's assume we use the last cmd as guess.
            # But we don't have the State object here, just 'p'.
            # Let's use [0,0,0] as default guess.
            
            sh_angles, el_angles, err = inverse_kinematics(
                el_target, fi_target, local_sh_pivot, fr, spec, side
            )
            
            # Add to new step
            # Determine power: if specified in original tokens?
            # The AI might say: "RIGHT_FIST CLOSE FRONT LEVEL 0.9"
            # Let's extract power if possible.
            
            def get_power(val_str):
                tok = val_str.split()
                try:
                    # If there's a 4th or 5th word that's a float, it's power
                    # But DISTANCE HORIZ VERT is 2 or 3 words.
                    # Let's check tok[-1]
                    if len(tok) > 1:
                        p_candidate = float(tok[-1])
                        if 0.0 <= p_candidate <= 1.0:
                            return p_candidate
                except:
                    pass
                return 1.0
                
            pw_sh = get_power(requested.get(el_key, requested.get(fi_key, "")))
            pw_el = get_power(requested.get(fi_key, requested.get(el_key, "")))
            
            new_step[f"{side}_shoulder"] = (sh_angles, pw_sh)
            new_step[f"{side}_elbow"] = (el_angles, pw_el)
            
    # Copy other motor commands as-is
    for k, v in step_dict.items():
        if k not in parts and k not in new_step:
            new_step[k] = v
            
    return new_step

import math
import numpy as np
import re
from config import H_DIR_WORDS, V_DIR_WORDS, DIST_THRESHOLDS, DIST_WORDS, DIST_REPRESENTATIVE, CHEST_BALL_RADIUS
from geometry import unit, rot, torso_frame

# Reverse mappings for decoding
H_WORD_TO_DEG = {v: k for k, v in H_DIR_WORDS.items()}
V_WORD_TO_DEG = {v: k for k, v in V_DIR_WORDS.items()}

def parse_tree(text):
    """Parses the AI returned tree into a dictionary of positions."""
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    if not lines:
        return None

    tree = {}
    current_part = None
    
    # Simple hierarchy parsing
    for line in lines:
        if line.upper() == "MY FIGHTER":
            continue
        
        # Check if it's a body part name (uppercase, no "POSITION:")
        if "POSITION:" not in line.upper():
            current_part = line.strip().upper()
            continue
        
        if current_part and "POSITION:" in line.upper():
            pos_val = line.split("POSITION:", 1)[1].strip().upper()
            tree[current_part] = pos_val

    return tree

def validate_tree(tree):
    """Strictly validates the returned tree structure and vocabulary."""
    required_balls = ["CHEST", "HEAD", "RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_FIST", "LEFT_SHOULDER", "LEFT_ELBOW", "LEFT_FIST"]
    
    if not tree:
        return False, "Empty tree"

    # 1. Correct tree root and official hierarchy check (implicit in parse_tree)
    # 2. All required ball names appear exactly once
    for ball in required_balls:
        if ball not in tree:
            return False, f"Missing required ball: {ball}"
    
    # 3. CHEST position is exactly ORIGIN
    if tree.get("CHEST") != "ORIGIN":
        return False, "CHEST position must be ORIGIN"

    # 4. Every position uses the exact official vocabulary
    for ball, pos in tree.items():
        if ball == "CHEST":
            continue
            
        if pos == "ORIGIN":
            return False, f"Only CHEST can be ORIGIN, found in {ball}"

        # GROUND check
        if pos.startswith("GROUND "):
            tokens = pos.split()
            if len(tokens) < 2:
                 return False, f"Invalid GROUND position: {pos}"
            # Check remaining vocabulary
            remaining = " ".join(tokens[1:])
        else:
            tokens = pos.split()
            if not tokens:
                return False, f"Empty position for {ball}"
            dist_word = tokens[0]
            if dist_word not in DIST_WORDS:
                return False, f"Invalid distance word '{dist_word}' in {ball}"
            remaining = " ".join(tokens[1:])

        # Vertical check (from the end)
        v_word = None
        for v_val in V_WORD_TO_DEG.keys():
            if remaining.endswith(v_val):
                v_word = v_val
                break
        
        if v_word is None:
            return False, f"Invalid vertical direction in {pos} for {ball}"
        
        # Horizontal check (if not straight up/down)
        if v_word not in ("STRAIGHT UP", "STRAIGHT DOWN"):
            h_candidate = remaining[:len(remaining)-len(v_word)].strip()
            if h_candidate not in H_WORD_TO_DEG:
                return False, f"Invalid horizontal direction '{h_candidate}' in {pos} for {ball}"
        else:
            # STRAIGHT UP/DOWN must NOT have horizontal direction
            h_candidate = remaining[:len(remaining)-len(v_word)].strip()
            if h_candidate:
                return False, f"Horizontal direction must be omitted for {v_word} in {pos} for {ball}"

    return True, "Valid"

def decode_position(pos_str, right, up, fwd, chest_pos):
    """Decodes a position word into a 3D coordinate relative to chest center."""
    if pos_str == "ORIGIN":
        return np.array([0.0, 0.0, 0.0])

    tokens = pos_str.split()
    dist_word = tokens[0]
    remaining = " ".join(tokens[1:])

    # Vertical
    v_word = None
    for v_val in V_WORD_TO_DEG.keys():
        if remaining.endswith(v_val):
            v_word = v_val
            break
    
    v_deg = V_WORD_TO_DEG[v_word]
    v_rad = math.radians(v_deg)

    # Horizontal
    h_deg = 0
    if v_word not in ("STRAIGHT UP", "STRAIGHT DOWN"):
        h_word = remaining[:len(remaining)-len(v_word)].strip()
        h_deg = H_WORD_TO_DEG.get(h_word, 0)
    
    h_rad = math.radians(h_deg)

    # Distance
    if dist_word == "GROUND":
        # Calculate ground intersection
        # Chest pos is in world space.
        # Direction in local frame:
        dx_dir = math.cos(v_rad) * math.sin(h_rad)
        dy_dir = math.sin(v_rad)
        dz_dir = math.cos(v_rad) * math.cos(h_rad)
        
        dir_world = dx_dir * right + dy_dir * up + dz_dir * fwd
        
        if dir_world[1] >= -1e-5: # Pointing up or level (very slightly down might be ok)
            return None # Infeasible
        
        # Ground is at Y=0. Chest is at chest_pos[1].
        # Distance to ground along dir_world: chest_pos[1] + r*dir_world[1] = 0 (roughly)
        # We want the ball surface to touch the ground.
        # So center_y = radius.
        # chest_pos[1] + dist * dir_world[1] = radius
        # dist = (radius - chest_pos[1]) / dir_world[1]
        
        # We need the ball radius. Let's pass it or assume standard arm radius.
        # For now, let's just use 0.024 (elbow/fist average roughly)
        r_ball = 0.024 
        dist = (r_ball - chest_pos[1]) / dir_world[1]
        
        if dist < 0:
            return None
            
        return dist * np.array([dx_dir, dy_dir, dz_dir])
    else:
        r = DIST_REPRESENTATIVE.get(dist_word, 0.35)
        # Position formulas matching observe.py and prompt
        dx = r * math.cos(v_rad) * math.sin(h_rad)
        dy = r * math.sin(v_rad)
        dz = r * math.cos(v_rad) * math.cos(h_rad)
        return np.array([dx, dy, dz])

def solve_arm_ik(shoulder_pivot_local, desired_elbow_local, desired_fist_local, spec, arm_side):
    """
    Solves for shoulder and elbow angles to reach desired local positions.
    Uses actual physics forward-kinematics equations.
    """
    m_sh_idx = -1
    m_el_idx = -1
    for i, mo in enumerate(spec.motors):
        if mo["name"] == f"{arm_side}_shoulder": m_sh_idx = i
        if mo["name"] == f"{arm_side}_elbow": m_el_idx = i
        
    mo_sh = spec.motors[m_sh_idx]
    mo_el = spec.motors[m_el_idx]
    
    L1 = mo_sh["L"][0] # Upper arm length
    L2 = mo_el["L"][0] # Forearm length
    s_sg = mo_sh["s"]
    e_sg = mo_el["s"]
    
    # Local axes
    right = np.array([1.0, 0.0, 0.0])
    up = np.array([0.0, 1.0, 0.0])
    fwd = np.array([0.0, 0.0, 1.0])

    def fk(q):
        # q = [pitch, out, bend]
        a, b, c = np.radians(q)
        # Shoulder
        d1 = s_sg * np.sin(b) * right - np.cos(b) * np.cos(a) * up + np.cos(b) * np.sin(a) * fwd
        el_pos = shoulder_pivot_local + L1 * d1
        # Elbow
        u = unit(el_pos - shoulder_pivot_local)
        d2 = rot(u, right, e_sg * c)
        fi_pos = el_pos + L2 * d2
        return el_pos, fi_pos

    # Target points relative to shoulder pivot
    # But desired_elbow_local is relative to chest center.
    
    # Solver (Damped Least Squares)
    cur_q = np.array([0.0, 45.0, 30.0]) # reasonable guess
    max_iters = 30
    damp = 0.01
    step_size = 0.3
    
    for _ in range(max_iters):
        el_curr, fi_curr = fk(cur_q)
        err_el = desired_elbow_local - el_curr
        err_fi = desired_fist_local - fi_curr
        
        full_err = np.concatenate([err_el * 2.0, err_fi * 1.0])
        if np.linalg.norm(full_err) < 1e-4:
            break
            
        J = np.zeros((6, 3))
        eps = 1e-3
        for i in range(3):
            q_plus = cur_q.copy()
            q_plus[i] += eps
            el_p, fi_p = fk(q_plus)
            J[0:3, i] = (el_p - el_curr) * 2.0 / eps
            J[3:6, i] = (fi_p - fi_curr) * 1.0 / eps
            
        JTJ = J.T @ J
        try:
            delta_q = np.linalg.inv(JTJ + (damp**2) * np.eye(3)) @ J.T @ full_err
            cur_q += delta_q * step_size
        except:
            break
            
        # Limits
        cur_q[0] = np.clip(cur_q[0], mo_sh["lim"][0][0], mo_sh["lim"][0][1])
        cur_q[1] = np.clip(cur_q[1], mo_sh["lim"][1][0], mo_sh["lim"][1][1])
        cur_q[2] = np.clip(cur_q[2], mo_el["lim"][0][0], mo_el["lim"][0][1])

    # Round to 15 degrees
    def round15(x):
        return round(x / 15.0) * 15.0
        
    final_q = [round15(cur_q[0]), round15(cur_q[1]), round15(cur_q[2])]
    return (final_q[0], final_q[1]), (final_q[2],)

def translate_trees(pose1_tree, pose2_tree, spec, f, p_state):
    """
    Translates Pose 1 and Pose 2 into absolute motor targets.
    Returns: {motor_name: (vals, power)}
    """
    fr = torso_frame(p_state, spec, f)
    right, up, fwd = fr
    p_chest = p_state[f * spec.n + spec.idx["chest"]]
    
    # We need to solve for both arms
    orders = {}
    
    for side in ("R", "L"):
        arm_side = "RIGHT" if side == "R" else "LEFT"
        
        # Current shoulder pivot (from Pose 1/Physical state)
        sh_idx = f * spec.n + spec.idx["sh" + side]
        sh_pos_world = p_state[sh_idx]
        d_sh = sh_pos_world - p_chest
        sh_pivot_local = np.array([np.dot(d_sh, right), np.dot(d_sh, up), np.dot(d_sh, fwd)])
        
        # Desired elbow and fist from Pose 2
        el_pos_word = pose2_tree.get(f"{arm_side}_ELBOW")
        fi_pos_word = pose2_tree.get(f"{arm_side}_FIST")
        
        if not el_pos_word or not fi_pos_word:
            continue
            
        el_target_local = decode_position(el_pos_word, right, up, fwd, p_chest)
        fi_target_local = decode_position(fi_pos_word, right, up, fwd, p_chest)
        
        if el_target_local is None or fi_target_local is None:
            # Infeasible (e.g. GROUND pointing up) - keep current targets or find best reachable
            # For now, let's just skip if strictly infeasible ground.
            continue
            
        sh_angles, el_angles = solve_arm_ik(sh_pivot_local, el_target_local, fi_target_local, spec, side)
        
        orders[f"{side}_shoulder"] = (sh_angles, 1.0)
        orders[f"{side}_elbow"] = (el_angles, 1.0)
        
    return orders

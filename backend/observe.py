"""OBSERVE: translates physical simulation state into natural-language 3D body trees and observations.
Never shows health numbers.
"""
import math
import numpy as np
from config import ARENA_R
from geometry import torso_frame

# ---- OFFICIAL 42 POSITION VOCABULARY VALUES ----

# 24 Horizontal direction values (360° circle: 0°=FRONT, 90°=RIGHT, 180°=BACK, 270°=LEFT)
H_DIR_WORDS = {
    0: "FRONT",
    15: "FRONT SLIGHT RIGHT",
    30: "FRONT RIGHT",
    45: "FRONT DIAGONAL RIGHT",
    60: "RIGHT DIAGONAL FRONT",
    75: "RIGHT SLIGHT FRONT",
    90: "RIGHT",
    105: "RIGHT SLIGHT BACK",
    120: "RIGHT DIAGONAL BACK",
    135: "RIGHT BACK",
    150: "BACK DIAGONAL RIGHT",
    165: "BACK SLIGHT RIGHT",
    180: "BACK",
    195: "BACK SLIGHT LEFT",
    210: "BACK DIAGONAL LEFT",
    225: "BACK LEFT",
    240: "LEFT DIAGONAL BACK",
    255: "LEFT SLIGHT BACK",
    270: "LEFT",
    285: "LEFT SLIGHT FRONT",
    300: "LEFT DIAGONAL FRONT",
    315: "LEFT FRONT",
    330: "FRONT DIAGONAL LEFT",
    345: "FRONT SLIGHT LEFT",
}

# 13 Vertical direction values (-90° to +90°)
V_DIR_WORDS = {
    90: "STRAIGHT UP",
    75: "NEAR UP",
    60: "HIGH UP",
    45: "DIAGONAL UP",
    30: "UPPER",
    15: "SLIGHT UPPER",
    0: "LEVEL",
    -15: "SLIGHT LOWER",
    -30: "LOWER",
    -45: "DIAGONAL DOWN",
    -60: "LOW DOWN",
    -75: "NEAR DOWN",
    -90: "STRAIGHT DOWN",
}

# 5 Distance values (measured after subtracting chest ball radius 0.092m)
def get_distance_band(pos_dist):
    if pos_dist <= 0.10:
        return "VERY-CLOSE"
    elif pos_dist <= 0.25:
        return "CLOSE"
    elif pos_dist <= 0.45:
        return "MID"
    elif pos_dist <= 0.70:
        return "FAR"
    else:
        return "VERY-FAR"


CHEST_BALL_RADIUS = 0.092


def round_angle_15(angle):
    """
    Rounds angle to nearest 15° using a consistent deterministic halfway rule:
    7° -> 0°, 8° -> 15°, 22° -> 15°, 23° -> 30°, -7° -> 0°, -8° -> -15°.
    """
    return int(math.floor(angle / 15.0 + 0.5)) * 15


def translate_direction_words(dx, dy, dz):
    """Calculates horizontal and vertical direction words from local DX, DY, DZ."""
    hypot_xz = math.sqrt(dx * dx + dz * dz)
    v_deg = math.degrees(math.atan2(dy, hypot_xz))
    v_rounded = max(-90, min(90, round_angle_15(v_deg)))
    v_word = V_DIR_WORDS[v_rounded]

    if v_rounded in (90, -90):
        # At straight up/down horizontal direction is undefined and omitted
        return None, v_word, v_rounded

    h_deg = math.degrees(math.atan2(dx, dz)) % 360.0
    h_rounded = round_angle_15(h_deg) % 360
    h_word = H_DIR_WORDS[h_rounded]

    return h_word, v_word, v_rounded


def translate_3d_position(dx, dy, dz, is_grounded=False):
    """
    Translates physical positions relative to chest center into natural words.
    The AI receives the translated words, NOT raw coordinates or numerical angles.
    Combined position syntax: DISTANCE + HORIZONTAL_DIRECTION + VERTICAL_DIRECTION
    (or GROUND + HORIZONTAL_DIRECTION + VERTICAL_DIRECTION)
    """
    center_dist = math.sqrt(dx * dx + dy * dy + dz * dz)
    pos_dist = max(0.0, center_dist - CHEST_BALL_RADIUS)

    if is_grounded:
        dist_word = "GROUND"
    else:
        dist_word = get_distance_band(pos_dist)

    h_word, v_word, v_rounded = translate_direction_words(dx, dy, dz)
    if v_rounded in (90, -90):
        return f"{dist_word} {v_word}"
    return f"{dist_word} {h_word} {v_word}"


def format_saved_library(library):
    """Formats full definitions and descriptions of saved moves and chains for the AI."""
    lines = []
    
    # Show active goal in practice
    active_goal = library.get("active_goal")
    if active_goal:
        lines.append(f"ACTIVE PRACTICE GOAL: {active_goal.upper()}")
        lines.append("")

    moves = library.get("moves", {})
    move_desc = library.get("move_descriptions", {})
    mastered = library.get("mastered_moves", {})
    
    if moves:
        lines.append("SAVED MOVES:")
        for name in sorted(moves.keys()):
            steps = moves[name]
            st_strs = []
            for st in steps:
                mc_strs = []
                for mname, (vals, pw) in st.items():
                    v_str = ",".join(str(int(x) if isinstance(x, (int, float)) and float(x).is_integer() else x) for x in vals)
                    mc_strs.append(f"{mname} {v_str} {pw:.1f}")
                st_strs.append(" ; ".join(mc_strs))
            code = " | ".join(st_strs)
            desc = move_desc.get(name, "A learned combat move.")
            
            # Add Mastery tag
            m_info = mastered.get(name, {})
            m_tag = f" [MASTERED {m_info.get('streak', 0)}/1]" if m_info.get('mastered') else f" [TRAINING {m_info.get('streak', 0)}/1]"
            
            lines.append(f"  MOVE: {name} = {code}{m_tag}")
            lines.append(f"  DESCRIPTION: {desc}")
    else:
        lines.append("SAVED MOVES: None")

    chains = library.get("chains", {})
    chain_desc = library.get("chain_descriptions", {})
    if chains:
        lines.append("\nSAVED CHAINS:")
        for name in sorted(chains.keys()):
            c_items = ", ".join(chains[name])
            desc = chain_desc.get(name, "A combination chain of multiple moves.")
            lines.append(f"  CHAIN: {name} = {c_items}")
            lines.append(f"  DESCRIPTION: {desc}")
    else:
        lines.append("\nSAVED CHAINS: None")

    return "\n".join(lines)


def _get_current_contacts(obj_name, p, spec, palive, lalive, f, is_link=False, lid=-1):
    """Determines what is touching this ball or joint in the current simulation frame."""
    contacts = []
    # Ground clearance check
    if not is_link:
        ix = spec.idx.get(obj_name, -1)
        if ix >= 0:
            ball_idx = f * spec.n + ix
            r = spec.r[ball_idx]
            y = p[ball_idx, 1]
            ground_clearance = y - r
            if ground_clearance <= 0.05:
                contacts.append("GROUND")

            # Check arena wall contact
            rho = np.hypot(p[ball_idx, 0], p[ball_idx, 2])
            if rho + r >= ARENA_R - 0.05 and y - r < 0.5:
                contacts.append("ARENA_WALL")

            # Check overlap with opponent balls
            if spec.nf == 2:
                opp_f = 1 - f
                for opp_name in ["chest", "head", "shR", "elR", "fistR", "shL", "elL", "fistL"]:
                    opp_ix = spec.idx.get(opp_name, -1)
                    if opp_ix >= 0:
                        opp_ball = opp_f * spec.n + opp_ix
                        dist = np.linalg.norm(p[ball_idx] - p[opp_ball])
                        if dist < (r + spec.r[opp_ball] + 0.03):
                            side_tag = "ENEMY_" + opp_name.upper()
                            contacts.append(side_tag)
    else:
        # For joint links, check ground
        if lid >= 0:
            la_p, lb_p = p[spec.la[lid]], p[spec.lb[lid]]
            lr = spec.lr[lid]
            min_y = min(la_p[1], lb_p[1]) - lr
            if min_y <= 0.05:
                contacts.append("GROUND")

    return ", ".join(contacts) if contacts else "NONE"


def _format_touch_events(events, since, f_char, part_name):
    """Collects touch events since previous AI decision involving this ball or joint."""
    evs = []
    prefix = f"{f_char}."
    for ev in events:
        if ev.get("event") != "touch":
            continue
        if ev.get("t", 0.0) <= since:
            continue
        a = ev.get("a", "")
        b = ev.get("b", "")

        match_a = a.startswith(prefix) and (part_name in a or part_name.lower() in a.lower())
        match_b = b.startswith(prefix) and (part_name in b or part_name.lower() in b.lower())

        if match_a or match_b:
            other = b if match_a else a
            e_joules = ev.get("energy_J", 0.0)
            t_sec = ev.get("t", 0.0)
            frame_approx = int(round(t_sec * 30))
            evs.append(f"FRAME: {frame_approx} | TIME: {t_sec:.2f}s | WITH: {other} | ENERGY: {e_joules:.2f}J")

    return "; ".join(evs) if evs else "NONE"


def build_fighter_tree(p, spec, palive, lalive, f, fr, events, since, frame, sim_time):
    """
    Builds the official fighter body tree (Section 6).
    All positions are measured relative to CHEST CENTER as origin in local (RIGHT, UP, FRONT) frame.
    """
    i = f * spec.n
    ix = spec.idx
    nl = spec.nl
    lidx = spec.lidx
    f_char = "AB"[f]
    right, up, fwd = fr

    p_chest = p[i + ix["chest"]]

    def rel_pos(ball_name):
        b_idx = i + ix[ball_name]
        d = p[b_idx] - p_chest
        dx = float(np.dot(d, right))
        dy = float(np.dot(d, up))
        dz = float(np.dot(d, fwd))
        is_ground = (p[b_idx, 1] - spec.r[b_idx]) <= 0.05
        return translate_3d_position(dx, dy, dz, is_grounded=is_ground)

    def ball_status(ball_name):
        b_idx = i + ix[ball_name]
        return "INTACT" if palive[b_idx] else "DESTROYED"

    def joint_status(j_name):
        lid = f * nl + lidx[j_name]
        return "INTACT" if lalive[lid] else "DESTROYED"

    tree = [
        "MY FIGHTER",
        f"FRAME: {frame}",
        f"SIMULATION TIME: {sim_time:.1f}s",
        "",
        "CHEST",
        f"  STATUS: {ball_status('chest')}",
        "  POSITION: ORIGIN",
        f"  CURRENT CONTACTS: {_get_current_contacts('chest', p, spec, palive, lalive, f)}",
        f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'chest')}",
        "",
        "NECK",
        "",
        "HEAD",
        f"  STATUS: {ball_status('head')}",
        f"  POSITION: {rel_pos('head')}",
        f"  CURRENT CONTACTS: {_get_current_contacts('head', p, spec, palive, lalive, f)}",
        f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'head')}",
        "",
        "RIGHT_ARM",
        "",
        "NECK_RIGHT_JOINT",
        f"  STATUS: {joint_status('NECK_RIGHT_JOINT')}",
        f"  CURRENT CONTACTS: {_get_current_contacts('NECK_RIGHT_JOINT', p, spec, palive, lalive, f, is_link=True, lid=f*nl+lidx['NECK_RIGHT_JOINT'])}",
        f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'NECK_RIGHT_JOINT')}",
        "",
        "RIGHT_SHOULDER",
        f"  STATUS: {ball_status('shR')}",
        f"  POSITION: {rel_pos('shR')}",
        f"  CURRENT CONTACTS: {_get_current_contacts('shR', p, spec, palive, lalive, f)}",
        f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'shR')}",
        "",
        "SHOULDER_RIGHT_JOINT",
        f"  STATUS: {joint_status('SHOULDER_RIGHT_JOINT')}",
        f"  CURRENT CONTACTS: {_get_current_contacts('SHOULDER_RIGHT_JOINT', p, spec, palive, lalive, f, is_link=True, lid=f*nl+lidx['SHOULDER_RIGHT_JOINT'])}",
        f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'SHOULDER_RIGHT_JOINT')}",
        "",
        "RIGHT_ELBOW",
        f"  STATUS: {ball_status('elR')}",
        f"  POSITION: {rel_pos('elR')}",
        f"  CURRENT CONTACTS: {_get_current_contacts('elR', p, spec, palive, lalive, f)}",
        f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'elR')}",
        "",
        "ELBOW_RIGHT_JOINT",
        f"  STATUS: {joint_status('ELBOW_RIGHT_JOINT')}",
        f"  CURRENT CONTACTS: {_get_current_contacts('ELBOW_RIGHT_JOINT', p, spec, palive, lalive, f, is_link=True, lid=f*nl+lidx['ELBOW_RIGHT_JOINT'])}",
        f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'ELBOW_RIGHT_JOINT')}",
        "",
        "RIGHT_FIST",
        f"  STATUS: {ball_status('fistR')}",
        f"  POSITION: {rel_pos('fistR')}",
        f"  CURRENT CONTACTS: {_get_current_contacts('fistR', p, spec, palive, lalive, f)}",
        f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'fistR')}",
        "",
        "LEFT_ARM",
        "",
        "NECK_LEFT_JOINT",
        f"  STATUS: {joint_status('NECK_LEFT_JOINT')}",
        f"  CURRENT CONTACTS: {_get_current_contacts('NECK_LEFT_JOINT', p, spec, palive, lalive, f, is_link=True, lid=f*nl+lidx['NECK_LEFT_JOINT'])}",
        f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'NECK_LEFT_JOINT')}",
        "",
        "LEFT_SHOULDER",
        f"  STATUS: {ball_status('shL')}",
        f"  POSITION: {rel_pos('shL')}",
        f"  CURRENT CONTACTS: {_get_current_contacts('shL', p, spec, palive, lalive, f)}",
        f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'shL')}",
        "",
        "SHOULDER_LEFT_JOINT",
        f"  STATUS: {joint_status('SHOULDER_LEFT_JOINT')}",
        f"  CURRENT CONTACTS: {_get_current_contacts('SHOULDER_LEFT_JOINT', p, spec, palive, lalive, f, is_link=True, lid=f*nl+lidx['SHOULDER_LEFT_JOINT'])}",
        f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'SHOULDER_LEFT_JOINT')}",
        "",
        "LEFT_ELBOW",
        f"  STATUS: {ball_status('elL')}",
        f"  POSITION: {rel_pos('elL')}",
        f"  CURRENT CONTACTS: {_get_current_contacts('elL', p, spec, palive, lalive, f)}",
        f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'elL')}",
        "",
        "ELBOW_LEFT_JOINT",
        f"  STATUS: {joint_status('ELBOW_LEFT_JOINT')}",
        f"  CURRENT CONTACTS: {_get_current_contacts('ELBOW_LEFT_JOINT', p, spec, palive, lalive, f, is_link=True, lid=f*nl+lidx['ELBOW_LEFT_JOINT'])}",
        f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'ELBOW_LEFT_JOINT')}",
        "",
        "LEFT_FIST",
        f"  STATUS: {ball_status('fistL')}",
        f"  POSITION: {rel_pos('fistL')}",
        f"  CURRENT CONTACTS: {_get_current_contacts('fistL', p, spec, palive, lalive, f)}",
        f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'fistL')}",
    ]

    return "\n".join(tree)


def build_enemy_tree(p, spec, my_f, fr, palive=None):
    """
    Builds the enemy body tree during fight mode (Section 7).
    All enemy ball positions are measured relative to MY CHEST CENTER.
    Uses my fighter's local RIGHT, UP, FRONT directions.
    The enemy chest's center-to-center distance is given in actual metres.
    NO contacts or touch events on enemy tree.
    """
    opp_f = 1 - my_f
    my_i = my_f * spec.n
    opp_i = opp_f * spec.n
    ix = spec.idx
    right, up, fwd = fr

    p_my_chest = p[my_i + ix["chest"]]
    p_opp_chest = p[opp_i + ix["chest"]]

    # Enemy chest relative vector
    d_chest = p_opp_chest - p_my_chest
    dx_c = float(np.dot(d_chest, right))
    dy_c = float(np.dot(d_chest, up))
    dz_c = float(np.dot(d_chest, fwd))
    center_to_center_dist = math.sqrt(dx_c * dx_c + dy_c * dy_c + dz_c * dz_c)

    h_word, v_word, v_round = translate_direction_words(dx_c, dy_c, dz_c)
    chest_pos_str = v_word if v_round in (90, -90) else f"{h_word} {v_word}"

    def opp_ball_status(ball_name):
        if palive is None:
            return "INTACT"
        b_idx = opp_i + ix[ball_name]
        return "INTACT" if palive[b_idx] else "DESTROYED"

    def rel_opp_pos(ball_name):
        b_idx = opp_i + ix[ball_name]
        d = p[b_idx] - p_my_chest
        dx = float(np.dot(d, right))
        dy = float(np.dot(d, up))
        dz = float(np.dot(d, fwd))
        is_ground = (p[b_idx, 1] - spec.r[b_idx]) <= 0.05
        return translate_3d_position(dx, dy, dz, is_grounded=is_ground)

    tree = [
        "MY CHEST CENTER = ORIGIN",
        "",
        "ENEMY FIGHTER",
        "",
        "CHEST",
        f"  STATUS: {opp_ball_status('chest')}",
        f"  POSITION: {chest_pos_str}",
        f"  CENTER-TO-CENTER DISTANCE: {center_to_center_dist:.2f} meters",
        "",
        "NECK",
        "",
        "HEAD",
        f"  STATUS: {opp_ball_status('head')}",
        f"  POSITION: {rel_opp_pos('head')}",
        "",
        "RIGHT_ARM",
        "",
        "RIGHT_SHOULDER",
        f"  STATUS: {opp_ball_status('shR')}",
        f"  POSITION: {rel_opp_pos('shR')}",
        "",
        "RIGHT_ELBOW",
        f"  STATUS: {opp_ball_status('elR')}",
        f"  POSITION: {rel_opp_pos('elR')}",
        "",
        "RIGHT_FIST",
        f"  STATUS: {opp_ball_status('fistR')}",
        f"  POSITION: {rel_opp_pos('fistR')}",
        "",
        "LEFT_ARM",
        "",
        "LEFT_SHOULDER",
        f"  STATUS: {opp_ball_status('shL')}",
        f"  POSITION: {rel_opp_pos('shL')}",
        "",
        "LEFT_ELBOW",
        f"  STATUS: {opp_ball_status('elL')}",
        f"  POSITION: {rel_opp_pos('elL')}",
        "",
        "LEFT_FIST",
        f"  STATUS: {opp_ball_status('fistL')}",
        f"  POSITION: {rel_opp_pos('fistL')}",
    ]

    return "\n".join(tree)


def format_movement_info(v, spec, f, fr):
    """
    Movement information (Section 8):
    Velocity info for chest and relevant balls (head, elbows, fists).
    Understood in simple terms (direction and speed).
    """
    i = f * spec.n
    ix = spec.idx
    right, up, fwd = fr

    balls = [
        ("CHEST", ix["chest"]),
        ("HEAD", ix["head"]),
        ("RIGHT_ELBOW", ix["shR"] if "elR" not in ix else ix["elR"]),
        ("RIGHT_FIST", ix["fistR"]),
        ("LEFT_ELBOW", ix["shL"] if "elL" not in ix else ix["elL"]),
        ("LEFT_FIST", ix["fistL"]),
    ]

    lines = ["CURRENT MOVEMENT:"]
    for label, b_ix in balls:
        vel = v[i + b_ix]
        spd = float(np.linalg.norm(vel))
        if spd < 0.05:
            lines.append(f"  {label}: STATIONARY (0.0 m/s)")
        else:
            dx = float(np.dot(vel, right))
            dy = float(np.dot(vel, up))
            dz = float(np.dot(vel, fwd))
            h_word, v_word, v_round = translate_direction_words(dx, dy, dz)
            dir_str = v_word if v_round in (90, -90) else f"{h_word} {v_word}"
            lines.append(f"  {label}: {spd:.2f} m/s towards {dir_str}")

    return "\n".join(lines)


def format_motor_state(spec, st, f, palive=None, lalive=None):
    """
    Motor state (Section 8):
    Useful current motor information (rotation, target rotation, power, tracking error).
    Disables motors if pivot ball or joint is destroyed.
    """
    lines = ["MOTOR STATE:"]
    for i, mo in enumerate(spec.motors):
        if mo["f"] != f:
            continue
        nm = mo["name"]
        pv_alive = palive[mo["pv"]] if palive is not None else True
        joint_alive = (lalive[mo["lid"]] if lalive is not None and "lid" in mo and mo["lid"] >= 0 else True)

        if not pv_alive or not joint_alive:
            lines.append(f"  {nm}: STATUS=DESTROYED (DISABLED)")
            continue

        cmd_vals = [int(round(x)) for x in st.cmd[i][:len(mo["lim"])]]
        pw = float(st.power[i])
        err = float(st.err[i])
        lines.append(f"  {nm}: TARGET_ROTATION={cmd_vals}° | POWER={pw:.2f} | ERROR={err:.3f} | STATUS=INTACT")
    return "\n".join(lines)


def build_detailed_pose_tree(p, v, spec, palive, lalive, f, fr, events, since, frame, sim_time, label="BODY POSE"):
    """
    Builds a detailed body pose tree including exact metres for small movement detection.
    Used for BEFORE/AFTER comparisons in Practice Mode.
    """
    i = f * spec.n
    ix = spec.idx
    nl = spec.nl
    lidx = spec.lidx
    f_char = "AB"[f]
    right, up, fwd = fr
    p_chest = p[i + ix["chest"]]
    
    chest_y = float(p_chest[1])
    chest_r = spec.r[i + ix["chest"]]
    chest_height = chest_y - chest_r
    
    def rel_pos_detailed(ball_name):
        b_idx = i + ix[ball_name]
        d = p[b_idx] - p_chest
        dx = float(np.dot(d, right))
        dy = float(np.dot(d, up))
        dz = float(np.dot(d, fwd))
        is_ground = (p[b_idx, 1] - spec.r[b_idx]) <= 0.05
        words = translate_3d_position(dx, dy, dz, is_grounded=is_ground)
        return f"{words} (Rel: {dx:+.3f}, {dy:+.3f}, {dz:+.3f}m)"

    def ball_status(ball_name):
        b_idx = i + ix[ball_name]
        return "INTACT" if palive[b_idx] else "DESTROYED"

    def joint_status(j_name):
        lid = f * nl + lidx[j_name]
        return "INTACT" if lalive[lid] else "DESTROYED"

    tree = [
        f"=== {label.upper()} ===",
        f"FRAME: {frame} | TIME: {sim_time:.2f}s",
        f"CHEST HEIGHT: {chest_height:.3f}m",
        "",
        "CHEST",
        f"  STATUS: {ball_status('chest')}",
        "  POSITION: ORIGIN",
        f"  CURRENT CONTACTS: {_get_current_contacts('chest', p, spec, palive, lalive, f)}",
        "",
        "HEAD",
        f"  STATUS: {ball_status('head')}",
        f"  POSITION: {rel_pos_detailed('head')}",
        f"  CURRENT CONTACTS: {_get_current_contacts('head', p, spec, palive, lalive, f)}",
        "",
        "RIGHT_ARM",
        "  SHOULDER",
        f"    STATUS: {ball_status('shR')}",
        f"    POSITION: {rel_pos_detailed('shR')}",
        f"    CONTACTS: {_get_current_contacts('shR', p, spec, palive, lalive, f)}",
        "  ELBOW",
        f"    STATUS: {ball_status('elR')}",
        f"    POSITION: {rel_pos_detailed('elR')}",
        f"    CONTACTS: {_get_current_contacts('elR', p, spec, palive, lalive, f)}",
        "  FIST",
        f"    STATUS: {ball_status('fistR')}",
        f"    POSITION: {rel_pos_detailed('fistR')}",
        f"    CONTACTS: {_get_current_contacts('fistR', p, spec, palive, lalive, f)}",
        "",
        "LEFT_ARM",
        "  SHOULDER",
        f"    STATUS: {ball_status('shL')}",
        f"    POSITION: {rel_pos_detailed('shL')}",
        f"    CONTACTS: {_get_current_contacts('shL', p, spec, palive, lalive, f)}",
        "  ELBOW",
        f"    STATUS: {ball_status('elL')}",
        f"    POSITION: {rel_pos_detailed('elL')}",
        f"    CONTACTS: {_get_current_contacts('elL', p, spec, palive, lalive, f)}",
        "  FIST",
        f"    STATUS: {ball_status('fistL')}",
        f"    POSITION: {rel_pos_detailed('fistL')}",
        f"    CONTACTS: {_get_current_contacts('fistL', p, spec, palive, lalive, f)}",
    ]
    return "\n".join(tree)


def format_motor_knowledge(knowledge):
    """Formats the persistent motor knowledge memory for the AI."""
    if not knowledge:
        return "MOTOR KNOWLEDGE MEMORY: Empty. Perform controlled experiments to learn motor effects."
    
    lines = ["MOTOR KNOWLEDGE MEMORY:"]
    for axis, data in knowledge.items():
        lines.append(f"  AXIS: {axis}")
        for direction, findings in data.items():
            lines.append(f"    DIRECTION: {direction}")
            for entry in findings:
                lines.append(f"      - {entry}")
    return "\n".join(lines)


def observe(p, v, spec, palive, lalive, cmd, st, f, t, events, since=0.0, enemy=True, total_seconds=60.0, errors=None, library=None, interval_history=None, transitions=None):
    """
    Builds the complete USER INPUT for one AI interval (Section 13).
    Extended for Practice Mode with BEFORE/AFTER poses and MOTOR KNOWLEDGE.
    """
    fr = torso_frame(p, spec, f)
    chest_pos = p[f * spec.n + spec.idx["chest"]]
    ring_margin = max(0.0, ARENA_R - float(np.hypot(chest_pos[0], chest_pos[2])))
    rem_time = max(0.0, total_seconds - t)

    parts = []

    # 1. Environment & timing header
    parts.append("=== ENVIRONMENT & TIMING ===")
    parts.append(f"FRAME: {st.frame}")
    parts.append(f"SIMULATION TIME: {t:.2f}s | REMAINING ROUND TIME: {rem_time:.1f}s")
    parts.append(f"DISTANCE TO ARENA WALL: {ring_margin:.2f}m")

    # 2. Command errors from previous answer
    if errors:
        parts.append("\n=== COMMAND ERRORS (PREVIOUS INTERVAL) ===")
        for e in errors[:5]:
            parts.append(f"  ERROR: {e}")

    # 3. Practice Mode: BEFORE/AFTER transitions
    if not enemy and transitions:
        parts.append("\n=== POSE-TO-POSE LEARNING (PREVIOUS MOVE) ===")
        parts.append(f"PREVIOUS COMMAND: {transitions.get('command', 'None')}")
        parts.append("\n" + build_detailed_pose_tree(**transitions['before'], label="BEFORE POSE"))
        parts.append("\n" + build_detailed_pose_tree(**transitions['after'], label="AFTER POSE"))
        parts.append("\nLEARNING TASK: Compare BEFORE and AFTER poses to understand the physical result of your command.")

    # 4. Interval description history (Five-interval context rule)
    parts.append("\n=== INTERVAL DESCRIPTIONS (LAST 5 INTERVALS, OLDEST FIRST) ===")
    if interval_history:
        recent = interval_history[-5:]
        for idx_h, desc in enumerate(recent, 1):
            parts.append(f"{idx_h}. {desc}")
    else:
        parts.append("No previous interval descriptions yet.")

    # 5. MY COMPLETE BODY TREE
    parts.append("\n=== MY COMPLETE BODY TREE (CURRENT) ===")
    parts.append(build_fighter_tree(p, spec, palive, lalive, f, fr, events, since, st.frame, t))

    # 6. ENEMY BODY TREE (Fight mode only)
    if enemy and spec.nf == 2:
        parts.append("\n=== ENEMY BODY TREE ===")
        parts.append(build_enemy_tree(p, spec, f, fr, palive=palive))

    # 7. Movement information
    parts.append("\n=== MOVEMENT INFORMATION ===")
    parts.append(format_movement_info(v, spec, f, fr))

    # 8. Motor state
    parts.append("\n=== MOTOR STATE ===")
    parts.append(format_motor_state(spec, st, f, palive=palive, lalive=lalive))

    # 9. Practice Mode: Motor Knowledge Memory
    if not enemy and library:
        parts.append("\n=== MOTOR KNOWLEDGE MEMORY ===")
        parts.append(format_motor_knowledge(library.get("motor_knowledge", {})))

    # 10. Saved moves and chains
    if library:
        parts.append("\n=== SAVED MOVES & CHAINS ===")
        parts.append(format_saved_library(library))

    parts.append("\nReply now with [THINKING] exactly 20 words [/THINKING] followed by your moves, chains, or do commands.")
    return "\n".join(parts)

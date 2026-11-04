"""OBSERVE: translates physical simulation state into natural-language 3D body trees and observations.
Never shows health numbers.
"""
import math
import numpy as np
from config import ARENA_R, H_DIR_WORDS, V_DIR_WORDS, DIST_THRESHOLDS, DIST_WORDS
from geometry import torso_frame

# Match contacts.respond(): a surface is considered touching within 1 mm.
GROUND_CONTACT_TOLERANCE = 1e-3

# Canonical 42-word vocabulary and distance thresholds come from config.py.

# 5 Distance values (measured directly from CHEST CENTER)
def get_distance_band(center_dist):
    for i, threshold in enumerate(DIST_THRESHOLDS):
        if center_dist <= threshold:
            return DIST_WORDS[i]
    return DIST_WORDS[-1]


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
    
    if is_grounded:
        dist_word = "GROUND"
    else:
        dist_word = get_distance_band(center_dist)

    h_word, v_word, v_rounded = translate_direction_words(dx, dy, dz)
    if v_rounded in (90, -90):
        return f"{dist_word} {v_word}"
    return f"{dist_word} {h_word} {v_word}"


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
            if ground_clearance <= GROUND_CONTACT_TOLERANCE:
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
            if min_y <= GROUND_CONTACT_TOLERANCE:
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


def build_fighter_tree(p, spec, palive, lalive, f, fr, events, since, frame, sim_time, positions_only=False):
    """
    Builds the official fighter body tree.
    All positions are measured relative to CHEST CENTER as origin in local (RIGHT, UP, FRONT) frame.
    positions_only: if True, omits status, contacts, and touch events (for memory).
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
        is_ground = (p[b_idx, 1] - spec.r[b_idx]) <= GROUND_CONTACT_TOLERANCE
        return translate_3d_position(dx, dy, dz, is_grounded=is_ground)

    def ball_status(ball_name):
        b_idx = i + ix[ball_name]
        return "INTACT" if palive[b_idx] else "DESTROYED"

    def joint_status(j_name):
        lid = f * nl + lidx[j_name]
        return "INTACT" if lalive[lid] else "DESTROYED"

    tree = ["MY FIGHTER"]
    if not positions_only:
        tree += [f"FRAME: {frame}", f"SIMULATION TIME: {sim_time:.1f}s", ""]
    
    tree += ["CHEST"]
    if not positions_only:
        tree.append(f"  STATUS: {ball_status('chest')}")
    tree.append("  POSITION: ORIGIN")
    if not positions_only:
        tree.append(f"  CURRENT CONTACTS: {_get_current_contacts('chest', p, spec, palive, lalive, f)}")
        tree.append(f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'chest')}")
    tree.append("")
    
    tree.append("NECK")
    tree.append("")
    
    tree.append("HEAD")
    if not positions_only:
        tree.append(f"  STATUS: {ball_status('head')}")
    tree.append(f"  POSITION: {rel_pos('head')}")
    if not positions_only:
        tree.append(f"  CURRENT CONTACTS: {_get_current_contacts('head', p, spec, palive, lalive, f)}")
        tree.append(f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'head')}")
    tree.append("")
    
    tree.append("RIGHT_ARM")
    tree.append("")
    
    tree.append("NECK_RIGHT_JOINT")
    if not positions_only:
        tree.append(f"  STATUS: {joint_status('NECK_RIGHT_JOINT')}")
        tree.append(f"  CURRENT CONTACTS: {_get_current_contacts('NECK_RIGHT_JOINT', p, spec, palive, lalive, f, is_link=True, lid=f*nl+lidx['NECK_RIGHT_JOINT'])}")
        tree.append(f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'NECK_RIGHT_JOINT')}")
    tree.append("")
    
    tree.append("RIGHT_SHOULDER")
    if not positions_only:
        tree.append(f"  STATUS: {ball_status('shR')}")
    tree.append(f"  POSITION: {rel_pos('shR')}")
    if not positions_only:
        tree.append(f"  CURRENT CONTACTS: {_get_current_contacts('shR', p, spec, palive, lalive, f)}")
        tree.append(f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'shR')}")
    tree.append("")
    
    tree.append("SHOULDER_RIGHT_JOINT")
    if not positions_only:
        tree.append(f"  STATUS: {joint_status('SHOULDER_RIGHT_JOINT')}")
        tree.append(f"  CURRENT CONTACTS: {_get_current_contacts('SHOULDER_RIGHT_JOINT', p, spec, palive, lalive, f, is_link=True, lid=f*nl+lidx['SHOULDER_RIGHT_JOINT'])}")
        tree.append(f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'SHOULDER_RIGHT_JOINT')}")
    tree.append("")
    
    tree.append("RIGHT_ELBOW")
    if not positions_only:
        tree.append(f"  STATUS: {ball_status('elR')}")
    tree.append(f"  POSITION: {rel_pos('elR')}")
    if not positions_only:
        tree.append(f"  CURRENT CONTACTS: {_get_current_contacts('elR', p, spec, palive, lalive, f)}")
        tree.append(f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'elR')}")
    tree.append("")
    
    tree.append("ELBOW_RIGHT_JOINT")
    if not positions_only:
        tree.append(f"  STATUS: {joint_status('ELBOW_RIGHT_JOINT')}")
        tree.append(f"  CURRENT CONTACTS: {_get_current_contacts('ELBOW_RIGHT_JOINT', p, spec, palive, lalive, f, is_link=True, lid=f*nl+lidx['ELBOW_RIGHT_JOINT'])}")
        tree.append(f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'ELBOW_RIGHT_JOINT')}")
    tree.append("")
    
    tree.append("RIGHT_FIST")
    if not positions_only:
        tree.append(f"  STATUS: {ball_status('fistR')}")
    tree.append(f"  POSITION: {rel_pos('fistR')}")
    if not positions_only:
        tree.append(f"  CURRENT CONTACTS: {_get_current_contacts('fistR', p, spec, palive, lalive, f)}")
        tree.append(f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'fistR')}")
    tree.append("")
    
    tree.append("LEFT_ARM")
    tree.append("")
    
    tree.append("NECK_LEFT_JOINT")
    if not positions_only:
        tree.append(f"  STATUS: {joint_status('NECK_LEFT_JOINT')}")
        tree.append(f"  CURRENT CONTACTS: {_get_current_contacts('NECK_LEFT_JOINT', p, spec, palive, lalive, f, is_link=True, lid=f*nl+lidx['NECK_LEFT_JOINT'])}")
        tree.append(f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'NECK_LEFT_JOINT')}")
    tree.append("")
    
    tree.append("LEFT_SHOULDER")
    if not positions_only:
        tree.append(f"  STATUS: {ball_status('shL')}")
    tree.append(f"  POSITION: {rel_pos('shL')}")
    if not positions_only:
        tree.append(f"  CURRENT CONTACTS: {_get_current_contacts('shL', p, spec, palive, lalive, f)}")
        tree.append(f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'shL')}")
    tree.append("")
    
    tree.append("SHOULDER_LEFT_JOINT")
    if not positions_only:
        tree.append(f"  STATUS: {joint_status('SHOULDER_LEFT_JOINT')}")
        tree.append(f"  CURRENT CONTACTS: {_get_current_contacts('SHOULDER_LEFT_JOINT', p, spec, palive, lalive, f, is_link=True, lid=f*nl+lidx['SHOULDER_LEFT_JOINT'])}")
        tree.append(f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'SHOULDER_LEFT_JOINT')}")
    tree.append("")
    
    tree.append("LEFT_ELBOW")
    if not positions_only:
        tree.append(f"  STATUS: {ball_status('elL')}")
    tree.append(f"  POSITION: {rel_pos('elL')}")
    if not positions_only:
        tree.append(f"  CURRENT CONTACTS: {_get_current_contacts('elL', p, spec, palive, lalive, f)}")
        tree.append(f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'elL')}")
    tree.append("")
    
    tree.append("ELBOW_LEFT_JOINT")
    if not positions_only:
        tree.append(f"  STATUS: {joint_status('ELBOW_LEFT_JOINT')}")
        tree.append(f"  CURRENT CONTACTS: {_get_current_contacts('ELBOW_LEFT_JOINT', p, spec, palive, lalive, f, is_link=True, lid=f*nl+lidx['ELBOW_LEFT_JOINT'])}")
        tree.append(f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'ELBOW_LEFT_JOINT')}")
    tree.append("")
    
    tree.append("LEFT_FIST")
    if not positions_only:
        tree.append(f"  STATUS: {ball_status('fistL')}")
    tree.append(f"  POSITION: {rel_pos('fistL')}")
    if not positions_only:
        tree.append(f"  CURRENT CONTACTS: {_get_current_contacts('fistL', p, spec, palive, lalive, f)}")
        tree.append(f"  TOUCH EVENTS: {_format_touch_events(events, since, f_char, 'fistL')}")

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
        is_ground = (p[b_idx, 1] - spec.r[b_idx]) <= GROUND_CONTACT_TOLERANCE
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

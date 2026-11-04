"""POSITION TREE -> MOTOR ROTATION TRANSLATOR.

The AI describes a desired body pose in the official position vocabulary.
This module converts that imaginary target pose into existing motor targets.
It never writes positions into the physics state.
"""
from __future__ import annotations

import math
import re
from typing import Dict, Optional, Tuple

import numpy as np

from config import DIST_WORDS, DIST_REPRESENTATIVE, H_DIR_WORDS, V_DIR_WORDS
from geometry import rot, torso_frame, unit

H_WORD_TO_DEG = {word: angle for angle, word in H_DIR_WORDS.items()}
V_WORD_TO_DEG = {word: angle for angle, word in V_DIR_WORDS.items()}

# Match the longest vertical term first. For example, SLIGHT UPPER must not
# be mistaken for the shorter suffix UPPER.
_VERTICAL_TERMS_LONGEST = sorted(V_WORD_TO_DEG, key=len, reverse=True)

BALL_PARTS = (
    "CHEST", "HEAD", "RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_FIST",
    "LEFT_SHOULDER", "LEFT_ELBOW", "LEFT_FIST",
)
_REQUIRED_POSITION_PARTS = set(BALL_PARTS)

_EXPECTED_TREE_HEADERS = (
    "MY FIGHTER",
    "CHEST",
    "NECK",
    "HEAD",
    "RIGHT_ARM",
    "NECK_RIGHT_JOINT",
    "RIGHT_SHOULDER",
    "SHOULDER_RIGHT_JOINT",
    "RIGHT_ELBOW",
    "ELBOW_RIGHT_JOINT",
    "RIGHT_FIST",
    "LEFT_ARM",
    "NECK_LEFT_JOINT",
    "LEFT_SHOULDER",
    "SHOULDER_LEFT_JOINT",
    "LEFT_ELBOW",
    "ELBOW_LEFT_JOINT",
    "LEFT_FIST",
)
_TREE_HEADERS = set(_EXPECTED_TREE_HEADERS)

_METADATA_PREFIXES = (
    "STATUS:", "CURRENT CONTACTS:", "CONTACTS:", "TOUCH EVENTS:",
    "FRAME:", "SIMULATION TIME:", "===", "MY CURRENT BODY TREE:",
)

_POSITION_RE = re.compile(r"^POSITION\s*:\s*(.*?)\s*$", re.IGNORECASE)


def _split_position(position: str) -> Optional[Tuple[str, Optional[str], str]]:
    """Return (distance, horizontal-or-None, vertical) for one valid position."""
    if not isinstance(position, str):
        return None
    text = " ".join(position.upper().strip().split())
    if text == "ORIGIN":
        return ("ORIGIN", None, "ORIGIN")
    if not text:
        return None

    tokens = text.split(" ", 1)
    if len(tokens) != 2:
        return None
    distance, directions = tokens
    if distance not in DIST_WORDS and distance != "GROUND":
        return None

    vertical = next(
        (term for term in _VERTICAL_TERMS_LONGEST
         if directions == term or directions.endswith(" " + term)),
        None,
    )
    if vertical is None:
        return None

    horizontal_text = directions[:-len(vertical)].strip()
    if vertical in ("STRAIGHT UP", "STRAIGHT DOWN"):
        if horizontal_text:
            return None
        horizontal = None
    else:
        if horizontal_text not in H_WORD_TO_DEG:
            return None
        horizontal = horizontal_text

    return distance, horizontal, vertical


def parse_tree(text: str, allow_metadata: bool = False) -> Optional[Dict[str, str]]:
    """Extract the eight physical-ball POSITION values from a returned tree.

    Only POSITION fields under official physical-ball headings are extracted.
    AI output is strict by default: status/contact/event fields, code fences,
    prose and unknown structural lines invalidate the complete response.
    allow_metadata=True is reserved for parsing the server's read-only input tree.
    """
    if not isinstance(text, str) or not text.strip():
        return None

    tree: Dict[str, str] = {}
    current_part: Optional[str] = None
    seen_headers = []
    saw_root = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        upper = " ".join(line.upper().split())
        if upper in _TREE_HEADERS:
            if len(seen_headers) >= len(_EXPECTED_TREE_HEADERS):
                return None
            if upper != _EXPECTED_TREE_HEADERS[len(seen_headers)]:
                return None
            if upper == "MY FIGHTER":
                if saw_root:
                    return None
                saw_root = True
            elif not saw_root:
                return None
            seen_headers.append(upper)
            current_part = upper if upper in _REQUIRED_POSITION_PARTS else None
            continue

        position_match = _POSITION_RE.match(line)
        if position_match:
            if current_part is None or current_part in tree:
                return None
            value = " ".join(position_match.group(1).upper().split())
            if not value:
                return None
            tree[current_part] = value
            continue

        if upper.startswith(_METADATA_PREFIXES):
            if allow_metadata:
                # Do not alter current_part: metadata belongs to the preceding ball.
                continue
            return None

        # A position-only target tree must not contain free-form prose,
        # motor syntax, or unrecognized body-part headings.
        return None

    if not saw_root or tuple(seen_headers) != _EXPECTED_TREE_HEADERS:
        return None
    return tree


def format_position_tree(tree: Dict[str, str]) -> str:
    """Render a validated position dictionary in the official tree order."""
    valid, reason = validate_tree(tree)
    if not valid:
        raise ValueError(f"Cannot format invalid position tree: {reason}")

    lines = []
    for header in _EXPECTED_TREE_HEADERS:
        lines.append(header)
        if header in _REQUIRED_POSITION_PARTS:
            lines.append(f"  POSITION: {tree[header]}")
        lines.append("")
    return "\n".join(lines).rstrip()


def validate_tree(tree: Optional[Dict[str, str]]) -> Tuple[bool, str]:
    """Strictly validate the physical-ball positions and official vocabulary."""
    if not isinstance(tree, dict) or not tree:
        return False, "Empty or malformed tree"

    keys = set(tree)
    missing = sorted(_REQUIRED_POSITION_PARTS - keys)
    extra = sorted(keys - _REQUIRED_POSITION_PARTS)
    if missing:
        return False, "Missing required positions: " + ", ".join(missing)
    if extra:
        return False, "Unexpected positioned parts: " + ", ".join(extra)

    if tree.get("CHEST") != "ORIGIN":
        return False, "CHEST position must be ORIGIN"

    for part in BALL_PARTS:
        if part == "CHEST":
            continue
        if tree[part] == "ORIGIN":
            return False, f"Only CHEST can be ORIGIN; found ORIGIN at {part}"
        if _split_position(tree[part]) is None:
            return False, f"Invalid position vocabulary or format for {part}: {tree[part]}"

    return True, "Valid"


def _local_vector(world_point, chest_pos, right, up, fwd):
    d = np.asarray(world_point, dtype=float) - np.asarray(chest_pos, dtype=float)
    return np.array([np.dot(d, right), np.dot(d, up), np.dot(d, fwd)], dtype=float)


def decode_position(
    position: str,
    right: np.ndarray,
    up: np.ndarray,
    fwd: np.ndarray,
    chest_pos: np.ndarray,
    ball_radius: float,
    distance_override: Optional[float] = None,
) -> Optional[np.ndarray]:
    """Decode one word position to a chest-relative local 3D point.

    Distance is centre-to-centre from CHEST. For GROUND, intersect the
    requested world-space ray with the floor using the actual target ball
    radius. Returns None when the requested ground ray cannot intersect.
    """
    parsed = _split_position(position)
    if parsed is None:
        return None

    distance_word, horizontal_word, vertical_word = parsed
    if distance_word == "ORIGIN":
        return np.zeros(3, dtype=float)

    h_deg = H_WORD_TO_DEG[horizontal_word] if horizontal_word else 0
    v_deg = V_WORD_TO_DEG[vertical_word]
    h_rad, v_rad = math.radians(h_deg), math.radians(v_deg)

    direction_local = np.array([
        math.cos(v_rad) * math.sin(h_rad),
        math.sin(v_rad),
        math.cos(v_rad) * math.cos(h_rad),
    ], dtype=float)

    if distance_word == "GROUND":
        direction_world = (
            direction_local[0] * right
            + direction_local[1] * up
            + direction_local[2] * fwd
        )
        if direction_world[1] >= -1e-8:
            return None
        ray_distance = (float(ball_radius) - float(chest_pos[1])) / direction_world[1]
        if not math.isfinite(ray_distance) or ray_distance < 0:
            return None
        return ray_distance * direction_local

    if distance_override is not None:
        radius = float(distance_override)
    else:
        radius = float(DIST_REPRESENTATIVE[distance_word])

    return radius * direction_local



def _closest_distance_in_band(word: str, current_distance: float) -> float:
    """Choose the nearest radius in a requested chest-centre distance band.

    The words represent ranges, not fixed coordinates. Selecting the nearest
    point in the requested range avoids artificial radial jumps caused by
    always targeting a band's midpoint.
    """
    bounds = {
        "VERY-CLOSE": (0.0, 0.10, True),
        "CLOSE": (0.10, 0.25, False),
        "MID": (0.25, 0.45, False),
        "FAR": (0.45, 0.70, False),
    }
    distance = max(0.0, float(current_distance))
    if word == "VERY-FAR":
        return max(distance, 0.7001)
    lower, upper, lower_inclusive = bounds[word]
    minimum = lower if lower_inclusive else lower + 1e-4
    return min(upper, max(minimum, distance))

def _find_motor(spec, name):
    for index, motor in enumerate(spec.motors):
        if motor.get("name") == name:
            return index, motor
    raise KeyError(f"Motor {name} is missing from the physics spec")


def _round_to_legal_15(value: float, limits: Tuple[float, float]) -> float:
    lo, hi = limits
    rounded = math.floor(float(value) / 15.0 + 0.5) * 15.0
    rounded = min(float(hi), max(float(lo), rounded))
    # All current motor limits align to 15 degrees. Keep a defensive check.
    if abs(rounded / 15.0 - round(rounded / 15.0)) > 1e-9:
        legal = [15.0 * n for n in range(math.ceil(lo / 15), math.floor(hi / 15) + 1)]
        rounded = min(legal, key=lambda candidate: abs(candidate - value))
    return float(rounded)


def solve_arm_ik(
    shoulder_pivot_local: np.ndarray,
    desired_elbow_local: np.ndarray,
    desired_fist_local: np.ndarray,
    spec,
    arm_side: str,
    initial_angles: Optional[Tuple[float, float, float]] = None,
):
    """Find absolute motor target angles for the desired elbow/fist points.

    Forward kinematics intentionally mirrors muscles._targets() exactly:
    shoulder ball motor with pitch/out, then elbow hinge bend.
    """
    _, mo_sh = _find_motor(spec, f"{arm_side}_shoulder")
    _, mo_el = _find_motor(spec, f"{arm_side}_elbow")

    upper_length = float(mo_sh["L"][0])
    forearm_length = float(mo_el["L"][0])
    shoulder_sign = float(mo_sh["s"])
    elbow_sign = float(mo_el["s"])

    right = np.array([1.0, 0.0, 0.0])
    up = np.array([0.0, 1.0, 0.0])
    fwd = np.array([0.0, 0.0, 1.0])
    shoulder_pivot_local = np.asarray(shoulder_pivot_local, dtype=float)

    def fk(q):
        pitch, out, bend = np.radians(q)
        upper_direction = (
            shoulder_sign * math.sin(out) * right
            - math.cos(out) * math.cos(pitch) * up
            + math.cos(out) * math.sin(pitch) * fwd
        )
        elbow_position = shoulder_pivot_local + upper_length * upper_direction
        upper_axis = unit(elbow_position - shoulder_pivot_local)
        forearm_direction = rot(upper_axis, right, elbow_sign * bend)
        fist_position = elbow_position + forearm_length * forearm_direction
        return elbow_position, fist_position

    if initial_angles is None:
        q = np.array([0.0, 0.0, 0.0], dtype=float)
    else:
        q = np.asarray(initial_angles, dtype=float).copy()

    limits = (mo_sh["lim"][0], mo_sh["lim"][1], mo_el["lim"][0])
    q[0] = np.clip(q[0], *limits[0])
    q[1] = np.clip(q[1], *limits[1])
    q[2] = np.clip(q[2], *limits[2])

    target_elbow = np.asarray(desired_elbow_local, dtype=float)
    target_fist = np.asarray(desired_fist_local, dtype=float)
    max_iterations = 100
    damping = 0.025
    max_step_degrees = 12.0
    epsilon_degrees = 0.05

    for _ in range(max_iterations):
        elbow_now, fist_now = fk(q)
        error = np.concatenate((2.0 * (target_elbow - elbow_now), target_fist - fist_now))
        if float(np.linalg.norm(error)) < 1e-5:
            break

        jacobian = np.zeros((6, 3), dtype=float)
        for axis in range(3):
            q_plus = q.copy()
            q_plus[axis] += epsilon_degrees
            elbow_plus, fist_plus = fk(q_plus)
            jacobian[:3, axis] = 2.0 * (elbow_plus - elbow_now) / epsilon_degrees
            jacobian[3:, axis] = (fist_plus - fist_now) / epsilon_degrees

        normal = jacobian.T @ jacobian + (damping ** 2) * np.eye(3)
        try:
            delta = np.linalg.solve(normal, jacobian.T @ error)
        except np.linalg.LinAlgError:
            break

        delta = np.clip(delta, -max_step_degrees, max_step_degrees)
        q += 0.65 * delta
        q[0] = np.clip(q[0], *limits[0])
        q[1] = np.clip(q[1], *limits[1])
        q[2] = np.clip(q[2], *limits[2])

    final_q = np.array([
        _round_to_legal_15(q[0], limits[0]),
        _round_to_legal_15(q[1], limits[1]),
        _round_to_legal_15(q[2], limits[2]),
    ], dtype=float)

    final_elbow, final_fist = fk(final_q)
    error_elbow = float(np.linalg.norm(target_elbow - final_elbow))
    error_fist = float(np.linalg.norm(target_fist - final_fist))
    return (float(final_q[0]), float(final_q[1])), (float(final_q[2]),), {
        "elbow_error_m": error_elbow,
        "fist_error_m": error_fist,
        "weighted_error_m": 2.0 * error_elbow + error_fist,
    }


def translate_trees(
    pose1_tree: Dict[str, str],
    pose2_tree: Dict[str, str],
    spec,
    fighter_index: int,
    p_state: np.ndarray,
    motor_targets: Optional[np.ndarray] = None,
    return_diagnostics: bool = False,
):
    """Translate current Pose 1 and imaginary desired Pose 2 into motor targets.

    Pose 1 is the latest measured tree. Pose 2 is temporary and is never
    written to the simulation. Unchanged word positions preserve their exact
    measured coordinates, avoiding artificial motion from distance-band
    midpoints. The solver starts at the currently commanded motor angles.
    """
    if not isinstance(pose1_tree, dict) or not isinstance(pose2_tree, dict):
        result = ({}, {"error": "Pose 1 or Pose 2 is not a parsed position tree"})
        return result if return_diagnostics else result[0]

    right, up, fwd = torso_frame(p_state, spec, fighter_index)
    chest_index = fighter_index * spec.n + spec.idx["chest"]
    chest_world = np.asarray(p_state[chest_index], dtype=float)
    orders = {}
    diagnostics = {"arms": {}, "errors": []}

    for side in ("R", "L"):
        long_side = "RIGHT" if side == "R" else "LEFT"
        elbow_name = f"{long_side}_ELBOW"
        fist_name = f"{long_side}_FIST"
        shoulder_name = f"{long_side}_SHOULDER"
        elbow_index = fighter_index * spec.n + spec.idx["el" + side]
        fist_index = fighter_index * spec.n + spec.idx["fist" + side]
        shoulder_index = fighter_index * spec.n + spec.idx["sh" + side]

        old_elbow_word = pose1_tree.get(elbow_name)
        old_fist_word = pose1_tree.get(fist_name)
        wanted_elbow_word = pose2_tree.get(elbow_name)
        wanted_fist_word = pose2_tree.get(fist_name)

        if not wanted_elbow_word or not wanted_fist_word:
            diagnostics["errors"].append(f"{long_side}: missing elbow/fist target")
            continue

        # If both controllable endpoints retain their current words, this arm
        # has no requested position change. Do not perturb the existing motor.
        if wanted_elbow_word == old_elbow_word and wanted_fist_word == old_fist_word:
            diagnostics["arms"][side] = {"status": "unchanged"}
            continue

        shoulder_pivot_local = _local_vector(p_state[shoulder_index], chest_world, right, up, fwd)
        current_elbow_local = _local_vector(p_state[elbow_index], chest_world, right, up, fwd)
        current_fist_local = _local_vector(p_state[fist_index], chest_world, right, up, fwd)

        def make_target(part_name, target_word, current_word, current_local, ball_index):
            if target_word == current_word:
                return current_local.copy()

            target_parts = _split_position(target_word)
            if target_parts and target_parts[0] != "GROUND":
                # A distance word is a range. Select the nearest radius in
                # that range to the measured current radius, rather than an
                # arbitrary midpoint that can make an otherwise valid limb
                # target geometrically impossible.
                distance_override = _closest_distance_in_band(
                    target_parts[0], float(np.linalg.norm(current_local))
                )
            else:
                distance_override = None

            return decode_position(
                target_word, right, up, fwd, chest_world,
                ball_radius=float(spec.r[ball_index]),
                distance_override=distance_override,
            )

        desired_elbow_local = make_target(
            elbow_name, wanted_elbow_word, old_elbow_word, current_elbow_local, elbow_index
        )
        desired_fist_local = make_target(
            fist_name, wanted_fist_word, old_fist_word, current_fist_local, fist_index
        )
        if desired_elbow_local is None or desired_fist_local is None:
            diagnostics["arms"][side] = {
                "status": "unreachable_ground_ray",
                "message": "A requested GROUND direction does not intersect the floor.",
            }
            continue

        sh_motor_index, _ = _find_motor(spec, f"{side}_shoulder")
        el_motor_index, _ = _find_motor(spec, f"{side}_elbow")
        if motor_targets is not None:
            initial_angles = (
                float(motor_targets[sh_motor_index][0]),
                float(motor_targets[sh_motor_index][1]),
                float(motor_targets[el_motor_index][0]),
            )
        else:
            initial_angles = (0.0, 0.0, 0.0)

        shoulder_angles, elbow_angles, fit = solve_arm_ik(
            shoulder_pivot_local,
            desired_elbow_local,
            desired_fist_local,
            spec,
            side,
            initial_angles=initial_angles,
        )

        old_angles = initial_angles
        new_angles = (shoulder_angles[0], shoulder_angles[1], elbow_angles[0])
        delta_angles = tuple(float(new - old) for new, old in zip(new_angles, old_angles))

        # Avoid issuing a no-op runner step. The current target remains active.
        if any(abs(delta) >= 7.5 for delta in delta_angles):
            orders[f"{side}_shoulder"] = (shoulder_angles, 1.0)
            orders[f"{side}_elbow"] = (elbow_angles, 1.0)

        diagnostics["arms"][side] = {
            "status": "targeted" if side + "_shoulder" in orders else "within_same_motor_bin",
            "old_angles": old_angles,
            "new_angles": new_angles,
            "delta_angles": delta_angles,
            **fit,
        }

    if return_diagnostics:
        return orders, diagnostics
    return orders

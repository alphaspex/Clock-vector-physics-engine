"""DEMO MOVE LIBRARY.

The AI selects a named action. Each action is a short, preconfigured motor
macro. Durations are measured in LIVE simulation ticks (7 ticks/second).
Replay records are flattened by rounds.py into 30-FPS motor-target events.
"""
from __future__ import annotations
import re


def _step(frames: int, **motors):
    return {"frames": int(frames), "motors": {k: (tuple(v), 1.0) for k, v in motors.items()}}


def _both(pitch, out, bend, frames=5):
    return _step(
        frames,
        R_shoulder=(pitch, out), L_shoulder=(pitch, out),
        R_elbow=(bend,), L_elbow=(bend,),
    )

# Recovery is deliberately split into three selectable actions so each stage
# can be observed before the next is chosen. Tests showed the full sequence
# can raise the head/chest from one specific prone pose; other falls vary.
MOVE_LIBRARY = {
    "HOLD": {
        "description": "Keep existing motor targets and observe the physical result.",
        "category": "control", "steps": [],
    },
    "GET_UP_HEAD_CLEAR": {
        "description": "Raise head and bring both fists toward supporting ground contact.",
        "category": "recovery", "steps": [_both(180, 0, 60, 7)],
    },
    "GET_UP_PRESS": {
        "description": "Reorient both arms to press against the floor and raise chest.",
        "category": "recovery", "steps": [_both(0, 0, 60, 3)],
    },
    "GET_UP_STABILIZE": {
        "description": "Stabilize the elevated torso with both arms supporting the body.",
        "category": "recovery", "steps": [_both(15, 0, 45, 7)],
    },
    "MOVE_FORWARD": {
        "description": "Drive both arms through a forward-directed push to advance the torso.",
        "category": "locomotion", "steps": [_both(90, 0, 60, 3)],
    },
    "MOVE_BACKWARD": {
        "description": "Pull both arms into a rearward-directed configuration to move backward.",
        "category": "locomotion", "steps": [_both(-90, 0, 60, 3)],
    },
    "TURN_LEFT": {
        "description": "Use opposing shoulder pitch to rotate the torso toward the left.",
        "category": "locomotion", "steps": [
            _step(4, R_shoulder=(-45, 0), L_shoulder=(45, 0), R_elbow=(45,), L_elbow=(45,)),
        ],
    },
    "TURN_RIGHT": {
        "description": "Use opposing shoulder pitch to rotate the torso toward the right.",
        "category": "locomotion", "steps": [
            _step(4, R_shoulder=(45, 0), L_shoulder=(-45, 0), R_elbow=(45,), L_elbow=(45,)),
        ],
    },
    "STRAFE_RIGHT": {
        "description": "Create asymmetric arm leverage to shift the torso toward the right.",
        "category": "locomotion", "steps": [
            _step(3, R_shoulder=(90, 0), L_shoulder=(0, 0), R_elbow=(60,), L_elbow=(60,)),
        ],
    },
    "STRAFE_LEFT": {
        "description": "Create opposite asymmetric arm leverage to shift the torso toward the left.",
        "category": "locomotion", "steps": [
            _step(3, R_shoulder=(0, 0), L_shoulder=(90, 0), R_elbow=(60,), L_elbow=(60,)),
        ],
    },
    "REACH_RIGHT": {
        "description": "Extend the right arm forward while retaining control of the left arm.",
        "category": "positioning", "steps": [
            _step(3, R_shoulder=(90, 0), R_elbow=(0,)),
        ],
    },
    "REACH_LEFT": {
        "description": "Extend the left arm forward while retaining control of the right arm.",
        "category": "positioning", "steps": [
            _step(3, L_shoulder=(90, 0), L_elbow=(0,)),
        ],
    },
    "REACH_BOTH": {
        "description": "Extend both arms forward together for a bilateral reach or push.",
        "category": "positioning", "steps": [
            _step(3, R_shoulder=(90, 0), L_shoulder=(90, 0), R_elbow=(0,), L_elbow=(0,)),
        ],
    },
    "GUARD_RIGHT": {
        "description": "Raise and bend the right arm into a compact defensive position.",
        "category": "defense", "steps": [_step(4, R_shoulder=(0, 90), R_elbow=(90,))],
    },
    "GUARD_LEFT": {
        "description": "Raise and bend the left arm into a compact defensive position.",
        "category": "defense", "steps": [_step(4, L_shoulder=(0, 90), L_elbow=(90,))],
    },
    "DOUBLE_GUARD": {
        "description": "Bring both arms into a symmetrical defensive configuration.",
        "category": "defense", "steps": [_both(0, 90, 90, 5)],
    },
    "JAB_RIGHT": {
        "description": "Quickly extend the right arm forward for a short-range strike.",
        "category": "attack", "steps": [_step(2, R_shoulder=(90, 0), R_elbow=(0,))],
    },
    "JAB_LEFT": {
        "description": "Quickly extend the left arm forward for a short-range strike.",
        "category": "attack", "steps": [_step(2, L_shoulder=(90, 0), L_elbow=(0,))],
    },
    "HOOK_RIGHT": {
        "description": "Sweep the right forearm laterally using shoulder rotation and elbow bend.",
        "category": "attack", "steps": [_step(3, R_shoulder=(45, 90), R_elbow=(60,))],
    },
    "HOOK_LEFT": {
        "description": "Sweep the left forearm laterally using shoulder rotation and elbow bend.",
        "category": "attack", "steps": [_step(3, L_shoulder=(45, 90), L_elbow=(60,))],
    },
    "DOUBLE_PUSH": {
        "description": "Drive both arms into a synchronized forward push against nearby support.",
        "category": "locomotion", "steps": [_both(45, 0, 0, 4)],
    },
}


def names():
    return tuple(MOVE_LIBRARY)


def describe_catalogue():
    lines = ["AVAILABLE PREBUILT ACTIONS (choose exactly one name per interval):"]
    for name, item in MOVE_LIBRARY.items():
        lines.append(f"{name} [{item['category']}]: {item['description']}")
    lines.append("Recovery order when prone: GET_UP_HEAD_CLEAR, then GET_UP_PRESS, then GET_UP_STABILIZE; inspect the new physical tree after every stage.")
    lines.append("Movement and attack labels describe intended actions, not guaranteed results. Physics decides what happens.")
    return "\n".join(lines)


def parse_action(text: str):
    """Return the exact catalog name from ACTION: NAME or a bare name."""
    if not isinstance(text, str) or not text.strip():
        return None
    cleaned = text.strip().upper()
    cleaned = cleaned.replace("`", "").replace("*", "")
    for name in MOVE_LIBRARY:
        if re.search(rf"(?im)^\s*(?:ACTION|MOVE)\s*:\s*{re.escape(name)}\s*$", cleaned):
            return name
    if cleaned in MOVE_LIBRARY:
        return cleaned
    # Accept a single labelled line only; never infer an action from prose.
    matches = re.findall(r"(?im)^\s*(?:ACTION|MOVE)\s*:\s*([A-Z0-9_]+)\s*$", cleaned)
    return matches[0] if len(matches) == 1 and matches[0] in MOVE_LIBRARY else None


def get(name):
    """Return a defensive copy of one action's timed runner steps."""
    if name not in MOVE_LIBRARY:
        raise KeyError(f"Unknown demo action: {name}")
    return [
        {"frames": step["frames"], "motors": dict(step["motors"])}
        for step in MOVE_LIBRARY[name]["steps"]
    ]


def info(name):
    item = MOVE_LIBRARY[name]
    return {"name": name, "description": item["description"], "category": item["category"]}

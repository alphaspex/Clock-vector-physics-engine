import math
import moves
import runner
from config import LIVE_DT, LIVE_FPS, FPS


def test_action_library_contains_recovery_forward_backward_and_turn_actions():
    required = {
        "GET_UP_HEAD_CLEAR", "GET_UP_PRESS", "GET_UP_STABILIZE",
        "MOVE_FORWARD", "MOVE_BACKWARD", "TURN_LEFT", "TURN_RIGHT",
        "STRAFE_LEFT", "STRAFE_RIGHT", "JAB_RIGHT", "JAB_LEFT",
        "HOOK_RIGHT", "HOOK_LEFT", "DOUBLE_GUARD", "HOLD",
    }
    assert required.issubset(set(moves.names()))
    assert len(moves.names()) >= 20


def test_every_prebuilt_motor_angle_is_a_legal_15_degree_value():
    for name in moves.names():
        for step in moves.get(name):
            assert 1 <= step["frames"] <= LIVE_FPS
            for motor, (angles, power) in step["motors"].items():
                assert motor in {"R_shoulder", "L_shoulder", "R_elbow", "L_elbow"}
                assert all(float(angle) % 15 == 0 for angle in angles)
                assert 0.0 <= power <= 1.0


def test_action_parser_accepts_only_catalogued_names():
    assert moves.parse_action("ACTION: MOVE_FORWARD") == "MOVE_FORWARD"
    assert moves.parse_action("**ACTION: GET_UP_PRESS**") == "GET_UP_PRESS"
    assert moves.parse_action("I think I should move forward") is None
    assert moves.parse_action("ACTION: UNKNOWN_MOVE") is None


def test_timed_runner_advances_even_when_motor_never_reaches_target():
    r = runner.override(runner.new(), moves.get("GET_UP_HEAD_CLEAR"))
    seen = []
    for _ in range(8):
        r, cmds = runner.advance(r, {name: 100.0 for name in ("R_shoulder", "L_shoulder", "R_elbow", "L_elbow")})
        if cmds:
            seen.append(cmds)
    assert len(seen) == 1
    assert r["cur"] is None
    assert r["remaining"] == 0


def test_live_fps_and_replay_fps_remain_separate():
    assert LIVE_FPS == 7
    assert math.isclose(LIVE_DT, 1 / 7)
    assert FPS == 30
    # one live tick is recorded at roughly 4.286 replay frames
    assert round(LIVE_DT * FPS) == 4


def test_replay_order_duration_is_scaled_to_30fps():
    live_frames = 7
    replay_frames = round(live_frames * FPS / LIVE_FPS)
    assert replay_frames == 30


def _run_action(name):
    import sim
    from config import LIVE_DT
    from geometry import torso_frame
    import numpy as np
    spec, state, runners = sim.new_match(1)
    before_chest = state.p[spec.idx["chest"]].copy()
    before_frame = torso_frame(state.p, spec, 0)[2].copy()
    runners = sim.give_orders(runners, 0, moves.get(name))
    duration = sum(step["frames"] for step in moves.get(name))
    for _ in range(duration):
        state, runners, _ = sim.tick(spec, state, runners, dt=LIVE_DT)
    after_frame = torso_frame(state.p, spec, 0)[2].copy()
    after_chest = state.p[spec.idx["chest"]]
    yaw_before = math.atan2(before_frame[0], before_frame[2])
    yaw_after = math.atan2(after_frame[0], after_frame[2])
    yaw = (math.degrees(yaw_after - yaw_before) + 180) % 360 - 180
    return after_chest - before_chest, yaw


def test_forward_and_backward_actions_move_chest_in_expected_local_direction():
    forward, _ = _run_action("MOVE_FORWARD")
    backward, _ = _run_action("MOVE_BACKWARD")
    # These are directional impulses, not promises of stable locomotion.
    assert forward[2] > 0.05
    assert backward[2] < -0.02


def test_turn_actions_rotate_in_opposite_directions():
    _, left_yaw = _run_action("TURN_LEFT")
    _, right_yaw = _run_action("TURN_RIGHT")
    assert left_yaw < -20
    assert right_yaw > 20


def test_three_stage_get_up_sequence_raises_head_and_chest_from_tested_prone_pose():
    import sim
    from config import LIVE_DT

    spec, state, runners = sim.new_match(1)
    idx = spec.idx
    prone = {
        "R_shoulder": ((45, 0), 1.0), "L_shoulder": ((45, 0), 1.0),
        "R_elbow": ((0,), 1.0), "L_elbow": ((0,), 1.0),
    }
    runners = sim.give_orders(runners, 0, [prone])
    for _ in range(7):
        state, runners, _ = sim.tick(spec, state, runners, dt=LIVE_DT)
    assert state.p[idx["chest"], 1] - spec.r[idx["chest"]] < 0.01
    assert state.p[idx["head"], 1] - spec.r[idx["head"]] < 0.01

    for action in ("GET_UP_HEAD_CLEAR", "GET_UP_PRESS", "GET_UP_STABILIZE"):
        runners = sim.give_orders(runners, 0, moves.get(action))
        for _ in range(sum(step["frames"] for step in moves.get(action))):
            state, runners, _ = sim.tick(spec, state, runners, dt=LIVE_DT)

    chest_clearance = state.p[idx["chest"], 1] - spec.r[idx["chest"]]
    head_clearance = state.p[idx["head"], 1] - spec.r[idx["head"]]
    assert chest_clearance > 0.10
    assert head_clearance > 0.30

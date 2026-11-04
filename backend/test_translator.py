"""Tests for the position-tree parser and pose-to-motor translator."""
import numpy as np

import body
import observe
import sim
import translator
from geometry import torso_frame


def _tree_string(values):
    lines = ["MY FIGHTER", "CHEST", "  POSITION: ORIGIN", "", "NECK", "", "HEAD", f"  POSITION: {values['HEAD']}", "",
             "RIGHT_ARM", "", "NECK_RIGHT_JOINT", "", "RIGHT_SHOULDER", f"  POSITION: {values['RIGHT_SHOULDER']}", "",
             "SHOULDER_RIGHT_JOINT", "", "RIGHT_ELBOW", f"  POSITION: {values['RIGHT_ELBOW']}", "",
             "ELBOW_RIGHT_JOINT", "", "RIGHT_FIST", f"  POSITION: {values['RIGHT_FIST']}", "",
             "LEFT_ARM", "", "NECK_LEFT_JOINT", "", "LEFT_SHOULDER", f"  POSITION: {values['LEFT_SHOULDER']}", "",
             "SHOULDER_LEFT_JOINT", "", "LEFT_ELBOW", f"  POSITION: {values['LEFT_ELBOW']}", "",
             "ELBOW_LEFT_JOINT", "", "LEFT_FIST", f"  POSITION: {values['LEFT_FIST']}"]
    return "\n".join(lines)


def _initial_pose(spec, state):
    frame = torso_frame(state.p, spec, 0)
    text = observe.build_fighter_tree(
        state.p, spec, state.palive, state.lalive, 0, frame, [], 0.0, 0, 0.0,
        positions_only=True,
    )
    return text, translator.parse_tree(text)


def test_position_tree_parsing_and_compound_vertical_words():
    spec, state, _ = sim.new_match(1)
    full = observe.build_fighter_tree(
        state.p, spec, state.palive, state.lalive, 0,
        torso_frame(state.p, spec, 0), [], 0.0, 0, 0.0,
    )
    parsed = translator.parse_tree(full, allow_metadata=True)
    assert translator.validate_tree(parsed)[0]

    values = dict(parsed)
    values["RIGHT_ELBOW"] = "CLOSE RIGHT SLIGHT UPPER"
    values["LEFT_ELBOW"] = "CLOSE LEFT SLIGHT LOWER"
    values["RIGHT_FIST"] = "GROUND STRAIGHT DOWN"
    text = _tree_string(values)
    round_trip = translator.parse_tree(text)
    assert translator.validate_tree(round_trip)[0]
    assert round_trip["RIGHT_ELBOW"] == "CLOSE RIGHT SLIGHT UPPER"
    assert round_trip["LEFT_ELBOW"] == "CLOSE LEFT SLIGHT LOWER"
    assert translator.parse_tree(translator.format_position_tree(round_trip)) == round_trip


def test_distance_is_measured_from_chest_centre():
    assert observe.get_distance_band(0.092) == "VERY-CLOSE"
    assert observe.get_distance_band(0.10) == "VERY-CLOSE"
    assert observe.get_distance_band(0.10001) == "CLOSE"
    assert observe.get_distance_band(0.25) == "CLOSE"
    assert observe.get_distance_band(0.25001) == "MID"
    assert observe.get_distance_band(0.45) == "MID"
    assert observe.get_distance_band(0.45001) == "FAR"
    assert observe.get_distance_band(0.70) == "FAR"
    assert observe.get_distance_band(0.70001) == "VERY-FAR"


def test_ground_decode_uses_actual_ball_radius():
    identity = (np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0]))
    chest = np.array([0.0, 0.35, 0.0])
    fist_radius = 0.022
    local = translator.decode_position(
        "GROUND STRAIGHT DOWN", *identity, chest, ball_radius=fist_radius
    )
    assert local is not None
    assert np.isclose(chest[1] + local[1], fist_radius, atol=1e-8)


def test_unchanged_pose_produces_no_motor_order():
    spec, state, _ = sim.new_match(1)
    _, pose = _initial_pose(spec, state)
    assert translator.validate_tree(pose)[0]
    orders, diagnostics = translator.translate_trees(
        pose, dict(pose), spec, 0, state.p, state.cmd, return_diagnostics=True
    )
    assert orders == {}
    assert diagnostics["arms"]["R"]["status"] == "unchanged"
    assert diagnostics["arms"]["L"]["status"] == "unchanged"


def test_changed_pose_generates_motor_targets_and_moves_physics():
    spec, state, runners = sim.new_match(1)
    _, pose1 = _initial_pose(spec, state)
    pose2 = dict(pose1)

    # This is the quantized 42-word description of a forward-raised right arm.
    pose2["RIGHT_ELBOW"] = "CLOSE FRONT DIAGONAL RIGHT LOWER"
    pose2["RIGHT_FIST"] = "MID FRONT RIGHT LOWER"

    orders, diagnostics = translator.translate_trees(
        pose1, pose2, spec, 0, state.p, state.cmd, return_diagnostics=True
    )
    assert "R_shoulder" in orders
    assert "R_elbow" in orders
    assert all(float(angle) % 15 == 0 for angle in orders["R_shoulder"][0])
    assert float(orders["R_elbow"][0][0]) % 15 == 0

    elbow_index = spec.idx["elR"]
    before = state.p[elbow_index].copy()
    runners = sim.give_orders(runners, 0, [orders])
    for _ in range(20):
        state, runners, _ = sim.tick(spec, state, runners)
    assert not np.allclose(state.cmd[spec.mix[(0, "R_shoulder")]][:2], [0.0, 0.0])
    assert np.linalg.norm(state.p[elbow_index] - before) > 0.005


def test_initial_fists_are_not_mislabeled_as_ground_contact_then_become_grounded():
    spec, state, runners = sim.new_match(1)
    frame = torso_frame(state.p, spec, 0)
    tree = observe.build_fighter_tree(
        state.p, spec, state.palive, state.lalive, 0,
        frame, [], 0.0, 0, 0.0,
    )
    assert "POSITION: MID RIGHT LOW DOWN\n  CURRENT CONTACTS: NONE" in tree

    for _ in range(20):
        state, runners, _ = sim.tick(spec, state, runners)
    frame = torso_frame(state.p, spec, 0)
    tree_after = observe.build_fighter_tree(
        state.p, spec, state.palive, state.lalive, 0,
        frame, [], 0.0, state.frame, state.frame / 7.0,
    )
    assert "RIGHT_FIST\n  STATUS: INTACT\n  POSITION: GROUND" in tree_after
    assert "CURRENT CONTACTS: GROUND" in tree_after


def test_observation_and_prompt_use_the_canonical_config_vocabulary():
    import config
    import prompts

    assert observe.H_DIR_WORDS is config.H_DIR_WORDS
    assert observe.V_DIR_WORDS is config.V_DIR_WORDS
    words = prompts.get_vocabulary_list().splitlines()
    assert len(words) == 43  # 42 official values plus the special GROUND value
    assert words.count("SLIGHT UPPER") == 1
    assert words.count("SLIGHT LOWER") == 1


def test_target_tree_requires_the_complete_official_hierarchy():
    spec, state, _ = sim.new_match(1)
    _, pose = _initial_pose(spec, state)
    valid_tree = _tree_string(pose)

    missing_header = valid_tree.replace("NECK_RIGHT_JOINT\n\n", "", 1)
    assert translator.parse_tree(missing_header) is None

    reordered = valid_tree.replace(
        "RIGHT_ARM\n\nNECK_RIGHT_JOINT", "NECK_RIGHT_JOINT\n\nRIGHT_ARM", 1
    )
    assert translator.parse_tree(reordered) is None

    assert translator.validate_tree(translator.parse_tree(valid_tree))[0]

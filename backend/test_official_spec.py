"""Comprehensive test suite for the Official Body, 3D Position Language, AI Observations, and Interval Memory specification."""
import math
import numpy as np
import body, moves, observe, geometry, damage, rules, db, muscles, sim
from config import *

def run_tests():
    passed = 0
    failed = 0

    def assert_eq(got, expected, msg):
        nonlocal passed, failed
        if got == expected:
            passed += 1
            print(f"[PASS] {msg}")
        else:
            failed += 1
            print(f"[FAIL] {msg} -> Got: {got!r}, Expected: {expected!r}")

    def assert_true(cond, msg):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"[PASS] {msg}")
        else:
            failed += 1
            print(f"[FAIL] {msg}")

    print("\n=== 1. OFFICIAL FIGHTER BODY STRUCTURE ===")
    spec = body.build_spec(1)
    # Check physical balls: exactly 8 balls
    expected_balls = ["chest", "head", "shR", "elR", "fistR", "shL", "elL", "fistL"]
    assert_eq(spec.n, 8, f"Fighter has exactly 8 balls (got {spec.n})")
    for name in expected_balls:
        assert_true(name in spec.idx, f"Ball '{name}' present in spec.idx")

    # Verify no hips, legs, knees, ankles, feet
    for removed in ["hip", "hipR", "hipL", "knR", "knL", "kneeR", "kneeL", "ankR", "ankL", "footR", "footL"]:
        assert_true(removed not in spec.idx, f"Old part '{removed}' absent from spec.idx")

    # Verify 6 named arm joints
    named_joints = [
        "NECK_RIGHT_JOINT", "NECK_LEFT_JOINT",
        "SHOULDER_RIGHT_JOINT", "SHOULDER_LEFT_JOINT",
        "ELBOW_RIGHT_JOINT", "ELBOW_LEFT_JOINT"
    ]
    for j in named_joints:
        assert_true(j in spec.named_joints, f"Named joint '{j}' present in spec")

    print("\n=== 2. JOINT RENDERING AND DESTRUCTION ===")
    import frames
    desc = frames.describe(spec)
    # Ensure all joints and neck links are rendered as shapes (7 links per fighter)
    rendered_links = [s for s in desc["shapes"] if s.get("k") == "cap"]
    assert_eq(len(rendered_links), spec.NL, f"All {spec.NL} joints and neck links are rendered as capsule shapes")

    # Joint destruction removes constraint and disables motor
    st = body.initial_state(spec)
    assert_true(st.lalive[spec.named_joints["SHOULDER_LEFT_JOINT"]], "Shoulder joint initially alive")
    st.lalive[spec.named_joints["SHOULDER_LEFT_JOINT"]] = False
    # Drive muscles with destroyed joint
    p_driven = st.p.copy()
    w_driven = spec.w.copy()
    muscles.drive(p_driven, w_driven, spec, {"L_shoulder": ((45.0, 0.0), 1.0)}, lalive=st.lalive)
    assert_true(np.allclose(p_driven[spec.idx["shL"]], st.p[spec.idx["shL"]]), "Destroyed shoulder joint does not transmit motor force")

    print("\n=== 3. MOTOR ROTATION RULE (EXACT 15° MULTIPLES) ===")
    info = spec.motor_info
    # Valid 15° commands
    p_valid = moves.parse("move test = L_shoulder -45,15 1.0 ; L_elbow 60 0.8", info)
    assert_eq(len(p_valid["errors"]), 0, f"Valid 15° multiples accepted without errors: {p_valid['errors']}")
    assert_eq(p_valid["moves"]["test"][0]["L_shoulder"], ((-45.0, 15.0), 1.0), "Motor angles preserved exactly")
    assert_eq(p_valid["moves"]["test"][0]["L_elbow"], ((60.0,), 0.8), "Elbow angle preserved exactly")

    # Invalid non-15° commands must be rejected, NEVER automatically rounded
    p_invalid1 = moves.parse("move bad1 = L_shoulder 10,20 1.0", info)
    assert_true(len(p_invalid1["errors"]) > 0, "10° and 20° rejected as non-15° multiples")
    assert_true("bad1" not in p_invalid1["moves"], "Invalid move not added to moves library")

    p_invalid2 = moves.parse("move bad2 = R_elbow 7 1.0", info)
    assert_true(len(p_invalid2["errors"]) > 0, "7° rejected as non-15° multiple")

    print("\n=== 4. POSITION REFERENCE & 42-WORD TRANSLATOR ===")
    # Rounding tests
    assert_eq(observe.round_to_15(7.0), 0.0, "7° rounds to 0°")
    assert_eq(observe.round_to_15(8.0), 15.0, "8° rounds to 15°")
    assert_eq(observe.round_to_15(22.0), 15.0, "22° rounds to 15°")
    assert_eq(observe.round_to_15(23.0), 30.0, "23° rounds to 30°")
    assert_eq(observe.round_to_15(-7.0), 0.0, "-7° rounds to 0°")
    assert_eq(observe.round_to_15(-8.0), -15.0, "-8° rounds to -15°")
    # Exact halfway deterministic rounding
    assert_eq(observe.round_to_15(7.5), 15.0, "7.5° halfway rounds to 15°")
    assert_eq(observe.round_to_15(22.5), 30.0, "22.5° halfway rounds to 30°")

    # Vocabulary checks
    assert_eq(len(observe.HORIZONTAL_WORDS), 24, "24 horizontal direction vocabulary words")
    assert_eq(len(observe.VERTICAL_WORDS), 13, "13 vertical direction vocabulary words")
    assert_eq(len(observe.DISTANCE_BANDS), 5, "5 distance bands")

    # Test coordinate frame (origin at chest: X=RIGHT, Y=UP, Z=FRONT)
    # Vector straight in front: (0, 0, 1.0)
    w_front = observe.describe_relative_vector(np.array([0.0, 0.0, 1.0]), clearance=1.0)
    assert_true(w_front.startswith("FRONT"), f"(0, 0, 1.0) is FRONT: got {w_front}")

    # Vector straight to right: (1.0, 0, 0)
    w_right = observe.describe_relative_vector(np.array([1.0, 0.0, 0.0]), clearance=1.0)
    assert_true(w_right.startswith("RIGHT"), f"(1.0, 0, 0) is RIGHT: got {w_right}")

    # Vector straight back: (0, 0, -1.0)
    w_back = observe.describe_relative_vector(np.array([0.0, 0.0, -1.0]), clearance=1.0)
    assert_true(w_back.startswith("BACK"), f"(0, 0, -1.0) is BACK: got {w_back}")

    # Vector straight to left: (-1.0, 0, 0)
    w_left = observe.describe_relative_vector(np.array([-1.0, 0.0, 0.0]), clearance=1.0)
    assert_true(w_left.startswith("LEFT"), f"(-1.0, 0, 0) is LEFT: got {w_left}")

    # Straight UP (0, 1.0, 0) -> horizontal direction omitted
    w_up = observe.describe_relative_vector(np.array([0.0, 1.0, 0.0]), clearance=1.0)
    assert_true("STRAIGHT UP" in w_up and "FRONT" not in w_up and "RIGHT" not in w_up, f"Straight up omits horizontal: {w_up}")

    # Straight DOWN (0, -1.0, 0) -> horizontal direction omitted
    w_down = observe.describe_relative_vector(np.array([0.0, -1.0, 0.0]), clearance=1.0)
    assert_true("STRAIGHT DOWN" in w_down and "FRONT" not in w_down, f"Straight down omits horizontal: {w_down}")

    # Ground replacement
    w_ground = observe.describe_relative_vector(np.array([0.0, -0.5, 0.5]), clearance=0.03)
    assert_true(w_ground.endswith("GROUND"), f"Low clearance (<0.05m) uses GROUND: got {w_ground}")

    print("\n=== 5. BODY TREES IN AI OBSERVATIONS ===")
    s2, a, rn = sim.new_match(2, gap=1.2)
    obs = observe.observe(a.p, s2, a.palive, a.cmd, 0, 1.0, [{"kind": "dyn", "ia": s2.idx["fistR"], "ib": s2.idx["head"] + s2.n, "E": 12.0}])
    assert_true("MY FIGHTER (CHEST CENTER IS ORIGIN)" in obs, "Own fighter tree present")
    assert_true("CURRENT CONTACTS:" in obs, "Current contacts present on own parts")
    assert_true("TOUCH EVENTS:" in obs, "Touch events present on own parts")
    assert_true("ENEMY FIGHTER (MEASURED FROM MY CHEST CENTER)" in obs, "Enemy tree present")
    assert_true("CENTER-TO-CENTER DISTANCE:" in obs and "meters" in obs, "Enemy chest distance given in exact metres")
    assert_true("ENEMY FIGHTER" in obs and "CURRENT CONTACTS:" not in obs.split("ENEMY FIGHTER")[1], "No contacts on enemy fighter tree")

    print("\n=== 6. 20-WORD THINKING EXTRACTION & DESCRIPTION RULES ===")
    # Exact 20 words
    thinking_20 = "I will strike the opponent chest with a quick left jab and recover immediately to protect my head from counters."
    raw_ai = f"[THINKING] {thinking_20} [/THINKING]\nmove hook = R_shoulder 45,0 1.0\ndo hook"
    th, ok_20, count = moves.extract_thinking(raw_ai)
    assert_eq(ok_20, True, "20-word thinking validated")
    assert_eq(count, 20, f"Word count is exactly 20 (got {count})")
    assert_eq(th, thinking_20, "Thinking text correctly extracted without brackets")

    # Invalid word counts
    th_short, ok_short, count_s = moves.extract_thinking("[THINKING] Quick jab. [/THINKING]")
    assert_eq(ok_short, False, "Short thinking flagged as not 20 words")
    assert_eq(count_s, 2, f"Short count is 2 (got {count_s})")

    # Move description (5-10 words) and Chain description (10-15 words)
    txt_desc = """
move cross = R_shoulder 60,0 1.0 : Powerful straight right punch targeting chest
chain 1-2 = jab, cross : Fast combination starting with left jab and finishing with right cross
"""
    p_desc = moves.parse(txt_desc, info)
    assert_eq(len(p_desc["errors"]), 0, f"Descriptions parsed cleanly: {p_desc['errors']}")
    assert_true("cross" in p_desc["move_descriptions"], "Move description stored")
    assert_true("1-2" in p_desc["chain_descriptions"], "Chain description stored")

    print("\n=== 7. ROUND SUMMARIES & SEPARATE MEMORY SLOTS ===")
    db.init()
    # Test saving and loading round summaries separately for practice vs fight and A vs B
    db.save_round_summary("round_1", "practice", "A", "1. WHAT I DID: jabbed. 2. WHAT I FAILED AT: missed. 3. WHAT I SHOULD HAVE DONE: duck.", 1)
    db.save_round_summary("round_2", "practice", "A", "1. WHAT I DID: hooked. 2. WHAT I FAILED AT: slow. 3. WHAT I SHOULD HAVE DONE: move.", 2)
    db.save_round_summary("round_3", "practice", "A", "1. WHAT I DID: defended. 2. WHAT I FAILED AT: balance. 3. WHAT I SHOULD HAVE DONE: counter.", 3)
    db.save_round_summary("round_4", "fight", "A", "1. WHAT I DID: fought hard. 2. WHAT I FAILED AT: got hit. 3. WHAT I SHOULD HAVE DONE: block.", 4)
    db.save_round_summary("round_5", "fight", "B", "1. WHAT I DID: counter-attacked. 2. WHAT I FAILED AT: nothing. 3. WHAT I SHOULD HAVE DONE: repeat.", 5)

    prac_a = db.load_round_summaries("practice", "A", limit=3)
    assert_eq(len(prac_a), 3, "Loads exactly latest 3 practice summaries for Fighter A")
    fight_a = db.load_round_summaries("fight", "A", limit=3)
    assert_eq(len(fight_a), 1, "Practice and fight summaries kept strictly separate")
    fight_b = db.load_round_summaries("fight", "B", limit=3)
    assert_eq(len(fight_b), 1, "Fighter A and B summaries kept strictly separate")
    assert_true("counter-attacked" in fight_b[0]["summary"], "Fighter B content correct")

    print(f"\n==========================================")
    print(f"RESULTS: {passed} PASSED, {failed} FAILED")
    print(f"==========================================")
    return failed == 0

if __name__ == "__main__":
    success = run_tests()
    import sys
    sys.exit(0 if success else 1)

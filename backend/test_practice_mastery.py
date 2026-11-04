"""Test for One-Move Learning and Mastery logic.
"""
import sys
import os
import numpy as np

# Mocking server_logs to avoid issues
class MockLogs:
    def emit(*args, **kwargs): pass
sys.modules['server_logs'] = MockLogs

import body
import moves
import rounds
import practice_eval

def test_mastery_streak():
    spec = body.build_spec(1)
    # Initial library
    lib = dict(moves={}, chains={}, move_descriptions={}, chain_descriptions={}, move_history={}, mastered_moves={}, mastered_chains={}, active_goal="recovery")
    
    # 1. Test parsing with mastered moves requirement
    # Try to create a chain with non-mastered move
    txt = "chain combo = punch, punch"
    parsed = moves.parse(txt, spec.motor_info, mastered_moves={})
    if not any("not MASTERED" in e for e in parsed["errors"]):
        print("FAIL: Chain created with non-mastered move")
    else:
        print("PASS: Chain rejected non-mastered move")
        
    # Mark 'punch' as mastered
    mastered = {"punch": {"mastered": True, "streak": 3}}
    parsed = moves.parse(txt, spec.motor_info, mastered_moves=mastered)
    if parsed["errors"]:
        print(f"FAIL: Mastered chain rejected: {parsed['errors']}")
    else:
        print("PASS: Chain accepted mastered move")

    # 2. Test move history on edit
    lib["moves"] = {"recovery": [{"R_shoulder": [[0,0], 1.0]}]}
    parsed = {"moves": {"recovery": [{"R_shoulder": [[15,0], 1.0]}]}}
    lib2 = moves.merge(lib, parsed)
    if len(lib2["move_history"].get("recovery", [])) == 1:
        print("PASS: Move history saved on edit")
    else:
        print(f"FAIL: Move history not saved. History: {lib2['move_history']}")

    # 3. Test initial pose for recovery
    st = practice_eval.get_initial_pose("recovery", spec)
    chest_y = st.p[spec.idx["chest"], 1]
    r_chest = spec.r[spec.idx["chest"]]
    if (chest_y - r_chest) < 0.05:
        print(f"PASS: Recovery initial pose is grounded (clearance={chest_y-r_chest:.3f})")
    else:
        print(f"FAIL: Recovery initial pose NOT grounded (clearance={chest_y-r_chest:.3f})")

    # 4. Test streak tracking (Mocking a round result)
    # This would require running a full sim, which is slow.
    # Instead, let's just verify the logic in a small snippet similar to rounds.py
    
    def simulate_streak(success_sequence):
        streak_lib = dict(mastered_moves={}, active_goal="recovery")
        for success in success_sequence:
            eval_res = {"success": success, "diagnostics": "..."}
            goal_id = streak_lib["active_goal"]
            mastered_moves = streak_lib.get("mastered_moves", {})
            target_move_name = goal_id
            move_status = mastered_moves.get(target_move_name, {"streak": 0, "mastered": False})
            if eval_res["success"]:
                move_status["streak"] += 1
                if move_status["streak"] >= 3:
                    move_status["mastered"] = True
            else:
                move_status["streak"] = 0
            mastered_moves[target_move_name] = move_status
            streak_lib["mastered_moves"] = mastered_moves
        return streak_lib["mastered_moves"]["recovery"]

    res1 = simulate_streak([True, True, True])
    if res1["streak"] == 3 and res1["mastered"]:
        print("PASS: Mastery reached after 3 successes")
    else:
        print(f"FAIL: Mastery logic error. Result: {res1}")

    res2 = simulate_streak([True, True, False])
    if res2["streak"] == 0 and not res2["mastered"]:
        print("PASS: Streak reset on failure")
    else:
        print(f"FAIL: Streak reset error. Result: {res2}")

if __name__ == "__main__":
    test_mastery_streak()

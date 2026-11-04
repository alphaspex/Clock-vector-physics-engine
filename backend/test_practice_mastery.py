"""Test for AI-Self-Approved Mastery logic.
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

def test_ai_self_mastery():
    spec = body.build_spec(1)
    
    # 1. Test Mastery via SUCCESS tag
    def simulate_ai_judgment(summary_text):
        lib = dict(mastered_moves={}, active_goal="recovery")
        ai_success = "RESULT: SUCCESS" in summary_text.upper()
        
        goal_id = lib["active_goal"]
        mastered_moves = lib.get("mastered_moves", {})
        target_move_name = goal_id
        move_status = mastered_moves.get(target_move_name, {"streak": 0, "mastered": False})
        
        if ai_success:
            move_status["streak"] = 1
            move_status["mastered"] = True
        else:
            move_status["streak"] = 0
            move_status["mastered"] = False
            
        mastered_moves[target_move_name] = move_status
        lib["mastered_moves"] = mastered_moves
        return lib["mastered_moves"]["recovery"]

    res1 = simulate_ai_judgment("The round went well. RESULT: SUCCESS")
    if res1["mastered"] and res1["streak"] == 1:
        print("PASS: Mastery granted on SUCCESS tag")
    else:
        print(f"FAIL: Mastery logic error on SUCCESS. Result: {res1}")

    res2 = simulate_ai_judgment("I failed to lift my chest. RESULT: FAILED")
    if not res2["mastered"] and res2["streak"] == 0:
        print("PASS: Mastery denied on FAILED tag")
    else:
        print(f"FAIL: Mastery logic error on FAILED. Result: {res2}")

    # 2. Test physical report generation
    st = body.initial_state(spec)
    report = practice_eval.get_physical_report("recovery", st, spec)
    if "FINAL PHYSICAL STATE REPORT" in report and "Chest Ground Clearance" in report:
        print("PASS: Physical report generated with correct sections")
    else:
        print(f"FAIL: Physical report content error. Report: {report}")

if __name__ == "__main__":
    test_ai_self_mastery()

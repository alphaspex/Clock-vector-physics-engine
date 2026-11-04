import sys
import os
import numpy as np
import math

# Add current dir to path to import backend modules
sys.path.append(os.getcwd())

from backend import translator, body, observe, geometry

def test_parse():
    print("Testing parse_position_to_point...")
    # Mock torso frame (Identity)
    fr = (np.array([1,0,0]), np.array([0,1,0]), np.array([0,0,1]))
    p_chest = np.array([0, 0.35, 0])
    
    # CLOSE FRONT LEVEL
    # CLOSE: 0.10 to 0.25 -> 0.175
    # FRONT: 0 deg
    # LEVEL: 0 deg
    # Expected: X=0, Y=0, Z=0.175 + 0.092 = 0.267
    pt = translator.parse_position_to_point("CLOSE FRONT LEVEL", fr, p_chest)
    print(f"CLOSE FRONT LEVEL: {pt}")
    assert np.allclose(pt, [0, 0, 0.267], atol=1e-3)
    
    # MID RIGHT LEVEL
    # MID: 0.25 to 0.45 -> 0.35
    # RIGHT: 90 deg
    # LEVEL: 0 deg
    # Expected: X=0.35+0.092 = 0.442, Y=0, Z=0
    pt = translator.parse_position_to_point("MID RIGHT LEVEL", fr, p_chest)
    print(f"MID RIGHT LEVEL: {pt}")
    assert np.allclose(pt, [0.442, 0, 0], atol=1e-3)

    # FAR STRAIGHT UP
    # FAR: 0.45 to 0.70 -> 0.575
    # STRAIGHT UP: 90 deg
    # Expected: X=0, Y=0.575+0.092 = 0.667, Z=0
    pt = translator.parse_position_to_point("FAR STRAIGHT UP", fr, p_chest)
    print(f"FAR STRAIGHT UP: {pt}")
    assert np.allclose(pt, [0, 0.667, 0], atol=1e-3)

def test_ik():
    print("\nTesting IK solver...")
    spec = body.build_spec(1)
    fr = (np.array([1,0,0]), np.array([0,1,0]), np.array([0,0,1]))
    p_chest = np.array([0, 0.35, 0])
    
    # Right shoulder pivot in torso frame (from body.py base)
    # shR: (0.17, 0.41, 0.0)
    # chest: (0.0, 0.35, 0.0)
    # local: (0.17, 0.06, 0.0)
    sh_pivot = np.array([0.17, 0.06, 0.0])
    
    # Target: Arm pointing forward
    # Elbow target: sh_pivot + L1 * fwd
    # Fist target: sh_pivot + (L1+L2) * fwd
    mo_sh = next(m for m in spec.motors if m["name"] == "R_shoulder")
    mo_el = next(m for m in spec.motors if m["name"] == "R_elbow")
    L1, L2 = mo_sh["L"][0], mo_el["L"][0]
    
    el_target = sh_pivot + np.array([0, 0, L1])
    fi_target = sh_pivot + np.array([0, 0, L1 + L2])
    
    sh_ang, el_ang, err = translator.inverse_kinematics(
        el_target, fi_target, sh_pivot, fr, spec, "R"
    )
    print(f"Forward reach: Sh={sh_ang}, El={el_ang}, Err={err:.4f}")
    # Expected: Pitch 90, Out 0, Bend 0
    assert abs(sh_ang[0] - 90) < 1e-1
    assert abs(sh_ang[1] - 0) < 1e-1
    assert abs(el_ang[0] - 0) < 1e-1

    # Target: Arm pointing right
    el_target = sh_pivot + np.array([L1, 0, 0])
    fi_target = sh_pivot + np.array([L1 + L2, 0, 0])
    sh_ang, el_ang, err = translator.inverse_kinematics(
        el_target, fi_target, sh_pivot, fr, spec, "R"
    )
    print(f"Right reach: Sh={sh_ang}, El={el_ang}, Err={err:.4f}")
    # Expected: Pitch 0, Out 90, Bend 0
    assert abs(sh_ang[0] - 0) < 1e-1
    assert abs(sh_ang[1] - 90) < 1e-1
    assert abs(el_ang[0] - 0) < 1e-1

def test_translation():
    print("\nTesting translate_step...")
    spec = body.build_spec(1)
    st = body.initial_state(spec)
    fr = geometry.torso_frame(st.p, spec, 0)
    
    step = {
        "RIGHT_FIST": "MID FRONT LEVEL 0.9",
        "R_shoulder": ((0.0, 0.0), 1.0) # Existing should stay
    }
    
    translated = translator.translate_step(step, st.p, spec, 0, fr)
    print(f"Translated step: {translated}")
    
    assert "R_shoulder" in translated
    assert "R_elbow" in translated
    # Check that power was extracted
    assert translated["R_shoulder"][1] == 0.9
    assert translated["R_elbow"][1] == 0.9

if __name__ == "__main__":
    try:
        test_parse()
        test_ik()
        test_translation()
        print("\nAll tests PASSED!")
    except Exception as e:
        print(f"\nTests FAILED: {e}")
        import traceback
        traceback.print_exc()

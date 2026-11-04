"""Tests. Each file is tested alone with made-up inputs (that is the point of I/O files)."""
import time, numpy as np
import body, moves, runner, damage, rules, sim, observe
from config import *
from geometry import torso_frame

ok = lambda c, msg: print(("PASS " if c else "FAIL ") + msg)
spec = body.build_spec(2)
info = spec.motor_info

# --- moves.parse alone
txt = """[THINKING] I will strike the opponent chest with a quick left jab and recover immediately to protect my head. [/THINKING]
move jab = L_shoulder 75,15 0.9 ; L_elbow 15 0.9 | L_shoulder 180,0 2.0 ; L_elbow 150 0.5
move bad_angle = L_shoulder 80,10 0.9
move bad_motor = L_pinky 10
chain combo = jab, jab
do combo"""
thinking, valid_20, count = moves.extract_thinking(txt)
ok(valid_20 and count == 20, f"extracted exact 20-word thinking (count={count})")
P = moves.parse(txt, info)
ok(P["moves"]["jab"][1]["L_shoulder"] == ((180.0, 0.0), 1.0), "values auto-clamped to max (power 2->1)")
ok(P["moves"]["jab"][1]["L_elbow"] == ((150.0,), 0.5), "elbow 150 -> 150")
ok(any("80" in e or "15" in e for e in P["errors"]), f"non-15-degree angle rejected: {P['errors']}")
ok(len(P["errors"]) >= 2, f"bad lines reported: {P['errors']}")
lib = moves.merge(dict(moves={}, chains={}), P)
steps, errs = moves.compile_do(P["do"], lib)
ok(len(steps) == 4, f"chain expands to {len(steps)} steps")

# --- runner alone: override + no timeout
r = runner.new(); r = runner.override(r, steps)
r, c = runner.advance(r, {}); ok("L_shoulder" in c, "first step starts")
for _ in range(500): r, c = runner.advance(r, {"L_shoulder": 1.0, "L_elbow": 1.0})
ok(r["cur"] is not None and len(r["queue"]) == 3, "stuck chain stays stuck (no timeout)")
r = runner.override(r, steps[:1]); ok(r["cur"] is None and len(r["queue"]) == 1, "new call overrides stuck chain")
r, c = runner.advance(r, {}); r, c2 = runner.advance(r, {"L_shoulder": 0.01, "L_elbow": 0.01})
ok(r["cur"] is None and r["queue"] == [], "step finishes when motors reached")

# --- damage alone
st = body.initial_state(spec)
fr = [torso_frame(st.p, spec, f) for f in range(2)]
head = spec.idx["head"]; fist = spec.idx["fistL"]; fistR = spec.idx["fistR"]
t = [dict(kind="dyn", ia=fist, ib=head, lid=-1, t=0.0, n=np.array([0, 0, 1.0]), E=10.0, pt=np.zeros(3))]
php, lhp, pal, lal, rec = damage.apply(t, st.php, st.lhp, st.palive, st.lalive, spec, fr, 1.0)
ok(abs(php[head] - (32 - 15)) < 1e-6, f"iron fist 10J on wood head: head 32 -> {php[head]:.1f} (x1.5)")
t = [dict(kind="dyn", ia=fist, ib=fistR, lid=-1, t=0, n=np.array([0, 0, 1.0]), E=50.0, pt=np.zeros(3))]
php, *_ = damage.apply(t, st.php, st.lhp, st.palive, st.lalive, spec, fr, 1.0)
ok(np.isinf(php[fistR]), "iron on iron: no damage, iron indestructible")
t = [dict(kind="dyn", ia=fist, ib=-1, lid=spec.lidx["neck"], t=0.5, n=np.array([0, 0, 1.0]), E=25.0, pt=np.zeros(3))]
php, lhp, pal, lal, rec = damage.apply(t, st.php, st.lhp, st.palive, st.lalive, spec, fr, 2.0)
ok(not lal[spec.lidx["neck"]] and any(x["event"] == "destroyed" for x in rec), "37.5J on neck (32J): neck destroyed")
o, lost, res = rules.judge(pal, lal, [(0, 0), (0, 0)], np.zeros(2), 2.0, spec)
ok(res == "B" and lost[0], f"neck destroyed -> fighter A loses, result={res}")
o, lost, res = rules.judge(st.palive, st.lalive, [(5.5, 0), (0, 0)], np.array([9.99, 0]), 2.0, spec)
ok(lost[0] and res == "B", "10 s outside ring -> loses")
o, lost, res = rules.judge(st.palive, st.lalive, [(0, 0), (0, 0)], np.zeros(2), 60.0, spec)
ok(res == "draw", "60 s with no winner -> draw")

# --- full physics: one fighter standing, timing
s1, stt, rn = sim.new_match(1)
t0 = time.time(); h0 = stt.p[s1.core[0]][1]
for i in range(90): stt, rn, rec = sim.tick(s1, stt, rn)
dt = (time.time() - t0) / 90
fr1 = torso_frame(stt.p, s1, 0)
print(f"INFO 3 s hold-pose: core height {h0*100:.0f}cm -> {stt.p[s1.core[0]][1]*100:.0f}cm, upright={fr1[1][1]:.2f}, "
      f"finite={np.isfinite(stt.p).all()}, {dt*1000:.1f} ms/frame (1 fighter)")
ok(np.isfinite(stt.p).all(), "no NaN / explosion")

# --- two fighters, jab at head, determinism
def fight():
    s2, a, rn = sim.new_match(2, gap=0.45, offset_x=0.17)
    p = moves.parse("move jab = L_shoulder 120,0 1 ; L_elbow 0 1", info)
    lb = moves.merge(dict(moves={}, chains={}), p)
    stp, _ = moves.compile_do(["jab"], lb)
    rn = sim.give_orders(rn, 0, stp)
    ev = []; mx = 0
    for i in range(60):
        a, rn, rec = sim.tick(s2, a, rn); ev += rec
        mx = max(mx, np.linalg.norm(a.v[spec.idx["fistL"]]))
    return s2, a, ev, mx
t0 = time.time(); s2, a1, ev1, mx = fight(); el = time.time() - t0
_, a2, ev2, _ = fight()
ok(np.array_equal(a1.p, a2.p) and ev1 == ev2, "determinism: same orders -> identical positions and events")
print(f"INFO 2 fighters, 2 s: {el/60*1000:.1f} ms/frame, peak fistL speed {mx:.1f} m/s")
for e in ev1[:8]: print("  ", e)
print("INFO enemy head hp:", round(float(a1.php[spec.idx['head'] + spec.n]), 1), "| result:", a1.result)
print(observe.observe(a1.p, s2, a1.palive, a1.cmd, 0, 2.0, ev1))

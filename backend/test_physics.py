"""Physics checks against hand-calculated answers. Uses hand-built mini specs (1-2 balls), no fighter needed."""
import numpy as np
from data import Spec
from config import *
import forces, constraints, contacts, sim

def mini(r, m, mats=None):
    N = len(r); r = np.array(r, float); m = np.array(m, float)
    e = np.zeros(0, int)
    return Spec(N=N, nf=1, r=r, m=m, w=1 / m, pmat=np.array(mats or [IRON] * N), kdrag=(0.5 * 1.2 * 0.5 * np.pi * r ** 2 / m)[:, None],
                fid=np.arange(N), ssI=np.array([0]) if N == 2 else e, ssJ=np.array([1]) if N == 2 else e, scS=e, scL=e,
                la=e, lb=e, lr=np.zeros(0), lmat=np.zeros(1, int))

def run(spec, p, v, frames, gravity=True, drag=True):
    """same sub-step loop as physics.step, minus muscles and links"""
    p, v = np.array(p, float), np.array(v, float)
    pal, lal = np.ones(spec.N, bool), np.ones(0, bool)
    dt = DT / SUBSTEPS; hist, ev = [], []
    for _ in range(frames):
        for _ in range(SUBSTEPS):
            vv = v.copy()
            if gravity: vv[:, 1] -= G * dt
            if drag: vv -= spec.kdrag * np.linalg.norm(vv, axis=1, keepdims=True) * vv * dt
            pp = p + vv * dt
            b = contacts.detect(pp, vv, spec, pal, lal)
            for _ in range(ITERS): pp = contacts.push_out(pp, b, spec)
            vv = (pp - p) / dt; p = pp
            v, tc = contacts.respond(vv, p, b, spec); ev += tc
        hist.append((p.copy(), v.copy()))
    return hist, ev

def chk(name, got, want, tol):
    ok = abs(got - want) <= tol * max(abs(want), 1e-9)
    print(f"{'PASS' if ok else 'FAIL'} {name}: got {got:.3f}, expected {want:.3f} (tol {tol*100:.0f}%)")

# 1 gravity: fall for 1 s
s = mini([.05], [1.0]); h, _ = run(s, [[0, 20, 0]], [[0, 0, 0]], 30)
chk("free fall in 1 s (m)", 20 - h[-1][0][0][1], 0.5 * G, 0.03)

# 2 bounce: drop 1 m, iron ball on ground, e = sqrt(.5*.4)
s = mini([.05], [1.0]); h, ev = run(s, [[0, 1.05, 0]], [[0, 0, 0]], 60, drag=False)
ys = [x[0][0][1] - .05 for x in h]; k = next(i for i, x in enumerate(h) if x[1][0][1] > 0); peak = max(ys[k:k + 15])   # first frame moving up again
e = np.sqrt(.5 * .4); chk("bounce height after 1 m drop (m)", peak, e ** 2 * 1.0, 0.15)

# 3 friction: slide 3 m/s on ground, mu = sqrt(.5*.6)
s = mini([.05], [1.0]); h, _ = run(s, [[0, .05, 0]], [[3, 0, 0]], 60, drag=False)
mu = np.sqrt(.5 * .6); dist = h[-1][0][0][0]; chk("slide distance (m)", dist, 9 / (2 * mu * G), 0.12)

# 4 wall: ball at wall height < 0.5 bounces back, ball above 0.5 passes over
for y, label in ((.3, "low ball (below 0.5 m)"), (1.0, "high ball (above wall)")):
    s = mini([.05], [1.0]); h, _ = run(s, [[4.5, y, 0]], [[3, 0, 0]], 40, gravity=False, drag=False)
    rho = max(x[0][0][0] for x in h); end = h[-1][0][0][0]
    print(f"{'PASS' if (rho < 5.0 if y < .5 else end > 5.1) else 'FAIL'} wall, {label}: max x {rho:.2f} m, end x {end:.2f} m")

# 5 head-on: 1 kg iron at 3 m/s hits 3 kg iron at rest, e = .5. expected v1'=-.375 v2'=1.125, absorbed 2.53 J
s = mini([.05, .05], [1.0, 3.0]); h, ev = run(s, [[0, 5, 0], [.3, 5, 0]], [[3, 0, 0], [0, 0, 0]], 15, gravity=False, drag=False)
v = h[-1][1]; P = (s.m[:, None] * v).sum(0)[0]
chk("collision: momentum after (kg m/s)", P, 3.0, 0.02)
chk("collision: ball 1 speed after", v[0][0], -0.375, 0.25)
chk("collision: ball 2 speed after", v[1][0], 1.125, 0.10)
chk("collision: absorbed energy reported (J)", sum(t["E"] for t in ev), 2.53, 0.15)

# 6 link strength: real fighter dropped from 1 m onto the ground, worst link stretch
sp, st, rn = sim.new_match(1); st.p[:, 1] += 1.0; worst = 0
for i in range(40):
    st, rn, _ = sim.tick(sp, st, rn)
    d = np.linalg.norm(st.p[sp.cb] - st.p[sp.ca], axis=1); worst = max(worst, float(np.max(np.abs(d - sp.cL) / sp.cL)))
print(f"INFO fighter dropped 1 m: worst link stretch {worst*100:.1f}% of its length, all finite: {np.isfinite(st.p).all()}")

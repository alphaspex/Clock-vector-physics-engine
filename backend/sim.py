"""SIM: the only file that wires the others together (the 'plug board').
new_match(nf, gap, offset_x)              OUT: (spec, state, runners)
give_orders(runners, f, steps)            IN: fighter + steps from moves.compile_do   OUT: runners (new orders override old ones)
tick(spec, state, runners)                OUT: (state, runners, records)   one frame = 1/30 s"""
import numpy as np
from config import DT
import body, physics, damage, rules, runner
from geometry import torso_frame


def new_match(nf=2, gap=3.0, offset_x=0.0):
    spec = body.build_spec(nf)
    return spec, body.initial_state(spec, gap, offset_x), [runner.new() for _ in range(nf)]


def give_orders(runners, f, steps):
    if not steps: return runners          # an answer with no moves changes nothing
    out = list(runners); out[f] = runner.override(runners[f], steps)
    return out


def tick(spec, state, runners):
    st, new_r = state.copy(), []
    for f in range(spec.nf):
        err = {mo["name"]: st.err[spec.mix[(f, mo["name"])]] for mo in spec.motors if mo["f"] == f}
        r2, cmds = runner.advance(runners[f], err)
        new_r.append(r2)
        for nm, (vals, pw) in cmds.items():
            i = spec.mix[(f, nm)]
            st.cmd[i] = [*vals, 0.0][:2]; st.power[i] = pw
    st, touches = physics.step(spec, st)
    st.frame += 1
    t = st.frame * DT
    frames = [torso_frame(st.p, spec, f) for f in range(spec.nf)]
    st.php, st.lhp, st.palive, st.lalive, recs = damage.apply(touches, st.php, st.lhp, st.palive, st.lalive, spec, frames, t)
    core_xz = [(st.p[spec.core[f]][0], st.p[spec.core[f]][2]) for f in range(spec.nf)]
    st.out_t, st.lost, st.result = rules.judge(st.palive, st.lalive, core_xz, st.out_t, t, spec)
    return st, new_r, recs

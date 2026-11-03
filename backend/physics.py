"""PHYSICS: one frame of the world (forces -> motion -> links -> contacts). No AI, no health, no rules.
step(spec, state)   IN: spec + state   OUT: (new state with p/v/err updated, touches[])"""
import numpy as np
from config import *
import forces, muscles, constraints, contacts


def step(spec, st, dt=DT):
    st = st.copy()
    groups = constraints.active_groups(spec, st.palive, st.lalive)
    substep_dt = dt / SUBSTEPS
    touches, err = [], st.err
    for _ in range(SUBSTEPS):
        v = forces.gravity_drag(st.v, spec, substep_dt)
        v, err = muscles.drive(st.p, v, st.cmd, st.power, st.palive, spec, substep_dt)   # muscles every sub-step: they also keep the legs stiff
        pp = st.p + v * substep_dt
        batches = contacts.detect(pp, v, spec, st.palive, st.lalive)
        for k in range(ITERS):   # sweep the links forward then backward so support travels up and down a limb
            pp = constraints.project(pp, spec, groups, reverse=(k % 2 == 1))
            pp = contacts.push_out(pp, batches, spec)
        v = (pp - st.p) / substep_dt
        st.p = pp
        st.v, tc = contacts.respond(v, st.p, batches, spec)
        touches += tc
    st.err = err
    return st, touches

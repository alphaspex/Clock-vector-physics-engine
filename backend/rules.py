"""RULES: who has lost, who won.
judge(palive, lalive, core_xz, out_t, t, spec)   IN: what is alive, core positions on the floor, ring timers, time
                                                 OUT: (out_t, lost[], result)   result: None | 'A' | 'B' | 'draw'"""
import numpy as np
from config import *


def judge(palive, lalive, core_xz, out_t, t, spec, dt=DT):
    out, lost = out_t.copy(), np.zeros(spec.nf, bool)
    for f in range(spec.nf):
        out[f] = out[f] + dt if np.hypot(*core_xz[f]) > ARENA_R else 0.0
        lost[f] = (not palive[spec.head[f]]) or (not lalive[spec.neck[f]]) or out[f] >= OUT_SECONDS
    result = None
    if spec.nf == 2:
        if lost.all(): result = "draw"
        elif lost[0]: result = "B"
        elif lost[1]: result = "A"
        elif t >= FIGHT_SECONDS: result = "draw"
    return out, lost, result

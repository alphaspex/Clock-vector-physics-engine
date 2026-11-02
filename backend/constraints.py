"""CONSTRAINTS: rigid links (the hold-force between connected balls).
active_groups(spec, palive, lalive)   IN: what is alive   OUT: list of index groups to solve
project(pp, spec, groups, reverse)    IN: predicted positions   OUT: positions after one link pass (reverse = walk the groups backwards)"""
import numpy as np
from geometry import rownorm


def active_groups(spec, palive, lalive):
    act = ((spec.co1 < 0) | lalive[spec.co1]) & ((spec.co2 < 0) | lalive[spec.co2])
    act &= (palive[spec.ca] & palive[spec.cb]) | (spec.co1 >= 0)
    return [g for g in (np.where(act & (spec.col == c))[0] for c in range(spec.col.max() + 1)) if len(g)]


def project(pp, spec, groups, reverse=False):
    for g in (groups[::-1] if reverse else groups):
        a, b = spec.ca[g], spec.cb[g]
        d = pp[b] - pp[a]
        dist = np.maximum(rownorm(d), 1e-9)
        wa, wb = spec.w[a], spec.w[b]
        s = ((dist - spec.cL[g]) / (dist * (wa + wb)))[:, None] * d
        pp[a] += wa[:, None] * s
        pp[b] -= wb[:, None] * s
    return pp

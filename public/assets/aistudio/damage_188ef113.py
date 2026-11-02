"""DAMAGE: turns touches into health loss. Damage = energy absorbed (J); iron hitting wood x1.5; iron never breaks.
apply(touches, php, lhp, palive, lalive, spec, frames, t)
   IN: touches from contacts + current health + torso frames
   OUT: (php, lhp, palive, lalive, records)   records = merged touch + 'destroyed' log rows"""
import numpy as np
from config import *


def _zone(n, fr):
    c = np.array([n @ fr[0], n @ fr[1], n @ fr[2]])
    a = int(np.argmax(np.abs(c)))
    return ("+" if c[a] > 0 else "-") + "xyz"[a]


def apply(touches, php, lhp, palive, lalive, spec, frames, t):
    php, lhp, palive, lalive = php.copy(), lhp.copy(), palive.copy(), lalive.copy()
    merged, out = {}, []
    for h in touches:
        ia, ib, lid, E = h["ia"], h["ib"], h["lid"], h["E"]
        nameA = spec.pname[ia]
        if h["kind"] == "dyn":
            nameB = spec.lname[lid] if lid >= 0 else spec.pname[ib]
            matB = spec.lmat[lid] if lid >= 0 else spec.pmat[ib]
            zB = ("start" if h["t"] < .33 else "mid" if h["t"] < .67 else "end") if lid >= 0 else _zone(h["n"], frames[spec.fid[ib]])
        else:
            nameB, matB, zB = h["kind"], None, "-"
        matA, dA, dB = spec.pmat[ia], 0.0, 0.0
        if matA == WOOD and palive[ia]:
            dA = E * (IRON_ON_WOOD if matB == IRON else 1.0) * (0.5 if matB == WOOD else 1.0)
            php[ia] -= dA
            if php[ia] <= 0: palive[ia] = False; out.append(dict(t=round(t, 3), event="destroyed", part=nameA))
        if matB == WOOD:
            dB = E * (IRON_ON_WOOD if matA == IRON else 1.0) * (0.5 if matA == WOOD else 1.0)
            if lid >= 0 and lalive[lid]:
                lhp[lid] -= dB
                if lhp[lid] <= 0: lalive[lid] = False; out.append(dict(t=round(t, 3), event="destroyed", part=nameB))
            elif lid < 0 and ib >= 0 and palive[ib]:
                php[ib] -= dB
                if php[ib] <= 0: palive[ib] = False; out.append(dict(t=round(t, 3), event="destroyed", part=nameB))
        e = merged.setdefault((nameA, nameB), dict(a=nameA, b=nameB, za=_zone(-h["n"], frames[spec.fid[ia]]), zb=zB,
                                                  E=0.0, dA=0.0, dB=0.0, pt=h["pt"]))
        e["E"] += E; e["dA"] += dA; e["dB"] += dB
    for e in merged.values():
        out.append(dict(t=round(t, 3), event="touch", a=e["a"], b=e["b"], za=e["za"], zb=e["zb"],
                        pt_cm=[int(round(x * 100)) for x in e["pt"]], energy_J=round(e["E"], 2),
                        dmg_a_J=round(e["dA"], 2), dmg_b_J=round(e["dB"], 2)))
    return php, lhp, palive, lalive, out

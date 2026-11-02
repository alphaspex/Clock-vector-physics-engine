"""CONTACTS: who touches whom, how they push apart, bounce and grip. Knows nothing about health.
detect(pp, v, spec, palive, lalive)       OUT: list of contact batches
push_out(pp, batches, spec)               OUT: positions with overlaps removed
respond(v, p, batches, spec)              OUT: (motion vectors after bounce+friction, touches[])
A touch = dict(kind, ia, ib, lid, t, n, E, pt):  E = energy absorbed (J), n = normal (from B toward A)."""
import numpy as np
from geometry import rownorm
from config import *


def _geom(b, pp, spec):
    A, ra = pp[b["ia"]], spec.r[b["ia"]]
    if b["kind"] == "dyn":
        P1, P2 = pp[b["ib1"]], pp[b["ib2"]]
        ab = P2 - P1; ll = (ab * ab).sum(1)
        t = np.where(ll > 1e-12, np.clip(((A - P1) * ab).sum(1) / np.maximum(ll, 1e-12), 0, 1), 0.0)
        d = A - (P1 + t[:, None] * ab)
        dist = np.maximum(rownorm(d), 1e-9)
        return b["rb"] + ra - dist, d / dist[:, None], t
    if b["kind"] == "ground":
        n = np.zeros_like(A); n[:, 1] = 1
        return ra - A[:, 1], n, np.zeros(len(A))
    rho = np.maximum(np.hypot(A[:, 0], A[:, 2]), 1e-9)
    rh = np.stack([A[:, 0] / rho, np.zeros(len(A)), A[:, 2] / rho], 1)
    inside = rho < ARENA_R
    pen = np.where(inside, rho + ra - (ARENA_R - WALL_T / 2), ARENA_R + WALL_T / 2 + ra - rho)
    pen = np.where(A[:, 1] - ra < WALL_H, pen, -1.0)
    return pen, np.where(inside[:, None], -rh, rh), np.zeros(len(A))


def detect(pp, v, spec, palive, lalive):
    r = spec.r
    d2 = ((pp[spec.ssI] - pp[spec.ssJ]) ** 2).sum(1)
    k = (d2 < (r[spec.ssI] + r[spec.ssJ] + .03) ** 2) & palive[spec.ssI] & palive[spec.ssJ]
    i, j = spec.ssI[k], spec.ssJ[k]
    P1, P2, A = pp[spec.la[spec.scL]], pp[spec.lb[spec.scL]], pp[spec.scS]
    ab = P2 - P1; ll = (ab * ab).sum(1)
    t = np.clip(((A - P1) * ab).sum(1) / np.maximum(ll, 1e-12), 0, 1)
    dist = rownorm(A - (P1 + t[:, None] * ab))
    k = (dist < r[spec.scS] + spec.lr[spec.scL] + .03) & palive[spec.scS] & lalive[spec.scL]
    s, l = spec.scS[k], spec.scL[k]
    out = [dict(kind="dyn", ia=np.concatenate([i, s]), ib1=np.concatenate([j, spec.la[l]]),
                ib2=np.concatenate([j, spec.lb[l]]), rb=np.concatenate([r[j], spec.lr[l]]),
                lid=np.concatenate([-np.ones(len(j), int), l]))]
    g = np.where((pp[:, 1] < r + .03) & palive)[0]
    out.append(dict(kind="ground", ia=g, lid=-np.ones(len(g), int)))
    rho = np.hypot(pp[:, 0], pp[:, 2])
    w_ = np.where((np.abs(rho - ARENA_R) < WALL_T / 2 + r + .03) & (pp[:, 1] - r < WALL_H + .03) & palive)[0]
    out.append(dict(kind="wall", ia=w_, lid=-np.ones(len(w_), int)))
    for b in out:
        if len(b["ia"]):
            pen, n, t = _geom(b, pp, spec)
            vB = (1 - t)[:, None] * v[b["ib1"]] + t[:, None] * v[b["ib2"]] if b["kind"] == "dyn" else 0
            b["vn"] = ((v[b["ia"]] - vB) * n).sum(1)
    return out


def push_out(pp, batches, spec):
    for b in batches:
        if not len(b["ia"]): continue
        pen, n, t = _geom(b, pp, spec)
        k = pen > 0
        if not k.any(): continue
        ia, pen, n, t = b["ia"][k], pen[k], n[k], t[k]
        wA = spec.w[ia]
        if b["kind"] == "dyn":
            i1, i2 = b["ib1"][k], b["ib2"][k]
            wB = (1 - t) ** 2 * spec.w[i1] + t ** 2 * spec.w[i2]
            lam = (pen / (wA + wB))[:, None] * n
            np.add.at(pp, ia, wA[:, None] * lam)
            np.add.at(pp, i1, -((1 - t) * spec.w[i1])[:, None] * lam)
            np.add.at(pp, i2, -(t * spec.w[i2])[:, None] * lam)
        else:
            np.add.at(pp, ia, pen[:, None] * n)
    return pp


def _push(v, spec, ia, i1, i2, t, d, j, wA, dyn):
    np.add.at(v, ia, (wA * j)[:, None] * d)
    if dyn:
        np.add.at(v, i1, -((1 - t) * spec.w[i1] * j)[:, None] * d)
        np.add.at(v, i2, -(t * spec.w[i2] * j)[:, None] * d)


def respond(v, p, batches, spec):
    v = v.copy(); touches = []
    for b in batches:
        if not len(b["ia"]): continue
        pen, n, t = _geom(b, p, spec)
        sel = np.where((pen > -1e-3) & (b["vn"] < 0))[0]
        if not len(sel): continue
        ia, n, t, vpre, lid = b["ia"][sel], n[sel], t[sel], b["vn"][sel], b["lid"][sel]
        dyn = b["kind"] == "dyn"
        i1 = b["ib1"][sel] if dyn else None; i2 = b["ib2"][sel] if dyn else None
        wA = spec.w[ia]
        wB = ((1 - t) ** 2 * spec.w[i1] + t ** 2 * spec.w[i2]) if dyn else np.zeros(len(ia))
        wS = wA + wB
        matA = spec.pmat[ia]
        if dyn:
            matB = np.where(lid >= 0, spec.lmat[np.maximum(lid, 0)], spec.pmat[i1])
            e = np.sqrt(np.array(REST)[matA] * np.array(REST)[matB]); mu = np.sqrt(np.array(MU)[matA] * np.array(MU)[matB])
        else:
            gm = GROUND if b["kind"] == "ground" else WALLM
            e = np.sqrt(np.array(REST)[matA] * gm[1]); mu = np.sqrt(np.array(MU)[matA] * gm[0])
        vB = ((1 - t)[:, None] * v[i1] + t[:, None] * v[i2]) if dyn else 0
        vn = ((v[ia] - vB) * n).sum(1)
        tgt = np.where(vpre < -BOUNCE_MIN_SPEED, -e * vpre, 0.0)
        _push(v, spec, ia, i1, i2, t, n, np.maximum(tgt - vn, 0) / wS, wA, dyn)
        vB = ((1 - t)[:, None] * v[i1] + t[:, None] * v[i2]) if dyn else 0
        vr = v[ia] - vB
        vt = vr - ((vr * n).sum(1))[:, None] * n
        vtn = np.maximum(rownorm(vt), 1e-9)
        jt = np.minimum(vtn / wS, mu * (np.maximum(tgt, vn) - vpre) / wS)
        _push(v, spec, ia, i1, i2, t, -vt / vtn[:, None], jt, wA, dyn)
        E = 0.5 / wS * vpre ** 2 * (1 - e ** 2)
        for q in np.where((vpre < -DAMAGE_MIN_SPEED) & (E > 0.005))[0]:
            touches.append(dict(kind=b["kind"], ia=int(ia[q]), ib=int(i1[q]) if dyn and lid[q] < 0 else -1,
                                lid=int(lid[q]), t=float(t[q]), n=n[q].copy(), E=float(E[q]),
                                pt=p[ia[q]] - n[q] * spec.r[ia[q]]))
    return v, touches

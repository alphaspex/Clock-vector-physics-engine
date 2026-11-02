"""BODY: builds the fighter bodies.
build_spec(nf)                     IN: number of fighters   OUT: Spec (parts, links, motors, tables)
initial_state(spec, gap, offset_x) IN: spec, distance      OUT: State at rest
"""
import numpy as np
from config import *
from data import Spec, State


def _template():
    P = [("core", 0, .68, 0, .092, IRON, 23.0), ("head", 0, .935, 0, .035, WOOD, .11)]
    for s, x in (("L", 1), ("R", -1)):
        P += [("sh" + s, .17 * x, .74, 0, .026, IRON, .52), ("hip" + s, .10 * x, .52, 0, .029, IRON, .72),
              ("el" + s, .17 * x, .52, 0, .024, IRON, .41), ("fist" + s, .17 * x, .30, 0, .022, IRON, .31),
              ("kn" + s, .10 * x, .28, 0, .026, IRON, .52), ("an" + s, .10 * x, .055, 0, .020, IRON, .23),
              ("heelA" + s, .10 * x + .0125, .01, -.02, .010, IRON, .035), ("heelB" + s, .10 * x - .0125, .01, -.02, .010, IRON, .035),
              ("toeA" + s, .10 * x + .0125, .01, .02, .010, IRON, .035), ("toeB" + s, .10 * x - .0125, .01, .02, .010, IRON, .035)]
    return P


def _links():
    Lk = [("neck", "core", "head", .007, WOOD)]
    for s in "LR":
        Lk += [("shLink" + s, "core", "sh" + s, .009, WOOD), ("hipLink" + s, "core", "hip" + s, .014, WOOD),
               ("upperArm" + s, "sh" + s, "el" + s, .009, WOOD), ("foreArm" + s, "el" + s, "fist" + s, .009, WOOD),
               ("thigh" + s, "hip" + s, "kn" + s, .014, WOOD), ("shin" + s, "kn" + s, "an" + s, .012, WOOD),
               ("ankJ1" + s, "an" + s, "heelA" + s, .010, IRON), ("ankJ2" + s, "an" + s, "heelB" + s, .010, IRON),
               ("ankJ3" + s, "an" + s, "toeA" + s, .010, IRON), ("ankJ4" + s, "an" + s, "toeB" + s, .010, IRON),
               ("footHeel" + s, "heelA" + s, "heelB" + s, .010, IRON), ("footToe" + s, "toeA" + s, "toeB" + s, .010, IRON),
               ("footSideA" + s, "heelA" + s, "toeA" + s, .010, IRON), ("footSideB" + s, "heelB" + s, "toeB" + s, .010, IRON)]
    return Lk


_ATTACH = {"head": "neck", "shL": "shLinkL", "shR": "shLinkR", "hipL": "hipLinkL", "hipR": "hipLinkR"}


def _motor_table():
    T = {}
    for s, sg in (("L", 1), ("R", -1)):
        T[s + "_shoulder"] = dict(kind="ball", pv="sh" + s, ch=["el" + s], dsc=["el" + s, "fist" + s], s=sg,
                                  lim=((-180, 180), (0, 180)), tau=25)
        T[s + "_elbow"] = dict(kind="hinge", pv="el" + s, pa="sh" + s, ch=["fist" + s], dsc=["fist" + s], s=-1,
                               lim=((0, 150),), tau=15)
        T[s + "_hip"] = dict(kind="ball", pv="hip" + s, ch=["kn" + s], dsc=["kn" + s, "an" + s, "heelA" + s, "heelB" + s, "toeA" + s, "toeB" + s],
                             s=sg, lim=((-20, 120), (-20, 45)), tau=90)
        T[s + "_knee"] = dict(kind="hinge", pv="kn" + s, pa="hip" + s, ch=["an" + s],
                              dsc=["an" + s, "heelA" + s, "heelB" + s, "toeA" + s, "toeB" + s], s=1, lim=((0, 140),), tau=90)
        T[s + "_ankle"] = dict(kind="ankle", pv="an" + s, pa="kn" + s, ch=["heelA" + s, "heelB" + s, "toeA" + s, "toeB" + s], dsc=None, s=1,
                               lim=((-40, 20),), tau=40)
    return T


def build_spec(nf=2):
    T, Lk = _template(), _links()
    n, nl = len(T), len(Lk)
    N, NL = n * nf, nl * nf
    names = [t[0] for t in T]
    idx = {nm: i for i, nm in enumerate(names)}
    lidx = {l[0]: i for i, l in enumerate(Lk)}
    base = np.array([t[1:4] for t in T], float)
    r = np.tile([t[4] for t in T], nf)
    pmat = np.tile([t[5] for t in T], nf).astype(int)
    m = np.tile([t[6] for t in T], nf).astype(float)
    fid = np.repeat(np.arange(nf), n)
    pname = [f"{'AB'[f]}.{nm}" for f in range(nf) for nm in names]
    la, lb = np.zeros(NL, int), np.zeros(NL, int)
    lr, lmat, llen, lname = np.zeros(NL), np.zeros(NL, int), np.zeros(NL), []
    for f in range(nf):
        for k, (nm, a, b, rad, mat) in enumerate(Lk):
            g = f * nl + k
            la[g], lb[g] = f * n + idx[a], f * n + idx[b]
            lr[g], lmat[g] = rad, mat
            llen[g] = np.linalg.norm(base[idx[b]] - base[idx[a]])
            lname.append(f"{'AB'[f]}.{nm}")
            if mat == WOOD:  # wood link mass rides on its two end balls
                ml = DENSITY[WOOD] * np.pi * rad ** 2 * llen[g]
                m[la[g]] += ml / 2; m[lb[g]] += ml / 2
    lhp0, php0 = np.full(NL, np.inf), np.full(N, np.inf)
    for g in range(NL):
        if lmat[g] == WOOD:
            lhp0[g] = HEAD_NECK_J if lname[g].endswith("neck") else WOOD_J_PER_CM3 * np.pi * (lr[g] * 100) ** 2 * (llen[g] * 100)
    for f in range(nf):
        php0[f * n + idx["head"]] = HEAD_NECK_J
    # rigid-link constraints [a, b, length, owner1, owner2]; torso cluster keeps its shape until its link breaks
    C = [[la[g], lb[g], llen[g], g, -1] for g in range(NL)]
    cl = ["core", "head", "shL", "shR", "hipL", "hipR"]
    linked = {(l[1], l[2]) for l in Lk}
    for f in range(nf):
        for i in range(len(cl)):
            for j in range(i + 1, len(cl)):
                a, b = cl[i], cl[j]
                if a == "core" or (a, b) in linked: continue
                C.append([f * n + idx[a], f * n + idx[b], np.linalg.norm(base[idx[a]] - base[idx[b]]),
                          f * nl + lidx[_ATTACH[a]], f * nl + lidx[_ATTACH[b]]])
    for f in range(nf):
        for s_ in "LR":
            for a, b in (("heelA", "toeB"), ("heelB", "toeA")):
                ia_, ib_ = f * n + idx[a + s_], f * n + idx[b + s_]
                C.append([ia_, ib_, np.linalg.norm(base[idx[a + s_]] - base[idx[b + s_]]), -1, -1])
    C = np.array(C, float)
    ca, cb = C[:, 0].astype(int), C[:, 1].astype(int)
    co1, co2 = C[:, 3].astype(int), C[:, 4].astype(int)
    used, col = [], np.zeros(len(ca), int)   # color constraints so each group can be solved in one numpy call
    for k in range(len(ca)):
        c = 0
        while c < len(used) and (ca[k] in used[c] or cb[k] in used[c]): c += 1
        if c == len(used): used.append(set())
        used[c] |= {ca[k], cb[k]}; col[k] = c
    D = np.full((N, N), 99)
    for i in range(N): D[i, i] = 0
    for a, b in zip(ca, cb): D[a, b] = D[b, a] = 1
    for k in range(N): D = np.minimum(D, D[:, k:k + 1] + D[k:k + 1, :])
    I, J = np.triu_indices(N, 1)
    ok = (fid[I] != fid[J]) | (D[I, J] > 2)
    S, Lg = np.meshgrid(np.arange(N), np.arange(NL), indexing="ij")
    S, Lg = S.ravel(), Lg.ravel()
    ok2 = (fid[S] != fid[la[Lg]]) | (np.minimum(D[S, la[Lg]], D[S, lb[Lg]]) > 1)
    motors, mix, info = [], {}, {}
    for f in range(nf):
        for nm, d in _motor_table().items():
            pv = f * n + idx[d["pv"]]
            ch = np.array([f * n + idx[c] for c in d["ch"]])
            dsc = ch if d["dsc"] is None else [f * n + idx[c] for c in d["dsc"]]
            mix[(f, nm)] = len(motors)
            motors.append(dict(f=f, name=nm, kind=d["kind"], pv=pv, ch=ch, s=d["s"], lim=d["lim"], tau=d["tau"],
                               pa=(f * n + idx[d["pa"]]) if "pa" in d else -1,
                               L=np.linalg.norm(base[ch - f * n] - base[pv - f * n], axis=1),
                               meff=m[ch] if d["kind"] == "ankle" else np.full(len(ch), m[dsc].sum())))
            info[nm] = dict(n=len(d["lim"]), lim=[list(x) for x in d["lim"]])
    return Spec(nf=nf, n=n, nl=nl, N=N, NL=NL, names=names, idx=idx, lidx=lidx, pname=pname, lname=lname, fid=fid,
                r=r, pmat=pmat, m=m, w=1.0 / m, kdrag=(0.5 * 1.2 * 0.5 * np.pi * r ** 2 / m)[:, None],
                la=la, lb=lb, lr=lr, lmat=lmat, llen=llen, lhp0=lhp0, php0=php0, base=base,
                ca=ca, cb=cb, cL=C[:, 2], co1=co1, co2=co2, col=col, D=D, ssI=I[ok], ssJ=J[ok],
                scS=S[ok2], scL=Lg[ok2], motors=motors, mix=mix, motor_info=info,
                head=np.array([f * n + idx["head"] for f in range(nf)]),
                core=np.array([f * n + idx["core"] for f in range(nf)]),
                neck=np.array([f * nl + lidx["neck"] for f in range(nf)]))


def initial_state(spec, gap=3.0, offset_x=0.0):
    p = np.zeros((spec.N, 3))
    for f in range(spec.nf):
        q = spec.base.copy()
        if spec.nf == 2:
            if f == 1:
                q[:, [0, 2]] *= -1; q[:, 2] += gap / 2; q[:, 0] += offset_x
            else:
                q[:, 2] -= gap / 2
        p[f * spec.n:(f + 1) * spec.n] = q
    M = len(spec.motors)
    return State(p=p, v=np.zeros_like(p), php=spec.php0.copy(), lhp=spec.lhp0.copy(),
                 palive=np.ones(spec.N, bool), lalive=np.ones(spec.NL, bool), cmd=np.zeros((M, 2)),
                 power=np.full(M, HOLD_POWER), err=np.zeros(M), frame=0, out_t=np.zeros(spec.nf),
                 lost=np.zeros(spec.nf, bool), result=None)

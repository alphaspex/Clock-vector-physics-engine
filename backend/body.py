"""BODY: builds the official fighter bodies.
build_spec(nf)                     IN: number of fighters   OUT: Spec (parts, links, motors, tables)
initial_state(spec, gap, offset_x) IN: spec, distance      OUT: State at rest
"""
import numpy as np
from config import *
from data import Spec, State


def _template():
    # 8 physical balls: CHEST, HEAD, and two arms (shoulder, elbow, fist)
    # Chest is the central ball. Neck is a connecting link (not a ball).
    P = [
        ("chest", 0.0, 0.35, 0.0, 0.092, IRON, 4.0),
        ("head", 0.0, 0.605, 0.0, 0.035, WOOD, 0.11),
    ]
    # Right arm (+X) and Left arm (-X)
    for s, x in (("R", 1), ("L", -1)):
        P += [
            ("sh" + s, 0.17 * x, 0.41, 0.0, 0.026, IRON, 0.52),
            ("el" + s, 0.17 * x, 0.19, 0.0, 0.024, IRON, 0.41),
            ("fist" + s, 0.17 * x, 0.04, 0.0, 0.022, IRON, 0.31),
        ]
    return P


def _links():
    # Neck connecting link between chest and head
    Lk = [("neck", "chest", "head", 0.007, WOOD)]
    # 6 individually identifiable named arm joints (internal connection forces)
    for s in ("R", "L"):
        side_name = "RIGHT" if s == "R" else "LEFT"
        Lk += [
            (f"NECK_{side_name}_JOINT", "chest", "sh" + s, 0.009, WOOD),
            (f"SHOULDER_{side_name}_JOINT", "sh" + s, "el" + s, 0.009, WOOD),
            (f"ELBOW_{side_name}_JOINT", "el" + s, "fist" + s, 0.009, WOOD),
        ]
    return Lk


_ATTACH = {
    "head": "neck",
    "shR": "NECK_RIGHT_JOINT",
    "shL": "NECK_LEFT_JOINT",
}


def _motor_table():
    T = {}
    for s, sg in (("R", 1), ("L", -1)):
        side_name = "RIGHT" if s == "R" else "LEFT"
        T[s + "_shoulder"] = dict(
            kind="ball", pv="sh" + s, ch=["el" + s], dsc=["el" + s, "fist" + s], s=sg,
            lim=((-180, 180), (0, 180)), tau=25,
            joint=f"SHOULDER_{side_name}_JOINT",
        )
        T[s + "_elbow"] = dict(
            kind="hinge", pv="el" + s, pa="sh" + s, ch=["fist" + s], dsc=["fist" + s], s=-1,
            lim=((0, 150),), tau=15,
            joint=f"ELBOW_{side_name}_JOINT",
        )
    return T


def build_spec(nf=2):
    T, Lk = _template(), _links()
    n, nl = len(T), len(Lk)
    N, NL = n * nf, nl * nf
    names = [t[0] for t in T]
    idx = {nm: i for i, nm in enumerate(names)}
    # Aliases for robust referencing
    idx["core"] = idx["chest"]
    idx["CHEST"] = idx["chest"]
    idx["HEAD"] = idx["head"]
    for s in ("R", "L"):
        side_name = "RIGHT" if s == "R" else "LEFT"
        idx[f"{side_name}_SHOULDER"] = idx["sh" + s]
        idx[f"{side_name}_ELBOW"] = idx["el" + s]
        idx[f"{side_name}_FIST"] = idx["fist" + s]

    lidx = {l[0]: i for i, l in enumerate(Lk)}
    lidx["NECK"] = lidx["neck"]
    for s in ("R", "L"):
        side_name = "RIGHT" if s == "R" else "LEFT"
        lidx[f"shLink{s}"] = lidx[f"NECK_{side_name}_JOINT"]
        lidx[f"upperArm{s}"] = lidx[f"SHOULDER_{side_name}_JOINT"]
        lidx[f"foreArm{s}"] = lidx[f"ELBOW_{side_name}_JOINT"]

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
            if mat == WOOD:
                ml = DENSITY[WOOD] * np.pi * rad ** 2 * llen[g]
                m[la[g]] += ml / 2
                m[lb[g]] += ml / 2

    lhp0, php0 = np.full(NL, np.inf), np.full(N, np.inf)
    for g in range(NL):
        if lmat[g] == WOOD:
            lhp0[g] = HEAD_NECK_J if lname[g].endswith("neck") else WOOD_J_PER_CM3 * np.pi * (lr[g] * 100) ** 2 * (llen[g] * 100)
    for f in range(nf):
        php0[f * n + idx["head"]] = HEAD_NECK_J

    # rigid-link constraints [a, b, length, owner1, owner2]
    # Link constraints
    C = [[la[g], lb[g], llen[g], g, -1] for g in range(NL)]
    cl = ["chest", "head", "shR", "shL"]
    linked = {(l[1], l[2]) for l in Lk}
    for f in range(nf):
        for i in range(len(cl)):
            for j in range(i + 1, len(cl)):
                a, b = cl[i], cl[j]
                if a == "chest" or (a, b) in linked:
                    continue
                oa = f * nl + lidx[_ATTACH[a]] if a in _ATTACH else -1
                ob = f * nl + lidx[_ATTACH[b]] if b in _ATTACH else -1
                C.append([f * n + idx[a], f * n + idx[b], np.linalg.norm(base[idx[a]] - base[idx[b]]), oa, ob])

    C = np.array(C, float)
    ca, cb = C[:, 0].astype(int), C[:, 1].astype(int)
    co1, co2 = C[:, 3].astype(int), C[:, 4].astype(int)
    used, col = [], np.zeros(len(ca), int)
    for k in range(len(ca)):
        c = 0
        while c < len(used) and (ca[k] in used[c] or cb[k] in used[c]):
            c += 1
        if c == len(used):
            used.append(set())
        used[c] |= {ca[k], cb[k]}
        col[k] = c

    D = np.full((N, N), 99)
    for i in range(N):
        D[i, i] = 0
    for a, b in zip(ca, cb):
        D[a, b] = D[b, a] = 1
    for k in range(N):
        D = np.minimum(D, D[:, k:k + 1] + D[k:k + 1, :])

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
            lid = f * nl + lidx[d["joint"]] if "joint" in d else -1
            motors.append(dict(
                f=f, name=nm, kind=d["kind"], pv=pv, ch=ch, s=d["s"], lim=d["lim"], tau=d["tau"],
                pa=(f * n + idx[d["pa"]]) if "pa" in d else -1,
                lid=lid,
                L=np.linalg.norm(base[ch - f * n] - base[pv - f * n], axis=1),
                meff=np.full(len(ch), m[dsc].sum()),
            ))
            info[nm] = dict(n=len(d["lim"]), lim=[list(x) for x in d["lim"]])

    chest_arr = np.array([f * n + idx["chest"] for f in range(nf)])
    return Spec(
        nf=nf, n=n, nl=nl, N=N, NL=NL, names=names, idx=idx, lidx=lidx, pname=pname, lname=lname, fid=fid,
        r=r, pmat=pmat, m=m, w=1.0 / m, kdrag=(0.5 * 1.2 * 0.5 * np.pi * r ** 2 / m)[:, None],
        la=la, lb=lb, lr=lr, lmat=lmat, llen=llen, lhp0=lhp0, php0=php0, base=base,
        ca=ca, cb=cb, cL=C[:, 2], co1=co1, co2=co2, col=col, D=D, ssI=I[ok], ssJ=J[ok],
        scS=S[ok2], scL=Lg[ok2], motors=motors, mix=mix, motor_info=info,
        chest=chest_arr,
        core=chest_arr,
        head=np.array([f * n + idx["head"] for f in range(nf)]),
        neck=np.array([f * nl + lidx["neck"] for f in range(nf)]),
    )


def initial_state(spec, gap=3.0, offset_x=0.0):
    p = np.zeros((spec.N, 3))
    for f in range(spec.nf):
        q = spec.base.copy()
        if spec.nf == 2:
            if f == 1:
                q[:, [0, 2]] *= -1
                q[:, 2] += gap / 2
                q[:, 0] += offset_x
            else:
                q[:, 2] -= gap / 2
        p[f * spec.n:(f + 1) * spec.n] = q
    M = len(spec.motors)
    return State(
        p=p, v=np.zeros_like(p), php=spec.php0.copy(), lhp=spec.lhp0.copy(),
        palive=np.ones(spec.N, bool), lalive=np.ones(spec.NL, bool), cmd=np.zeros((M, 2)),
        power=np.full(M, HOLD_POWER), err=np.zeros(M), frame=0, out_t=np.zeros(spec.nf),
        lost=np.zeros(spec.nf, bool), result=None,
    )

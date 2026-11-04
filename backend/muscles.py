"""MUSCLES: motors as torque-limited pulls toward a target pose.
drive(p, v, cmd, power, palive, spec, dt)   IN: positions, motion, motor commands
                                            OUT: (new motion vectors, per-motor error)"""
import numpy as np
from config import MUSCLE_W, MUSCLE_Z, MAX_JOINT_SPEED
from geometry import rownorm, unit, rot, torso_frame


def _targets(mo, cmd, p, fr):
    if len(mo["ch"]) == 0:
        return np.empty((0, 3))
    right, up, fwd = fr
    pv = p[mo["pv"]]
    if mo["kind"] in ("ball", "spin"):     # cmd = (pitch forward deg, out deg); arm hangs down at (0,0)
        a, b = np.radians(cmd)
        d = mo["s"] * np.sin(b) * right - np.cos(b) * np.cos(a) * up + np.cos(b) * np.sin(a) * fwd
        return np.array([pv + mo["L"][0] * d])
    u = unit(pv - p[mo["pa"]])
    if mo["kind"] == "hinge":    # cmd[0] = bend deg
        return np.array([pv + mo["L"][0] * rot(u, right, mo["s"] * np.radians(cmd[0]))])
    return np.array([pv])


def drive(p, v, cmd, power, palive, spec, dt, lalive=None):
    v = v.copy()
    err = np.zeros(len(spec.motors))
    frames = [torso_frame(p, spec, f) for f in range(spec.nf)]
    for i, mo in enumerate(spec.motors):
        if not palive[mo["pv"]]:
            continue
        if lalive is not None and "lid" in mo and mo["lid"] >= 0 and not lalive[mo["lid"]]:
            continue
        ch, pv = mo["ch"], mo["pv"]
        if len(ch) == 0:
            err[i] = 0.0
            continue
        e = _targets(mo, cmd[i], p, frames[mo["f"]]) - p[ch]
        err[i] = float(np.max(rownorm(e) / mo["L"]))
        F = (MUSCLE_W ** 2 * e - 2 * MUSCLE_Z * MUSCLE_W * (v[ch] - v[pv])) * mo["meff"][:, None]
        cap = mo["tau"] * power[i] / mo["L"] / len(ch)
        F *= np.minimum(1.0, cap / np.maximum(rownorm(F), 1e-9))[:, None]
        v[ch] += F / spec.m[ch][:, None] * dt
        v[pv] -= F.sum(0) / spec.m[pv] * dt
        vr = v[ch] - v[pv]
        v[ch] = v[pv] + vr * np.minimum(1.0, MAX_JOINT_SPEED * mo["L"] / np.maximum(rownorm(vr), 1e-9))[:, None]
    return v, err

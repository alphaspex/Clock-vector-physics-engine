"""MUSCLES: motors as torque-limited pulls toward a target pose.
drive(p, v, cmd, power, palive, spec, dt)   IN: positions, motion, motor commands
                                            OUT: (new motion vectors, per-motor error)"""
import numpy as np
from config import MUSCLE_W, MUSCLE_Z, MAX_JOINT_SPEED
from geometry import rownorm, unit, rot, torso_frame


def _targets(mo, cmd, p, fr):
    side, up, fwd = fr
    pv = p[mo["pv"]]
    if mo["kind"] == "ball":     # cmd = (pitch forward deg, out deg); arm hangs down at (0,0)
        a, b = np.radians(cmd)
        d = mo["s"] * np.sin(b) * side - np.cos(b) * np.cos(a) * up + np.cos(b) * np.sin(a) * fwd
        return np.array([pv + mo["L"][0] * d])
    u = unit(pv - p[mo["pa"]])
    if mo["kind"] == "hinge":    # cmd[0] = bend deg
        return np.array([pv + mo["L"][0] * rot(u, side, mo["s"] * np.radians(cmd[0]))])
    f = unit(np.cross(u, side)); psi = np.radians(cmd[0])   # ankle: + = toes up
    a = .045 * (u * np.cos(psi) + f * np.sin(psi)); b = .02 * (f * np.cos(psi) - u * np.sin(psi)); c = .0125 * side
    return np.array([pv + a - b + c, pv + a - b - c, pv + a + b + c, pv + a + b - c])   # heelA, heelB, toeA, toeB


def drive(p, v, cmd, power, palive, spec, dt):
    v = v.copy()
    err = np.zeros(len(spec.motors))
    frames = [torso_frame(p, spec, f) for f in range(spec.nf)]
    for i, mo in enumerate(spec.motors):
        if not palive[mo["pv"]]:
            continue
        ch, pv = mo["ch"], mo["pv"]
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

"""OBSERVE: the text an AI sees.  Never shows health.
observe(p, spec, palive, cmd, f, t, events, since, enemy)
   IN: positions, spec, who is alive, motor commands, fighter id, time, event list, only events after `since`
   OUT: short text"""
import numpy as np
from config import ARENA_R
from geometry import torso_frame

_PTS = ["head", "fistL", "fistR", "elL", "elR", "knL", "knR", "anL", "anR"]


def observe(p, spec, palive, cmd, f, t, events, since=0.0, enemy=True):
    n, ix = spec.n, spec.idx
    side, up, fwd = torso_frame(p, spec, f)
    core = p[spec.core[f]]

    def rel(i):
        d = p[i] - core
        return [int(round(d @ fwd * 100)), int(round(d @ side * 100)), int(round(d @ up * 100))]

    yaw = int(round(np.degrees(np.arctan2(fwd[0], fwd[2]))))
    L = [f"t={t:.1f}s you: x={core[0]:.2f} z={core[2]:.2f} yaw={yaw} core_h={core[1] * 100:.0f}cm "
         f"upright={up[1]:.2f} ring_margin={ARENA_R - np.hypot(core[0], core[2]):.1f}m",
         "cm from your core as [fwd,left,up]",
         "you: " + " ".join(f"{k}={rel(f * n + ix[k])}" for k in _PTS if palive[f * n + ix[k]]),
         "motors: " + " ".join(f"{mo['name']}={[int(x) for x in cmd[i]][:len(mo['lim'])]}"
                               for i, mo in enumerate(spec.motors) if mo["f"] == f)]
    if enemy and spec.nf == 2:
        e = 1 - f
        d = p[spec.core[e]] - core
        br = int(round(np.degrees(np.arctan2(d @ side, d @ fwd))))
        L.append(f"enemy: dist={np.hypot(d[0], d[2]):.2f}m bearing={br}deg(+left) core_h={p[spec.core[e]][1] * 100:.0f}cm")
        L.append("enemy: " + " ".join(f"{k}={rel(e * n + ix[k])}" for k in _PTS if palive[e * n + ix[k]]))
    me = "AB"[f]
    tl = [x for x in events if x["event"] == "touch" and x["t"] > since and x["energy_J"] > 0.2
          and (x["a"][0] == me or x["b"][0] == me)]
    if tl:
        L.append("touches: " + "; ".join(f"t={x['t']} {x['a']}.{x['za']}->{x['b']}.{x['zb']} {x['energy_J']}J" for x in tl[-6:]))
    return "\n".join(L)

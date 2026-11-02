"""DATA: the two shapes of data that travel between files. No logic except copy()."""
from dataclasses import dataclass
import numpy as np


class Spec:
    """Read-only description of the bodies in a match. Built once by body.build_spec."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


@dataclass
class State:
    """Everything that changes during a match. Files take a State and return a new one."""
    p: np.ndarray        # (N,3) particle positions
    v: np.ndarray        # (N,3) motion vectors
    php: np.ndarray      # (N,) health of wooden balls (joules, inf = indestructible)
    lhp: np.ndarray      # (NL,) health of links
    palive: np.ndarray
    lalive: np.ndarray
    cmd: np.ndarray      # (M,2) motor target angles (deg)
    power: np.ndarray    # (M,) 0..1
    err: np.ndarray      # (M,) distance to target, fraction of limb length
    frame: int
    out_t: np.ndarray    # seconds each fighter's core has been outside the ring
    lost: np.ndarray
    result: object       # None | 'A' | 'B' | 'draw'

    def copy(self):
        return State(self.p.copy(), self.v.copy(), self.php.copy(), self.lhp.copy(), self.palive.copy(),
                     self.lalive.copy(), self.cmd.copy(), self.power.copy(), self.err.copy(), self.frame,
                     self.out_t.copy(), self.lost.copy(), self.result)

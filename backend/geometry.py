"""GEOMETRY: small math helpers.  IN: vectors/arrays.  OUT: vectors/arrays."""
import numpy as np


def rownorm(a, keepdims=False):
    """Length of each row, faster than np.linalg.norm."""
    r = np.sqrt(np.einsum("ij,ij->i", a, a))
    return r[:, None] if keepdims else r


def unit(v):
    return v / max(np.linalg.norm(v), 1e-9)


def rot(v, k, a):
    """Rotate vector v around unit axis k by angle a (radians)."""
    return v * np.cos(a) + np.cross(k, v) * np.sin(a) + k * np.dot(k, v) * (1 - np.cos(a))


def torso_frame(p, spec, f):
    """IN: positions, spec, fighter id.  OUT: (side, up, fwd) unit vectors. side points to the fighter's LEFT."""
    i, ix = f * spec.n, spec.idx
    side = unit(p[i + ix["shL"]] - p[i + ix["shR"]])
    up0 = unit((p[i + ix["shL"]] + p[i + ix["shR"]]) / 2 - (p[i + ix["hipL"]] + p[i + ix["hipR"]]) / 2)
    fwd = unit(np.cross(side, up0))
    return side, np.cross(fwd, side), fwd

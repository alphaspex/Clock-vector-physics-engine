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
    """IN: positions, spec, fighter id.
    OUT: (right, up, fwd) orthonormal unit vectors.
    X = RIGHT, Y = UP, Z = FRONT.
    Calculates body frame using:
      - The neck link direction from the chest toward upper attachment / head.
      - The left-to-right shoulder direction.
    """
    i = f * spec.n
    ix = spec.idx
    chest_idx = ix.get("chest", ix.get("core", 0))
    head_idx = ix.get("head", 1)
    shR_idx = ix.get("shR", ix.get("RIGHT_SHOULDER", 2))
    shL_idx = ix.get("shL", ix.get("LEFT_SHOULDER", 5))

    p_chest = p[i + chest_idx]
    p_head = p[i + head_idx]
    p_shR = p[i + shR_idx]
    p_shL = p[i + shL_idx]

    neck_vec = p_head - p_chest
    neck_dir = unit(neck_vec) if np.linalg.norm(neck_vec) > 1e-6 else np.array([0.0, 1.0, 0.0])

    sh_vec = p_shR - p_shL
    sh_dir = unit(sh_vec) if np.linalg.norm(sh_vec) > 1e-6 else np.array([1.0, 0.0, 0.0])

    # Left-to-right shoulder direction orthogonalized against neck_dir -> RIGHT
    right_raw = sh_dir - np.dot(sh_dir, neck_dir) * neck_dir
    right = unit(right_raw) if np.linalg.norm(right_raw) > 1e-6 else sh_dir

    # Z = FRONT = RIGHT x UP (where UP is neck_dir)
    fwd = unit(np.cross(right, neck_dir))

    # Y = UP = FRONT x RIGHT (guarantees perfect orthonormal frame)
    up = unit(np.cross(fwd, right))

    return right, up, fwd

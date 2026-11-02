"""FORCES: always-on forces.
gravity_drag(v, spec, dt)   IN: motion vectors   OUT: motion vectors after gravity + air drag"""
import numpy as np
from geometry import rownorm
from config import G


def gravity_drag(v, spec, dt):
    v = v.copy()
    v[:, 1] -= G * dt
    v -= spec.kdrag * rownorm(v, True) * v * dt
    return v

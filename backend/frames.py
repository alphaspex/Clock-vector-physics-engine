"""FRAMES: turns a match into plain messages for any viewer. The viewer only draws what these say.
describe(spec)         OUT: dict(points, shapes[balls and capsules by point index], world, fps)   (sent once)
snapshot(spec, state)  OUT: dict(t, p=[x,y,z,...], x=[dead shape ids])                           (sent per frame)"""
from config import ARENA_R, WALL_H, WALL_T, FPS, DT


def describe(spec):
    shapes = [dict(k="ball", p=i, r=round(float(spec.r[i]), 4), n=spec.pname[i]) for i in range(spec.N)]
    shapes += [dict(k="cap", a=int(spec.la[g]), b=int(spec.lb[g]), r=round(float(spec.lr[g]), 4), n=spec.lname[g]) for g in range(spec.NL)]
    return dict(points=spec.N, shapes=shapes, world=dict(ring=ARENA_R, wall_h=WALL_H, wall_t=WALL_T), fps=FPS, nf=spec.nf)


def snapshot(spec, st):
    dead = [i for i in range(spec.N) if not st.palive[i]] + [spec.N + g for g in range(spec.NL) if not st.lalive[g]]
    return dict(t=round(st.frame * DT, 3), p=[round(float(x), 3) for x in st.p.ravel()], x=dead)

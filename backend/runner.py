"""RUNNER: plays a list of steps one after another for ONE fighter. Knows nothing about bodies.
A step is finished when every motor in it reached its target (err < REACHED). No timeout:
a stuck chain just stays stuck until the next AI call overrides it.
new()                      OUT: empty runner
override(runner, steps)    IN: new steps   OUT: runner that has dropped everything old and will play only these
advance(runner, err)       IN: runner + {motor: error}   OUT: (runner, commands {motor: (vals, power)} to set now)"""
from config import REACHED


def new():
    return dict(queue=[], cur=None)


def override(runner, steps):
    return dict(queue=list(steps), cur=None)


def advance(runner, err):
    q, cur, cmds = list(runner["queue"]), runner["cur"], {}
    if cur is not None and all(err.get(nm, 0.0) < REACHED for nm in cur):
        cur = None
    if cur is None and q:
        cur = q.pop(0)
        cmds = dict(cur)
    return dict(queue=q, cur=cur), cmds

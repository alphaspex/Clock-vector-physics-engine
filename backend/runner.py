"""Timed action runner.

Supports timed macro steps {frames: LIVE_TICKS, motors: {...}} and legacy
motor dictionaries. Timed steps prevent unreachable targets from blocking a
macro indefinitely. LIVE_TICKS are 7-FPS simulation ticks, not replay frames.
"""
from config import REACHED


def new():
    return dict(queue=[], cur=None, remaining=0)


def override(runner, steps):
    return dict(queue=list(steps or []), cur=None, remaining=0)


def advance(runner, err):
    q = list(runner.get("queue", []))
    cur = runner.get("cur")
    remaining = int(runner.get("remaining", 0))
    cmds = {}

    if cur is not None:
        if "motors" in cur and "frames" in cur:
            remaining -= 1
            if remaining <= 0:
                cur = None
        elif all(err.get(name, 0.0) < REACHED for name in cur):
            cur = None

    if cur is None and q:
        nxt = q.pop(0)
        if "motors" in nxt and "frames" in nxt:
            cur = dict(nxt)
            remaining = max(1, int(nxt.get("frames", 1)))
            cmds = dict(nxt["motors"])
        else:
            cur = dict(nxt)
            remaining = 0
            cmds = dict(nxt)

    return dict(queue=q, cur=cur, remaining=remaining), cmds

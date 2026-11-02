"""DIGEST: turns a finished round into a short text for the AI's memory note.
digest(events, orders, result, f, max_chars)   IN: event log, orders, result, fighter id   OUT: text"""
import re
from config import FPS


def digest(events, orders, result, f, max_chars=3500):
    me, foe = "AB"[f], "AB"[1 - f]
    verdict = {None: "round ended without a result", "draw": "DRAW"}.get(result, "YOU WON" if result == me else "YOU LOST")
    L = [f"Result: {verdict}."]
    dos = [(o["frame"] / FPS, ", ".join(re.findall(r"(?im)^\s*do\s+(.*)$", o.get("text", "")))) for o in orders if o["f"] == f]
    dos = [f"t={t:.0f}s {d}" for t, d in dos if d]
    L.append("Your commands: " + ("; ".join(dos[:25]) if dos else "none"))
    touches = [e for e in events if e["event"] == "touch" and e["energy_J"] >= 0.3 and (e["a"][0] == me or e["b"][0] == me)]
    touches.sort(key=lambda e: -e["energy_J"])
    L.append("Strongest touches: " + ("; ".join(f"t={e['t']} {e['a']}.{e['za']}->{e['b']}.{e['zb']} {e['energy_J']}J dmg {e['dmg_a_J'] + e['dmg_b_J']}J" for e in touches[:10]) or "none"))
    dead = [f"t={e['t']} {e['part']}" for e in events if e["event"] == "destroyed"]
    L.append("Parts destroyed: " + ("; ".join(dead) if dead else "none"))
    return "\n".join(L)[:max_chars]

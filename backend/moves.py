"""MOVES: the move language the AI writes.  Knows nothing about physics.
  move NAME = L_shoulder 80,10 0.9 ; L_elbow 10 0.9 | L_shoulder 10 0.5     ('|' = next step, ';' = next motor)
  chain NAME = a, b, c        (moves and chains can be chained)
  do a, b                     (what to run now)
parse(text, motor_info)            IN: AI text + {motor: {n, lim}}   OUT: {moves, chains, do, errors}  (values auto-clamped)
merge(library, parsed)             IN: old library + parsed          OUT: new library {moves, chains}
compile_do(do, library)            IN: names to run + library        OUT: (steps, errors)   step = {motor: (vals, power)}"""
import re


def parse(text, motor_info):
    moves, chains, do, errors = {}, {}, [], []
    for raw in text.splitlines():
        m = re.match(r"^\s*(move|chain|do)\b\s*(.*)$", raw, re.I)
        if not m: continue
        kind, rest = m.group(1).lower(), m.group(2)
        if kind == "do":
            do += [x.strip() for x in rest.split(",") if x.strip()]
            continue
        if "=" not in rest:
            errors.append(f"line '{raw.strip()[:40]}': missing '='"); continue
        name, body = [x.strip() for x in rest.split("=", 1)]
        if kind == "chain":
            chains[name] = [x.strip() for x in body.split(",") if x.strip()]
            continue
        steps = []
        for st in body.split("|"):
            step = {}
            for mc in st.split(";"):
                tok = mc.split()
                if not tok: continue
                if tok[0] not in motor_info:
                    errors.append(f"{name}: unknown motor '{tok[0]}'"); continue
                if len(tok) < 2:
                    errors.append(f"{name}: {tok[0]} needs an angle"); continue
                try:
                    vals = [float(x) for x in tok[1].split(",")]
                    pw = float(tok[2]) if len(tok) > 2 else 1.0
                except ValueError:
                    errors.append(f"{name}: bad number in '{mc.strip()}'"); continue
                info = motor_info[tok[0]]
                vals = [min(max(vals[k] if k < len(vals) else 0.0, lo), hi) for k, (lo, hi) in enumerate(info["lim"])]
                step[tok[0]] = (tuple(vals), min(max(pw, 0.0), 1.0))
            if step: steps.append(step)
        if not steps: errors.append(f"{name}: no valid steps")
        else: moves[name] = steps
    return dict(moves=moves, chains=chains, do=do, errors=errors)


def merge(library, parsed):
    return dict(moves={**library["moves"], **parsed["moves"]}, chains={**library["chains"], **parsed["chains"]})


def compile_do(do, library, max_steps=500):
    steps, errors = [], []

    def walk(name, depth):
        if depth > 8: errors.append(f"'{name}': chain nested too deep"); return
        if name in library["moves"]: steps.extend(library["moves"][name])
        elif name in library["chains"]:
            for x in library["chains"][name]: walk(x, depth + 1)
        else: errors.append(f"unknown move/chain '{name}'")
    for nm in do: walk(nm, 0)
    return steps[:max_steps], errors

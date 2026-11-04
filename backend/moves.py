"""MOVES: the move language the AI writes.
  [THINKING]
  Exactly 20 words describing the current moment.
  [/THINKING]
  move NAME = R_shoulder 60,0 0.9 ; R_elbow 30 0.9 | R_shoulder 0,0 0.5
  description: A quick punch aimed forward at the opponent.
  chain NAME = a, b, c
  description: Advance, raise the guard, then deliver a forward punch.
  do a, b

extract_thinking(text)             OUT: (thinking_text, word_count, clean_text, error)
parse(text, motor_info)            IN: AI text + {motor: {n, lim}}   OUT: {moves, chains, do, errors, move_descriptions, chain_descriptions}
merge(library, parsed)             IN: old library + parsed          OUT: new library
compile_do(do, library)            IN: names to run + library        OUT: (steps, errors)
"""
import re


def extract_thinking(text):
    """
    Extracts [THINKING]...[/THINKING] section.
    Python captures this section separately from motor/action output.
    Returns: (thinking_text, word_count, clean_text, error)
    """
    if not text:
        return "", 0, "", "empty input"

    pattern = r"\[THINKING\](.*?)\[/THINKING\]"
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if not m:
        # Fallback check for unclosed or line-based thinking tag
        m2 = re.search(r"^\s*\[?THINKING\]?\s*[:\n](.*)", text, re.IGNORECASE)
        if m2:
            raw = m2.group(1).splitlines()[0].strip()
            clean = text[:m2.start()] + "\n" + "\n".join(text[m2.start():].splitlines()[1:])
            words = raw.split()
            err = None if len(words) == 20 else f"Thinking description has {len(words)} words (expected exactly 20 words)"
            return raw, len(words), clean, err
        return "", 0, text, "missing [THINKING] section"

    raw_thinking = m.group(1).strip()
    # Remove thinking block so it never corrupts motor instructions
    clean_text = text[:m.start()] + "\n" + text[m.end():]
    words = raw_thinking.split()
    word_count = len(words)
    err = None if word_count == 20 else f"Thinking description has {word_count} words (expected exactly 20 words)"
    return raw_thinking, word_count, clean_text, err


def is_exact_15_mult(val):
    rem = abs(val) % 15.0
    return rem < 1e-4 or abs(rem - 15.0) < 1e-4


def parse(text, motor_info, mastered_moves=None):
    # Ensure thinking section is removed before parsing actions
    _, _, clean_text, _ = extract_thinking(text)

    moves, chains, do, forget, errors = {}, {}, [], [], []
    move_descriptions = {}
    chain_descriptions = {}

    last_defined_kind = None  # 'move' or 'chain'
    last_defined_name = None

    for raw in clean_text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # Check for description line
        m_desc = re.match(r"^(?:description|desc)\s*[:=]\s*(.*)$", line, re.I)
        if m_desc:
            desc_text = m_desc.group(1).strip()
            wc = len(desc_text.split())
            if last_defined_kind == "move" and last_defined_name:
                move_descriptions[last_defined_name] = desc_text
                if not (5 <= wc <= 10):
                    errors.append(f"{last_defined_name}: move description has {wc} words (expected 5-10 words)")
            elif last_defined_kind == "chain" and last_defined_name:
                chain_descriptions[last_defined_name] = desc_text
                if not (10 <= wc <= 15):
                    errors.append(f"{last_defined_name}: chain description has {wc} words (expected 10-15 words)")
            continue

        # Check for move, chain, do, or forget/delete command
        m = re.match(r"^\s*(move|chain|do|forget|delete)\b[:\s]*(.*)$", line, re.I)
        if not m:
            continue

        kind, rest = m.group(1).lower(), m.group(2).strip()

        if kind in ("forget", "delete"):
            if rest.startswith("="):
                rest = rest[1:].strip()
            forget += [x.strip() for x in rest.split(",") if x.strip()]
            last_defined_kind = None
            last_defined_name = None
            continue

        if kind == "do":
            # Strip optional '=' if present
            if rest.startswith("="):
                rest = rest[1:].strip()
            do += [x.strip() for x in rest.split(",") if x.strip()]
            last_defined_kind = None
            last_defined_name = None
            continue

        if "=" not in rest:
            errors.append(f"line '{line[:40]}': missing '='")
            continue

        name, body = [x.strip() for x in rest.split("=", 1)]

        if kind == "chain":
            chain_moves = [x.strip() for x in body.split(",") if x.strip()]
            # Chain Rule: Only mastered moves can be used in chains
            if mastered_moves is not None:
                invalid = [m for m in chain_moves if m not in mastered_moves]
                if invalid:
                    errors.append(f"chain {name}: components {invalid} are not MASTERED moves")
                    continue
            chains[name] = chain_moves
            last_defined_kind = "chain"
            last_defined_name = name
            continue

        # Kind == "move"
        last_defined_kind = "move"
        last_defined_name = name
        steps = []

        for st in body.split("|"):
            step = {}
            for mc in st.split(";"):
                tok = mc.split()
                if not tok:
                    continue
                motor_name = tok[0]
                body_parts = ["RIGHT_ELBOW", "RIGHT_FIST", "LEFT_ELBOW", "LEFT_FIST"]
                is_body_part = motor_name in body_parts
                
                if motor_name not in motor_info and not is_body_part:
                    errors.append(f"{name}: unknown motor or body part '{motor_name}'")
                    continue
                if len(tok) < 2:
                    errors.append(f"{name}: {motor_name} needs an angle or position description")
                    continue
                
                if is_body_part:
                    # For body parts, we store the rest of the tokens as the "position description"
                    # We'll translate this later in the simulation loop
                    desc = " ".join(tok[1:])
                    step[motor_name] = desc
                    continue

                try:
                    vals = [float(x) for x in tok[1].split(",")]
                    pw = float(tok[2]) if len(tok) > 2 else 1.0
                except ValueError:
                    errors.append(f"{name}: bad number in '{mc.strip()}'")
                    continue

                # Motor rotation rule: angles must be exact multiples of 15°
                # Reject invalid motor angles that are not multiples of 15°. Never automatically round.
                invalid_angles = [v for v in vals if not is_exact_15_mult(v)]
                if invalid_angles:
                    errors.append(f"{name}: {motor_name} angle {invalid_angles[0]} is not an exact multiple of 15° (command rejected)")
                    continue

                info = motor_info[motor_name]
                vals = [min(max(vals[k] if k < len(vals) else 0.0, lo), hi) for k, (lo, hi) in enumerate(info["lim"])]
                step[motor_name] = (tuple(vals), min(max(pw, 0.0), 1.0))

            if step:
                steps.append(step)

        if not steps:
            errors.append(f"{name}: no valid steps")
        else:
            moves[name] = steps

    return dict(
        moves=moves,
        chains=chains,
        do=do,
        forget=forget,
        errors=errors,
        move_descriptions=move_descriptions,
        chain_descriptions=chain_descriptions,
    )


def merge(library, parsed):
    old_moves = library.get("moves", {})
    new_moves = parsed.get("moves", {})
    history = library.get("move_history", {})

    # Detect edits and save history
    for name, steps in new_moves.items():
        if name in old_moves and old_moves[name] != steps:
            # Move was edited, push previous to history
            history.setdefault(name, []).append({
                "steps": old_moves[name],
                "description": library.get("move_descriptions", {}).get(name, ""),
                "timestamp": None # Will be filled by caller if needed
            })

    moves = {**old_moves, **new_moves}
    chains = {**library.get("chains", {}), **parsed.get("chains", {})}
    move_desc = {**library.get("move_descriptions", {}), **parsed.get("move_descriptions", {})}
    chain_desc = {**library.get("chain_descriptions", {}), **parsed.get("chain_descriptions", {})}

    for fg in parsed.get("forget", []):
        moves.pop(fg, None)
        chains.pop(fg, None)
        move_desc.pop(fg, None)
        chain_desc.pop(fg, None)

    return dict(
        moves=moves,
        chains=chains,
        move_descriptions=move_desc,
        chain_descriptions=chain_desc,
        move_history=history,
        mastered_moves=library.get("mastered_moves", {}),
        mastered_chains=library.get("mastered_chains", {})
    )


def compile_do(do, library, max_steps=500):
    steps, errors = [], []

    def walk(name, depth):
        if depth > 8:
            errors.append(f"'{name}': chain nested too deep")
            return
        if name in library.get("moves", {}):
            steps.extend(library["moves"][name])
        elif name in library.get("chains", {}):
            for x in library["chains"][name]:
                walk(x, depth + 1)
        else:
            errors.append(f"unknown move/chain '{name}'")

    for nm in do:
        walk(nm, 0)

    return steps[:max_steps], errors

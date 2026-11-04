"""PROMPTS: builds every text the AI reads. Pure text in, text out. Never mentions health.
language_help(info) / practice_system(info, notes) / fight_system(info, notes, me) / turn_message(obs, errors, lib)
note_system() / note_user(digest_text)"""
_SEM = {"shoulder": "angles: pitch,out. pitch = swing forward(+)/back(-), 0 = arm hangs down. out = sideways 0..180, arm can never cross the body.",
        "hip": "angles: pitch,out. pitch = leg forward(+)/back(-), 0 = leg straight down. out = sideways (negative = inward).",
        "elbow": "one angle: bend of the forearm forward.", "knee": "one angle: bend of the shin backward.",
        "ankle": "one angle: foot tilt, + = toes up, - = toes down."}


def language_help(info):
    rows = []
    for base, text in _SEM.items():
        lim = info["L_" + base]["lim"]
        rows.append(f"  L_{base} / R_{base}: {text} limits {' and '.join(f'{a}..{b}' for a, b in lim)} degrees")
    return ("MOTORS (values outside limits are clamped automatically):\n" + "\n".join(rows) +
            "\nLANGUAGE (one command per line):\n"
            "  move NAME = L_shoulder 80,10 0.9 ; L_elbow 20 0.9 | L_shoulder 0,0 0.5\n"
            "     ';' separates motors in one step, '|' starts the next step, last number = power 0..1 (torque and speed).\n"
            "  chain NAME = move1, move2, chain3      (chains may contain moves and chains)\n"
            "  do NAME, NAME                          (run now; REPLACES whatever is currently running)\n"
            "A step ends when its motors reach their targets. A blocked or fallen limb stays stuck until your next 'do'.")


def _mem(notes):
    return ("\nYOUR NOTES FROM EARLIER ROUNDS (oldest first):\n" + "\n".join(f"- {n}" for n in notes)) if notes else ""


_WORLD = ("You control a stick-fighter, 1 m tall and about 30 kg, built from iron balls joined by wooden links, in a real physics "
          "world (gravity 9.81, flat ground, round arena radius 5 m with a 0.5 m wall). Nothing is scripted: you only set motor "
          "targets and physics decides everything. Heavy iron balls hurt wood; iron cannot be destroyed. Your feet are tiny, so "
          "standing is hard: falling, crawling and getting up are all valid.\n")


def practice_system(info, notes):
    return (_WORLD + "PRACTICE ROUND: you are alone, nothing can hurt you. Learn to stand, move, hit hard. Save useful moves and "
            "chains: they are kept for your fights. Each turn you see your pose, then reply with at most 2 short sentences "
            "followed by language lines.\n" + language_help(info) + _mem(notes))


def fight_system(info, notes, me):
    return (_WORLD + f"FIGHT ROUND: you are fighter {me}. You win if the enemy head or neck is destroyed, or the enemy core stays "
            "outside the ring for 10 seconds. 60 seconds, otherwise a draw. You cannot see anyone's health. Use your saved moves "
            "by name with 'do'. Reply with at most 1 short sentence then language lines.\n" + language_help(info) + _mem(notes))


def turn_message(obs, errors, lib):
    s = obs + "\nYour saved moves: " + (", ".join(sorted(lib["moves"])) or "none") + " | chains: " + (", ".join(sorted(lib["chains"])) or "none")
    if errors: s += "\nProblems with your last answer: " + "; ".join(errors[:5])
    return s + "\nAnswer now."


def note_system():
    return "You write one short memory note (max 150 words) for your future self about what worked and what failed. Plain text only."


def note_user(digest_text):
    return digest_text + "\nWrite the note now."

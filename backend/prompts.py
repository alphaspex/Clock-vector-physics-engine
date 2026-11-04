"""PROMPTS: position-tree action prompts and factual interval summaries."""
from config import H_DIR_WORDS, V_DIR_WORDS, DIST_WORDS


def get_vocabulary_list():
    """Render the canonical vocabulary constants, one official word per line."""
    lines = list(DIST_WORDS)
    lines.append("GROUND")
    lines.extend(H_DIR_WORDS[angle] for angle in sorted(H_DIR_WORDS))
    lines.extend(V_DIR_WORDS[angle] for angle in sorted(V_DIR_WORDS, reverse=True))
    return "\n".join(lines)


_BODY_GUIDE = (
    "BODY STRUCTURE & PHYSICAL GUIDE:\n"
    "- Your body consists of a central CHEST, a NECK, a HEAD, and two arms. Each arm has a SHOULDER, ELBOW and FIST.\n"
    "- The CHEST is the origin for all relative positions and is indestructible.\n"
    "- The NECK is a connecting link, not a physical ball.\n"
    "- You have NO LEGS, NO KNEES, NO HIPS, NO ANKLES, and NO FEET.\n"
    "- The two shoulder motors rotate each upper arm. The elbow motors bend each forearm. FISTS have no motors.\n"
    "- The SHOULDER ball is the arm pivot. The arm motors cannot independently reposition the shoulder ball.\n"
    "- The HEAD has no direct motor. It may move indirectly when the chest and body move through physical forces.\n"
    "- Use arm positions and ground contact to support, lift, stabilize and move the chest.\n"
    "- Because you have no legs or feet, an upright posture must be supported by your arms; do not assume human standing support exists.\n"
    "- Protect your HEAD and NECK. Their destruction causes instant defeat.\n"
)

_VOCABULARY_INFO = (
    "OFFICIAL POSITION VOCABULARY (ONE ENTRY PER LINE; USE THESE EXACT WORDS):\n"
    + get_vocabulary_list()
    + "\n\nPOSITION FORMAT:\n"
    "DISTANCE HORIZONTAL_DIRECTION VERTICAL_DIRECTION\n"
    "Or omit horizontal direction for STRAIGHT UP / STRAIGHT DOWN.\n"
    "GROUND is a permitted special distance value and means actual floor contact.\n"
    "Examples: MID FRONT LEVEL; FAR RIGHT LOWER; GROUND FRONT LEVEL; VERY-CLOSE STRAIGHT UP.\n"
    "All positions are relative to CHEST CENTER, in local X=RIGHT, Y=UP, Z=FRONT.\n"
)

_OUTPUT_RULES = (
    "TARGET TREE OUTPUT RULES:\n"
    "- You receive the latest measured physical body tree. It may contain STATUS, CURRENT CONTACTS and TOUCH EVENTS.\n"
    "- Return a NEW DESIRED BODY TREE for the next interval, not a report of what already happened.\n"
    "- Return the complete official hierarchy, with POSITION fields only.\n"
    "- The only positioned parts are CHEST, HEAD, RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_FIST, LEFT_SHOULDER, LEFT_ELBOW and LEFT_FIST.\n"
    "- CHEST must be POSITION: ORIGIN. Every other physical ball must have exactly one POSITION field.\n"
    "- Include the structural headings NECK, RIGHT_ARM, LEFT_ARM, NECK_RIGHT_JOINT, SHOULDER_RIGHT_JOINT, ELBOW_RIGHT_JOINT, NECK_LEFT_JOINT, SHOULDER_LEFT_JOINT and ELBOW_LEFT_JOINT, but do not put POSITION fields under them.\n"
    "- Do NOT return STATUS, CURRENT CONTACTS, TOUCH EVENTS, FRAME, SIMULATION TIME, health, movement telemetry, explanations, markdown, JSON or motor commands.\n"
    "- Do NOT invent body parts or omit any physical ball. Use exact official body-part names.\n"
    "- Every position must use exact official vocabulary. Do not misspell, abbreviate or invent words.\n"
    "- The requested pose is only a target. Physics, gravity, collisions, contact and the opponent may prevent it from happening.\n"
    "- You do not control the head or chest directly. Python will use only elbow and fist target positions to calculate available shoulder and elbow rotations.\n"
    "- Changing only HEAD, CHEST or SHOULDER position descriptions does not create a motor command.\n"
    "- When the task is not achieved, choose a meaningful next configuration for the ELBOW and/or FIST positions. Do not repeat the same arm target positions unless keeping the current arm pose is intentional.\n"
    "- Consider the actual current tree and contacts. A target marked GROUND asks for a reachable ground-contact position, but physics and other contacts determine whether it actually makes contact.\n"
    "- GROUND direction must point downward toward the world floor. A horizontal or upward GROUND ray cannot intersect the floor and will be rejected by Python.\n"
    "- Output ONLY the tree. No prose before or after it.\n"
    "\nREQUIRED OUTPUT SHAPE:\n"
    "MY FIGHTER\n"
    "CHEST\n  POSITION: ORIGIN\n"
    "NECK\nHEAD\n  POSITION: [official position]\n"
    "RIGHT_ARM\nNECK_RIGHT_JOINT\nRIGHT_SHOULDER\n  POSITION: [official position]\n"
    "SHOULDER_RIGHT_JOINT\nRIGHT_ELBOW\n  POSITION: [official position]\n"
    "ELBOW_RIGHT_JOINT\nRIGHT_FIST\n  POSITION: [official position]\n"
    "LEFT_ARM\nNECK_LEFT_JOINT\nLEFT_SHOULDER\n  POSITION: [official position]\n"
    "SHOULDER_LEFT_JOINT\nLEFT_ELBOW\n  POSITION: [official position]\n"
    "ELBOW_LEFT_JOINT\nLEFT_FIST\n  POSITION: [official position]\n"
)


def practice_system(task_text, current_tree=None, memory_records=None):
    """System prompt for Practice Mode. Current physical tree is supplied as user input."""
    memory_lines = ["TASK MEMORY (LATEST 7 COMPLETED INTERVALS):"]
    if memory_records:
        for i, record in enumerate(memory_records, 1):
            memory_lines.extend([
                f"INTERVAL {i} DESCRIPTION: {record.get('description', '')}",
                "PRE-TREE:", record.get("pre_tree", ""),
                "POST-TREE:", record.get("post_tree", ""),
                "",
            ])
    else:
        memory_lines.append("None yet.")

    return (
        "ROLE: You are an autonomous physics combat fighter in PRACTICE MODE.\n"
        "Your job is to choose the next desired body pose that advances the selected task.\n\n"
        + _BODY_GUIDE + "\n"
        + _VOCABULARY_INFO + "\n"
        + _OUTPUT_RULES + "\n"
        + f"PRACTICE TASK: {task_text}\n\n"
        + "Use the current physical tree supplied in the user message as Pose 1. Return your desired target tree as Pose 2.\n\n"
        + "\n".join(memory_lines)
    )


def fight_system(fighter_name, current_tree=None, enemy_tree=None, memory_records=None, round_summaries=None):
    """System prompt for Fight Mode. Trees are supplied once in the user message."""
    memory_lines = ["FIGHT MEMORY (LATEST 7 COMPLETED INTERVALS):"]
    if memory_records:
        for i, record in enumerate(memory_records, 1):
            memory_lines.extend([
                f"INTERVAL {i} DESCRIPTION: {record.get('description', '')}",
                "PRE-TREE:", record.get("pre_tree", ""),
                "POST-TREE:", record.get("post_tree", ""),
                "",
            ])
    else:
        memory_lines.append("None yet.")

    summary_lines = ["PREVIOUS FIGHT ROUND SUMMARIES:"]
    if round_summaries:
        summary_lines.extend(f"ROUND {i}: {summary}" for i, summary in enumerate(round_summaries, 1))
    else:
        summary_lines.append("None yet.")

    return (
        f"ROLE: You are Fighter {fighter_name} in FIGHT MODE.\n"
        "TASK: WIN THE FIGHT.\n"
        "Choose your next desired body pose using the current physical tree and the enemy's read-only tree.\n\n"
        + _BODY_GUIDE + "\n"
        + _VOCABULARY_INFO + "\n"
        + _OUTPUT_RULES + "\n"
        + "The enemy tree is information only. Rewrite ONLY your own tree.\n\n"
        + "\n".join(summary_lines) + "\n\n"
        + "\n".join(memory_lines)
    )


def fight_user(current_tree, enemy_tree):
    return (
        "MY CURRENT PHYSICAL BODY TREE (POSE 1):\n"
        + current_tree
        + "\n\nENEMY CURRENT BODY TREE (READ-ONLY):\n"
        + enemy_tree
        + "\n\nReturn only MY desired position tree (POSE 2)."
    )


def batch_description_system():
    return (
        "ROLE: You are a factual physical observer.\n"
        "TASK: Generate exactly one description for each provided interval record.\n"
        "RULES:\n"
        "- Each description must contain 15-30 words inclusive.\n"
        "- Describe observable physical changes between PRE-TREE and POST-TREE.\n"
        "- Mention important body-part position changes or explicitly state when positions barely changed.\n"
        "- Be factual. Do not invent motor actions, contacts or events not supported by the two trees.\n"
        "- Do not claim that a task succeeded unless the trees support that conclusion.\n"
        "- Return exactly the same number of numbered descriptions as input records.\n"
        "FORMAT:\nINTERVAL 1: [15-30 word description]\nINTERVAL 2: [15-30 word description]\n..."
    )


def batch_description_user(records):
    lines = []
    for i, record in enumerate(records, 1):
        lines.extend([
            f"INTERVAL {i}:",
            "PRE-TREE:", record.get("pre_tree", ""),
            "POST-TREE:", record.get("post_tree", ""),
            "",
        ])
    return "\n".join(lines)


def round_summary_system(fighter_name):
    return (
        f"ROLE: You are Fighter {fighter_name}'s strategic memory processor.\n"
        "TASK: Write a concise strategic memory summary for this completed fight round.\n"
        "Describe what physically happened, what appeared effective or ineffective, and the most useful lesson for the next fight.\n"
        "Use only the supplied interval descriptions and before/after position trees. Do not invent events or actions.\n"
        "Do not issue movement commands or generate a target body tree."
    )


def round_summary_user(records, result_text):
    lines = [f"ROUND RESULT: {result_text}", "FIGHTER INTERVAL RECORDS:"]
    for i, record in enumerate(records, 1):
        lines.extend([
            f"INTERVAL {i} DESCRIPTION: {record.get('text') or record.get('description') or ''}",
            "PRE-TREE:", record.get("pre_tree", ""),
            "POST-TREE:", record.get("post_tree", ""),
            "",
        ])
    lines.append("Write the concise strategic memory summary now.")
    return "\n".join(lines)

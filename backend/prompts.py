"""PROMPTS: builds system and user prompts for Practice and Fight modes, and memory descriptions.
Pure text in, text out.
"""
from config import H_DIR_WORDS, V_DIR_WORDS, DIST_WORDS

def get_vocabulary_list():
    lines = []
    # Distance
    for d in DIST_WORDS:
        lines.append(d)
    lines.append("GROUND")
    # Horizontal
    for h in sorted(H_DIR_WORDS.keys()):
        lines.append(H_DIR_WORDS[h])
    # Vertical
    for v in sorted(V_DIR_WORDS.keys(), reverse=True):
        lines.append(V_DIR_WORDS[v])
    return "\n".join(lines)

_BODY_GUIDE = (
    "BODY STRUCTURE & PHYSICAL GUIDE:\n"
    "- Your body consists of a central CHEST, a NECK, a HEAD, and two arms. Each arm has a SHOULDER, ELBOW and FIST.\n"
    "- The CHEST is your origin for all relative positions. It is indestructible.\n"
    "- You have NO LEGS, NO KNEES, NO HIPS, NO ANKLES, and NO FEET.\n"
    "- To move, use your shoulders and elbows to position your fists against the ground and push.\n"
    "- Protect your HEAD and NECK. Their destruction causes instant defeat. Keep them away from the ground.\n"
)

_VOCABULARY_INFO = (
    "POSITION VOCABULARY (ONE PER LINE):\n"
    + get_vocabulary_list() + "\n"
    "\nPOSITION FORMAT:\n"
    "DISTANCE HORIZONTAL_DIRECTION VERTICAL_DIRECTION\n"
    "Or: DISTANCE STRAIGHT UP / DISTANCE STRAIGHT DOWN\n"
    "Example: MID FRONT LEVEL, FAR RIGHT LOWER, GROUND FRONT LEVEL, VERY-CLOSE STRAIGHT UP\n"
)

def practice_system(task_text, current_tree, memory_records=None):
    """System prompt for Practice Mode."""
    memory_section = "TASK MEMORY (LATEST 7 INTERVALS):\n"
    if memory_records:
        for i, rec in enumerate(memory_records):
            memory_section += f"RECORD {i+1}:\n"
            memory_section += f"DESCRIPTION: {rec['description']}\n"
            memory_section += f"PRE-TREE:\n{rec['pre_tree']}\n"
            memory_section += f"POST-TREE:\n{rec['post_tree']}\n\n"
    else:
        memory_section += "None yet.\n"

    return (
        "ROLE: You are an autonomous physics combat fighter in PRACTICE MODE.\n"
        "\n"
        + _BODY_GUIDE + "\n"
        + _VOCABULARY_INFO + "\n"
        f"PRACTICE TASK: {task_text}\n\n"
        "INSTRUCTION: Rewrite your entire body tree with the positions you want. return ONLY the tree. No prose, no JSON, no Markdown.\n"
        "\n"
        + memory_section +
        "\nCURRENT BODY TREE:\n"
        + current_tree
    )

def fight_system(fighter_name, current_tree, enemy_tree, memory_records=None, round_summaries=None):
    """System prompt for Fight Mode."""
    memory_section = "FIGHT MEMORY (LATEST 7 INTERVALS):\n"
    if memory_records:
        for i, rec in enumerate(memory_records):
            memory_section += f"RECORD {i+1}:\n"
            memory_section += f"DESCRIPTION: {rec['description']}\n"
            memory_section += f"PRE-TREE:\n{rec['pre_tree']}\n"
            memory_section += f"POST-TREE:\n{rec['post_tree']}\n\n"
    else:
        memory_section += "None yet.\n"

    summaries_section = "PREVIOUS FIGHT ROUND SUMMARIES:\n"
    if round_summaries:
        for i, s in enumerate(round_summaries):
            summaries_section += f"ROUND {i+1}: {s}\n"
    else:
        summaries_section += "None yet.\n"

    return (
        f"ROLE: You are Fighter {fighter_name} in FIGHT MODE.\n"
        "TASK: WIN THE FIGHT\n"
        "\n"
        + _BODY_GUIDE + "\n"
        + _VOCABULARY_INFO + "\n"
        "INSTRUCTION: Rewrite your entire body tree with the positions you want. return ONLY the tree. No prose, no JSON, no Markdown.\n"
        "\n"
        + summaries_section + "\n"
        + memory_section +
        "\nMY CURRENT BODY TREE:\n"
        + current_tree +
        "\nENEMY'S CURRENT BODY TREE (READ-ONLY):\n"
        + enemy_tree
    )

def batch_description_system():
    """System prompt for batch interval description generation."""
    return (
        "ROLE: You are a factual physical observer.\n"
        "TASK: Generate exactly one description for each provided interval record.\n"
        "RULES:\n"
        "- Each description must be 15-30 words inclusive.\n"
        "- Describe observable physical changes between PRE-TREE and POST-TREE.\n"
        "- Mention body-part position changes.\n"
        "- Be factual and concise. No hidden reasoning or goals.\n"
        "- Return EXACTLY the same number of descriptions as input records.\n"
        "FORMAT:\n"
        "INTERVAL 1: [Description]\n"
        "INTERVAL 2: [Description]\n"
        "..."
    )

def batch_description_user(records):
    """User prompt for batch description."""
    lines = []
    for i, rec in enumerate(records):
        lines.append(f"INTERVAL {i+1} RECORD:")
        lines.append(f"PRE-TREE:\n{rec['pre_tree']}")
        lines.append(f"POST-TREE:\n{rec['post_tree']}")
        lines.append("")
    return "\n".join(lines)

def round_summary_system(fighter_name):
    """System prompt for end-of-round summary generation."""
    return (
        f"ROLE: You are Fighter {fighter_name}'s strategic memory processor.\n"
        "TASK: Generate a concise strategic memory summary for this round.\n"
        "RULES:\n"
        "- Capture what physically happened.\n"
        "- Identify what was effective or ineffective.\n"
        "- State one useful lesson for the future.\n"
        "- Be concise and direct."
    )

def round_summary_user(records, result_text):
    """User prompt for round summary."""
    lines = [f"ROUND RESULT: {result_text}\n", "INTERVAL RECORDS:"]
    for i, rec in enumerate(records):
        lines.append(f"Interval {i+1}: {rec['description']}")
        lines.append(f"PRE-TREE:\n{rec['pre_tree']}")
        lines.append(f"POST-TREE:\n{rec['post_tree']}\n")
    lines.append("Write your strategic summary now.")
    return "\n".join(lines)

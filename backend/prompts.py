"""Action-selection prompts for the prebuilt demo-move controller."""
from moves import describe_catalogue

_BODY_GUIDE = (
    "BODY AND PHYSICS GUIDE:\n"
    "- You control a physical upper-body fighter: CHEST, NECK, HEAD, and two arms with SHOULDER, ELBOW and FIST.\n"
    "- The CHEST is the central indestructible ball. The HEAD and wooden connecting parts can be damaged.\n"
    "- There are NO legs, hips, knees, ankles or feet. All support, movement, turning and attacks come from the arms and ground contact.\n"
    "- Shoulder motors rotate upper arms; elbow motors bend forearms. Fists have no motors.\n"
    "- Gravity, collisions, ground contact and the opponent determine the actual result. Never assume a requested action succeeded.\n"
    "- Protect the head and neck. If grounded or unstable, prioritize the appropriate GET_UP action before attacking.\n"
)


def practice_system(task_text, current_tree="", memory_records=None):
    memory = ["RECENT PRACTICE MEMORY (LATEST 7 INTERVALS):"]
    for i, rec in enumerate(memory_records or [], 1):
        memory.extend([
            f"INTERVAL {i}: {rec.get('description', '')}",
            "PRE-TREE:", rec.get("pre_tree", ""),
            "POST-TREE:", rec.get("post_tree", ""),
        ])
    if not memory_records:
        memory.append("None yet.")
    return (
        "ROLE: You are an autonomous physical fighter in PRACTICE MODE.\n"
        f"TASK: {task_text}\n\n"
        + _BODY_GUIDE + "\n"
        + describe_catalogue() + "\n\n"
        + "Choose exactly ONE action name per interval. Use the current physical tree and recent memory. "
        "For recovery, select the GET_UP stages in order, checking the newly observed pose after each stage. "
        "For movement, use MOVE_FORWARD, MOVE_BACKWARD, TURN_LEFT, TURN_RIGHT, STRAFE_LEFT or STRAFE_RIGHT. "
        "For a fighting task, select a short attack or defensive action only when appropriate. "
        "Return exactly: ACTION: NAME. Do not return a position tree, motor angles, code, JSON or prose.\n\n"
        + "\n".join(memory)
    )


def fight_system(fighter_name, current_tree="", enemy_tree="", memory_records=None, round_summaries=None):
    memory = ["RECENT FIGHT MEMORY (LATEST 7 INTERVALS):"]
    for i, rec in enumerate(memory_records or [], 1):
        memory.extend([
            f"INTERVAL {i}: {rec.get('description', '')}",
            "PRE-TREE:", rec.get("pre_tree", ""),
            "POST-TREE:", rec.get("post_tree", ""),
        ])
    if not memory_records:
        memory.append("None yet.")
    summaries = ["PREVIOUS FIGHT ROUND SUMMARIES:"]
    summaries.extend(f"ROUND {i}: {s}" for i, s in enumerate(round_summaries or [], 1))
    if not round_summaries:
        summaries.append("None yet.")
    return (
        f"ROLE: You are Fighter {fighter_name} in FIGHT MODE.\nTASK: WIN THE FIGHT.\n\n"
        + _BODY_GUIDE + "\n"
        + describe_catalogue() + "\n\n"
        + "Choose exactly ONE action name per interval. Use your current tree, the enemy tree and your own memory. "
        "Close distance with movement actions when needed. Turn toward the opponent before striking. "
        "If your head is grounded or your body is unstable, recover first. Use short jabs/hooks at close range and guard when threatened. "
        "Never assume an attack caused damage; inspect the next physical observation. "
        "Return exactly: ACTION: NAME. Do not return a position tree, motor angles, code, JSON or prose.\n\n"
        + "\n".join(summaries) + "\n\n" + "\n".join(memory)
    )


def batch_description_system():
    return (
        "ROLE: factual physical observer. Describe each provided interval from its PRE-TREE and POST-TREE. "
        "Return one line per record as INTERVAL N: description. Each description must be 15-30 words. "
        "Do not invent motor actions, contacts, attacks or outcomes."
    )


def batch_description_user(records):
    lines = []
    for i, rec in enumerate(records, 1):
        lines.append(f"INTERVAL {i}:")
        lines.append(f"PRE-TREE:\n{rec.get('pre_tree', '')}")
        lines.append(f"POST-TREE:\n{rec.get('post_tree', '')}")
    return "\n\n".join(lines)


def round_summary_system(fighter_name):
    return (
        f"ROLE: strategic memory summarizer for Fighter {fighter_name}. "
        "Summarize what physically happened, which actions appeared useful or ineffective, and one lesson for future fights. "
        "Use only supplied records. Do not invent damage or movement."
    )


def round_summary_user(records, result_text):
    lines = [f"ROUND RESULT: {result_text}", "INTERVAL RECORDS:"]
    for i, rec in enumerate(records, 1):
        lines.append(f"INTERVAL {i}: {rec.get('text') or rec.get('description') or ''}")
        lines.append(f"PRE-TREE:\n{rec.get('pre_tree', '')}")
        lines.append(f"POST-TREE:\n{rec.get('post_tree', '')}")
    return "\n\n".join(lines)

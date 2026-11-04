"""PROMPTS: builds system and user prompts for Practice and Fight modes, and round summaries.
Pure text in, text out. Never mentions raw health numbers.
"""

_WORLD_RULES = (
    "WORLD & PHYSICS RULES:\n"
    "- Gravity is 9.81 m/s^2 downwards. Ground is a flat ring of radius 5.0 m with a 0.5 m wall.\n"
    "- You control a stick-fighter built from physical balls linked by wooden links.\n"
    "- CHEST is the central ball. Heavy iron balls hurt wood. Fists and chest cannot be destroyed.\n"
    "- There are no hips, legs, knees, ankles, or feet. Moving and rotating your central chest ball around the arena relies on your fists/elbows/shoulders contacting the ground and applying differential arm torque.\n"
    "- Motors apply torque towards target angles. Physics and collisions govern all movement.\n"
    "- Check body tree STATUS tags: if a body part or motor shows STATUS: DESTROYED (DISABLED), do NOT attempt to move or issue commands for it.\n"
)

_OFFICIAL_BODY_STRUCTURE = (
    "OFFICIAL BODY STRUCTURE:\n"
    "FIGHTER\n"
    "└── CHEST (central ball, origin for all relative measurements)\n"
    "    └── NECK (connecting link, not a ball)\n"
    "        ├── HEAD (physical ball)\n"
    "        ├── RIGHT_ARM\n"
    "        │   ├── NECK_RIGHT_JOINT (connection force to chest/neck)\n"
    "        │   └── RIGHT_SHOULDER (physical ball)\n"
    "        │       └── SHOULDER_RIGHT_JOINT (connection force to shoulder)\n"
    "        │           └── RIGHT_ELBOW (physical ball)\n"
    "        │               └── ELBOW_RIGHT_JOINT (connection force to elbow)\n"
    "        │                   └── RIGHT_FIST (physical ball)\n"
    "        └── LEFT_ARM\n"
    "            ├── NECK_LEFT_JOINT (connection force to chest/neck)\n"
    "            └── LEFT_SHOULDER (physical ball)\n"
    "                └── SHOULDER_LEFT_JOINT (connection force to shoulder)\n"
    "                    └── LEFT_ELBOW (physical ball)\n"
    "                        └── ELBOW_LEFT_JOINT (connection force to elbow)\n"
    "                            └── LEFT_FIST (physical ball)\n"
    "\n"
    "CRITICAL ANATOMY NOTICE:\n"
    "- You are an upper-body bipedal torso only.\n"
    "- You have NO LEGS, NO KNEES, NO HIPS, NO ANKLES, and NO FEET.\n"
    "- Never attempt to issue commands, descriptions, or references to legs or knees.\n"
    "\n"
    "CRITICAL HEAD & NECK PROTECTION DIRECTIVE:\n"
    "- Protect your HEAD and NECK at all times. Head or neck destruction causes INSTANT DEFEAT.\n"
    "- It is acceptable for your CHEST to rest on the ground, but NEVER allow your HEAD to impact or fall onto the floor.\n"
    "- Maintain a stable grounded chest pose to allow for deliberate movement planning without falling further.\n"
    "- DO NOT damage your own head or neck when executing movements, punches, or rotation routines.\n"
    "- DO NOT slam or drag your head into the ground or arena wall when crawling or shifting your chest.\n"
    "- Keep shoulders and elbows positioned to shield your neck and head from ground impact and opponent strikes.\n"
)

_POSITION_VOCABULARY = (
    "3D POSITION VOCABULARY (42 OFFICIAL WORDS):\n"
    "All positions describe relative locations from CHEST CENTER as the origin in local frame (X=RIGHT, Y=UP, Z=FRONT).\n"
    "Standard syntax: DISTANCE + HORIZONTAL_DIRECTION + VERTICAL_DIRECTION\n"
    "\n"
    "A. Horizontal Direction (24 values, 360° circle around Y axis):\n"
    "  0°: FRONT | 15°: FRONT SLIGHT RIGHT | 30°: FRONT RIGHT | 45°: FRONT DIAGONAL RIGHT | 60°: RIGHT DIAGONAL FRONT | 75°: RIGHT SLIGHT FRONT\n"
    "  90°: RIGHT | 105°: RIGHT SLIGHT BACK | 120°: RIGHT DIAGONAL BACK | 135°: RIGHT BACK | 150°: BACK DIAGONAL RIGHT | 165°: BACK SLIGHT RIGHT\n"
    "  180°: BACK | 195°: BACK SLIGHT LEFT | 210°: BACK DIAGONAL LEFT | 225°: BACK LEFT | 240°: LEFT DIAGONAL BACK | 255°: LEFT SLIGHT BACK\n"
    "  270°: LEFT | 285°: LEFT SLIGHT FRONT | 300°: LEFT DIAGONAL FRONT | 315°: LEFT FRONT | 330°: FRONT DIAGONAL LEFT | 345°: FRONT SLIGHT LEFT\n"
    "\n"
    "B. Vertical Direction (13 values, -90° to +90°):\n"
    "  +90°: STRAIGHT UP | +75°: NEAR UP | +60°: HIGH UP | +45°: DIAGONAL UP | +30°: UPPER | +15°: SLIGHT UPPER\n"
    "  0°: LEVEL | -15°: SLIGHT LOWER | -30°: LOWER | -45°: DIAGONAL DOWN | -60°: LOW DOWN | -75°: NEAR DOWN | -90°: STRAIGHT DOWN\n"
    "  (Note: At STRAIGHT UP or STRAIGHT DOWN, horizontal direction is omitted because it is undefined).\n"
    "\n"
    "C. Distance (5 bands, measured beyond chest radius):\n"
    "  0-0.10 m: VERY-CLOSE | 0.10-0.25 m: CLOSE | 0.25-0.45 m: MID | 0.45-0.70 m: FAR | Over 0.70 m: VERY-FAR\n"
    "\n"
    "D. Ground:\n"
    "  When a body ball touches the floor, its distance word is replaced with GROUND (e.g., GROUND FRONT LEVEL).\n"
)

_MOTOR_RULES = (
    "MOTOR CONTROL & EXACT 15° ROTATION RESTRICTION:\n"
    "- MOTORS: R_shoulder, L_shoulder, R_elbow, L_elbow\n"
    "  - Shoulder angles: (pitch, out). pitch = forward(+)/back(-); out = sideways(0..180).\n"
    "  - Elbow angle: (bend). bend forward (0..150).\n"
    "- CHEST LOCOMOTION & ROTATION:\n"
    "  - Push fists/elbows against the ground to rotate your chest and crawl across the ring.\n"
    "  - Differential shoulder angles (e.g., R_shoulder 45,30 vs L_shoulder -45,30) apply ground reaction torque that rotates your chest.\n"
    "- STRICT ROTATION RULE:\n"
    "  - Motor angles must be EXACT MULTIPLES OF 15° (e.g. -45°, -30°, -15°, 0°, 15°, 30°, 45°, 60°).\n"
    "  - Any command with an angle that is not a multiple of 15° is rejected.\n"
    "  - Do NOT issue position or distance commands to motors.\n"
    "\n"
    "OUTPUT SYNTAX PER INTERVAL:\n"
    "1. Situation description (MANDATORY, exactly 20 words):\n"
    "   [THINKING]\n"
    "   Exactly 20 words describing the current moment, body pose, movement, contact, or opponent situation.\n"
    "   [/THINKING]\n"
    "2. Move definitions with 5-10 word descriptions:\n"
    "   move NAME = R_shoulder 60,0 1.0 ; R_elbow 30 1.0 | R_shoulder 0,0 0.5\n"
    "   description: A quick punch aimed forward at the opponent.\n"
    "3. Chain definitions with 10-15 word descriptions:\n"
    "   chain NAME = move1, move2\n"
    "   description: Advance, raise the guard, then deliver a forward punch.\n"
    "4. Execution command:\n"
    "   do NAME, NAME\n"
    "5. Delete/forget ineffective moves or chains (PRACTICE MODE):\n"
    "   forget MOVE_OR_CHAIN_NAME\n"
)

_DECISION_PRIORITIES = (
    "DECISION PRIORITIES & STRATEGY EVALUATION RULES:\n"
    "1. Protect: Keep the head and neck away from dangerous ground contact at all times.\n"
    "2. Recover: If the chest is grounded, prioritize stabilization. Grounded chest contact is acceptable; use it as a stable base to plan your next move while strictly preventing head impact.\n"
    "3. Establish support: Use fist contact and arm position to create a stable base.\n"
    "4. Stabilize: Stop unwanted sliding and regain control.\n"
    "5. Move: Only after recovery, attempt crawling and rotation.\n"
    "6. Fight: When an opponent is present, balance recovery, defense, and attack.\n"
    "\n"
    "CRITICAL PHYSICAL ADAPTATION RULES:\n"
    "- Never repeat a failed physical strategy without a meaningful change.\n"
    "- After issuing motor rotations, examine the next physical observation. If the expected movement did not happen, identify what physically prevented it and choose a different motor action. Do not assume that issuing a movement means it succeeded.\n"
    "- When recovery fails repeatedly, stop experimenting with unrelated movements. Change the support position, motor rotations, or recovery approach based on the actual contact and movement information.\n"
    "- In your mandatory 20-word [THINKING] block, explicitly diagnose your active priority tier and any physical movement obstructions.\n"
    "- PHYSICAL FEEDBACK RULE: After every decision, check whether chest height, fist contact and support improved. If not, change the motor rotations. Never repeat an unsuccessful action unchanged.\n"
)


def _format_round_summaries(summaries, mode_label):
    if not summaries:
        return f"\nPREVIOUS {mode_label.upper()} ROUND SUMMARIES: None yet.\n"
    lines = [f"\nPREVIOUS {mode_label.upper()} ROUND SUMMARIES (latest {len(summaries)}, oldest first):"]
    for i, s in enumerate(summaries, 1):
        lines.append(f"Round {i}:\n{s}\n")
    return "\n".join(lines)


def practice_system(info, round_summaries=None):
    """System prompt for Practice Mode (One-Move Learning and Mastery)."""
    return (
        "ROLE: You are an autonomous physics combat fighter in PRACTICE MODE.\n"
        "OBJECTIVE: Master one physical movement at a time. Do not create multiple moves or chains for the same goal.\n"
        "\n"
        "POSE-TO-POSE LEARNING & MOTOR KNOWLEDGE (PRACTICE ONLY):\n"
        "1. BEFORE/AFTER POSE: You will receive two body trees for each interval. Compare them to see exactly what changed.\n"
        "2. MOTOR KNOWLEDGE: You have a persistent memory of how specific motor axes affect your body. Use this to refine your moves.\n"
        "3. EXPERIMENTS: If you don't know what a motor does, perform a CONTROLLED EXPERIMENT. Change ONE axis by 15° and observe the result.\n"
        "4. UPDATING KNOWLEDGE: To update your memory, use this syntax in your response:\n"
        "   MOTOR KNOWLEDGE: AXIS [axis] DIRECTION [dir] FINDING [your brief physical discovery]\n"
        "   Supported axes: R_shoulder pitch, R_shoulder out, L_shoulder pitch, L_shoulder out, R_elbow bend, L_elbow bend.\n"
        "\n"
        "ONE-MOVE LEARNING RULES:\n"
        "1. FOCUS: Each session has one specific goal (e.g., 'recovery').\n"
        "2. ITERATE: If a move fails, EDIT its joint angles and timing in the next trial. Do not rename it.\n"
        "3. MASTERY: A move is MASTERED after 1 successful trial. Only mastered moves can be used in chains.\n"
        "4. CHAINS: You can only create 'chain NAME = a, b' if 'a' and 'b' are already in your MASTERED_MOVES list.\n"
        "5. DIAGNOSE: Use the physical diagnostics from the previous round to refine your motor rotations.\n"
        "\n"
        + _WORLD_RULES + "\n"
        + _OFFICIAL_BODY_STRUCTURE + "\n"
        + _DECISION_PRIORITIES + "\n"
        + _POSITION_VOCABULARY + "\n"
        + _MOTOR_RULES + "\n"
        + _format_round_summaries(round_summaries, "Practice")
    )


def fight_system(info, round_summaries=None, me="A"):
    """System prompt for Fight Mode (Execution of Mastered Skills)."""
    return (
        f"ROLE: You are Fighter {me} in FIGHT MODE.\n"
        "OBJECTIVE: Defeat the opponent using your MASTERED MOVES and CHAINS.\n"
        "\n"
        "FIGHT EXECUTION RULES:\n"
        "1. USE 'DO': Execute saved moves and chains using 'do NAME'.\n"
        "2. PRIORITIZE: Use moves marked as MASTERED for maximum reliability.\n"
        "3. NO CREATION: Do not create new moves or chains during a fight. Focus on tactical timing and selection.\n"
        "\n"
        + _WORLD_RULES + "\n"
        + _OFFICIAL_BODY_STRUCTURE + "\n"
        + _DECISION_PRIORITIES + "\n"
        + _POSITION_VOCABULARY + "\n"
        + _MOTOR_RULES + "\n"
        + _format_round_summaries(round_summaries, f"Fight (Fighter {me})")
    )


def round_summary_system():
    """System prompt for end-of-round summary generation with self-assessment."""
    return (
        "You are an expert combat analyst and judge. Review the chronological 20-word interval descriptions and the FINAL PHYSICAL STATE REPORT from your completed round.\n"
        "Write a concise 3-part summary:\n"
        "1. WHAT I DID - actions and results.\n"
        "2. WHAT I FAILED AT - mistakes or missed opportunities.\n"
        "3. WHAT I SHOULD HAVE DONE - better response or adjustments.\n\n"
        "CRITICAL SELF-ASSESSMENT:\n"
        "After your summary, evaluate if you met your goal based on the physical report data.\n"
        "Conclude your response with exactly one of the following lines:\n"
        "RESULT: SUCCESS (if physical criteria were met)\n"
        "RESULT: FAILED (if physical criteria were not met)\n"
        "Keep the summary concise and direct."
    )


def round_summary_user(interval_descriptions, physical_report=""):
    """User prompt providing interval descriptions and physical telemetry."""
    lines = ["Here are your chronological interval descriptions:"]
    for i, desc in enumerate(interval_descriptions, 1):
        lines.append(f"Interval {i}: {desc}")
    
    if physical_report:
        lines.append("\n" + physical_report)
        
    lines.append("\nWrite your 3-part summary and final RESULT judgment now.")
    return "\n".join(lines)

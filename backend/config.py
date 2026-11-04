"""CONFIG: constants only. No functions, no logic. Every other file reads these numbers."""
FPS = 30
DT = 1.0 / FPS
LIVE_FPS = 7
LIVE_DT = 1.0 / LIVE_FPS
SUBSTEPS = 8          # physics steps per frame (1 = exactly one step per frame)
ITERS = 8             # link/contact solver passes per physics step
G = 9.81
IRON, WOOD = 0, 1
DENSITY = (7000.0, 600.0)
MU = (0.5, 0.4)       # friction per material
REST = (0.5, 0.4)     # bounce per material
GROUND = (0.6, 0.4)   # (friction, bounce)
WALLM = (0.5, 0.4)
WOOD_J_PER_CM3 = 0.18
HEAD_NECK_J = 32.0
IRON_ON_WOOD = 1.5
ARENA_R, WALL_H, WALL_T = 5.0, 0.5, 0.2
OUT_SECONDS = 10.0
FIGHT_SECONDS = 60.0
PRACTICE_SECONDS = 180.0
HOLD_POWER = 0.35     # pose-holding strength until the AI commands a motor
MUSCLE_W, MUSCLE_Z = 25.0, 1.0
MAX_JOINT_SPEED = 25.0
REACHED = 0.12        # a step counts as done when its motors are this close (limb-length fractions)
DAMAGE_MIN_SPEED = 0.3
BOUNCE_MIN_SPEED = 0.5

# ---- AI providers (from dev.meta.ai/docs and baseten.co/library/muse-spark-open) ----
PROVIDERS = {
    "meta":         dict(base="https://api.meta.ai/v1", model="muse-spark-1.3", key_env="MODEL_API_KEY", effort=True, role="system", endpoint="/responses"),
    "meta_contrib": dict(base="https://api.meta.ai/v1", model="muse-spark-1.3-contributor", key_env="MODEL_API_KEY", effort=True, role="system", endpoint="/responses"),
    "baseten":      dict(base="https://inference.baseten.co/v1", model="meta-models/muse-spark-open-1026", key_env="BASETEN_API_KEY", effort=False, role="developer", endpoint="/chat/completions"),
}
EFFORTS = ("minimal", "low", "medium", "high", "xhigh", "max")   # "none" is rejected by Muse Spark (HTTP 400)
PRACTICE_EFFORT, FIGHT_EFFORT, NOTE_EFFORT = "high", "minimal", "low"
PRACTICE_MAX_TOKENS, FIGHT_MAX_TOKENS, NOTE_MAX_TOKENS = 6000, 1500, 800   # reasoning + visible text together
NOTE_MAX_CHARS = 800      # about 200 tokens

# ---- Round durations (minutes in UI, converted to seconds server-side) ----
MIN_DURATION_MINUTES = 0.2     # 12 seconds minimum
MAX_DURATION_MINUTES = 30.0    # 30 minutes maximum
DEFAULT_PRACTICE_MINUTES = 3.0 # 180 seconds
DEFAULT_FIGHT_MINUTES = 1.0    # 60 seconds

# ---- 42-WORD POSITION VOCABULARY ----
H_DIR_WORDS = {
    0: "FRONT",
    15: "FRONT SLIGHT RIGHT",
    30: "FRONT RIGHT",
    45: "FRONT DIAGONAL RIGHT",
    60: "RIGHT DIAGONAL FRONT",
    75: "RIGHT SLIGHT FRONT",
    90: "RIGHT",
    105: "RIGHT SLIGHT BACK",
    120: "RIGHT DIAGONAL BACK",
    135: "RIGHT BACK",
    150: "BACK DIAGONAL RIGHT",
    165: "BACK SLIGHT RIGHT",
    180: "BACK",
    195: "BACK SLIGHT LEFT",
    210: "BACK DIAGONAL LEFT",
    225: "BACK LEFT",
    240: "LEFT DIAGONAL BACK",
    255: "LEFT SLIGHT BACK",
    270: "LEFT",
    285: "LEFT SLIGHT FRONT",
    300: "LEFT DIAGONAL FRONT",
    315: "LEFT FRONT",
    330: "FRONT DIAGONAL LEFT",
    345: "FRONT SLIGHT LEFT",
}

V_DIR_WORDS = {
    90: "STRAIGHT UP",
    75: "NEAR UP",
    60: "HIGH UP",
    45: "DIAGONAL UP",
    30: "UPPER",
    15: "SLIGHT UPPER",
    0: "LEVEL",
    -15: "SLIGHT LOWER",
    -30: "LOWER",
    -45: "DIAGONAL DOWN",
    -60: "LOW DOWN",
    -75: "NEAR DOWN",
    -90: "STRAIGHT DOWN",
}

# Distance bands measured directly from CHEST CENTER.
# VERY-CLOSE: 0.00 - 0.10, CLOSE: 0.10 - 0.25, MID: 0.25 - 0.45, FAR: 0.45 - 0.70, VERY-FAR: > 0.70
DIST_THRESHOLDS = [0.10, 0.25, 0.45, 0.70]
DIST_WORDS = ["VERY-CLOSE", "CLOSE", "MID", "FAR", "VERY-FAR"]

# Representative distances for decoding
DIST_REPRESENTATIVE = {
    "VERY-CLOSE": 0.05,
    "CLOSE": 0.175,
    "MID": 0.35,
    "FAR": 0.575,
    "VERY-FAR": 0.85, # Representative for VERY-FAR (will be checked for reachability)
}

CHEST_BALL_RADIUS = 0.092


"""Global tuning constants for Yoonario."""

# --- Display ---
TILE = 16
VIEW_W, VIEW_H = 320, 240          # logical resolution
SCALE = 3                          # window = logical * SCALE
FPS = 60
DT = 1.0 / FPS

# --- Physics (px/sec, px/sec^2) ---
GRAVITY = 1500.0
MAX_FALL = 420.0
JUMP_VEL = -335.0                  # initial jump velocity
JUMP_CUT = 0.45                    # velocity multiplier when jump released early
JUMP_HOLD_GRAV = 0.52              # gravity multiplier while holding jump & rising
COYOTE_TIME = 0.08                 # seconds of grace after leaving a ledge
JUMP_BUFFER = 0.12                 # seconds a jump press is remembered

WALK_SPEED = 105.0
RUN_SPEED = 165.0
ACCEL = 620.0
AIR_ACCEL = 480.0
FRICTION = 780.0
ICE_FRICTION = 130.0
STOMP_BOUNCE = -230.0
STOMP_BOUNCE_HELD = -330.0         # bounce if jump held during stomp

# --- Player ---
SMALL_W, SMALL_H = 11, 14
BIG_W, BIG_H = 11, 27
HURT_INVULN = 2.0                  # seconds of invulnerability after being hit
RESPAWN_DELAY = 2.5                # seconds before respawn
SPAWN_INVULN = 2.0

# Character stat multipliers: (speed, jump, accel, gravity)
CHARACTERS = [
    {"name": "Yoonario", "color": "red",    "speed": 1.00, "jump": 1.00, "accel": 1.00, "grav": 1.00},
    {"name": "Luna",     "color": "green",  "speed": 0.97, "jump": 1.09, "accel": 0.85, "grav": 1.00},
    {"name": "Dash",     "color": "blue",   "speed": 1.14, "jump": 0.98, "accel": 1.15, "grav": 1.05},
    {"name": "Pip",      "color": "yellow", "speed": 0.93, "jump": 1.00, "accel": 1.00, "grav": 0.86},
]

# --- Enemies ---
GRUB_SPEED = 28.0
SHELL_WALK_SPEED = 24.0
SHELL_SLIDE_SPEED = 200.0
SPINY_SPEED = 32.0
FLIT_SPEED = 40.0
FLIT_AMP = 24.0                    # sine amplitude (px)
PLANT_PERIOD = 3.2                 # seconds per emerge cycle
FIREBALL_SPEED = 210.0
FIREBALL_BOUNCE = -160.0
BOSS_HP = 3

# --- Scoring ---
SCORE_COIN = 100
SCORE_STOMP = 200
SCORE_KICK = 200
SCORE_FIREBALL_KILL = 200
SCORE_POWERUP = 1000
SCORE_1UP = 2000
SCORE_FLAG_BASE = 2000
SCORE_BOSS = 5000
LEVEL_TIME = 300                   # countdown; grants bonus score, never kills

# --- Networking ---
NET_PORT = 26501
SNAP_RATE = 30                     # host snapshot Hz
PSTATE_RATE = 30                   # client player-state send Hz
INTERP_DELAY = 0.1                 # seconds of interpolation buffer
NET_TIMEOUT = 6.0                  # drop peer after silence
MAX_PLAYERS = 4
PROTOCOL_VERSION = 1

"""Dark Cloud 2 (Dark Chronicle) memory addresses.
Game ID: SCUS-97213 (US)

Addresses derived from Ghidra disassembly of the SCUS_972.13 ELF.
gp = 0x0037E4F0, PINE base = 0x20000000.
"""


class Mode:
    """LoopNo values — the main game loop state."""
    EXIT = 0
    DUNGEON = 1
    TOWN = 2
    TITLE = 3       # Title screen / startup


# --- Game detection ---
DC2_GAME_ID = "SCUS-97213"

# --- Core game state ---
LOOP_NO = 0x20376FCC               # Main game loop state (0=exit, 1=dungeon, 2=town, 3=title)
NEXT_LOOP_NO = 0x20376FD0          # Next loop to transition to
NOW_MODE = 0x2037875C               # Sub-mode within current loop (battle mode etc)
MENU_MODE = 0x20377000              # Menu system state
PAUSE_FLAG = 0x20377188             # Pause state
PAUSE_MENU_MODE = 0x20377044        # Pause menu sub-mode
BATTLE_FLAG = 0x2037874C            # In battle
BATTLE_COUNT = 0x20378534           # Battle counter
PLAY_TIME_COUNT = 0x203786B8        # Play time counter
WINDOW_MODE = 0x20378818            # Window/dialog mode
VIEW_MODE = 0x203770B0              # Camera view mode

# --- Character ---
ACTIVE_CHARA_NO = 0x2037715C        # Active character (0=Max, 1=Monica)
CONTROL_CHARA_ID = 0x20377160       # Controlled character ID
CONTROL_MODE = 0x20377170           # Control mode
CHARA_MODE = 0x203784D0             # Character mode
CHARA_STATUS = 0x203787D0           # Character status flags
MAIN_CHARA = 0x203772C8             # Main character pointer
BUGGY_HP = 0x203787DC               # Ridepod HP (float)

# --- Save data ---
# SaveData base is at 0x21E01810 (static)
# ActiveSaveData is a pointer to the current save data
SAVE_DATA_BASE = 0x21E01810
ACTIVE_SAVE_DATA_PTR = 0x20376FE4   # Pointer to active save data

# Save data structure offsets (from SaveData base):
#   +0x1a08  = chapter / game progression state
#   +0x1a10  = time of day (float)
#   +0x1a14  = weather/time value
#   +0x1c574 = config data
#   +0x1c578 = vibration setting
#   +0x1c5b4 = CSaveDataDungeon
#   +0x1d2a0 = CUserDataManager

# CUserDataManager offsets (from UserDataManager base):
#   +0x3f48          = Max character data (CCharaData, 0x38c bytes per character)
#   +0x3f48 + 0x38c  = Monica character data
#   +0x4680          = Ridepod data
#   +0x44d9c         = Gilda (int32, max 999,999)

# Absolute addresses (SaveData + offsets):
CHAPTER = 0x21E03218                # SaveData + 0x1a08
TIME_OF_DAY = 0x21E03220            # SaveData + 0x1a10
GILDA = 0x21E6384C                  # SaveData + 0x1d2a0 + 0x44d9c
CONFIG_DATA = 0x21E1DD84            # SaveData + 0x1c574
VIBRATION = 0x21E1DD88              # SaveData + 0x1c578

# Character data absolute addresses:
MAX_CHARA_DATA = 0x21E20A58         # SaveData + 0x1d2a0 + 0x3f48
MONICA_CHARA_DATA = 0x21E20DE4      # SaveData + 0x1d2a0 + 0x3f48 + 0x38c
RIDEPOD_DATA = 0x21E21B90           # SaveData + 0x1d2a0 + 0x4680

# --- Dungeon ---
DNG_SAVE_DATA_PTR = 0x20377294      # Pointer to dungeon save data
DNG_SAVE_DATA_DNG_PTR = 0x20377298  # Pointer to CSaveDataDungeon
DNG_STATUS = 0x21E9F6E0             # Dungeon status
NOW_FLOOR_INFO_PTR = 0x20377278     # Pointer to current floor info
ACTIVE_MONSTER_PTR = 0x203772A8     # Pointer to active monster

# Floor info structure (0x14 bytes per floor):
#   +0x00 = floor flags
#   +0x0e = medal/condition flags (bitmask)
#   +0x10 = kill count (short)

# --- Shop ---
NOW_SHOP_ID = 0x20377D44            # Current shop ID
NOW_SELL_MODE = 0x20377D2C          # Sell mode
SHOP_MODE_PREV = 0x20377D4C         # Previous shop mode

# --- Mod flags (runtime — above _end at 0x21F64E00, not in save data) ---
PNACH_FLAG = 0x21F70020             # 1 if PNACH active (set by PNACH)
MOD_FLAG = 0x21F70024               # 1 if Python mod is running (set by mod)
FAST_START_FLAG = 0x21F70028         # 1 if fast start enabled (set by mod)
WIDESCREEN_FLAG = 0x21F7002C         # 1 if widescreen enabled (set by mod)
DIALOG_FLAG = 0x21F70030             # Write message ID here to trigger dialog

# --- Mod flags (in save data — persisted in save file) ---
# Using unused tail of save data: SaveData + 0x62900 = 0x21E64110
# Save data is 0x65930 bytes, game uses up to ~0x62840, so 0x62900+ is safe
_MOD_SAVE_BASE = 0x21E64110
ENHANCED_MOD_SAVE_FLAG = _MOD_SAVE_BASE + 0x00   # 1 = Reforged save file
MOD_SAVE_VERSION = _MOD_SAVE_BASE + 0x01         # Mod version byte
OPTION_SAVE_RUN_SPEED = _MOD_SAVE_BASE + 0x02    # Index into SPEED_OPTIONS (town)
OPTION_SAVE_PICKUP_RADIUS = _MOD_SAVE_BASE + 0x03  # Index into PICKUP_RADIUS_OPTIONS
OPTION_SAVE_MAP_POS = _MOD_SAVE_BASE + 0x04        # Index into MINIMAP_POS_OPTIONS
OPTION_SAVE_MAP_POS_TARGET = _MOD_SAVE_BASE + 0x05 # Index into MINIMAP_POS_OPTIONS (when targeting)
OPTION_SAVE_DNG_SPEED = _MOD_SAVE_BASE + 0x06      # Index into SPEED_DNG_OPTIONS
# Reserve _MOD_SAVE_BASE + 0x07 through +0xFF for future mod options

# --- Title screen ---
TITLE_INFO_PTR = 0x20377E6C         # Pointer to TitleInfo struct
TITLE_PHASE = 0x20377E98            # TitlePhase (16-bit)

# --- Misc systems ---
SPHIDA_SCORE = 0x20378008           # Spheda score
GEO_REQUEST_FLAG = 0x203774E0       # Georama request flag
QUEST_MAN = 0x20377D84              # Quest manager
MONSTER_BOOK_PTR = 0x20378124       # Monster book pointer
ACTIVE_SLOT = 0x20377660            # Active save slot

# --- Character names ---
CHARACTER_NAMES = {0: "Max", 1: "Monica"}

# --- Dungeon names ---
DUNGEON_NAMES = {
    0: "Underground Water Channel",
    1: "Rainbow Butterfly Wood",
    2: "Starlight Canyon",
    3: "Ocean's Roar Cave",
    4: "Mount Gundor",
    5: "Moon Flower Palace",
    6: "Zelmite Mine",
}

# --- Town/area names ---
TOWN_NAMES = {
    0: "Palm Brinks",
    1: "Sindain",
    2: "Balance Valley",
    3: "Veniccio",
    4: "Heim Rada",
    5: "Moon Flower Palace",
}

# --- Gamepad (CGamePad at 0x3D76E0) ---
GAMEPAD = 0x203D76E0
GAMEPAD_BUTTONS = 0x203D76E4        # +0x04: current button bitmask
GAMEPAD_PREV_BUTTONS = 0x203D777C   # +0x9C: previous frame buttons
GAMEPAD_MENU_LOCK = 0x203D7B3C      # +0x45C: menu mode lock (0=unlocked)
LOCK_CHARA = 0x2037718C             # LockChara counter (>0 = player frozen)

class Pad:
    """PS2 gamepad button bitmasks (from CGamePad +0x04)."""
    TRIANGLE = 0x0010
    O        = 0x0020
    X        = 0x0040
    SQUARE   = 0x0080
    UP       = 0x1000
    RIGHT    = 0x2000
    DOWN     = 0x4000
    LEFT     = 0x8000

# --- Dialog system ---
# Town: CharaControl multiplies analog input by frameRate * 5.0
# The 5.0 is loaded via `lui` at these addresses:
SPEED_INSTR_MAIN = 0x201a58e0       # CharaControl (town) — lui v0, 0x40a0
# TODO: Dungeon speed uses a different movement system (LoopMode==0).
# Tried: patching 0x20314B00 (wrong function), action_info+0x794 (script speed, no effect).
# The dungeon character movement is driven by CActionChara::RunScript → CollisionCheck.
# Solution: PNACH cave hooks CollisionCheck to scale velocity. Python patches lui instruction.
SPEED_INSTR_DNG = 0x21F70780        # lui v0, imm in dungeon speed cave (patched by Python)

SPEED_DNG_OPTIONS = {
    "1x (Default)": 0x3F80,   # 1.0
    "1.5x":         0x3FC0,   # 1.5
    "1.75x":        0x3FE0,   # 1.75
    "2x":           0x4000,   # 2.0
    "2.25x":        0x4010,   # 2.25
    "2.5x":         0x4020,   # 2.5
    "2.75x":        0x4030,   # 2.75
    "3x":           0x4040,   # 3.0
}

# lui opcode: 0x3C02XXYY where XXYY = upper 16 bits of float
# Only floats with lower 16 bits == 0 work cleanly
SPEED_OPTIONS = {
    "1x (Default)": 0x40a0,   # 5.0
    "1.5x":         0x40f0,   # 7.5
    "1.75x":        0x410c,   # 8.75
    "2x":           0x4120,   # 10.0
    "2.25x":        0x4134,   # 11.25
    "2.5x":         0x4148,   # 12.5
    "2.75x":        0x415c,   # 13.75
    "3x":           0x4170,   # 15.0
}

def speed_lui(upper16):
    """Build the full lui v0, imm instruction word (town)."""
    return 0x3C020000 | upper16

# --- Pickup radius ---
# IsGet__9CPullItemFPf compares distance < field_0x5c * 20.0
# The 20.0 is loaded via `lui v1, 0x41a0` at this address:
PICKUP_RADIUS_INSTR = 0x201b9144

PICKUP_RADIUS_OPTIONS = {
    "1x (Default)": 0x41a0,   # 20.0
    "2x":           0x4220,   # 40.0
    "3x":           0x4270,   # 60.0
    "5x":           0x42c8,   # 100.0
}

def pickup_radius_lui(upper16):
    """Build the full lui v1, imm instruction word."""
    return 0x3C030000 | upper16

# --- Large map position ---
# Mode 2 (large map) X/Y are set by `li` instructions before Draw__14CMiniMapSymbolFPf.
# Three call sites write these values every frame. We patch the `li` immediate.
# Format: addiu reg, zero, imm16 → 0x2402XXYY (v0) or 0x2403XXYY (v1)
# Site 1: main dungeon draw
MINIMAP_LG_X1 = 0x201D0360   # li v0, 0x150  (X)
MINIMAP_LG_Y1 = 0x201D036C   # li v1, 0xd4   (Y)
# Site 2: Sphida draw (different defaults: X=0x100, Y=0xe6)
MINIMAP_LG_X2 = 0x202EB864   # li v1, 0x100  (X)
MINIMAP_LG_Y2 = 0x202EB870   # li v0, 0xe6   (Y)
# Site 3: other dungeon draw
MINIMAP_LG_X3 = 0x202EBB84   # li v0, 0x150  (X)
MINIMAP_LG_Y3 = 0x202EBB90   # li v1, 0xd4   (Y)

# Default large map: X=0x150(336), Y=0xD4(212), W=0x140(320), H=0x118(280)
# Screen is 512x448. Map center (X,Y) with scissor at (X-W/2, Y-H/2).
# Options shift X,Y to reposition. Sphida offsets are adjusted proportionally.
MINIMAP_POS_OPTIONS = {
    "Center (Default)": (0x150, 0xD4, 0x100, 0xE6),  # (site1/3 X, site1/3 Y, site2 X, site2 Y)
    "Top-Right":        (0x1C0, 0x8C, 0x170, 0x9E),
    "Top-Left":         (0xA0,  0x8C, 0x050, 0x9E),
    "Center-Left":      (0xB0,  0xD4, 0x060, 0xE6),
    "Center-Right":     (0x1F0, 0xD4, 0x1A0, 0xE6),
    "Bottom-Right":     (0x1C0, 0x118, 0x170, 0x12A),
}

# --- Lock-on targeting ---
# MainChara is a pointer; *(MainChara) + 0x772 is a short: 0 = not locked on, non-zero = locked on
LOCKON_OFFSET = 0x772

# --- Options menu extension ---
CMENU_OPTION_PTR = 0x203781B0          # Pointer to CMenuOption object (valid when options screen open)
OPTION_BUTTON_FORM = 0x20378198        # Pointer to OptionButtonForm (button sprites form)
MENU_COMMON_INFO = 0x203779E8          # Pointer to MenuCommonInfo (menu state struct)
CONFIG_OPTION_NUM_I = 0x203769F8       # Float: number of navigable option rows
CONFIG_OPTION_NUM_F = 0x203769FC       # Float: same (used by different code paths)

# --- Dialog system ---
DIALOG_MODE = 0x21F70038            # Window mode for next dialog (0/4=passive, 5=interactive)
DIALOG_ACTIVE = 0x21F7003C          # 1=dialog showing (managed by cave)
SYSTEM_MESSAGE_0 = 0x21E94AC0       # ClsMes object for SystemMessage slot 0
SYS_MES_BUFFER = 0x21E81240         # SysMesBuffer (message table, 365 entries)
MSG_0x81B1_TEXT = 0x21E87EEE        # Text address for msg 0x81B1 (last entry, safe to overwrite)

# --- HUD overlay ---
HUD_FLAG = 0x21F70040               # 1=draw HUD overlay (set by Python)
HUD_LINE_COUNT = 0x21F70044         # Number of lines to draw (max 6)

# --- Auto repair powder ---
AUTO_REPAIR_FLAG = 0x21F70048       # 1=auto-repair enabled (set by Python)
REPAIR_CONSUMED = 0x21F7004C        # Set by PNACH cave: 1=melee powder used, 2=ranged powder used

# --- Auto key (dungeon door) ---
AUTO_KEY_FLAG = 0x21F70050          # 1=auto-key enabled (set by Python)
KEY_CONSUMED = 0x21F70054           # Set by PNACH cave: box_index+1 when key used (0=none)

# Inventory: UserDataManager = SaveData + 0x1D2A0 = 0x21E1EAB0
# 150 slots of 0x6C bytes. Per slot: +0x00=type(short), +0x02=itemID(short), +0x10=count(short)
USER_DATA_MANAGER = 0x21E1EAB0
INVENTORY_SLOT_SIZE = 0x6C
INVENTORY_SLOT_COUNT = 150

# Repair powder item IDs (from GetEnableRepairItemNo)
REPAIR_POWDER_MELEE = 0x126         # Repair Powder (weapon sub-types 1,3,0xD)
REPAIR_POWDER_RANGED = 0x12A        # Gun Repair Powder (weapon sub-type 2)
HUD_TEXT_BASE = 0x21F70A00          # Text lines, 64 bytes each (6 lines max)
HUD_LINE_LEN = 64                   # Max bytes per line (including null)

# Floor info pointers (set by game when on a dungeon floor)
DNG_INFO_FLOOR_INFO = 0x203773C0    # Ptr to current floor save data (medal flags etc)
DNG_INFO_ROOM_INFO = 0x203773C4     # Ptr to current floor static data (requirements)

# --- Dungeon scene ---
DNG_MAIN_SCENE = 0x2037729C         # Pointer to DngMainScene (CScene)
# Event ClsMes: *(DngMainScene + 0x2240)  (GetSceneMessage(scene,0) + 0x34)
_SCENE_MSG_CLSMES_OFFSET = 0x2240   # scene + 0x220C + 0x34

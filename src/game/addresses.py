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

# --- Mod flags (in save data — persisted in save file) ---
# Using unused tail of save data: SaveData + 0x62900 = 0x21E64110
# Save data is 0x65930 bytes, game uses up to ~0x62840, so 0x62900+ is safe
_MOD_SAVE_BASE = 0x21E64110
ENHANCED_MOD_SAVE_FLAG = _MOD_SAVE_BASE + 0x00   # 1 = Reforged save file
MOD_SAVE_VERSION = _MOD_SAVE_BASE + 0x01         # Mod version byte
# Reserve _MOD_SAVE_BASE + 0x02 through +0xFF for future mod options

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

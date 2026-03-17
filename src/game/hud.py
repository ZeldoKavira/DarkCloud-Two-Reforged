"""HUD overlay — writes dungeon floor requirement text to mod memory for PNACH rendering."""

import logging
from core.memory import Memory
from core import settings
from game import addresses as addr

log = logging.getLogger(__name__)

_MEDAL_TIME = 0x10
_MEDAL_SPHIDA = 0x80
_MEDAL_CHALLENGE = 0x08

_PINE = 0x20000000
_TREE_DNGMAP = 0x2037843C
_BATTLE_SCENE = 0x203772A0

_CONDITION_LABELS = {
    0: "Defeat all",
    1: "Attack with Max only",
    2: "Attack with specific weapon",
    3: "Attack with Monica only",
    4: "Attack with Monster only",
    5: "Clear without healing",
    6: "Attack with Wrench only",
    7: "Attack with Gun only",
    8: "Attack with Sword only",
    9: "Attack with Armband only",
    10: "Attack with Ridepod only",
    11: "Attack with Items only",
}

_VIOLATION_MASK = {
    0: 0,
    1: 0x79,   # Max only: forbid Monica+Monster+Items+Ridepod
    2: 0x79,
    3: 0x67,   # Monica only: forbid Ridepod+Melee+Max+Items+Monster
    4: 0x5F,   # Monster only: forbid everything except 0x20
    5: 0x80,   # No healing
    10: 0x7E,  # Ridepod only: forbid everything except 0x01
    11: 0x3F,  # Items only: forbid everything except 0x40
}

# Per-floor session state
_start_kills = None
_last_floor_ptr = None
_frozen_time = None


def _get_floor_info(mem):
    tree = mem.read_int(_TREE_DNGMAP)
    if tree == 0:
        return None
    tree = _PINE + tree
    dng_save = mem.read_int(addr.DNG_SAVE_DATA_DNG_PTR)
    if dng_save == 0:
        return None
    dng_save = _PINE + dng_save
    idx = mem.read_int(dng_save)
    floor_id = mem.read_int(dng_save + (idx + 1) * 4) & 0xFF
    grid = mem.read_int(tree + 4)
    if grid == 0:
        return None
    grid = _PINE + grid
    count = mem.read_int(tree + 8)
    for i in range(min(count, 200)):
        entry = grid + i * 0x70
        if mem.read_short(entry) == 1 and mem.read_byte(entry + 0x28) == floor_id:
            return entry + 0x20
    return None


def write_hud(mem, loop_no):
    global _start_kills, _last_floor_ptr, _frozen_time

    if loop_no not in (addr.Mode.DUNGEON, addr.Mode.TOWN):
        mem.write_int(addr.HUD_FLAG, 0)
        _clear_synth(mem)
        _last_floor_ptr = None
        return

    ptr = mem.read_int(addr.NOW_FLOOR_INFO_PTR)
    if ptr == 0:
        mem.write_int(addr.HUD_FLAG, 0)
        _last_floor_ptr = None
        return
    ptr = _PINE + ptr

    medal_flags = mem.read_short(ptr + 0x0E)
    kill_count = mem.read_short(ptr + 0x10)

    # Track per-session kills: reset when floor changes
    if ptr != _last_floor_ptr:
        _start_kills = kill_count
        _last_floor_ptr = ptr
        _frozen_time = None

    session_kills = kill_count - _start_kills

    active_mon = mem.read_int(addr.ACTIVE_MONSTER_PTR)
    total = 0
    if active_mon != 0:
        total = mem.read_int(_PINE + active_mon + 0xFFF4)

    # Static floor data
    cond_label = "Floor Goal"
    time_limit = 0
    cond_type_id = -1
    room = _get_floor_info(mem)
    if room:
        cond_type = mem.read_byte(room + 0x1a)
        cond_param = mem.read_int(room + 0x1c)
        if cond_type == 2 and 1 <= cond_param <= 4:
            cond_type_id = cond_param + 5
        elif cond_type == 3 and cond_param == 5:
            cond_type_id = 10  # Ridepod only
        elif cond_type == 1 and cond_param == 0:
            cond_type_id = 11  # Items only
        else:
            cond_type_id = cond_type
        cond_label = _CONDITION_LABELS.get(cond_type_id, f"Condition {cond_type_id}")
        time_limit = mem.read_int(room + 0x10)

    # Battle scene
    battle_ptr = mem.read_int(_BATTLE_SCENE)
    elapsed = 0
    usage = 0
    all_dead = False
    if battle_ptr != 0:
        battle_ptr = _PINE + battle_ptr
        play_time = mem.read_int(addr.SAVE_DATA_BASE + 0x1a00)
        start_time = mem.read_int(battle_ptr + 0x90)
        elapsed = play_time - start_time
        if elapsed < 0 or elapsed > 360000:  # negative or >100 min = stale start_time
            elapsed = 0
        usage = mem.read_int(battle_ptr + 0x98)
        all_dead = mem.read_int(battle_ptr + 0x5c) == 1

    # Freeze timer when all dead
    if all_dead and _frozen_time is None:
        _frozen_time = elapsed
    display_time = _frozen_time if _frozen_time is not None else elapsed

    lines = []

    # Kills
    k_mark = "* " if all_dead else "- "
    lines.append(f"{k_mark}Kills: {session_kills}/{total}")

    # Time Attack
    m = "* " if medal_flags & _MEDAL_TIME else "- "
    e_sec = display_time // 60
    e_m, e_s = divmod(e_sec, 60)
    if time_limit > 0:
        tl_sec = time_limit // 60
        tl_m, tl_s = divmod(tl_sec, 60)
        if all_dead and e_sec <= tl_sec:
            lines.append(f"{m}Time Attack: {e_m}:{e_s:02d} / {tl_m}:{tl_s:02d} CLEAR")
        elif not all_dead and e_sec > tl_sec:
            lines.append(f"{m}Time Attack: {e_m}:{e_s:02d} / {tl_m}:{tl_s:02d} FAILED")
        else:
            lines.append(f"{m}Time Attack: {e_m}:{e_s:02d} / {tl_m}:{tl_s:02d}")
    else:
        lines.append(f"{m}Time Attack: {e_m}:{e_s:02d}")

    # Sphida
    m = "* " if medal_flags & _MEDAL_SPHIDA else "- "
    lines.append(f"{m}Sphida")

    # Floor condition
    m = "* " if medal_flags & _MEDAL_CHALLENGE else "- "
    mask = _VIOLATION_MASK.get(cond_type_id if cond_type_id >= 0 else -1, 0)
    violated = mask != 0 and (usage & mask) != 0
    if violated:
        lines.append(f"{m}{cond_label} FAILED")
    else:
        lines.append(f"{m}{cond_label}")

    _write_lines(mem, lines)
    if settings.get("synth_hud") is not False:
        _write_synth(mem)
    else:
        _clear_synth(mem)


def _write_lines(mem, lines):
    for i, line in enumerate(lines[:6]):
        raw = line.encode("ascii", errors="replace")[:addr.HUD_LINE_LEN - 1] + b"\x00"
        raw = raw.ljust(addr.HUD_LINE_LEN, b"\x00")
        base = addr.HUD_TEXT_BASE + i * addr.HUD_LINE_LEN
        for j in range(0, len(raw), 4):
            word = int.from_bytes(raw[j:j+4], "little")
            mem.write_int(base + j, word)
    mem.write_int(addr.HUD_LINE_COUNT, len(lines))
    mem.write_int(addr.HUD_FLAG, 1)


def _write_synth_str(mem, pine_addr, s):
    raw = s.encode("ascii")[:15] + b"\x00"
    raw = raw.ljust(16, b"\x00")
    for i in range(0, 16, 4):
        word = int.from_bytes(raw[i:i+4], "little")
        mem.write_int(pine_addr + i, word)


def _clear_synth(mem):
    _write_synth_str(mem, addr.SYNTH_STR_MELEE, "")
    _write_synth_str(mem, addr.SYNTH_STR_RANGED, "")


def _write_synth(mem):
    # Only draw when the game's own HUD is visible (BattleAreaScene+0x48 != 0)
    scene_ptr = mem.read_int(_BATTLE_SCENE)
    if scene_ptr == 0:
        _clear_synth(mem)
        return
    if mem.read_byte(_PINE + scene_ptr + 0x48) == 0:
        _clear_synth(mem)
        return
    mode = mem.read_short(addr.BATTLE_PARAMATER + 0x06)
    if mode != 0:
        _clear_synth(mem)
        return
    base_ptr = mem.read_int(addr.BATTLE_PARAMATER + 0x30)
    if base_ptr == 0:
        _clear_synth(mem)
        return
    base = _PINE + base_ptr
    for slot, str_addr in enumerate((addr.SYNTH_STR_MELEE, addr.SYNTH_STR_RANGED)):
        off = slot * addr.WEAPON_SLOT_SIZE
        item_id = mem.read_short(base + off + 0x02)
        if item_id == 0 or item_id == 0xFFFF:
            _write_synth_str(mem, str_addr, "")
            continue
        synth_pts = mem.read_short(base + off + 0x3C)
        if synth_pts <= 0:
            _write_synth_str(mem, str_addr, "")
            continue
        _write_synth_str(mem, str_addr, f"+{synth_pts}")

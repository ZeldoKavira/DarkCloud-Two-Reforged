"""Fishing HUD — shows fishing state when fishing is active."""

import logging
import struct as _struct
from core.memory import Memory
from game import addresses as addr

log = logging.getLogger(__name__)

_PINE = 0x20000000

_CHARA_MODES = {
    1: "Selecting cast point",
    2: "Casting...",
    3: "Waiting for bite...",
    5: "Fish on!",
    6: "Got away...",
    7: "Caught!",
}

_FISH_NAMES = [
    "Priscleen", "Bobo", "Gobbler", "Nonky", "Kaji", "Baku Baku",
    "Mardan Garayan", "Gummy", "Niler", "Umadakara", "Tarton", "Piccoly",
    "Bon", "Hama Hama", "Negie", "Den", "Heela", "Baron Garayan",
]

_PREF_TAG = {1: "+", 2: "++", 3: "+++"}

_FISH_DATA = 0x21F59D00
_GP = 0x0037E4F0
_FP_BASE = 0x2035D2B0
_FP_ENTRY = 0x54
_FP_BAIT_OFF = 0x28
_MEDAL_FISH = 0x20


def _get_bait_pref(mem, fish_idx, esa_no):
    if esa_no < 0 or esa_no > 17:
        return -1
    return mem.read_short(_FP_BASE + fish_idx * _FP_ENTRY + esa_no * 2 + _FP_BAIT_OFF)


def _get_pond_fish(mem):
    fpm_ptr = mem.read_int(_PINE + _GP - 0x5F0C)
    fpm_num = mem.read_int(_PINE + _GP - 0x5F10)
    if not fpm_ptr or fpm_num < 1:
        return []
    scene = mem.read_int(0x21F59E30)
    if not scene:
        return []
    map_no = mem.read_int(_PINE + scene + 0x2E58)
    pine_fpm = _PINE + fpm_ptr
    fish_set = set()
    for i in range(fpm_num):
        base = pine_fpm + i * 0x88
        entry_map = mem.read_int(base)
        if entry_map > 0x7FFFFFFF:
            entry_map -= 0x100000000
        if entry_map != -1 and entry_map != map_no:
            continue
        count = mem.read_int(base + 0x24)
        for j in range(min(count, 8)):
            ft = mem.read_int(base + 0x28 + j * 0xC)
            if ft < len(_FISH_NAMES):
                fish_set.add(ft)
    return sorted(fish_set)


def _get_fish_medal_info(mem, loop_no):
    """Return (needed, direction) or None if not in dungeon or already collected.
    direction > 0 means 'at least', < 0 means 'at most'. Size in cm."""
    if loop_no != addr.Mode.DUNGEON:
        return None
    from game.hud import _get_floor_info
    ptr = mem.read_int(addr.NOW_FLOOR_INFO_PTR)
    if not ptr:
        return None
    medal_flags = mem.read_short(_PINE + ptr + 0x0E)
    if medal_flags & _MEDAL_FISH:
        return None  # already collected
    room = _get_floor_info(mem)
    if not room:
        return None
    direction = mem.read_byte(room + 0x17)
    if direction > 127:
        direction -= 256
    if direction == 0:
        return None
    size_raw = mem.read_short(room + 0x18)
    return (size_raw / 100.0, direction)


_pond_cache = (None, [])


def write_fishing_hud(mem: Memory, loop_no):
    global _pond_cache
    if loop_no not in (addr.Mode.DUNGEON, addr.Mode.TOWN):
        return False

    fg_mode = mem.read_int(addr.FISHING_LOOP_MODE)
    if fg_mode == 0:
        return False

    chara_mode = mem.read_int(addr.FISHING_CHARA_MODE)
    mode_text = _CHARA_MODES.get(chara_mode, "")
    lines = [mode_text] if mode_text else ["Fishing"]

    if chara_mode in (5, 7):
        fish_type = mem.read_int(_FISH_DATA)
        if fish_type > 0x7FFFFFFF:
            fish_type -= 0x100000000
        idx = fish_type - 1
        name = _FISH_NAMES[idx] if 0 <= idx < len(_FISH_NAMES) else "???"
        raw_size = mem.read_int(_FISH_DATA + 4)
        size = _struct.unpack('f', _struct.pack('I', raw_size))[0]
        hp = mem.read_int(_FISH_DATA + 32)
        lines[0] = f"{name} {size:.1f}cm FP:{hp}"
    elif chara_mode in (0, 1, 2, 3):
        # Medal info
        medal = _get_fish_medal_info(mem, loop_no)
        if medal:
            sz, d = medal
            op = ">=" if d > 0 else "<="
            lines.append(f"Medal: {op} {sz:.0f}cm")

        # Pond fish list, one per line
        try:
            scene = mem.read_int(0x21F59E30)
            if _pond_cache[0] != scene:
                _pond_cache = (scene, _get_pond_fish(mem))
            pond = _pond_cache[1]
            if pond:
                esa_no = mem.read_int(_PINE + _GP - 0x6004)
                if esa_no > 0x7FFFFFFF:
                    esa_no -= 0x100000000
                for ft in pond:
                    if len(lines) >= 6:
                        break
                    name = _FISH_NAMES[ft]
                    pref = _get_bait_pref(mem, ft, esa_no)
                    tag = _PREF_TAG.get(pref, "")
                    lines.append(f"  {name} {tag}")
        except Exception:
            pass

    max_lines = min(len(lines), 6)
    for i in range(max_lines):
        raw = lines[i].encode("ascii", errors="replace")[:addr.HUD_LINE_LEN - 1] + b"\x00"
        raw = raw.ljust(addr.HUD_LINE_LEN, b"\x00")
        base = addr.HUD_TEXT_BASE + i * addr.HUD_LINE_LEN
        for j in range(0, len(raw), 4):
            word = int.from_bytes(raw[j:j+4], "little")
            mem.write_int(base + j, word)
    mem.write_int(addr.HUD_LINE_COUNT, max_lines)
    mem.write_int(addr.HUD_FLAG, 1)
    return True

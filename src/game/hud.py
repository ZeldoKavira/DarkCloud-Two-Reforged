"""HUD overlay — writes dungeon floor requirement text to mod memory for PNACH rendering."""

import logging
from core.memory import Memory
from core import settings
from game import addresses as addr

log = logging.getLogger(__name__)

_MEDAL_TIME = 0x10
_MEDAL_SPHIDA = 0x80
_MEDAL_CHALLENGE = 0x08
_MEDAL_FISH = 0x20

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
_last_start_time = None


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
    start_time = 0
    if battle_ptr != 0:
        battle_ptr = _PINE + battle_ptr
        play_time = mem.read_int(addr.SAVE_DATA_BASE + 0x1a00)
        start_time = mem.read_int(battle_ptr + 0x90)
        elapsed = play_time - start_time
        if elapsed < 0 or elapsed > 360000:  # negative or >100 min = stale start_time
            elapsed = 0
        usage = mem.read_int(battle_ptr + 0x98)
        all_dead = mem.read_int(battle_ptr + 0x5c) == 1

    # Reset frozen time when floor changes (detected by start_time changing)
    global _last_start_time
    if start_time != _last_start_time:
        _frozen_time = None
        _last_start_time = start_time

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

    # Fishing
    m = "* " if medal_flags & _MEDAL_FISH else "- "
    lines.append(f"{m}Fishing")

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


# --- Gift box (clown chest) HUD ---

_item_name_cache = {}


def _read_item_name(mem, item_id):
    """Read item name from game memory via the item data table."""
    if item_id <= 0 or item_id >= 0x200:
        return None
    if item_id in _item_name_cache:
        return _item_name_cache[item_id]
    try:
        # Read convert table entry
        idx = mem.read_short(addr.ITEM_CONVERT_TABLE + item_id * 2)
        if idx < 0:
            return None
        # Read base pointer
        base = mem.read_int(addr.GAME_DATA_BASE_PTR)
        if base == 0:
            return None
        # Entry = base + idx * 44, name pointer at +0x28
        entry = _PINE + base + idx * 44
        name_ptr = mem.read_int(entry + 0x28)
        if name_ptr == 0:
            return None
        # Read null-terminated string (up to 32 bytes)
        raw = b""
        for i in range(0, 32, 4):
            word = mem.read_int(_PINE + name_ptr + i)
            raw += word.to_bytes(4, "little")
            if b"\x00" in word.to_bytes(4, "little"):
                break
        name = raw.split(b"\x00")[0].decode("ascii", errors="replace")
        if name:
            _item_name_cache[item_id] = name
        return name or None
    except Exception:
        return None




_SCRIPT_VARS_PTR = addr.GIFT_BOX_SCRIPT_VARS

def write_gift_box_hud(mem, _unused):
    """Patch clown box dialog to show item names and guarantee chosen item."""
    if not settings.get("gift_box_hud"):
        return
    scene = mem.read_int(0x2037729C)
    if scene == 0:
        return
    msg_sys = mem.read_int(_PINE + scene + 0x2240)
    if msg_sys == 0:
        return
    pine_cls = _PINE + msg_sys
    msg_id = mem.read_int(pine_cls + 0x17E4)
    patched = getattr(write_gift_box_hud, '_patched', False)

    # Dialog closed — restore offset, force chosen item based on cursor
    if patched and msg_id not in (0x8B7, 0x8B8):
        mem.write_short(write_gift_box_hud._entry_addr, write_gift_box_hud._orig_off)
        items = write_gift_box_hud._items
        counts = write_gift_box_hud._counts
        idx = getattr(write_gift_box_hud, '_last_cursor', 0)
        if idx < 0 or idx >= len(items):
            idx = 0
        _force_chosen_item(mem, items[idx], counts[idx])
        write_gift_box_hud._patched = False
        return

    # During 0x8B8 — force item only when cursor changes
    if patched and msg_id == 0x8B8:
        idx = mem.read_int(pine_cls + 0x1AE4)
        items = write_gift_box_hud._items
        counts = write_gift_box_hud._counts
        if idx < 0 or idx >= len(items):
            idx = 0
        if idx != getattr(write_gift_box_hud, '_last_cursor', -1):
            write_gift_box_hud._last_cursor = idx
            _force_chosen_item(mem, items[idx], counts[idx])
        return

    if patched or msg_id != 0x8B7:
        return

    # --- Patch during 0x8B7 ---
    tbl_ptr = mem.read_int(pine_cls + 0x21D4)
    if tbl_ptr == 0:
        return
    tbl = _PINE + tbl_ptr
    count = mem.read_short(tbl)
    for i in range(min(count, 200)):
        if mem.read_short(tbl + 4 + i * 4) == 0x8B8:
            entry_addr = tbl + 4 + i * 4 + 2
            break
    else:
        return

    orig_off = mem.read_short(entry_addr)
    last_off = mem.read_short(tbl + 4 + (count - 1) * 4 + 2)
    last_text = tbl + (count + 1) * 2 + last_off * 2

    # Read items from treasure box
    bs = mem.read_int(0x203772A0)
    if bs == 0:
        return
    tbm = mem.read_int(_PINE + bs + 0x7C)
    if tbm == 0:
        return
    sel = mem.read_int(_PINE + tbm + 0xA9C)
    if sel < 0 or sel >= 0x18:
        return
    box = _PINE + tbm + sel * 0x70
    item1 = mem.read_short(box + 0x6C)
    item2 = mem.read_short(box + 0x6E)
    cnt1 = max(mem.read_short(box + 0x70), 1)
    cnt2 = max(mem.read_short(box + 0x72), 1)
    name1 = (_read_item_name(mem, item1) if 0 < item1 < 0xFFFF else "???") or f"#{item1:03X}"
    name2 = (_read_item_name(mem, item2) if 0 < item2 < 0xFFFF else "???") or f"#{item2:03X}"
    q1 = f"{cnt1}x " if cnt1 > 1 else ""
    q2 = f"{cnt2}x " if cnt2 > 1 else ""

    # First option = item1, second = item2
    from game.dialog import encode
    encoded = encode(f"The red box ({q1}{name1}){{n}}The yellow box ({q2}{name2})")
    for i, s in enumerate(encoded):
        mem.write_short(last_text + i * 2, s)
    mem.write_short(entry_addr, last_off)

    # Store state — player picks option 0 or 1, we force that item
    write_gift_box_hud._patched = True
    write_gift_box_hud._orig_off = orig_off
    write_gift_box_hud._entry_addr = entry_addr
    write_gift_box_hud._items = [item1, item2]
    write_gift_box_hud._counts = [cnt1, cnt2]
    write_gift_box_hud._pine_cls = pine_cls
    write_gift_box_hud._last_cursor = -1
    _force_chosen_item(mem, item1, cnt1)


def _force_chosen_item(mem, chosen, cnt):
    """Write chosen item to all script variable slots."""
    sp = mem.read_int(_SCRIPT_VARS_PTR)
    if sp == 0:
        return
    p = _PINE + sp
    mem.write_int(p + 0x0C, chosen)
    mem.write_int(p + 0x14, chosen)
    mem.write_int(p + 0x4C, chosen)
    mem.write_int(p + 0x5C, chosen)
    mem.write_int(p + 0x1C, cnt)
    mem.write_int(p + 0x54, cnt)

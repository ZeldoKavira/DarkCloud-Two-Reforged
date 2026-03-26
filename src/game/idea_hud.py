"""Idea HUD — shows when camera viewfinder is pointing at a new idea."""

import logging
from core.memory import Memory
from game import addresses as addr
from data.idea_names import IDEA_NAMES

log = logging.getLogger(__name__)

_PINE = 0x20000000
# InventUserData = SaveData + 0x251D0, neta array at +8
# SaveData = USER_DATA_MANAGER - 0x1D2A0
_NETA_BASE = 0x01E269E8  # 0x01E01810 + 0x251D0 + 8
_PHOTO_BASE = 0x01E26DE8  # InventUserData + 0x408, 30 slots × 0x18

_collected_ideas: set[int] = set()


def _refresh_collected(mem):
    """Cache neta array + pending photo ideas into a set."""
    global _collected_ideas
    s = set()
    try:
        for i in range(256):
            nid = mem.read_short(_PINE + _NETA_BASE + i * 2)
            if nid == 0:
                break
            s.add(nid)
    except Exception:
        pass
    try:
        for i in range(30):
            base = _PINE + _PHOTO_BASE + i * 0x18
            if mem.read_byte(base) == 0:
                continue
            idea = mem.read_short(base + 0x0A)
            if 0 < idea < 0xFFFF:
                s.add(idea)
    except Exception:
        pass
    _collected_ideas = s


def _is_idea_collected(idea_id):
    return idea_id in _collected_ideas

# Cached per-floor: type → scoop_id (only 12bc != 0)
_type_to_scoop: dict[int, int] = {}
# All valid scoops regardless of 12bc flag
_type_to_scoop_any: dict[int, int] = {}
_last_active_monster = 0
# Object ideas seen via InScreenFunc (accumulated during camera use)
_seen_object_ideas: set[int] = set()
_last_scene_ptr = 0


def _lookup_idea_name(idea_id):
    return IDEA_NAMES.get(idea_id, "")


def _scan_scene_ideas(mem):
    """Scan CMap inline parts + CEditMap parts for type-7 function point idea IDs."""
    global _seen_object_ideas
    try:
        _do_scan_scene_ideas(mem)
    except Exception:
        pass


def _do_scan_scene_ideas(mem):
    global _seen_object_ideas
    ms = mem.read_int(0x203771A0)  # MainScene
    if ms == 0:
        return
    map_count = mem.read_int(_PINE + ms + 0x27E0)
    ideas = set()
    for mi in range(min(map_count, 10)):
        sm = _PINE + ms + mi * 0x38 + 0x27E4
        if mem.read_int(sm) == 0:
            continue
        cmap = mem.read_int(sm + 0x34)
        if cmap == 0:
            continue
        # CMap inline parts: count at +0x328, ptr at +0x32C, stride 0x310
        icount = mem.read_int(_PINE + cmap + 0x328)
        iparts = mem.read_int(_PINE + cmap + 0x32C)
        if iparts != 0 and 0 < icount < 500:
            for pi in range(icount):
                # Type 7 only (photo objects): mngr + 4 + 7*4 = +0x2D0
                node = mem.read_int(_PINE + iparts + pi * 0x310 + 0x2D0)
                while node != 0 and node < 0x02000000:
                    idea = mem.read_int(_PINE + node + 0x30)
                    if 0 < idea < 0x10000:
                        ideas.add(idea)
                    node = mem.read_int(_PINE + node)
        # CEditMap parts: count +0xD40, ptr +0xD44, stride 0x330
        ecount = mem.read_int(_PINE + cmap + 0xD40)
        eparts = mem.read_int(_PINE + cmap + 0xD44)
        if eparts != 0 and 0 < ecount < 500:
            for pi in range(ecount):
                node = mem.read_int(_PINE + eparts + pi * 0x330 + 0x2D0)
                while node != 0 and node < 0x02000000:
                    idea = mem.read_int(_PINE + node + 0x30)
                    if 0 < idea < 0x10000:
                        ideas.add(idea)
                    node = mem.read_int(_PINE + node)
                    node = mem.read_int(_PINE + node)
    _seen_object_ideas = ideas


def _build_type_scoop_map(mem):
    """Scan active monsters to build type→scoop mappings."""
    global _type_to_scoop, _type_to_scoop_any, _last_active_monster
    am = mem.read_int(0x203772A8)  # ActiveMonster ptr
    if am == 0:
        return
    _last_active_monster = am
    _type_to_scoop = {}
    _type_to_scoop_any = {}
    for i in range(24):
        ptr = mem.read_int(_PINE + am + 0x484 + i * 4)
        if ptr == 0 or ptr > 0x02000000:
            continue
        status = mem.read_short(_PINE + ptr + 0x68A)
        if status != 2:
            continue
        tp = mem.read_int(_PINE + ptr + 0x1150)
        if tp == 0:
            continue
        mtype = mem.read_short(_PINE + tp)
        scoop = mem.read_int(_PINE + ptr + 0x12B8)
        if 0 < scoop < 0x10000:
            _type_to_scoop_any[mtype] = scoop
            if mem.read_int(_PINE + ptr + 0x12BC) != 0:
                _type_to_scoop[mtype] = scoop


_IDEA_TEXT_SIZE = 256


def _write_idea_text(mem, text: str):
    """Write ASCII string to IDEA_TEXT buffer (256 bytes max)."""
    raw = text.encode("ascii", errors="replace")[:_IDEA_TEXT_SIZE - 1] + b"\x00"
    raw = raw.ljust(_IDEA_TEXT_SIZE, b"\x00")
    mem.write_bytes(addr.IDEA_TEXT, raw)


def tick(mem, loop_no):
    """Called by render dispatcher each tick."""
    global _last_scene_ptr, _seen_object_ideas
    # Check if disabled
    if mem.read_byte(addr.OPTION_SAVE_IDEA_HUD) == 1:
        _write_idea_text(mem, "")
        return
    mode = mem.read_int(addr.TAKE_PHOTO_MODE)

    # Detect shutter press — suppress potential idea for that monster type
    _last_mode = getattr(tick, '_last_mode', 0)
    _last_type = getattr(tick, '_last_type', -1)
    if _last_mode == 2 and mode in (3, 5) and _last_type > 0:
        s = getattr(tick, '_photographed', set())
        s.add(_last_type)
        tick._photographed = s
    tick._last_mode = mode

    if mode not in (0, 2):
        _write_idea_text(mem, "")
        return

    if mode == 0:
        # Not in camera — check if any uncollected ideas on floor
        _tick_ctr = getattr(tick, '_ctr', 0) + 1
        tick._ctr = _tick_ctr
        if _tick_ctr % 10 == 0 or not (_type_to_scoop_any or _seen_object_ideas):
            _build_type_scoop_map(mem)
            _refresh_collected(mem)
            _scan_scene_ideas(mem)
        # Count monster ideas + cached object ideas
        all_ideas = set(_type_to_scoop_any.values()) | _seen_object_ideas
        uncollected = [sc for sc in sorted(all_ideas) if not _is_idea_collected(sc)]
        count = len(uncollected)
        if count > 0:
            text = f"{count} Idea{'s' if count != 1 else ''} nearby"
            if mem.read_byte(addr.OPTION_SAVE_IDEA_NAMES) == 1:
                for uid in uncollected:
                    name = _lookup_idea_name(uid)
                    if name:
                        line = f"\n- {name}"
                        if len(text) + len(line) >= _IDEA_TEXT_SIZE - 1:
                            break
                        text += line
            _write_idea_text(mem, text)
        else:
            _write_idea_text(mem, "")
        return

    # Camera open — rebuild maps periodically
    _tick_ctr = getattr(tick, '_ctr', 0) + 1
    tick._ctr = _tick_ctr
    if _tick_ctr % 10 == 0 or not (_type_to_scoop_any or _seen_object_ideas):
        _build_type_scoop_map(mem)
        _refresh_collected(mem)
        _scan_scene_ideas(mem)

    # Check monster in viewfinder
    mtype = mem.read_int(addr.IDEA_MONSTER_TYPE)
    tick._last_type = mtype
    if mtype > 0:
        # 12bc != 0 → guaranteed idea
        scoop = _type_to_scoop.get(mtype)
        if scoop and not _is_idea_collected(scoop):
            name = _lookup_idea_name(scoop)
            _write_idea_text(mem, f"New Idea: {name}" if name else "New Idea")
            return
        # 12bc == 0 but valid scoop exists → potential (unless already photographed)
        scoop_any = _type_to_scoop_any.get(mtype)
        if scoop_any and not _is_idea_collected(scoop_any):
            if mtype not in getattr(tick, '_photographed', set()):
                name = _lookup_idea_name(scoop_any)
                _write_idea_text(mem, f"Potential: {name}" if name else "Potential Idea")
                return

    # Check object in viewfinder
    obj_id = mem.read_int(addr.IDEA_OBJECT_ID)
    if obj_id > 0 and obj_id < 0x10000:
        if not _is_idea_collected(obj_id):
            name = _lookup_idea_name(obj_id)
            _write_idea_text(mem, f"New Idea: {name}" if name else "New Idea")
            return

    _write_idea_text(mem, "")

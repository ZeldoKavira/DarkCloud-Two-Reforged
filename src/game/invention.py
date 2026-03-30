"""Invention helper — dims invalid memo entries on the make screen."""

from core.memory import Memory
from game import addresses as addr
from data.inventions import RECIPES

_PINE = 0x20000000
_INVENT_USER_DATA_PTR = 0x203775C4  # gp - 0x6F2C

_discovered: set[int] = set()
_next_slot: int = -1  # -1 = needs initial scan


def _scan_discovered(mem: Memory) -> tuple[set[int], int]:
    """Full scan. Returns (discovered set, next empty slot index)."""
    iud = mem.read_int(_INVENT_USER_DATA_PTR)
    if iud == 0:
        return set(), 1
    found = set()
    base = _PINE + iud + 0x6D8
    # Slot 0 is always 0 ("New Invention"), start from 1
    for i in range(1, 256):
        item = mem.read_short(base + i * 4)
        if item == 0:
            return found, i
        found.add(item)
    return found, 256


_prev_cursor: int = -1

_prev_dim = bytearray(b'\xff' * 256)


def tick(mem: Memory):
    """Called each mod tick. Updates dim table when invention screen is open."""
    global _discovered, _next_slot, _prev_cursor
    menu = mem.read_int(addr.CMENU_INVENT_PTR)
    if menu == 0:
        return

    # Check if a new discovery appeared at the watched slot
    iud = mem.read_int(_INVENT_USER_DATA_PTR)
    if iud != 0:
        if _next_slot < 0:
            _discovered, _next_slot = _scan_discovered(mem)
        else:
            val = mem.read_short(_PINE + iud + 0x6D8 + _next_slot * 4)
            if val != 0:
                _discovered, _next_slot = _scan_discovered(mem)

    # Read all memo ideas
    # Read all memo ideas
    memo_ideas = set()
    memo_list = []
    for i in range(256):
        mid = mem.read_short(addr.NETA_MEMO_ID + i * 2)
        memo_list.append(mid)
        if mid != 0:
            memo_ideas.add(mid)

    # Filter out discovered recipes
    active_recipes = [(r, ideas) for r, ideas in RECIPES if r not in _discovered]

    sel_count = mem.read_short(_PINE + menu + 0x60C)

    if sel_count == 0:
        valid = set()
        for _result, ideas in active_recipes:
            if all(i in memo_ideas for i in ideas):
                valid.update(ideas)
    else:
        selected = set()
        for i in range(sel_count):
            src_type = mem.read_byte(_PINE + menu + 0x61C + i)
            slot_idx = mem.read_int(_PINE + menu + 0x610 + i * 4)
            if src_type == 0:
                idea = mem.read_short(addr.PHOTO_BASE + slot_idx * 0x18 + 0x0A)
            else:
                idea = mem.read_short(addr.NETA_MEMO_ID + slot_idx * 2)
            if 0 < idea < 0xFFFF:
                selected.add(idea)

        valid = set()
        for _result, ideas in active_recipes:
            idea_set = set(ideas)
            if selected.issubset(idea_set):
                remaining = idea_set - selected
                if remaining.issubset(memo_ideas):
                    valid.update(remaining)

    # Write dim table
    memo_count = 0
    dim_bytes = bytearray(256)
    for i in range(256):
        mid = memo_list[i]
        if mid != 0:
            memo_count = i + 1
        dim_bytes[i] = 0 if mid != 0 and mid in valid else 1
    for i in range(memo_count):
        mem.write_byte(addr.INVENT_DIM_TABLE + i, dim_bytes[i])

    # Cursor skip: if cursor is on a dimmed entry, move in the direction of travel
    cursor = mem.read_int(_PINE + menu + 0x134)
    if _prev_cursor < 0:
        _prev_cursor = cursor
    if 0 <= cursor < memo_count and dim_bytes[cursor] == 1:
        step = -1 if cursor < _prev_cursor else 1
        pos = cursor + step
        while 0 <= pos < memo_count:
            if dim_bytes[pos] == 0:
                mem.write_int(_PINE + menu + 0x134, pos)
                cursor = pos
                break
            pos += step
    _prev_cursor = cursor

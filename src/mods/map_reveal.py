"""Map reveal + crystal placement on new dungeon floors."""

import logging
from core.memory import Memory
from game import addresses as addr
from mods import event_skip

log = logging.getLogger(__name__)

PINE = 0x20000000
_last_floor_ptr: int | None = None


def tick(mem: Memory):
    global _last_floor_ptr
    ptr = mem.read_int(addr.NOW_FLOOR_INFO_PTR)
    if ptr == 0:
        _last_floor_ptr = None
        return
    if ptr == _last_floor_ptr:
        return
    _last_floor_ptr = ptr
    event_skip.set_pending()
    log.info("New floor detected (ptr=0x%X)", ptr)
    scene_ptr = mem.read_int(0x2037729C)
    if scene_ptr == 0:
        return
    scene = PINE + scene_ptr
    flags = mem.read_int(scene + 0x2FF4)
    if mem.read_byte(addr.OPTION_SAVE_START_MAP) == 1:
        flags |= 1
        _reveal_map(mem)
    if mem.read_byte(addr.OPTION_SAVE_START_CRYSTAL) == 1:
        flags |= 2
    mem.write_int(scene + 0x2FF4, flags)


def _reveal_map(mem: Memory):
    """Replicate MinimapAllVisible — set all map cells visible."""
    automap = PINE + 0x01EA0480
    w = mem.read_short(automap + 0x1B8)
    h = mem.read_short(automap + 0x1BA)
    grid_ptr = mem.read_int(automap + 0x1CC)
    if grid_ptr == 0 or w == 0 or h == 0:
        return
    grid = PINE + grid_ptr
    for i in range(w * h):
        mem.write_short(grid + i * 0x1C + 0x0C, 1)

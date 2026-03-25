"""Event skip — auto-skip cutscenes."""

from core.memory import Memory
from game import addresses as addr

_pending_floor_skip: bool = False


def set_pending():
    global _pending_floor_skip
    _pending_floor_skip = True


def tick(mem: Memory):
    global _pending_floor_skip
    ev = mem.read_int(addr.EVENT_SKIP_FLAG)
    if ev != 1:
        return
    skip_all = mem.read_byte(addr.OPTION_SAVE_SKIP_ALL_EVENTS) == 1
    skip_entry = mem.read_byte(addr.OPTION_SAVE_AUTO_SKIP_EVENT) != 1
    if skip_all or (skip_entry and _pending_floor_skip):
        mem.write_int(addr.EVENT_SKIP_FLAG, 3)
        _pending_floor_skip = False

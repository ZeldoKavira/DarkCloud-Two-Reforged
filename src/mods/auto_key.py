"""Auto key — consume dungeon gate keys automatically."""

import logging
from core.memory import Memory
from mods.inventory import find_item, consume_item

log = logging.getLogger(__name__)

PINE = 0x20000000


def tick(mem: Memory, enabled: bool, dialog=None):
    if not enabled:
        return

    menu_state = mem.read_int(PINE + 0x01ECD618)
    if menu_state != 9:
        return
    key_id = mem.read_short(PINE + 0x01ECD64C)
    if key_id < 0x151 or key_id > 0x15F:
        return
    if find_item(mem, key_id) is not None:
        consume_item(mem, key_id)
        p_use = mem.read_int(0x20377CE0)
        if p_use != 0:
            mem.write_int(0x20000000 + p_use + 4, key_id)
        mem.write_int(0x20377CE0, 0)
        mem.write_int(PINE + 0x01ECD630, key_id)
        mem.write_int(PINE + 0x01ECD618, 0)
        mem.write_int(PINE + 0x01ECE500, 0)
        log.info("Auto-used gate key 0x%X", key_id)
    else:
        mem.write_int(PINE + 0x01ECD630, 0)
        mem.write_int(PINE + 0x01ECD618, 0)
        mem.write_int(PINE + 0x01ECE500, 0)
        if dialog:
            dialog.show("You don't have the required key.", duration=3, mode=0)

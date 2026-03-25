"""Shared inventory helpers — find and consume items."""

from core.memory import Memory
from game import addresses as addr


def find_item(mem: Memory, item_id: int) -> int | None:
    """Find inventory or equipped slot address containing item_id, or None."""
    for base, count in [(addr.USER_DATA_MANAGER, addr.INVENTORY_SLOT_COUNT),
                        (addr.EQUIP_SLOT_BASE, addr.EQUIP_SLOT_COUNT),
                        (addr.EQUIP_SLOT_BASE_MON, addr.EQUIP_SLOT_COUNT)]:
        for i in range(count):
            slot = base + i * addr.INVENTORY_SLOT_SIZE
            iid = mem.read_short(slot + 2)
            if iid == item_id:
                c = mem.read_short(slot + 0x10)
                if c > 0:
                    return slot
    return None


def consume_item(mem: Memory, item_id: int) -> bool:
    """Decrement count of item_id in inventory. Returns True if successful."""
    slot = find_item(mem, item_id)
    if slot is None:
        return False
    count = mem.read_short(slot + 0x10)
    if count <= 1:
        mem.write_short(slot + 0x10, 0)
        mem.write_short(slot + 0x00, 0)
        mem.write_short(slot + 0x02, 0)
    else:
        mem.write_short(slot + 0x10, count - 1)
    return True

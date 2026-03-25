"""Auto repair — consume repair powders when PNACH cave signals."""

import logging
from core.memory import Memory
from game import addresses as addr
from mods.inventory import find_item

log = logging.getLogger(__name__)

_slot_cache: dict[int, int] = {}
_needs_scan: bool = True
_flag_set: bool = False


def tick(mem: Memory, enabled: bool):
    global _slot_cache, _needs_scan, _flag_set

    if not enabled:
        if _flag_set:
            mem.write_int(addr.AUTO_REPAIR_FLAG, 0)
            mem.write_int(addr.AUTO_REPAIR_FLAG_RANGED, 0)
            mem.write_int(addr.AUTO_REPAIR_FLAG_ARMBAND, 0)
            _flag_set = False
        return

    consumed = mem.read_int(addr.REPAIR_CONSUMED)
    if consumed != 0:
        mem.write_int(addr.REPAIR_CONSUMED, 0)
        if consumed == 1:
            item_id = addr.REPAIR_POWDER_MELEE
            flag_addr = addr.AUTO_REPAIR_FLAG
        elif consumed == 2:
            item_id = addr.REPAIR_POWDER_RANGED
            flag_addr = addr.AUTO_REPAIR_FLAG_RANGED
        else:
            item_id = addr.REPAIR_POWDER_ARMBAND
            flag_addr = addr.AUTO_REPAIR_FLAG_ARMBAND
        cached = _slot_cache.get(item_id)
        if cached is not None:
            iid = mem.read_short(cached + 2)
            count = mem.read_short(cached + 0x10)
            if iid == item_id and count > 0:
                mem.write_short(cached + 0x10, count - 1)
                log.info("Auto-used Repair Powder (0x%X)", item_id)
                if count - 1 <= 0:
                    _needs_scan = True
            else:
                _needs_scan = True
        else:
            _needs_scan = True
        mem.write_int(flag_addr, 1)

    if _needs_scan:
        cache = {}
        melee_slot = find_item(mem, addr.REPAIR_POWDER_MELEE)
        ranged_slot = find_item(mem, addr.REPAIR_POWDER_RANGED)
        armband_slot = find_item(mem, addr.REPAIR_POWDER_ARMBAND)
        if melee_slot: cache[addr.REPAIR_POWDER_MELEE] = melee_slot
        if ranged_slot: cache[addr.REPAIR_POWDER_RANGED] = ranged_slot
        if armband_slot: cache[addr.REPAIR_POWDER_ARMBAND] = armband_slot
        _slot_cache = cache
        mem.write_int(addr.AUTO_REPAIR_FLAG, 1 if melee_slot else 0)
        mem.write_int(addr.AUTO_REPAIR_FLAG_RANGED, 1 if ranged_slot else 0)
        mem.write_int(addr.AUTO_REPAIR_FLAG_ARMBAND, 1 if armband_slot else 0)
        _flag_set = bool(cache)
        _needs_scan = False

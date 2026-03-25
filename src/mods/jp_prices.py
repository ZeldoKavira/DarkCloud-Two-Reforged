"""JP price patches for shops."""

import logging
from core.memory import Memory
from game import addresses as addr

log = logging.getLogger(__name__)

PINE = 0x20000000
_shop_patched: bool = False


def tick(mem: Memory, enabled: bool):
    global _shop_patched
    shop = mem.read_int(addr.SHOP_PTR)
    if shop == 0:
        _shop_patched = False
        return
    if not enabled or _shop_patched:
        return
    for item_id, buy, sell in addr.JP_PRICE_PATCHES:
        base = PINE + shop + addr.SHOP_PRICE_OFF + item_id * 8
        if buy is not None:
            mem.write_int(base, buy)
        if sell is not None:
            mem.write_int(base + 4, sell)
    _shop_patched = True
    log.info("Applied JP price patches")

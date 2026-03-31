"""Georama auto-buy — purchase missing materials via game's yes/no dialog.

Flow:
1. While on material list (sub=0), detect shortages and write buy text to
   msg 0x0C51 slot, set GEO_BUY_FLAG
2. User presses X → PNACH Part 1 skips error, redirects to confirm path
3. PNACH Part 2 writes 0x0C51 to +0x21E6, clears ACTIVE, sets state=2
4. Game shows yes/no dialog with our buy text
5. Yes → Python deducts gilda; No → back to material list
"""

import logging
from core.memory import Memory
from game import addresses as addr
from data.items import ITEM_NAMES, GEORAMA_BUY_PRICES

log = logging.getLogger(__name__)

P = 0x20000000
CMENU_GEO_PT = 0x203774EC
CDC2MES_PTR = 0x21ECCA48
GEO_BUY_FLAG = P + 0x01F71840
GEO_MAT_DATA = P + 0x01F71850

_SUB_STATE = 0x02
_MAKEBRD = 0x1B7C4
_MAT_COUNT = 0x1B7DC
_EPARTS_PTR = 0x1B7F0

_state = "idle"
_shortages = []
_total = 0


def _read_shortages(mem, geo):
    mc = mem.read_int(geo + _MAT_COUNT)
    epi_raw = mem.read_int(geo + _EPARTS_PTR)
    if not epi_raw or mc < 1:
        return []
    epi = P + epi_raw
    out = []
    for i in range(min(mc, 4)):
        slot = geo + _MAKEBRD + i * 6
        if not mem.read_byte(slot) or mem.read_byte(slot + 1):
            continue
        shortage = mem.read_short(slot + 4)
        if shortage <= 0:
            continue
        iid = mem.read_int(epi + i * 8 + 0x70)
        if iid <= 0 or iid >= 0x200:
            continue
        price = GEORAMA_BUY_PRICES.get(iid, 0)
        if price <= 0:
            continue
        out.append((iid, shortage, price))
    return out


def _write_buy_data(mem, geo):
    """Write buy text to msg 0x0C51 slot."""
    from game.dialog import encode

    cdc_ptr = mem.read_int(CDC2MES_PTR)
    if not cdc_ptr or cdc_ptr < 0x100000:
        return False
    tbl_ptr = mem.read_int(P + cdc_ptr + 0x21D4)
    if not tbl_ptr or tbl_ptr < 0x100000:
        return False
    tbl = P + tbl_ptr
    count = mem.read_short(tbl)
    if count < 2:
        return False

    txt_addr = 0
    for i in range(count):
        if mem.read_short(tbl + 4 + i * 4) == 0x0C51:
            off = mem.read_short(tbl + 4 + i * 4 + 2)
            txt_addr = tbl + count * 2 + off * 2 + 2
            break
    if not txt_addr:
        return False

    epi_raw = mem.read_int(geo + 0x1B7F0)
    build_name = "?"
    build_qty = mem.read_int(geo + 0x100)
    if epi_raw:
        name_ptr = mem.read_int(P + epi_raw + 0x3C)
        if name_ptr:
            chars = []
            for i in range(24):
                b = mem.read_byte(P + name_ptr + i)
                if b == 0: break
                chars.append(chr(b) if 32 <= b < 127 else "?")
            build_name = "".join(chars)

    gilda = mem.read_int(addr.GILDA)
    lines = [f'Building {build_qty}x "{build_name}" requires:']
    for iid, s, p in _shortages:
        name = ITEM_NAMES.get(iid, f"#{iid:03X}")
        lines.append(f" {s}x {name} ({p * s}g)")
    lines.append(f"Total: {_total}g  Gilda: {gilda}g")
    lines.append("Are you sure?")
    text = encode("{n}".join(lines))
    while len(text) % 2:
        text.append(0)
    for i in range(0, len(text), 2):
        mem.write_int(txt_addr + i * 2, text[i] | (text[i + 1] << 16))
    return True


def tick(mem: Memory, dialog):
    global _state, _shortages, _total

    gp = mem.read_int(CMENU_GEO_PT)
    if not gp:
        _state = "idle"
        return
    geo = P + gp
    mode = mem.read_short(geo + 0x00)
    sub = mem.read_short(geo + _SUB_STATE)

    if mode != 6:
        _state = "idle"
        return

    if _state == "idle":
        if sub == 0:
            shortages = _read_shortages(mem, geo)
            if not shortages:
                return
            total = sum(s * p for _, s, p in shortages)
            gilda = mem.read_int(addr.GILDA)
            if total <= 0 or total > gilda:
                return
            _shortages = shortages
            _total = total
            if not _write_buy_data(mem, geo):
                return
            mem.write_int(GEO_BUY_FLAG, 1)
            _state = "waiting_x"
            log.info("Geo buy: ready, %dg", total)

    elif _state == "waiting_x":
        if sub == 0:
            shortages = _read_shortages(mem, geo)
            if not shortages:
                mem.write_int(GEO_BUY_FLAG, 0)
                _state = "idle"
                return
            total = sum(s * p for _, s, p in shortages)
            gilda = mem.read_int(addr.GILDA)
            if total <= 0 or total > gilda:
                mem.write_int(GEO_BUY_FLAG, 0)
                _state = "idle"
                return
            if shortages != _shortages:
                _shortages = shortages
                _total = total
                _write_buy_data(mem, geo)
        elif sub == 2:
            _state = "confirming"
            log.info("Geo buy: confirm showing")
        elif sub != 0:
            _state = "idle"

    elif _state == "confirming":
        if sub != 2:
            if sub == 1:
                gilda = mem.read_int(addr.GILDA)
                mem.write_int(addr.GILDA, max(0, gilda - _total))
                log.info("Geo buy: confirmed, deducted %dg", _total)
            else:
                log.info("Geo buy: cancelled")
            _state = "idle"

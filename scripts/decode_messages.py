#!/usr/bin/env python3
"""Decode DC2 message dump (msg-table-dump.json) to readable text."""
import json, sys

# Build reverse lookup from dialog.py's encoding
_REV = {}
for c in range(0x01, 0x3C):
    _REV[c] = chr(c + 0x20)
for c in range(0x3C, 0x5E):
    _REV[c] = chr(c + 0x21)
_REV[0xFF02] = ' '
_REV[0xFF00] = '\n'
_REV[0xFF01] = ''  # terminator

_CTRL = {
    0xFD03: '[X]', 0xFD04: '[O]', 0xFD05: '[Tri]', 0xFD06: '[Sq]',
    0xFD1A: '[>>]', 0xFC01: '[red]', 0xFC00: '[/color]',
}

def decode(shorts):
    out = []
    i = 0
    while i < len(shorts):
        s = shorts[i]
        if s == 0xFF01:
            break
        if s in _CTRL:
            out.append(_CTRL[s])
        elif s in _REV:
            out.append(_REV[s])
        elif s < 0x100:
            out.append(f'[0x{s:02X}]')
        else:
            out.append(f'[0x{s:04X}]')
        i += 1
    return ''.join(out)

path = sys.argv[1] if len(sys.argv) > 1 else 'dev-files/msg-table-dump.json'
with open(path) as f:
    data = json.load(f)

for msg_id in sorted(data.keys(), key=lambda x: int(x, 16)):
    entry = data[msg_id]
    shorts = [int(s, 16) for s in entry['raw_shorts']]
    text = decode(shorts)
    print(f"{msg_id}: {text}")

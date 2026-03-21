#!/usr/bin/env python3
"""Check PNACH files for memory address collisions in code cave space."""
import re, glob, os

PNACH_DIR = os.path.join(os.path.dirname(__file__), "..", "pcsx2-files", "pnach")
PATCH_RE = re.compile(r"^patch=[01],EE,([0-9A-Fa-f]+),extended,([0-9A-Fa-f]+)", re.IGNORECASE)

# Address prefix → write size: 00=byte(1), 10=short(2), 20=word(4)
SIZE_MAP = {0x00: 1, 0x10: 2, 0x20: 4}

entries = []

for path in sorted(glob.glob(os.path.join(PNACH_DIR, "*.pnach"))):
    fname = os.path.basename(path)
    with open(path) as f:
        for line_no, line in enumerate(f, 1):
            m = PATCH_RE.match(line.strip())
            if not m:
                continue
            raw_addr = int(m.group(1), 16)
            top_nibble = (raw_addr >> 28) & 0xF
            # Skip PCSX2 conditional codes (E/D prefix = control flow, not memory writes)
            if top_nibble in (0xE, 0xD):
                continue
            prefix = (raw_addr >> 24) & 0xF0
            size = SIZE_MAP.get(prefix, 4)
            # Strip to PS2 address (low 28 bits, minus size prefix)
            base = raw_addr & 0x0FFFFFFF
            entries.append((fname, line_no, base, size, line.strip()))

# Known intentional collisions to ignore
_IGNORE = {
    (0x001CEB70, "06-hud-overlay.pnach", "13-synth-hud.pnach"),  # synth chains to hud cave
    (0x00377E98, "01-save-blocker.pnach", "02-fast-start.pnach"), # both write same value
    (0x006FBA40, "01-save-blocker.pnach", "02-fast-start.pnach"), # both write same value
}

entries.sort(key=lambda e: (e[2], e[0], e[1]))

collisions = []
for i in range(len(entries)):
    f1, l1, a1, s1, t1 = entries[i]
    for j in range(i + 1, len(entries)):
        f2, l2, a2, s2, t2 = entries[j]
        if a2 >= a1 + s1:
            break
        if f1 == f2 and a1 == a2:
            continue
        overlap_addr = a1
        if (overlap_addr, f1, f2) in _IGNORE or (overlap_addr, f2, f1) in _IGNORE:
            continue
        collisions.append((entries[i], entries[j]))

if not collisions:
    print(f"No collisions found across {len(entries)} patches.")
else:
    print(f"Found {len(collisions)} collision(s):\n")
    for (f1, l1, a1, s1, t1), (f2, l2, a2, s2, t2) in collisions:
        print(f"  COLLISION: 0x{a1:08X}+{s1} overlaps 0x{a2:08X}+{s2}")
        print(f"    {f1}:{l1}  {t1}")
        print(f"    {f2}:{l2}  {t2}")
        print()

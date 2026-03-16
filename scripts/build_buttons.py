#!/usr/bin/env python3
"""
Button Atlas Builder for Dark Cloud 2 Reforged

Generates custom button textures and outputs swizzle offset/value pairs
for surgical injection into the texture atlas without affecting other buttons.

Usage:
    python3 build_buttons.py

Reads:
    Textures/OptionsMenu/buttons.json               — Button definitions
    Textures/OptionsMenu/blank_button_template.png   — 56x24 blank large button
    Textures/OptionsMenu/blank_small_36x24.png       — 36x24 blank small button

Writes:
    Textures/OptionsMenu/btn_patch.bin               — Sparse patch (offset:value pairs)
    Textures/OptionsMenu/btn_patch_preview.png       — Visual preview
    Textures/OptionsMenu/button_uvs.json             — UV coordinates for inject code
"""

import json, os, struct
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEX_DIR = os.path.join(SCRIPT_DIR, '..', 'Textures', 'OptionsMenu')
FONT_ATLAS = os.path.join(TEX_DIR, 'dc2_font_atlas.png')

BG = 0x6F
TEXT = 0xFF
ATLAS_W = 256
CUSTOM_Y = 200  # Well below native buttons (last native ~y=168)

LARGE_BTN = (56, 24)
SMALL_BTN = (36, 24)

# DC2 font atlas constants
CELL_W, CELL_H = 16, 20
BOLD_MAP = {}
for i in range(8):
    BOLD_MAP[chr(0x30 + i)] = ((24 + i) * 16, 80)
BOLD_MAP['8'] = (0, 100)
BOLD_MAP['9'] = (16, 100)
for i in range(26):
    BOLD_MAP[chr(0x41 + i)] = ((2 + i) * 16, 100)
BOLD_MAP[' '] = (0, 0)
BOLD_MAP['.'] = (14 * 16, 0)  # Period from regular font row

_font_atlas = None
def get_font_atlas():
    global _font_atlas
    if _font_atlas is None:
        _font_atlas = Image.open(FONT_ATLAS)
    return _font_atlas

def get_bold_glyph(ch):
    ch = ch.upper()
    if ch not in BOLD_MAP:
        return Image.new('RGBA', (CELL_W, CELL_H), (0,0,0,0))
    x, y = BOLD_MAP[ch]
    atlas = get_font_atlas()
    g = atlas.crop((x, y, x + CELL_W, y + CELL_H))
    r, gr, b, a = g.split()
    a = a.point(lambda p: 255 if p > 10 else 0)
    return Image.merge('RGBA', (r, gr, b, a))

def swizzle_offset(x, y, w=256):
    """Get the byte offset in swizzled data for pixel (x,y)."""
    bl = (y & ~0xf) * w + (x & ~0xf) * 2
    ss = (((y + 2) >> 2) & 1) * 4
    pY = (((y & ~3) >> 1) + (y & 1)) & 7
    cl = pY * w * 2 + ((x + ss) & 7) * 4
    bn = ((y >> 1) & 1) + ((x >> 2) & 2)
    return bl + cl + bn

def swizzle_8bpp(linear, w, h):
    """Swizzle linear pixel data into PS2 PSMT8 format."""
    out = [0] * len(linear)
    for y in range(h):
        for x in range(w):
            idx = swizzle_offset(x, y, w)
            if idx < len(out):
                out[idx] = linear[y * w + x]
    return out

def render_dc2_text(text, btn_w, btn_h):
    """Render text using DC2 font atlas, return RGBA image sized for button."""
    text = text.upper()
    
    # Get glyphs with tight horizontal crop
    glyphs = []
    for ch in text:
        g = get_bold_glyph(ch)
        bbox = g.split()[3].getbbox()
        if bbox:
            glyphs.append(g.crop((bbox[0], 0, bbox[2], CELL_H)))
        else:
            glyphs.append(Image.new('RGBA', (4, CELL_H), (0,0,0,0)))  # space
    
    # Compose with 1px spacing
    spacing = 1
    total_w = sum(g.width for g in glyphs) + spacing * (len(glyphs) - 1)
    
    text_img = Image.new('RGBA', (total_w, CELL_H), (0,0,0,0))
    cx = 0
    for g in glyphs:
        text_img.paste(g, (cx, 0), g.split()[3])
        cx += g.width + spacing
    
    # Scale to fit button with padding
    max_w = btn_w - 8
    max_h = btn_h - 6
    scale_w = max_w / total_w if total_w > max_w else 1.0
    scale_h = max_h / CELL_H if CELL_H > max_h else 1.0
    scale = min(scale_w, scale_h, 0.75)
    
    new_w, new_h = int(total_w * scale), int(CELL_H * scale)
    return text_img.resize((new_w, new_h), Image.NEAREST)

def load_template(size):
    name = 'blank_button_template.png' if size == LARGE_BTN else 'blank_small_36x24.png'
    img = Image.open(os.path.join(TEX_DIR, name)).convert('L')
    return [[img.getpixel((x, y)) for x in range(size[0])] for y in range(size[1])]

def make_button(text, size, font_size=None):
    w, h = size
    template = load_template(size)
    
    # Render DC2 font text
    text_comp = render_dc2_text(text, w, h)
    
    # Center horizontally, down 1px from center
    tx = (w - text_comp.width) // 2
    ty = (h - text_comp.height) // 2 + 1
    
    # Build grayscale button
    btn = [row[:] for row in template]
    
    # Shadow pass (offset by 1,1)
    for cy in range(text_comp.height):
        for cx in range(text_comp.width):
            bx, by = tx + cx + 1, ty + cy + 1
            if 0 <= bx < w and 0 <= by < h:
                _, _, _, a = text_comp.getpixel((cx, cy))
                if a > 128:
                    btn[by][bx] = int(btn[by][bx] * 0.3)  # darken for shadow
    
    # White text pass
    for cy in range(text_comp.height):
        for cx in range(text_comp.width):
            bx, by = tx + cx, ty + cy
            if 0 <= bx < w and 0 <= by < h:
                _, _, _, a = text_comp.getpixel((cx, cy))
                if a > 128:
                    btn[by][bx] = TEXT  # pure white
    
    return btn

def main():
    buttons_json = os.path.join(TEX_DIR, 'buttons.json')
    if not os.path.exists(buttons_json):
        config = [
            {"text": "1x",   "size": "small", "font_size": 24},
            {"text": "1.5x", "size": "small", "font_size": 20},
            {"text": "2x",   "size": "small", "font_size": 24},
        ]
        with open(buttons_json, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Created default {buttons_json}")
    else:
        with open(buttons_json) as f:
            config = json.load(f)

    # Build sparse patch: only write pixels that are part of our buttons
    uvs = []
    x_cursor = 0
    y_cursor = CUSTOM_Y
    row_height = 0
    # Collect (swizzle_offset, value) for each button pixel
    pixel_map = {}  # swizzle_offset -> value

    print(f"Building {len(config)} custom buttons...")
    for btn_def in config:
        size = LARGE_BTN if btn_def["size"] == "large" else SMALL_BTN
        w, h = size
        font_size = btn_def.get("font_size", 36 if size == LARGE_BTN else 24)
        if x_cursor + w > ATLAS_W:
            y_cursor += row_height; x_cursor = 0; row_height = 0
        btn = make_button(btn_def["text"], size, font_size)
        for by in range(h):
            for bx in range(w):
                off = swizzle_offset(x_cursor + bx, y_cursor + by, ATLAS_W)
                pixel_map[off] = btn[by][bx]
        uvs.append({"text": btn_def["text"], "x": x_cursor, "y": y_cursor, "w": w, "h": h})
        print(f"  '{btn_def['text']}' at ({x_cursor}, {y_cursor}) {w}x{h}")
        x_cursor += w; row_height = max(row_height, h)

    # Group into aligned 4-byte writes for efficiency
    # Sort offsets, group consecutive aligned sets of 4
    sorted_offs = sorted(pixel_map.keys())
    patch_data = bytearray()
    i = 0
    while i < len(sorted_offs):
        off = sorted_offs[i]
        aligned = off & ~3  # align to 4-byte boundary
        # Collect up to 4 bytes at this aligned offset
        word_bytes = [0, 0, 0, 0]
        mask_bytes = [False, False, False, False]
        j = i
        while j < len(sorted_offs) and sorted_offs[j] < aligned + 4:
            byte_pos = sorted_offs[j] - aligned
            word_bytes[byte_pos] = pixel_map[sorted_offs[j]]
            mask_bytes[byte_pos] = True
            j += 1
        # If all 4 bytes are ours, write as a full word
        if all(mask_bytes):
            # Format: 'F' (full), u32 offset, u32 value
            word = word_bytes[0] | (word_bytes[1] << 8) | (word_bytes[2] << 16) | (word_bytes[3] << 24)
            patch_data.extend(struct.pack('<cII', b'F', aligned, word))
        else:
            # Format: 'B' (byte), u32 offset, u8 value — for each set byte
            for k in range(4):
                if mask_bytes[k]:
                    patch_data.extend(struct.pack('<cIB', b'B', aligned + k, word_bytes[k]))
        i = j

    out_path = os.path.join(TEX_DIR, 'btn_patch.bin')
    with open(out_path, 'wb') as f:
        f.write(patch_data)
    print(f"Saved patch: {out_path} ({len(pixel_map)} pixels, {len(patch_data)} bytes)")

    # Preview - calculate height needed
    max_y = max(uv["y"] + uv["h"] for uv in uvs) - CUSTOM_Y
    preview = Image.new('L', (ATLAS_W, max_y), BG)
    for uv, bd in zip(uvs, config):
        size = LARGE_BTN if bd["size"] == "large" else SMALL_BTN
        btn = make_button(bd["text"], size)
        for by in range(size[1]):
            for bx in range(size[0]):
                preview.putpixel((uv["x"] + bx, uv["y"] - CUSTOM_Y + by), btn[by][bx])
    preview.save(os.path.join(TEX_DIR, 'btn_patch_preview.png'))

    meta = {"atlas_base": "0x01B73F60", "buttons": uvs}
    with open(os.path.join(TEX_DIR, 'button_uvs.json'), 'w') as f:
        json.dump(uvs, f, indent=2)
    with open(os.path.join(TEX_DIR, 'btn_patch_meta.json'), 'w') as f:
        json.dump(meta, f, indent=2)
    print(f"Done! {len(uvs)} buttons.")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Entry program for make.fun news-image-20261117.

Stdlib only. Reads news.json + assets.json + the raster PNG assets in this
repository, draws the page furniture (background, ticker bar, rules), pastes
the illustrations, the dotted world map and the text overlay, and writes one
1024x1024 PNG to /output/entry.png. Deterministic: two runs are byte-identical.

The grader runs this in a stock Python image with no Pillow, so PNG decoding
and encoding are implemented here from scratch (color types 0/2/3/6, bit
depths 1/2/4/8, all five filters including Paeth).
"""
import binascii
import hashlib
import json
import os
import struct
import sys
import zlib

BASE = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------- layout (MUST match build_assets.py)
W, H = 1024, 1024
MARGIN = 24
TICKER_Y, TICKER_H = 80, 26

CREAM = (247, 243, 234)
RED = (179, 38, 30)
INK = (26, 26, 26)
RULE = (190, 182, 165)

# ------------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        r, g, b = bg
        for i in range(0, len(self.px), 3):
            self.px[i] = r
            self.px[i + 1] = g
            self.px[i + 2] = b

    def rect(self, x, y, w, h, color):
        r, g, b = color
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        for yy in range(y0, y1):
            base = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                o = base + (xx - x0) * 3
                self.px[o] = r
                self.px[o + 1] = g
                self.px[o + 2] = b

    def hline(self, x, y, w, color):
        self.rect(x, y, w, 1, color)

    def paste_rgba(self, img, ox, oy):
        """Alpha-composite an RGBA image (w, h, rows of bytes) onto the canvas."""
        iw, ih, rows = img
        for yy in range(ih):
            dy = oy + yy
            if dy < 0 or dy >= self.h:
                continue
            row = rows[yy]
            for xx in range(iw):
                dx = ox + xx
                if dx < 0 or dx >= self.w:
                    continue
                o = (dy * self.w + dx) * 3
                a = row[xx * 4 + 3]
                if a == 0:
                    continue
                if a == 255:
                    self.px[o] = row[xx * 4]
                    self.px[o + 1] = row[xx * 4 + 1]
                    self.px[o + 2] = row[xx * 4 + 2]
                else:
                    ia = 255 - a
                    self.px[o] = (row[xx * 4] * a + self.px[o] * ia) // 255
                    self.px[o + 1] = (row[xx * 4 + 1] * a + self.px[o + 1] * ia) // 255
                    self.px[o + 2] = (row[xx * 4 + 2] * a + self.px[o + 2] * ia) // 255

    def paste_rgb(self, img, ox, oy):
        # NOTE: decode_png always returns RGBA rows (4 bytes per pixel),
        # even for RGB sources.
        iw, ih, rows = img
        for yy in range(ih):
            dy = oy + yy
            if dy < 0 or dy >= self.h:
                continue
            row = rows[yy]
            for xx in range(iw):
                dx = ox + xx
                if dx < 0 or dx >= self.w:
                    continue
                o = (dy * self.w + dx) * 3
                s = xx * 4
                self.px[o] = row[s]
                self.px[o + 1] = row[s + 1]
                self.px[o + 2] = row[s + 2]


# -------------------------------------------------------------- PNG decode
def _paeth(a, b, c):
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter(raw, w, h, bpp, rowbytes):
    out = bytearray()
    prev = bytearray(rowbytes)
    pos = 0
    for _ in range(h):
        ftype = raw[pos]
        pos += 1
        row = bytearray(raw[pos:pos + rowbytes])
        pos += rowbytes
        if ftype == 0:
            pass
        elif ftype == 1:
            for i in range(bpp, rowbytes):
                row[i] = (row[i] + row[i - bpp]) & 0xFF
        elif ftype == 2:
            for i in range(rowbytes):
                row[i] = (row[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(rowbytes):
                left = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(rowbytes):
                a = row[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + _paeth(a, b, c)) & 0xFF
        else:
            raise ValueError("bad PNG filter %d" % ftype)
        out += row
        prev = row
    return out


def decode_png(path):
    """Return (w, h, rows) where rows are RGBA byte strings, one per row."""
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("%s: not a PNG" % path)
    pos = 8
    idat = bytearray()
    plte = None
    trns = None
    width = height = bitdepth = colortype = interlace = None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            width, height, bitdepth, colortype, _comp, _filt, interlace = struct.unpack(
                ">IIBBBBB", chunk)
        elif ctype == b"PLTE":
            plte = chunk
        elif ctype == b"tRNS":
            trns = chunk
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
    if interlace != 0:
        raise ValueError("%s: interlaced PNG not supported" % path)
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[colortype]
    if bitdepth not in (1, 2, 4, 8):
        raise ValueError("%s: bit depth %d not supported" % (path, bitdepth))
    bpp = max(1, channels * bitdepth // 8)
    rowbytes = (width * channels * bitdepth + 7) // 8
    raw = zlib.decompress(bytes(idat))
    pix = _unfilter(raw, width, height, bpp, rowbytes)
    rows = []
    for y in range(height):
        row = pix[y * rowbytes:(y + 1) * rowbytes]
        rows.append(_expand_row(row, width, colortype, bitdepth, plte, trns))
    return width, height, rows


def _expand_row(row, width, colortype, bitdepth, plte, trns):
    out = bytearray()
    if colortype == 6 and bitdepth == 8:
        return bytes(row)
    if colortype == 2 and bitdepth == 8:
        for i in range(width):
            out += row[i * 3:i * 3 + 3]
            out.append(255)
        return bytes(out)
    if colortype == 0:
        if bitdepth == 8:
            for i in range(width):
                g = row[i]
                out += bytes((g, g, g, 255))
            return bytes(out)
        # sub-byte grey: unpack MSB-first
        vals = _unpack_bits(row, width, bitdepth)
        maxv = (1 << bitdepth) - 1
        for v in vals:
            g = v * 255 // maxv
            out += bytes((g, g, g, 255))
        return bytes(out)
    if colortype == 3:
        idx = _unpack_bits(row, width, bitdepth) if bitdepth < 8 else list(row[:width])
        for i in idx:
            r, g, b = plte[i * 3:i * 3 + 3]
            a = trns[i] if trns is not None and i < len(trns) else 255
            out += bytes((r, g, b, a))
        return bytes(out)
    raise ValueError("unsupported PNG color type %d depth %d" % (colortype, bitdepth))


def _unpack_bits(row, width, bitdepth):
    vals = []
    per = 8 // bitdepth
    mask = (1 << bitdepth) - 1
    for byte in row:
        for k in range(per):
            shift = 8 - bitdepth * (k + 1)
            vals.append((byte >> shift) & mask)
            if len(vals) >= width:
                return vals
    return vals


# -------------------------------------------------------------- PNG encode
def _filter_row(ftype, row, prev, bpp):
    out = bytearray(row)
    if ftype == 0:
        return bytes(out)
    if ftype == 1:
        for i in range(len(out) - 1, bpp - 1, -1):
            out[i] = (out[i] - out[i - bpp]) & 0xFF
        return bytes(out)
    if ftype == 2:
        for i in range(len(out)):
            out[i] = (out[i] - prev[i]) & 0xFF
        return bytes(out)
    if ftype == 4:
        for i in range(len(out)):
            a = out[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            out[i] = (out[i] - _paeth(a, b, c)) & 0xFF
        return bytes(out)
    raise ValueError("bad filter %d" % ftype)


def _row_cost(fbytes):
    return sum(abs(b if b < 128 else b - 256) for b in fbytes)


def encode_png_rgb(canvas):
    """Encode the canvas as an RGB PNG (no ancillary chunks, deterministic)."""
    w, h = canvas.w, canvas.h
    raw = bytearray()
    prev = bytearray(w * 3)
    for y in range(h):
        row = bytes(canvas.px[y * w * 3:(y + 1) * w * 3])
        best = None
        best_cost = None
        for ftype in (0, 1, 2, 4):
            fbytes = _filter_row(ftype, row, prev, 3)
            cost = _row_cost(fbytes)
            if best_cost is None or cost < best_cost:
                best_cost = cost
                best = bytes([ftype]) + fbytes
        raw += best
        prev = bytearray(row)
    comp = zlib.compress(bytes(raw), 9)

    def chunk(ctype, payload):
        return (struct.pack(">I", len(payload)) + ctype + payload
                + struct.pack(">I", binascii.crc32(ctype + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


# -------------------------------------------------------------------- main
def main():
    with open(os.path.join(BASE, "news.json"), encoding="utf-8") as f:
        news = json.load(f)
    stories = news["stories"]
    if len(stories) != 35:
        raise ValueError("expected 35 stories, got %d" % len(stories))
    with open(os.path.join(BASE, "assets.json"), encoding="utf-8") as f:
        assets = json.load(f)

    canvas = Canvas(W, H, CREAM)

    # ticker bar (full width) + section rules
    canvas.rect(0, TICKER_Y, W, TICKER_H, RED)
    for y in (348, 612, 808, 982):
        canvas.hline(MARGIN, y, W - 2 * MARGIN, RULE)

    # illustrations
    for n in sorted(assets["illu"], key=lambda k: int(k)):
        slot = assets["illu"][n]
        img = decode_png(os.path.join(BASE, slot["file"]))
        if img[0] != slot["w"] or img[1] != slot["h"]:
            raise ValueError("%s: size %dx%d, manifest says %dx%d"
                             % (slot["file"], img[0], img[1], slot["w"], slot["h"]))
        canvas.paste_rgb(img, slot["x"], slot["y"])

    # dotted world map
    m = assets["map"]
    map_img = decode_png(os.path.join(BASE, m["file"]))
    canvas.paste_rgb(map_img, m["x"], m["y"])

    # text overlay (RGBA, on top of everything)
    ov = decode_png(os.path.join(BASE, assets["overlay"]))
    if ov[0] != W or ov[1] != H:
        raise ValueError("overlay size %dx%d, expected %dx%d" % (ov[0], ov[1], W, H))
    canvas.paste_rgba(ov, 0, 0)

    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    outpath = os.path.join(outdir, "entry.png")
    png = encode_png_rgb(canvas)
    with open(outpath, "wb") as f:
        f.write(png)
    digest = hashlib.sha256(png).hexdigest()
    print("WROTE %s %d bytes sha256=%s" % (outpath, len(png), digest))
    if len(png) > 1048576:
        print("ERROR: output exceeds 1 MiB", file=sys.stderr)
        sys.exit(1)
    if canvas.w > 1024 or canvas.h > 1024:
        print("ERROR: output exceeds 1024x1024", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

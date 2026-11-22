"""Just enough PNG to move clipboard pictures to and from Windows, which keeps them as DIBs
(device-independent bitmaps). Pictures travel between computers as PNG.

decode() reads 8-bit non-interlaced PNGs (grey, RGB, palette, grey+alpha, RGBA): what screenshots
and copied images are. encode() writes RGBA.
"""

import struct
import zlib


class PNGError(Exception):
    pass


def encode(width, height, rgba):
    """rgba: bytes, rows top to bottom, 4 bytes a pixel."""
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))


def decode(data):
    """-> (width, height, rgba bytes top to bottom)."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise PNGError("not a PNG")
    pos, idat, plte, trns = 8, bytearray(), None, None
    w = h = depth = ctype = interlace = None
    while pos + 8 <= len(data):
        n, t = struct.unpack(">I4s", data[pos:pos + 8])
        d = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if t == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", d)
        elif t == b"PLTE":
            plte = d
        elif t == b"tRNS":
            trns = d
        elif t == b"IDAT":
            idat += d
        elif t == b"IEND":
            break
    if w is None or depth != 8 or interlace:
        raise PNGError("unsupported PNG (needs 8-bit, not interlaced)")
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype)
    if not bpp:
        raise PNGError("unsupported colour type")
    raw = zlib.decompress(bytes(idat))
    stride = w * bpp
    prev = bytearray(stride)
    out = bytearray(w * h * 4)
    i = 0
    for y in range(h):
        f = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        _unfilter(f, line, prev, bpp)
        o = y * w * 4
        if ctype == 6:
            out[o:o + w * 4] = line
        elif ctype == 2:
            out[o:o + w * 4:4] = line[0::3]
            out[o + 1:o + w * 4:4] = line[1::3]
            out[o + 2:o + w * 4:4] = line[2::3]
            out[o + 3:o + w * 4:4] = b"\xff" * w
        elif ctype == 0:
            for k in range(3):
                out[o + k:o + w * 4:4] = line
            out[o + 3:o + w * 4:4] = b"\xff" * w
        elif ctype == 4:
            for k in range(3):
                out[o + k:o + w * 4:4] = line[0::2]
            out[o + 3:o + w * 4:4] = line[1::2]
        else:
            for x in range(w):
                idx = line[x]
                out[o + x * 4:o + x * 4 + 3] = plte[idx * 3:idx * 3 + 3]
                out[o + x * 4 + 3] = trns[idx] if trns and idx < len(trns) else 255
        prev = line
    return w, h, bytes(out)


def _unfilter(f, line, prev, bpp):
    n = len(line)
    if f == 0:
        return
    if f == 1:
        for x in range(bpp, n):
            line[x] = (line[x] + line[x - bpp]) & 0xFF
    elif f == 2:
        for x in range(n):
            line[x] = (line[x] + prev[x]) & 0xFF
    elif f == 3:
        for x in range(n):
            a = line[x - bpp] if x >= bpp else 0
            line[x] = (line[x] + ((a + prev[x]) >> 1)) & 0xFF
    elif f == 4:
        for x in range(n):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
            line[x] = (line[x] + pr) & 0xFF
    else:
        raise PNGError("bad filter")


# ---- Windows DIB <-> PNG -------------------------------------------------------

def dib_to_png(dib):
    """A CF_DIB / CF_DIBV5 blob (BITMAPINFOHEADER + pixels) -> PNG bytes."""
    hsize, w, h, planes, bits, comp = struct.unpack("<IiiHHI", dib[:20])
    clr_used = struct.unpack("<I", dib[32:36])[0]
    if bits not in (24, 32):
        raise PNGError("only 24 and 32-bit pictures")
    offset = hsize
    if comp == 3 and hsize == 40:
        offset += 12  # BI_BITFIELDS masks after a plain header
    offset += clr_used * 4
    top_down = h < 0
    h = abs(h)
    bpp = bits // 8
    stride = ((w * bits + 31) // 32) * 4
    px = dib[offset:]
    alpha_any = False
    if bits == 32:
        for y in range(h):
            if any(px[y * stride + 3:y * stride + w * 4:4]):
                alpha_any = True
                break
    out = bytearray(w * h * 4)
    for y in range(h):
        sy = y if top_down else h - 1 - y
        row = px[sy * stride:sy * stride + w * bpp]
        o = y * w * 4
        out[o:o + w * 4:4] = row[2::bpp]
        out[o + 1:o + w * 4:4] = row[1::bpp]
        out[o + 2:o + w * 4:4] = row[0::bpp]
        out[o + 3:o + w * 4:4] = row[3::4] if (bits == 32 and alpha_any) else b"\xff" * w
    return encode(w, h, bytes(out))


def png_to_dib(data):
    """PNG bytes -> a CF_DIB blob (32-bit, bottom-up, BI_RGB)."""
    w, h, rgba = decode(data)
    hdr = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 32, 0, w * h * 4, 2835, 2835, 0, 0)
    out = bytearray(w * h * 4)
    for y in range(h):
        src = rgba[(h - 1 - y) * w * 4:(h - y) * w * 4]
        o = y * w * 4
        out[o:o + w * 4:4] = src[2::4]
        out[o + 1:o + w * 4:4] = src[1::4]
        out[o + 2:o + w * 4:4] = src[0::4]
        out[o + 3:o + w * 4:4] = src[3::4]
    return hdr + bytes(out)

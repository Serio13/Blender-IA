"""Lector PNG minimo (8 bits, RGB/RGBA) para comprobar lo que escribe Blender sin depender de Blender."""
import struct
import zlib

import numpy as np


def read_png(path):
    data = open(path, "rb").read()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, meta = 8, b"", None
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            meta = struct.unpack(">IIBBBBB", chunk)
        elif kind == b"IDAT":
            idat += chunk
        pos += 12 + length
    w, h, depth, ctype = meta[:4]
    assert depth == 8 and ctype in (2, 6), "solo 8 bits RGB/RGBA (depth=%s ctype=%s)" % (depth, ctype)
    bpp = 3 if ctype == 2 else 4
    raw = zlib.decompress(idat)
    stride = w * bpp
    out = np.zeros((h, stride), dtype=np.int32)
    prev = np.zeros(stride, dtype=np.int32)
    i = 0
    for y in range(h):
        f = raw[i]
        line = np.frombuffer(raw[i + 1:i + 1 + stride], dtype=np.uint8).astype(np.int32)
        i += 1 + stride
        if f == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 255
        elif f == 2:
            line = (line + prev) & 255
        elif f == 3:
            for x in range(stride):
                left = line[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + ((left + prev[x]) >> 1)) & 255
        elif f == 4:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pred) & 255
        out[y] = line
        prev = line
    arr = out.reshape(h, w, bpp).astype(np.float32) / 255.0
    if bpp == 3:
        arr = np.concatenate([arr, np.ones((h, w, 1), np.float32)], axis=2)
    return arr

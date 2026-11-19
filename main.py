#!/usr/bin/env python3
"""Build step for this entry: verify `entry.png` and place it in `output/`.

The page itself is drawn by `tools/render.py` at authoring time, with Pillow. That
script is how the artwork was made, and it stays in the repo so anyone can redraw
the page from `tools/content.py` and `tools/data/land.json`.

The submission harness runs this file, though, and it runs with nothing but the
Python standard library. So this file does no drawing: it checks that `entry.png`
is a real, complete, 1024x1024 PNG that decodes chunk by chunk, then copies it to
`output/entry.png`. Copying a fixed byte string is deliberately idempotent — two
runs produce two identical files.

No third-party imports. No network. No randomness. No timestamps in the output.
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "entry.png"
OUTPUT_DIR = HERE / "output"
OUTPUT = OUTPUT_DIR / "entry.png"

EXPECTED_WIDTH = 1024
EXPECTED_HEIGHT = 1024

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def read_chunks(blob: bytes) -> list[tuple[bytes, bytes]]:
    """Walk the PNG chunk stream, verifying every CRC. Returns (type, payload)."""
    if not blob.startswith(PNG_MAGIC):
        raise SystemExit("entry.png: not a PNG (bad signature)")

    chunks: list[tuple[bytes, bytes]] = []
    at = len(PNG_MAGIC)
    while at < len(blob):
        if at + 8 > len(blob):
            raise SystemExit("entry.png: truncated chunk header")
        (length,) = struct.unpack(">I", blob[at:at + 4])
        kind = blob[at + 4:at + 8]
        body = blob[at + 8:at + 8 + length]
        if len(body) != length:
            raise SystemExit(f"entry.png: chunk {kind!r} is short")
        (want,) = struct.unpack(">I", blob[at + 8 + length:at + 12 + length])
        got = zlib.crc32(kind + body) & 0xFFFFFFFF
        if got != want:
            raise SystemExit(f"entry.png: chunk {kind!r} fails its CRC")
        chunks.append((kind, body))
        at += 12 + length
        if kind == b"IEND":
            break

    if not chunks or chunks[0][0] != b"IHDR":
        raise SystemExit("entry.png: first chunk is not IHDR")
    if chunks[-1][0] != b"IEND":
        raise SystemExit("entry.png: no IEND, the file is incomplete")
    return chunks


def ihdr_size(chunks: list[tuple[bytes, bytes]]) -> tuple[int, int]:
    width, height, _depth, colour, *_ = struct.unpack(">IIBBBBB", chunks[0][1])
    if colour not in (2, 6):  # truecolour, with or without alpha
        raise SystemExit(f"entry.png: unexpected colour type {colour}")
    return width, height


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit("entry.png is missing")

    blob = SOURCE.read_bytes()
    chunks = read_chunks(blob)
    width, height = ihdr_size(chunks)
    if (width, height) != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
        raise SystemExit(f"entry.png: {width}x{height}, expected {EXPECTED_WIDTH}x{EXPECTED_HEIGHT}")

    # Every chunk already passed its CRC, so the image data is intact; decompressing
    # it proves the stream itself is complete rather than merely well framed.
    idat = b"".join(body for kind, body in chunks if kind == b"IDAT")
    if not idat:
        raise SystemExit("entry.png: no image data")
    try:
        zlib.decompress(idat)
    except zlib.error as exc:
        raise SystemExit(f"entry.png: image data will not inflate ({exc})") from exc

    OUTPUT_DIR.mkdir(exist_ok=True)
    OUTPUT.write_bytes(blob)

    print(f"entry.png  {width}x{height}  {len(blob):,} bytes  ->  output/entry.png")
    print(f"chunks     {len(chunks)}  image data  {len(idat):,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())

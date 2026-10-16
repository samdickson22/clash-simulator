"""Bounded decoding of the nine-byte LZMA header used by native logic assets."""

from __future__ import annotations

import lzma


def decode_logic_asset(data: bytes, *, max_bytes: int = 16 * 1024 * 1024) -> bytes:
    """Decode a declared-size asset without trusting its decompression size."""
    if len(data) < 10:
        raise ValueError("truncated logic asset header")
    size = int.from_bytes(data[5:9], "little")
    if size > max_bytes:
        raise ValueError("logic asset exceeds decoded size limit")
    # LZMA-alone stores an eight-byte size; the asset format stores four.
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE, memlimit=64 * 1024 * 1024)
    try:
        result = decoder.decompress(data[:9] + bytes(4) + data[9:], max_length=size + 1)
    except lzma.LZMAError as error:
        raise ValueError("invalid compressed logic asset") from error
    if len(result) != size or not decoder.eof or decoder.unused_data:
        raise ValueError("logic asset length or stream boundary mismatch")
    return result

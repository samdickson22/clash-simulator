import lzma

import pytest

from clasher.native_assets import decode_logic_asset


def asset(plain):
    encoded = lzma.compress(plain, format=lzma.FORMAT_ALONE)
    return encoded[:5] + len(plain).to_bytes(4, "little") + encoded[13:]


def test_decodes_native_header_and_preserves_exact_text():
    plain = b'[ACTION.Test]\nClassType = "ActionGroup"\n'
    assert decode_logic_asset(asset(plain)) == plain


@pytest.mark.parametrize("kind", ["truncated", "size", "trailing", "limit"])
def test_rejects_corruption_and_excessive_allocation(kind):
    data = asset(b"hello")
    if kind == "truncated":
        data = data[:-5]
    elif kind == "size":
        data = data[:5] + (3).to_bytes(4, "little") + data[9:]
    elif kind == "trailing":
        data += b"extra"
    with pytest.raises(ValueError):
        decode_logic_asset(data, max_bytes=4 if kind == "limit" else 100)

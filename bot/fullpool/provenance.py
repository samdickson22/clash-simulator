"""Runtime provenance tag for generated data (pin set, root, receipt/native/gamedata shas), so every shard and row
records which card mechanics produced it (later card batches arrive as new pins; data can then be weighted or
refreshed by pin)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=None)
def _sha(path):
    from bot.fullpool.extend import sha256
    return sha256(path) if Path(path).exists() else None


def runtime_tag(rt):
    root = Path(rt.root)
    return dict(pins=os.environ.get('CLASHER_BOT_RUNTIME_PINS', 'r1'), root=str(root),
                root_receipt_sha256=_sha(str(root / 'CARDS-RUNTIME-RECEIPT.json')),
                native_sha256=rt.pins.get('native_sha256'), gamedata_sha256=rt.pins.get('gamedata_sha256'),
                card_scope=rt.pins.get('card_scope', 'c56'))

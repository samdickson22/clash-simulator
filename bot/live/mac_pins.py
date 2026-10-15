"""Extra runtime pin sets for non-Linux natives (LIVE track; no change to Linux behaviour).

bot/players/runtime.py asserts the native/checkpoint SHA-256s of the pin set named by CLASHER_BOT_RUNTIME_PINS
(default 'r1' = the Linux native 44874fd6). A Mac-built clasher_core.abi3.so has another hash, so the Mac needs its
own set. Instead of editing runtime.py, `register()` adds the sets in mac_pins.json to runtime.PIN_SETS (r1/r2 are
never overwritten) and must run before Runtime():

    import bot.live.mac_pins; bot.live.mac_pins.register()
    CLASHER_BOT_RUNTIME_PINS=mac-r1 CLASHER_DELAY_NATIVE_DIR=<root>/native-mac  ... Runtime()

A Mac set only differs in native_sha256 (same R3a/main02 checkpoints). Fill mac_pins.json ONLY after
`python -m bot.live.native_parity check` passes on the Mac with that binary. `python -m bot.live.mac_pins` prints the
active set.
"""
from __future__ import annotations

import json
from pathlib import Path

PIN_FILE = Path(__file__).with_name('mac_pins.json')


def register(path=PIN_FILE):
    from bot.players import runtime
    if not Path(path).exists():
        return []
    sets = json.loads(Path(path).read_text())
    added = []
    for name, spec in sets.items():
        if name in ('r1', 'r2'):
            raise ValueError('mac_pins.json must not redefine the Linux pin sets')
        if set(spec) - {'native_sha256', 'base', 'note', 'parity_fixture_sha256'}:
            raise ValueError(f'{name}: only native_sha256 may differ from its base set')
        base = runtime.PIN_SETS[spec.get('base', 'r1')]
        runtime.PIN_SETS[name] = dict(base, native_sha256=spec['native_sha256'])
        added.append(name)
    return added


if __name__ == '__main__':
    print(register())
    from bot.players.runtime import selected_pins
    print(selected_pins())

"""Bind the completed canonical 64-game gate to this source and binary."""
import hashlib
import json
from pathlib import Path
from stage2 import fingerprint

out = Path(__file__).resolve().parent
receipt = out / 'stage2_games.json'
games = json.loads(receipt.read_text())
assert games['fingerprint'] == fingerprint()
assert set(games['results']) == {str(i) for i in range(64)}
assert all(r['ok'] for r in games['results'].values())
files = ('engine-rs/src/lib.rs', 'engine-rs/clasher_core.abi3.so', 'engine-rs/differential.py', 'gamedata.json')
(out / 'stage2_full_gate.json').write_text(json.dumps(dict(games_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest(), games=64,
    boundaries=sum(r['boundaries'] for r in games['results'].values()), files={f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in files}), indent=2)+'\n')

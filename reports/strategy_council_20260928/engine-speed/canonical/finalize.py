"""Write readiness only after every canonical-data receipt has passed."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from stage2 import fingerprint as stage2_fingerprint
from test_stage3 import fingerprint as stage3_fingerprint

C = Path(__file__).resolve().parent
ES = C.parent
ROOT = ES.parents[2]

def read(name):
    return json.loads((C / name).read_text())

def last_json(name):
    return json.loads(next(line for line in reversed((C / name).read_text().splitlines()) if line.startswith('{')))

assert (C / 'rust.exit').read_text().strip() == '0'
assert (C / 'recorded.exit').read_text().strip() == '0'
assert (C / 'c56.exit').read_text().strip() == '0'
assert (C / 'cargo_clean.exit').read_text().strip() == '0'
assert (C / 'final_checks.exit').read_text().strip() == '0'
assert (C / 'native_recorded.exit').read_text().strip() == '0'
data = read('data_diff.json')
assert hashlib.sha256((ROOT / 'gamedata.json').read_bytes()).hexdigest() == data['sha256']
p16 = last_json('p16_workspace_final.log')
c56 = last_json('c56_canonical_check.log')
assert p16['checked_episodes'] == 12 and p16['mismatches'] == []
assert c56['episodes'] == 7 and c56['mismatches'] == []
random_base = json.loads((ES / 'random_identity_baseline_admitted.json').read_text())
random_work = read('random_workspace.json')
assert len(random_work['results']) == 24 and not random_work['mismatches']
assert random_base['results'] == random_work['results']
recorded_base = json.loads((ES / 'recorded_identity_baseline_admitted.json').read_text())
recorded_work = read('recorded_workspace.json')
assert len(recorded_work['results']) == 8 and not recorded_work['mismatches']
assert recorded_base['results'] == recorded_work['results']
assert all(r['actual'] == r['expected'] for r in recorded_work['results'].values())
native_recorded = read('native_recorded.json')['results']
assert len(native_recorded) == 8 and all(r['actual'] == r['expected'] for r in native_recorded)
games = read('stage2_games.json')
imports = read('stage2_snapshots.json')
placements = read('stage2_placements.json')
planner = read('stage3_planner.json')
native = read('stage3_games.json')
for receipt in (games, imports, placements):
    assert receipt['fingerprint'] == stage2_fingerprint()
    assert all(r['ok'] for r in receipt['results'].values())
assert len(games['results']) == 64
assert imports['summary']['imports'] >= 512 and imports['summary']['clone_gate']
assert sum(r['accepted'] for r in placements['results'].values()) >= 2000
assert all(sum(r['pocket_accepted'] for r in placements['results'].values() if r['seat'] == seat) > 0 for seat in (0, 1))
for receipt in (planner, native):
    assert receipt['fingerprint'] == stage3_fingerprint()
assert len(planner['results']) >= 50 and len(native['results']) >= 8
assert planner['corpus_sha256'] == hashlib.sha256((C / 'stage3_roots.pkl').read_bytes()).hexdigest()
summary = dict(
    time=datetime.now(timezone.utc).isoformat(), gamedata_sha256=data['sha256'], admitted_gamedata_sha256=data['admitted_sha256'],
    identity=dict(p16=p16, c56=c56, recorded=dict(episodes=8, mismatches=[]), random=dict(episodes=24, boundaries=sum(r['boundaries'] for r in random_work['results'].values()), pocket_placements=[sum(r['pocket_placements'][seat] for r in random_work['results'].values()) for seat in (0, 1)], mismatches=[])),
    rust=dict(stage2_games=64, stage2_boundaries=sum(r['boundaries'] for r in games['results'].values()), live_imports=imports['summary'], placements=sum(r['accepted'] for r in placements['results'].values()), placement_boundaries=sum(r['boundaries'] for r in placements['results'].values()), planner_calls=len(planner['results']), candidates=sum(r['candidates'] for r in planner['results'].values()), rollout_ticks=sum(r['rollout_ticks'] for r in planner['results'].values()), native_games=len(native['results']), native_game_ticks=sum(r['ticks'] for r in native['results'].values()), mismatches=0),
    native_recorded=dict(games=8, planner_calls=sum(r['actual']['planner_calls'] for r in native_recorded), mismatches=0),
    rust_binary_sha256=hashlib.sha256((ROOT/'engine-rs/clasher_core.abi3.so').read_bytes()).hexdigest(),
    report='reports/strategy_council_20260928/engine-speed/GAMEDATA_CANONICAL.md')
(C / 'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
marker = ES.parent / 'GAMEDATA_CANONICAL_READY'
assert not marker.exists()
# Caller finalizes the report before explicitly publishing the marker.
print(json.dumps(summary, indent=2))

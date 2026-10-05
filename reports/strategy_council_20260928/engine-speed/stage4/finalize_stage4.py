"""Publish Stage4 admission only from completed, source-bound gate receipts."""
import hashlib
import json
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(root/'engine-rs'))
from stage2 import fingerprint
folder=Path(__file__).resolve().parent
identity=fingerprint()
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
labels=('controller_checks_r65','controller_roots_r65','c56_games_r65',
        'fresh_placements_r65','c56_imports_r65b','c56_pockets_r65b',
        'adapter_regressions_r65b','area_adapter_proof','character_area_r65b')
for label in labels:
    assert (folder/f'{label}.exit').read_text().strip()=='0',label
bridge_path=folder/'area_adapter_requalification.json'
bridge=json.loads(bridge_path.read_text())
assert bridge['new_fingerprint']==identity
assert bridge['proof_source_sha256']==sha(folder/'qualify_area_adapter.py')
assert bridge['native_binary_sha256']==sha(root/'engine-rs/clasher_core.abi3.so')
assert len(bridge['identical_initial_states'])==78
receipts={}
for name in ('controller_roots','c56_games','c56_placements'):
    path=folder/f'{name}_r65.json'
    assert sha(path)==bridge['frozen_receipts'][str(path.relative_to(root))]
    receipts[name]=json.loads(path.read_text())
    assert receipts[name]['fingerprint']==bridge['old_fingerprint']
for name in ('c56_imports','c56_pockets'):
    receipts[name]=json.loads((folder/f'{name}_r65b.json').read_text())
    assert receipts[name]['fingerprint']==identity
    assert receipts[name]['adapter_requalification_sha256']==sha(bridge_path)
assert receipts['c56_imports']['source_game_fingerprint']==bridge['old_fingerprint']
assert receipts['c56_pockets']['source_games_sha256']==sha(folder/'c56_games_r65.json')
assert receipts['c56_pockets']['driver_sha256']==sha(folder/'pocket_placements_r65b.py')
plan=folder/'c56_human64_plan.json';plan_sha=sha(plan)
declaration=json.loads(plan.read_text())
assert all(sha(root/name)==digest for name,digest in declaration['sources'].items())
assert len(declaration['episodes'])==64
assert all(r['plan_sha256']==plan_sha for r in receipts.values())
assert set(receipts['c56_games']['results'])=={str(i) for i in range(64)}
assert set(receipts['c56_imports']['results'])==set(receipts['c56_games']['results'])
for key,row in receipts['c56_games']['results'].items():
    assert row['episode']==declaration['episodes'][int(key)]
assert all(v['ok'] for r in receipts.values() for v in r['results'].values())
roots=[v for r in receipts['controller_roots']['results'].values() for v in r['roots']]
assert len(roots)>=256 and all(r['seats']==2 and r['styles']==3 for r in roots)
games=list(receipts['c56_games']['results'].values())
assert len(games)>=64 and all(r['terminal'] and r['decisions']>0 for r in games)
imports=[v for r in receipts['c56_imports']['results'].values() for v in r['roots']]
assert len(imports)>=1024 and all(r['root_tick']>0 and r['ticks']==200 for r in imports)
placements=[v for name in ('c56_placements','c56_pockets') for r in receipts[name]['results'].values() for v in r['placements']]
assert all(r['root_crowns']>0 and r['root_tick']>0 for r in receipts['c56_pockets']['results'].values())
accepted=[v for v in placements if v['accepted']]
assert len(accepted)>=4480
assert all(any(p['pocket'] and p['seat']==seat for p in accepted) for seat in (0,1))
assert all(any(p['enemy_side'] and p['card']==name for p in accepted) for name in ('Miner','GoblinBarrel'))
assert len({p['card'] for p in accepted})==56
stream=folder/'stream_imports_r65b.py'
assert receipts['c56_imports']['stream_driver_sha256']==hashlib.sha256(stream.read_bytes()).hexdigest()
for key,row in receipts['c56_imports']['results'].items():
    assert row['game_record_sha256']==hashlib.sha256(json.dumps(receipts['c56_games']['results'][key],sort_keys=True).encode()).hexdigest()
fresh=folder/'fresh_placements.py'
assert receipts['c56_placements']['fresh_driver_sha256']==hashlib.sha256(fresh.read_bytes()).hexdigest()
card_path=folder/'card_kernel_r64_manifest.json';card=json.loads(card_path.read_text())
assert card['status'].startswith('card kernel admitted')
exporters={'differential.py','live_snapshot.py','scope_snapshot.py','spawn_snapshot.py','champion_snapshot.py'}
assert bridge['old_exporter_sha256']==card['hashes']['engine-rs/live_snapshot.py']
assert bridge['new_exporter_sha256']==sha(root/'engine-rs/live_snapshot.py')
for name,digest in card['hashes'].items():
    if name=='engine-rs/live_snapshot.py':
        continue
    if (name.startswith('engine-rs/src/') and name!='engine-rs/src/scripts.rs') or (name.startswith('engine-rs/') and Path(name).name in exporters) or name=='gamedata.json':
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest, f'physics requires recertification: {name}'
assert hashlib.sha256((root/card['frozen_native_library']).read_bytes()).hexdigest()==card['hashes']['engine-rs/clasher_core.abi3.so']
entry=json.loads((folder/'start_sources.json').read_text())['hashes']
assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in entry.items() if name.startswith('src/clasher/') or name=='gamedata.json')
repair=root/'reports/strategy_council_20260928/c56/data/qa/v3b/gates.json'
assert hashlib.sha256(repair.read_bytes()).hexdigest()==card['repair_gate_sha256']
assert hashlib.sha256((root/'src/clasher/cards/c56_champions.py').read_bytes()).hexdigest()==card['final_champion_source_sha256']
assert (folder/'champion_identity_r61b.exit').read_text().strip()=='0'
assert 'Identity checks passed: stage4_champions_r61b' in (folder.parent/'logs/stage4_champion_identity_r61b.log').read_text()
log=(folder.parent/'logs/stage4_controller_checks_r65.log').read_text()
assert 'Ran 13 tests' in log and '\nOK\n' in log
log=(folder.parent/'logs/stage4_adapter_regressions_r65b.log').read_text()
assert 'Ran 126 tests' in log and '\nOK\n' in log
speed=sum(r['python_cpu'] for r in games)/sum(r['rust_cpu'] for r in games)
clone=max(r['clone_us'] for r in imports)
assert speed>=30 and clone<20,(speed,clone)
paths=[*root.joinpath('engine-rs/src').glob('*.rs'),*root.joinpath('engine-rs').glob('*.py'),root/'engine-rs/build.sh',root/'engine-rs/clasher_core.abi3.so',root/'gamedata.json']
out=dict(status='Stage4 admitted on required C56 gates; native C56 SRP Stage5 not implemented',fingerprint=identity,plan_sha256=plan_sha,
    frozen_simulation_fingerprint=bridge['old_fingerprint'],adapter_requalification_sha256=sha(bridge_path),
    receipt_sha256={name:sha(folder/f'{name}_{"r65b" if name in ("c56_imports","c56_pockets") else "r65"}.json') for name in receipts},
    validator_sha256=sha(Path(__file__)),adapter_regressions=126,
    gate_exit_sha256={label:sha(folder/f'{label}.exit') for label in labels},
    validation_log_sha256={label:sha(folder.parent/f'logs/stage4_{label}.log') for label in ('controller_checks_r65','adapter_regressions_r65b','champion_identity_r61b')},
    scope=dict(actor_cards=56,engine_cards=62,extra_opponent_cards=6,level=11,script_abilities='masked; engine ability API qualified separately'),
    card_kernel_certificate_sha256=hashlib.sha256(card_path.read_bytes()).hexdigest(),card_regressions=card['regressions'],focused_cases=card['focused_cases'],focused_ticks=card['focused_ticks'],prior_bundle_games=card['prior_bundle_games'],champion_games=card['champion_games'],champion_accepted_abilities=card['accepted_abilities'],controller_regressions=13,
    controller_roots=len(roots),controller_actor_roots=sum(r['seats'] for r in roots),controller_style_comparisons=sum(r['seats']*r['styles'] for r in roots),
    native_scripted_human_games=len(games),game_ticks=sum(r['ticks'] for r in games),controller_decisions=sum(r['decisions'] for r in games),accepted_game_plays=sum(r['accepted'] for r in games),
    live_imports=len(imports),import_continuation_ticks=sum(r['ticks'] for r in imports),accepted_public_placements=len(accepted),placement_continuation_ticks=len(placements)*80,placement_cards=sorted({p['card'] for p in accepted}),pocket_placements_by_seat={seat:sum(p['pocket'] and p['seat']==seat for p in accepted) for seat in (0,1)},enemy_side_anywhere_placements={name:sum(p['enemy_side'] and p['card']==name for p in accepted) for name in ('Miner','GoblinBarrel')},
    step_speedup=speed,max_100_clone_mean_us=clone,mismatches=dict(digest=0,actions=0,rng=0,public_views=0,masks=0),python_identity='P16+C56+recorded8+random24 passed; reference source/data unchanged',
    final_champion_source_sha256=card['final_champion_source_sha256'],repair_gate_sha256=card['repair_gate_sha256'],hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
(folder/'stage4_manifest.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ('hashes','placement_cards')},indent=2))

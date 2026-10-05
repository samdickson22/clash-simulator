"""Final read-only integrity/resource audit; quality gates remain separate."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import subprocess

ROOT=Path('/Users/sam/Desktop/code/clasher')
L1=ROOT/'reports/strategy_council_20260928/live-loop/l1'
V3=L1/'v3'
DATA=V3/'dataset-merged'
read=lambda p:[json.loads(l) for l in p.read_text().splitlines()]
sha=lambda p:hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
manifest=json.loads((DATA/'manifest.json').read_text())
episodes={e['episode_id']:e for e in read(DATA/'episodes-merged.jsonl')}
selection=json.loads((V3/'evaluation-validation/selection.json').read_text())
checks={};coverage={s:Counter() for s in ('train','validation','heldout')}
seeds=[];decks=[];video_errors=[];fence_errors=[];receipt_errors=[];cost_errors=[];frame_errors=[]
count=frames=incomplete=0
for entry in manifest['matches']:
    ep=entry['episode_id'];stats=episodes[ep];seeds.append(entry['seed'])
    decks.extend(tuple(sorted(d)) for d in entry['decks'])
    video=DATA/'videos'/f'{ep}.mp4'
    if sha(video)!=stats['video_sha256']:video_errors.append(ep)
    folder=DATA/'evaluation_only'/ep
    fr=read(folder/'frames.jsonl');frames+=len(fr)
    if len(fr)!=stats['frames'] or any(r['frame_index']!=i for i,r in enumerate(fr)):frame_errors.append(ep)
    if any(a['timestamp_ms']>=b['timestamp_ms'] for a,b in zip(fr,fr[1:])):frame_errors.append(ep)
    for row in read(folder/'observations.jsonl'):
        fence=row.get('observation_fence',{})
        if (not fence.get('no_logic_step_during_observation') or fence.get('before')!=fence.get('after')
                or fence['before'][2]!=row['tick']):fence_errors.append(ep);break
    accepted=[e for e in read(folder/'events.jsonl') if e['accepted']]
    count+=len(accepted)
    if len(accepted)!=stats['accepted_events']:receipt_errors.append(ep)
    for e in accepted:
        if e['status']['state']!='succeeded' or e['status']['executeTick']!=e['tick']:receipt_errors.append(ep)
        if e['cost']!=selection['costs'][e['card']]:cost_errors.append([ep,e['card'],e['cost'],selection['costs'][e['card']]])
        if entry['split']=='train' or entry['capture_protocol']>=2:coverage[entry['split']][e['player_id'],e['card']]+=1
    audit=json.loads((V3/'audit'/ep/'complete.json').read_text())
    incomplete+=len(audit['incomplete_event_windows'])
    if entry['split']!='train' and entry['capture_protocol']>=2:
        if audit['incomplete_event_windows'] or audit['unresolved_scheduled_commands']:receipt_errors.append(ep)
checks.update(minimum_deployments=count>=3000,minimum_complete_windows=count-incomplete>=3000,
    seeds_disjoint=len(seeds)==len(set(seeds)),decks_disjoint=len(decks)==len(set(decks)),
    video_hashes=not video_errors,frame_counts_and_times=not frame_errors,
    native_observation_fences=not fence_errors,accepted_receipts=not receipt_errors,public_cost_parity=not cost_errors)
missing={s:[f'{side}:{name}' for side in (0,1) for name in manifest['cards'] if not c[side,name]] for s,c in coverage.items()}
checks['all_56_cards_both_sides_in_each_split']=not any(missing.values())
old_decks=set()
for path in (L1/'dataset/manifest.json',L1/'v1/dataset-merged/manifest.json',L1/'v2/dataset/manifest.json'):
    for entry in json.loads(path.read_text())['matches']:old_decks.update(tuple(sorted(d)) for d in entry['decks'])
checks['decks_disjoint_from_previous_l1']=not(set(decks)&old_decks)
model_meta=json.loads((V3/'model/manifest.json').read_text())
checks['training_split_only']=set(model_meta['training_episodes'])=={e['episode_id'] for e in manifest['matches'] if e['split']=='train'}
checks['model_hash']=sha(V3/'model/last.pt')==json.loads((V3/'model/complete.json').read_text())['sha256']
source_errors=[]
for split in ('validation','heldout'):
    folder=V3/f'inference-{split}';complete=json.loads((folder/'complete.json').read_text())
    for name in ('frames','candidates'):
        checks[f'{split}_{name}_hash']=sha(folder/(name+'.jsonl'))==complete[name+'_sha256']
    for path,digest in json.loads((folder/'manifest.json').read_text())['sources'].items():
        if sha(Path(path))!=digest:source_errors.append(path)
checks['inference_source_and_input_pins']=not source_errors
held=json.loads((V3/'evaluation-heldout/metrics.json').read_text())
checks['heldout_selection_pin']=held['selection_sha256']==sha(V3/'evaluation-validation/selection.json')
checks['boundary_audit']=json.loads((V3/'boundary-runtime.json').read_text())['passed']
reference=ROOT/'reports/strategy_council_20260928/srp-public/derived_public_state.py'
checks['protected_reference_unchanged']=sha(reference)==sha(L1/'v2/derived_public_state_reference.py')
live=[]
for path in V3.glob('emulator*/complete.json'):
    r=json.loads(path.read_text());stop=path.parent/'stop.json'
    if not stop.exists() or not json.loads(stop.read_text()).get('stopped'):live.append(r['pid']);continue
    proc=subprocess.run(['ps','-p',str(r['pid']),'-o','command='],capture_output=True,text=True)
    if proc.returncode==0 and 'clasher_reference_api35' in proc.stdout and '-port '+r['serial'].split('-')[-1] in proc.stdout:live.append(r['pid'])
checks['all_owned_emulators_stopped']=not live

def sizes(root):
    seen=set();logical=allocated=0
    for path in root.rglob('*'):
        if not path.is_file():continue
        s=path.stat();key=s.st_dev,s.st_ino
        if key in seen:continue
        seen.add(key);logical+=s.st_size;allocated+=s.st_blocks*512
    return dict(logical_bytes=logical,allocated_bytes=allocated,unique_files=len(seen))
new=sizes(V3);total=sizes(L1.parent)
checks['new_data_cap']=max(new['logical_bytes'],new['allocated_bytes'])<2*1024**3
checks['live_loop_cap']=max(total['logical_bytes'],total['allocated_bytes'])<5.5*1024**3
result=dict(checks=checks,passed=all(checks.values()),deployments=count,complete_event_windows=count-incomplete,
    frames=frames,matches=len(episodes),coverage_missing=missing,new_storage=new,live_loop_storage=total,
    video_errors=video_errors,fence_errors=fence_errors,receipt_errors=receipt_errors,cost_errors=cost_errors,
    source_errors=source_errors,owned_emulators_still_running=live,quality_gates=held['gates'],acceptance_established=False,
    tests='51 focused L1 tests passed; these do not override failed stream quality gates.')
(V3/'final-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['passed'] else 1)

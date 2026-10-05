import bootstrap
from bootstrap import HERE,ROOT
import hashlib,json,time
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert 'OK' in (HERE/'tests-r3.log').read_text()
assert json.loads((HERE/'preflight.json').read_text())['complete']
final=json.loads((HERE/'final-preflight.json').read_text());assert final['terminal']
for name,want in final['sources'].items():assert sha(HERE/name)==want,name
for v in ['A','B','C','D','board_clean','hp_clean','hud_clean','events_clean','latency_clean']:
    assert json.loads((HERE/f'development-6100-{v}.json').read_text())['terminal'],v
assert json.loads((HERE/'seed-audit.json').read_text())['passed']
assert not list((HERE/'confirmation').glob('*.json'))
assert not (HERE/'evaluation-manifest.json').exists()
# Corrected a missing-placement category discovered by the pre-outcome rate test.
# Preserve the initial registration and bind the unchanged schedule to the correction.
schedule_path=HERE/'schedule.json';schedule=json.loads(schedule_path.read_text())
(HERE/'schedule.initial.json').write_bytes(schedule_path.read_bytes())
changes=[]
for p,old in schedule['sources'].items():
    current=sha(Path(p))
    if current!=old:
        assert Path(p) in (HERE/'noise-model.json',HERE/'PREREG.md'),p
        changes.append(dict(path=p,before=old,after=current));schedule['sources'][p]=current
schedule_path.write_text(json.dumps(schedule,indent=2)+'\n')
(HERE/'preconfirmation-amendment.json').write_text(json.dumps(dict(unix=time.time(),changes=changes,reason='Rate test found absent-coordinate events were omitted from the residual resampler. Restored null placement samples. Also calibrated HP coverage over all truth rather than only surviving detections. No confirmation games existed; seeds, decks, sample size, hypotheses and gates unchanged.'),indent=2)+'\n')
# Every source snapshot still equals its recorded origin bytes at copy time.
for source,row in json.loads((HERE/'source-copies.json').read_text()).items():assert sha(HERE/row['copy'])==row['sha256'],source
old=json.loads((ROOT/'reports/strategy_council_20260928/engine-speed/stage5b-r3/evaluation-manifest.json').read_text())
drift=[]
for source,want in old['files'].items():
    p=Path(source)
    if source.startswith('src/clasher/') and 'vision' not in p.parts and p.exists() and sha(p)!=want:drift.append(source)
assert not drift,drift
paths=[p for p in (HERE/'runtime').rglob('*') if p.is_file()]
paths += list(HERE.glob('*.py'))+list(HERE.glob('*.sh'))
paths += [HERE/n for n in ('PREREG.md','noise-model.json','source-copies.json','seed-audit.json','schedule.json','preconfirmation-amendment.json','tests-r3.log','noise-rate-test.json','preflight.json','final-preflight.json')]
files={str(p.relative_to(HERE)):sha(p) for p in sorted(set(paths))}
manifest=dict(sealed_unix=time.time(),files=files,games=1664,processes=3,nice=10,deadline_seconds=.2,native_threads=2,stage5b_python_drift=drift)
(HERE/'evaluation-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('sealed',sha(HERE/'evaluation-manifest.json'),len(files),'files',flush=True)

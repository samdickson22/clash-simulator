"""Final read-back of frozen sources, complete pairs, scores and artifact limits."""
import hashlib
import json
from pathlib import Path
from qualify import write
from evaluate import verify_manifest

h=Path(__file__).resolve().parent
manifest=json.loads((h/'evaluation-manifest.json').read_text());verify_manifest(manifest)
result=json.loads((h/'result.json').read_text())
inputs=json.loads((h/'schedule.json').read_text())['sources']
for source,want in inputs.items():
    with Path(source).open('rb') as stream: got=hashlib.file_digest(stream,'sha256').hexdigest()
    assert got==want,('registered input changed',source)
rows=[json.loads(p.read_text()) for p in sorted((h/'confirmation').glob('pair*.json'))]
assert len(rows)==256 and len({(r['pair'],r['seat']) for r in rows})==256
assert {r['pair'] for r in rows}==set(range(128))
for r in rows:
    assert r['score']==(.5 if r['winner'] is None else float(r['winner']==r['seat']))
    assert 0<r['ticks']<=6001
    assert len(r['wall_cpu_search'])==len(range(90,r['ticks'],5))
    assert r['host']['nice']==10 and r['host']['torch_threads']==1
assert sum(r['score'] for r in rows)==224
assert sum(len(r['wall_cpu_search']) for r in rows)==result['timing']['decisions']==209575
assert sum(r['timing']['overruns'] for r in rows)==16
assert sum(v['accepted'] for r in rows for v in r['abilities'].values())==49
assert all((h/f'confirmation-worker{i}.exit').read_text().strip()=='0' for i in range(3))
entry=json.loads((h/'entry_sources.json').read_text())['files']
changed=[p for p,w in entry.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=w]
owned={'engine-rs/differential.py','engine-rs/src/lib.rs','engine-rs/src/scripts.rs','engine-rs/src/leaf.rs'}
assert set(changed)<=owned|{'src/clasher/vision/l1_training.py'},changed
assert hashlib.sha256(Path('gamedata.json').read_bytes()).hexdigest()==entry['gamedata.json']
assert hashlib.sha256(Path('engine-rs/clasher_core.abi3.so').read_bytes()).hexdigest()==entry['engine-rs/clasher_core.abi3.so']
size=sum(p.stat().st_size for p in h.rglob('*') if p.is_file());assert size<1024**3
completion=json.loads((h/'completion.json').read_text())
assert completion['report_sha256']==hashlib.sha256((h.parent/'STAGE5.md').read_bytes()).hexdigest()
write(h/'final-audit.json',dict(passed=True,games=256,pairs=128,decisions=209575,accepted_abilities=49,
    unchanged_sealed_files=len(manifest['files']),registered_input_pins=inputs,changed_entry_files=changed,stage5_bytes=size,
    report_sha256=completion['report_sha256'],statistical_pass=True,budget_pass=False))
print('Final audit PASS;',size,'bytes; statistical PASS, budget FAIL')

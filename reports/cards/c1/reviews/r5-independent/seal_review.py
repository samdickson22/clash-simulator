"""Hash/identity seal only. Never reruns old tests or mutates reviewed source."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((HERE/'receipt.json').read_text())
assert subprocess.check_output(['/usr/bin/git','rev-parse','HEAD'],cwd=ROOT).decode().strip()==r['candidate']
historical={}
for round_name in ('r3','r4'):
    directory=HERE.parent/(round_name+'-independent')
    old=json.loads((directory/'receipt.json').read_text())
    for name,expected in old['artifacts'].items():
        path=directory/name
        assert sha(path)==expected,str(path)
        historical[str(path.relative_to(ROOT))]=expected
for path,expected in r['preserved_before'].items():
    assert sha(ROOT/path)==expected,path
for path,expected in r['candidate_delta_file_sha256'].items():
    assert sha(ROOT/path)==expected,path
old=json.loads((HERE.parent/'r3-independent/receipt.json').read_text())
for name in ('peek.py','snapcmp_probe.py'):
    path=ROOT/'reports/cards/c1/tools'/name
    assert sha(path)==old['readpath_and_preserved_sha256'][str(path)]
    historical[str(path.relative_to(ROOT))]=sha(path)
report=HERE.parent/'FINAL-TOOLS-r5.md'
assert '**APPROVE**' in report.read_text() and r['candidate'] in report.read_text()
seal=dict(candidate=r['candidate'],tree=r['tree'],verdict='APPROVE',scope=r['scope'],
    command=['/mpac/sdicks02/repos/clasher-bot/.venv/bin/python','-I','-S','-B','reports/cards/c1/reviews/r5-independent/seal_review.py'],
    cwd=str(ROOT),exit_code=0,ended_utc=datetime.now(timezone.utc).isoformat(),
    all_61_prior_artifacts_unchanged=True,historical_receipt_indexed_artifacts=historical,
    candidate_62_worktree_files_unchanged=True,
    report_sha256=sha(report),receipt_sha256=sha(HERE/'receipt.json'),
    review_source_sha256={p.name:sha(p) for p in HERE.glob('*.py')},
    review_artifact_sha256={p.name:sha(p) for p in HERE.iterdir() if p.is_file() and p.name not in ('final-seal.json','seal-review.log')})
with (HERE/'final-seal.json').open('x') as f:json.dump(seal,f,sort_keys=True,indent=2)
print(json.dumps(dict(candidate=r['candidate'],verdict='APPROVE',preserved_historical_index_entries=len(historical),report_sha256=sha(report),receipt_sha256=sha(HERE/'receipt.json'),exit_code=0),indent=2))

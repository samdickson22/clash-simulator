"""Final read-only verification and scratch seal; no test/driver/process/signal execution."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[4]
REPORT=REPO/'reports/cards/c1/reviews/FINAL-TOOLS-r4.md'
r=json.loads((HERE/'receipt.json').read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
commands=[]
for argv in (['git','rev-parse','HEAD','HEAD^{tree}'],['git','diff','--exit-code'],['git','status','--short']):
    p=subprocess.run(argv,cwd=REPO,capture_output=True,text=True)
    commands.append(dict(argv=argv,cwd=str(REPO),exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr))
    assert p.returncode==0
assert commands[0]['stdout'].splitlines()==[r['candidate'],r['candidate_tree']]
for name,value in r['candidate_delta_file_sha256'].items(): assert sha(REPO/name)==value,name
for name,value in r['preserved_r3_and_untracked_sha256'].items(): assert sha(REPO/name)==value,name
old=json.loads((REPO/'reports/cards/c1/reviews/r3-independent/receipt.json').read_text())
for name in ('peek.py','snapcmp_probe.py'):
    p=REPO/'reports/cards/c1/tools'/name
    assert sha(p)==old['readpath_and_preserved_sha256'][str(p)]
for name,value in r['artifacts'].items(): assert sha(HERE/name)==value,name
seal=dict(candidate=r['candidate'],tree=r['candidate_tree'],verdict='REJECT',finding='R4-1',
    report_sha256=sha(REPORT),receipt_sha256=sha(HERE/'receipt.json'),commands=commands,
    all_candidate_and_original_preserved_hashes_still_match=True,
    artifact_sha256={p.name:sha(p) for p in HERE.iterdir() if p.is_file() and p.name!='seal-review.log'},
    scope='Only final read-only Git/hash comparisons and this scratch seal; all old evidence/source untouched.')
with (HERE/'final-seal.json').open('x') as f: json.dump(seal,f,indent=2,sort_keys=True)
print(json.dumps(dict(candidate=seal['candidate'],tree=seal['tree'],verdict=seal['verdict'],
    report_sha256=seal['report_sha256'],receipt_sha256=seal['receipt_sha256'],all_hashes_match=True),indent=2))

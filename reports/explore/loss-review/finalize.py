"""Reduce final diagnostics, recording inputs, code identity, and CPU receipts."""
import hashlib,json,subprocess,time,socket
from pathlib import Path
root=Path('/mpac/sdicks02/repos/clasher');base=root/'reports/explore/loss-review'
for _ in range(120):
    paths=[Path('/mpac/sdicks02/jobs/clasher')/f'loss-review-human-{role}-v4.exit' for role in ('train','dev')]
    if all(p.exists() for p in paths):
        if any(p.read_text().strip()!='0' for p in paths):raise RuntimeError('human job failed')
        break
    time.sleep(5)
else:raise RuntimeError('bounded human wait expired')
python=str(root/'.venv/bin/python')
subprocess.run([python,'-m','clasher.analysis.loss_review.reduce_traces','--source',str(base/'sim-production-v1'),
    '--out',str(base/'sim-reduced-v2/games'),'--workers','64'],check=True)
subprocess.run([python,'-m','clasher.analysis.loss_review.summarize','--inputs',str(base/'human-train-v4/games.jsonl'),
    str(base/'human-dev-v4/games.jsonl'),str(base/'sim-reduced-v2/games'),
    '--out',str(base/'results-v2.json'),'--workers','64','--bootstrap','1000'],check=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=list((root/'src/clasher/analysis/loss_review').glob('*.py'))
receipt=dict(host=socket.gethostname(),source_sha256={str(p.relative_to(root)):sha(p) for p in files},
    inputs={str(p.relative_to(root)):sha(p) for p in [base/'human-train-v4/games.jsonl',base/'human-dev-v4/games.jsonl',base/'sim-production-v1/schedule.json']},
    result_sha256=sha(base/'results-v2.json'),human_receipts=[json.loads((base/f'human-{role}-v4/receipt.json').read_text()) for role in ('train','dev')],
    simulation_receipt=json.loads((base/'sim-production-v1/receipt.json').read_text()))
(base/'run-receipt.json').write_text(json.dumps(receipt,separators=(',',':'))+'\n')

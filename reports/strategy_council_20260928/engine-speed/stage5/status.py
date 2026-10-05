"""Read-only run status without peeking at held-out strength outcomes."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
rows=[json.loads(p.read_text()) for p in (HERE/'confirmation').glob('pair*.json')]
print(json.dumps(dict(games=len(rows),decisions=sum(len(r['wall_cpu_search']) for r in rows),
    max_wall=max((r['timing']['max'] for r in rows),default=0),overruns=sum(r['timing']['overruns'] for r in rows),
    worker_exits={str(i):(HERE/f'confirmation-worker{i}.exit').read_text().strip() if (HERE/f'confirmation-worker{i}.exit').exists() else None for i in range(3)},
    completed_pairs=sum(sum(r['pair']==pair for r in rows)==2 for pair in {r['pair'] for r in rows})),indent=2))

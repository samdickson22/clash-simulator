from pathlib import Path
from datetime import datetime,timezone
import json,os
HERE=Path(__file__).resolve().parent
files=list((HERE/'confirmation').glob('*.json'));statuses=[]
for worker in range(3):
    exitfile=HERE/f'worker{worker}.exit';current=HERE/f'worker{worker}-current.json'
    if exitfile.exists():statuses.append(f'Worker {worker}: exited {exitfile.read_text().strip()}.')
    elif current.exists():
        c=json.loads(current.read_text());statuses.append(f"Worker {worker}: PID {c['pid']}, {c['mode']} pair {c['pair']}, {c['variant']} seat {c['seat']}.")
    else:statuses.append(f'Worker {worker}: not started.')
size=sum(p.stat().st_size for p in HERE.rglob('*') if p.is_file())
text=f"# Search noise progress\n\nUpdated {datetime.now(timezone.utc).isoformat()}.\n\nTerminal receipts: {len(files)}/1664. Outcomes remain sealed until all games finish. Storage: {size/1e6:.2f} MB / 300 MB.\n\n"+'\n'.join(statuses)+'\n\n'
text+='Resume with ../pilot/detach.sh launcher.log bash launch.sh from this directory, or use its absolute paths from the repository root. Workers hold exclusive advisory locks and skip only terminal receipts with the current manifest. Never delete existing receipts or change sealed code. Source changes require a documented new registration.\n\nNo unrelated process was signalled. Runtime and evidence are private to search-noise/. The full analysis writes RESULTS.md, result.json and FINAL.txt only after all 1664 games and source checks pass.\n'
if not (HERE/'completion.json').exists():(HERE/'PROGRESS.md').write_text(text)
print(len(files),'/1664',f'{size/1e6:.2f} MB',*statuses,sep='\n')

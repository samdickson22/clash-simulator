"""Read-only resumable Stage 6 status. Never starts or stops workers."""
import json
from pathlib import Path
import subprocess

folder=Path(__file__).resolve().parent
for label,filename in (
    ('early-r4','early-r4-focused.json'),
    ('early2-r6','early2-r6-focused.json'),
    ('arena8-r9','arena8-r9-focused.json'),
    ('requested-r10','requested-r10.json'),
    ('requested-r11b','requested-r11b-focused.json'),
    ('requested-r12','requested-r12-focused.json'),
    ('payload-r21','payload-r21-focused.json'),
    ('graveyard-r23','graveyard-r23-focused.json'),
    ('haste-dragon-r27','haste-dragon-r27-focused.json'),
    ('dash-r30','dash-r30-focused.json'),
    ('leap-r32','leap-r32-focused.json'),
    ('hook-r34','hook-r34-focused.json'),
    ('reuse-r12','reuse-r12-focused.json'),
    ('remaining-probe-r11b','remaining-probe-r11b.json'),
    ('planner-early100-r12','planner-early100-r12.json'),
    ('planner100-r4','planner100-r4.json'),
    ('planner-search100-r4','planner-search100-r4.json'),
):
    p=folder/filename;data=json.loads(p.read_text()) if p.exists() else {}
    rows=list(data.get('results',{}).values())
    exit_path=folder/f'{label}.exit'
    print(json.dumps(dict(label=label,results=len(rows),passed=sum(r.get('ok',False) for r in rows),
                          searchable=sum(len(r.get('candidates',[]))>1 for r in rows),
                          exit=exit_path.read_text().strip() if exit_path.exists() else None)))
for suite in ('recorded','random'):
    p=folder.parent/'logs'/f'{suite}_stage6-entry.json'
    if p.exists():
        data=json.loads(p.read_text());print(json.dumps(dict(identity=suite,results=len(data['results']),mismatches=data['mismatches'])))
p=folder/'entry-identity.exit'
print('entry-identity exit:',p.read_text().strip() if p.exists() else 'pending')
qualified=set()
for p in folder.glob('*-manifest.json'):
    data=json.loads(p.read_text())
    historical=p.name in ('early-manifest.json','early2-manifest.json','arena8-r9-manifest.json')
    if historical or (data.get('reference_preserved') and data.get('mismatches')==0):
        qualified.update(data['cards'])
print('incrementally qualified cards:',len(qualified),sorted(qualified))
processes=subprocess.check_output(['ps','-axo','pid,ppid,ni,etime,command'],text=True)
for line in processes.splitlines():
    if ('stage6/' in line or 'stage6-entry.json' in line) and 'ps -axo' not in line and 'status.py' not in line:
        print(line)

"""Read-only progress check. Never prints interim strength outcomes."""
import json,subprocess,time
from pathlib import Path
H=Path(__file__).resolve().parent
out=dict(time=time.time(),native_completed=len(list((H/'native').glob('pair-*.json'))),simulator_completed=len(list((H/'simulator').glob('pair-*.json'))),
 bytes=sum(p.stat().st_size for p in H.rglob('*') if p.is_file()),workers=[],error=None)
for p in sorted(H.glob('eval-*.launch.json')):
 r=json.loads(p.read_text());label=p.name.removesuffix('.launch.json');exitfile=H/(label+'.exit')
 state=subprocess.run(['ps','-p',str(r['pid']),'-o','command='],capture_output=True,text=True)
 out['workers'].append(dict(label=label,pid=r['pid'],alive=state.returncode==0 and str(H/'run.sh') in state.stdout,
 exit=exitfile.read_text().strip() if exitfile.exists() else None))
decision_files=list((H/'native').glob('pair-*/decisions.jsonl'))
if decision_files:
 latest=max(decision_files,key=lambda p:p.stat().st_mtime)
 out['latest_decisions']=str(latest.relative_to(H))
 out['latest_write_age_seconds']=round(time.time()-latest.stat().st_mtime,2)
if (H/'pipeline-error.json').exists():out['error']=json.loads((H/'pipeline-error.json').read_text())
print(json.dumps(out,indent=2))

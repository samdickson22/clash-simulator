"""Read only durable progress/receipt identities; never inspect game outcomes."""
import argparse,json,os,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);a=p.parse_args()
r=dict(utc=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip())
if (a.job/'progress.json').exists():r['progress']=json.loads((a.job/'progress.json').read_text())
for phase in ('smoke','reporting','smoke-r2','smoke-r3','reporting-r2'):
 d=a.job/phase
 if not d.exists():continue
 entry={'terminal_files':len(list((d/'games').glob('*.json')))}
 for name in ('launch','receipt','supervisor-exit'):
  if (d/(name+'.json')).exists():entry[name]=json.loads((d/(name+'.json')).read_text())
 if 'launch' in entry:
  for key in ('supervisor_pid','child_pid'):
   pid=entry['launch'][key];proc=Path(f'/proc/{pid}')
   entry[key+'_live']=proc.exists()
   if proc.exists():entry[key+'_cmdline']=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
 r[phase]=entry
print(json.dumps(r,indent=2))

"""Stop only verified S4 dev-v1 children; parent reaps CPU and records failure."""
import json,os,signal,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;J=Path('/mpac/sdicks02/jobs/clasher')
# fleet PID is shell; locate the Python supervisor by exact command and child lineage.
found=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  args=(p/'cmdline').read_bytes().split(b'\0')
  if b'reports/strategy_council_20260928/search-noise-s4/dev_launch.py' in args and b'v1' in args and args[0].endswith(b'python'):
   stat=(p/'stat').read_text();fields=stat[stat.rfind(')')+2:].split();found.append((int(p.name),int(fields[1]),int(fields[11])+int(fields[12])))
 except (FileNotFoundError,PermissionError,IndexError):pass
ids={pid for pid,_,_ in found};parents=[r for r in found if r[1] not in ids];assert len(parents)==1,parents
parent=parents[0][0];children=[r for r in found if r[1]==parent];assert children and len(children)<=12
os.kill(parent,signal.SIGSTOP)
receipt=dict(utc=time.time(),reason='Development performance: repeated enumeration of ambiguous queue hands; no confirmation process is targeted.',supervisor=parent,children=[dict(pid=p,ppid=pp,cpu_seconds=cpu/os.sysconf('SC_CLK_TCK')) for p,pp,cpu in children])
(HERE/'dev-v1-interrupted.json').write_text(json.dumps(receipt,indent=2)+'\n')
try:
 for pid,ppid,cpu in children:
  args=(Path('/proc')/str(pid)/'cmdline').read_bytes().split(b'\0');assert b'reports/strategy_council_20260928/search-noise-s4/dev_launch.py' in args and b'v1' in args
  os.kill(pid,signal.SIGTERM)
finally:os.kill(parent,signal.SIGCONT)
print(json.dumps(receipt))

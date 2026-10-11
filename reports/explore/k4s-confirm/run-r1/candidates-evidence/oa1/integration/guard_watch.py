"""Run the FROZEN host_audit.census on the source host while the OA-1 copier runs; record how every copier-related
process is classified (allowlist kind) and whether anything is foreign/active. Usage: guard_watch.py TJ SECONDS OUT"""
import json,sys,time
from pathlib import Path
from host_audit import census
TJ=Path(sys.argv[1]);end=time.monotonic()+float(sys.argv[2]);out=Path(sys.argv[3])
before=None;seen={};foreign_hits=[];active_hits=[];samples=0
KEYS=('rsync','find','sshd: sdicks02@notty','env T1_COPIER')
while time.monotonic()<end:
 after,forbidden,active,_=census(TJ,before);before=after;samples+=1
 for r in after:
  if any(k in r['cmd'] for k in KEYS):seen.setdefault(r['cmd'][:160],set()).add(r.get('allowlist_kind'))
 foreign_hits+=[r['cmd'][:160] for r in forbidden];active_hits+=[r['cmd'][:160] for r in active]
 time.sleep(0.05)
out.write_text(json.dumps(dict(samples=samples,copier_related={k:sorted(map(str,v)) for k,v in seen.items()},foreign=sorted(set(foreign_hits)),active=sorted(set(active_hits))),indent=1))
print(out.read_text())

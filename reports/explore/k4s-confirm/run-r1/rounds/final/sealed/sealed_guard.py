"""Sealed-mode guard (K4S run r1). Runs a frozen tool unchanged via runpy with a Python audit hook that (1) logs every
open / listdir / scandir path to a log file and (2) RAISES before any access under the counted-block view, the hub
copies or a games directory, so no outcome-bearing byte can be read even if a barrier unexpectedly passed.
Usage: sealed_guard.py LOG SCRIPT [ARGS...]"""
import os,runpy,sys
log=open(sys.argv[1],'w',buffering=1);script=sys.argv[2]
BLOCK=('/final-view','/hub-blocks/','/games')
def hook(event,args):
 if event in ('open','os.listdir','os.scandir'):
  p=args[0] if args else None
  if isinstance(p,(str,bytes,os.PathLike)):
   s=os.fsdecode(p)
   log.write(f'{event}\t{s}\n')
   if any(b in s for b in BLOCK):
    log.write(f'BLOCKED\t{s}\n');raise PermissionError(f'sealed guard: refused access to {s}')
sys.addaudithook(hook)
sys.argv=[script]+sys.argv[3:]
sys.path.insert(0,os.path.dirname(os.path.abspath(script)))
runpy.run_path(script,run_name='__main__')

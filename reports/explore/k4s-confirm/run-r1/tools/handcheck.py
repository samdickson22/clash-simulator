"""K4S runner r1: recorded hand check after a health read (coordinator ruling on round r3 audit F1), used until the F1
checkpoint fix is approved. Local only: never contacts a host. Reads the health receipt just written (via
health/last-check.json), rounds/history.json and the sha256-verified phase dispatch; writes one JSON next to the receipt.
Per host: expected (dispatch rows) vs complete, supervisor-exit reason, supervisor process. Flags a running host with
complete > expected, or an exited host unless reason=null and complete == expected. Any missing or malformed input is
recorded as UNKNOWN and flagged. Exit 2 on any flag. Records its own sha256. Explicit checks only (no assert).
Usage: handcheck.py PHASE"""
import collections,hashlib,json,re,sys
from pathlib import Path

L=Path('/mpac/sdicks02/k4s-runner/run-r1')
SELF=Path(__file__).resolve()

def need(cond,msg):
 if not cond:raise ValueError(msg)

def main(argv,root=L):
 phase=argv[1] if len(argv)>1 else ''
 out=dict(schema='clasher.k4s.health-handcheck.v2',script=str(SELF.name),script_sha256=hashlib.sha256(SELF.read_bytes()).hexdigest(),
          phase=phase,status='UNKNOWN',hosts={},flags=[],
          note='recorded hand check (coordinator ruling on round r3 audit F1): completed vs dispatch per host + supervisor exit reason')
 dest=None
 try:
  need(re.fullmatch(r'(reporting|replacement-r[0-9]+)',phase) is not None,f'phase {phase!r}')
  last=json.loads((root/'health'/'last-check.json').read_text())
  need(isinstance(last,dict) and isinstance(last.get('out'),str),'last-check.json has no receipt path')
  rp=Path(last['out']);need(rp.parent==root/'health' and rp.name.endswith('.json'),f'receipt path {rp}')
  dest=rp.with_name(rp.name[:-5]+'-handcheck.json')
  raw_rec=rp.read_bytes();rec=json.loads(raw_rec)
  out.update(health_receipt=rp.name,health_sha256=hashlib.sha256(raw_rec).hexdigest())
  need(isinstance(rec,dict) and rec.get('phase')==phase,f'receipt phase {rec.get("phase") if isinstance(rec,dict) else None!r} != {phase}')
  need(isinstance(rec.get('hosts'),dict) and set(rec['hosts'])=={'127x03','127x04'},'receipt hosts')
  out['health_utc']=rec.get('utc')
  hist=json.loads((root/'rounds'/'history.json').read_text());need(isinstance(hist,list),'history is not a list')
  ent=[e for e in hist if isinstance(e,dict) and e.get('phase')==phase];need(len(ent)==1,f'history has {len(ent)} entries for {phase}')
  name,want=ent[0].get('dispatch_file'),ent[0].get('dispatch_sha256')
  need(isinstance(name,str) and re.fullmatch(r'[A-Za-z0-9_.-]+[.]json',name) is not None,f'dispatch_file {name!r}')
  need(isinstance(want,str) and re.fullmatch(r'[0-9a-f]{64}',want) is not None,f'dispatch_sha256 {want!r}')
  raw=(root/'dispatch'/name).read_bytes();need(hashlib.sha256(raw).hexdigest()==want,'dispatch sha256 != history')
  doc=json.loads(raw);need(isinstance(doc,dict) and isinstance(doc.get('blocks'),list),'dispatch blocks')
  need(all(isinstance(b,dict) and isinstance(b.get('host'),str) for b in doc['blocks']),'dispatch row without host')
  exp=collections.Counter(b['host'] for b in doc['blocks']);out['dispatch_sha256']=want
 except Exception as e:
  out['flags'].append(f'UNKNOWN: {type(e).__name__}: {e}')
  return finish(out,dest,root)
 for h in ('127x03','127x04'):
  try:
   y=rec['hosts'][h].get('remote') if isinstance(rec['hosts'][h],dict) else None
   need(isinstance(y,dict),'no remote data')
   c=y.get('COMPLETE');need(isinstance(c,str) and re.fullmatch(r'[0-9]+',c) is not None,f'COMPLETE {c!r}')
   comp=int(c);need(exp[h]>0,'no dispatch rows for host')
   sx=y.get('SUPEXIT');sp=y.get('SUPPROC')
   if sx is None:
    need(isinstance(sp,str) and len(sp.split())==2,f'running but SUPPROC {sp!r}')
    state='running';ok=comp<=exp[h] and not sp.split()[1].startswith(('Z','T'))
   else:
    reason=sx.split(':',1)[-1].strip();state='exited reason '+reason
    ok=reason=='null' and comp==exp[h]
   out['hosts'][h]=dict(expected=exp[h],complete=comp,supervisor_exit=sx,supervisor_proc=sp,state=state,ok=ok)
   if not ok:out['flags'].append(f'{h}: {state} complete {comp}/{exp[h]}')
  except Exception as e:
   out['hosts'][h]=dict(status='UNKNOWN',error=f'{type(e).__name__}: {e}',ok=False)
   out['flags'].append(f'{h}: UNKNOWN: {type(e).__name__}: {e}')
 out['status']='OK' if not out['flags'] else 'FLAGGED'
 return finish(out,dest,root)

def finish(out,dest,root):
 if dest is None:dest=root/'health'/'handcheck-UNKNOWN.json'
 dest.write_text(json.dumps(out,indent=1)+'\n')
 print(dest.name,out['status'],{h:(f"{v['complete']}/{v['expected']} {v['state']}" if 'state' in v else v.get('error')) for h,v in out['hosts'].items()},'FLAGS',out['flags'])
 return 2 if out['flags'] else 0

if __name__=='__main__':
 sys.exit(main(sys.argv))

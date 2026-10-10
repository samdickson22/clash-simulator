"""Bind fresh inventory and future reserved formulas. Exploration; NEVER ADOPTABLE."""
import argparse,hashlib,json,resource,socket,subprocess,time
from pathlib import Path
OFFSETS=[0,13,100000,100001,100002,100003,271828,271829]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--job',required=True);j=Path(p.parse_args().job);start=time.monotonic()
 inventory=j/'postkill-seed-inventory03.json';r=json.loads(inventory.read_text());reserved=json.loads((j/'postkill-reserved-ranges.json').read_text())
 assert r['exact_scan_passed'] and not r['errors'] and not r['overlap']
 assert not any('roader' in path.lower() for path in r['files'])
 ours=[dict(name='descriptive',base=4503602007370496,count=600),dict(name='qualification',base=4503602017370496,count=32)]
 checks=0
 for a in ours:
  for b in reserved['reserved']:
   for x in OFFSETS:
    for y in OFFSETS:
     assert a['base']+x+a['count']<=b['base']+y or b['base']+y+b['count']<=a['base']+x,(a,b,x,y)
     checks+=1
 u=resource.getrusage(resource.RUSAGE_SELF)
 result=dict(passed=True,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),lane='exploration; never adoptable',never_adoptable=True,adoption_eligible=False,ranges=ours,offsets=OFFSETS,reserved=reserved['reserved'],reserved_sources=reserved['sources'],expanded_interval_pairs_checked=checks,inventory=dict(host=r['host'],path=str(inventory),sha256=sha(inventory),files=len(r['files']),declarations=len(r['declarations']),formula_contexts=len(r['formula_contexts']),roots=r['roots'],excluded=r['excluded'],errors=0,overlaps=0,scan_cpu_seconds=r['cpu_seconds'],scan_wall_seconds=r['wall_seconds'],scanner_sha256=sha(j/'ops/seed_audit_postkill.py')),audit_cpu_seconds=u.ru_utime+u.ru_stime,audit_wall_seconds=time.monotonic()-start,scope='Fresh literal/formula provenance plus explicit future R3/K2/G/R2 and original ranges; own new declarations excluded, pinned original freezes reserved explicitly.',withdrawn_provisional=dict(base=4503601807370496,count=600,used=False,reason='K-v2 collision; no audit/staging/game on provisional bank'))
 (j/'postkill-seed-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['passed','utc','lane','expanded_interval_pairs_checked','audit_cpu_seconds']}))
if __name__=='__main__':main()

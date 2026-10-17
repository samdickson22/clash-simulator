"""Atomic whole-case claims, fresh empirical prior first when registered."""
import argparse,json,os,re
from sam_common import ROOT,utc
def claim(worker):
 assert re.fullmatch(r'127x0[134]-[a-zA-Z0-9_-]+',worker)
 if (ROOT/'STOP').exists() or not (ROOT/'preflight/receipt.json').exists():return None
 for stage in ('battlelog1850','shifted'):
  path=ROOT/stage/'validation/bank.json'
  if not path.exists():continue
  bank=json.loads(path.read_text());claims=ROOT/stage/'claims';claims.mkdir(exist_ok=True)
  for index in bank['dispatch_order']:
   dest=claims/f'{index:04d}.json'
   try:fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
   except FileExistsError:continue
   with os.fdopen(fd,'w') as stream:json.dump(dict(utc=utc(),worker=worker,index=index,stage=stage,case_id=bank['cases'][index]['id']),stream)
   return dict(stage=stage,index=index)
 return None
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--worker',required=True);a=p.parse_args();print(json.dumps(claim(a.worker)))

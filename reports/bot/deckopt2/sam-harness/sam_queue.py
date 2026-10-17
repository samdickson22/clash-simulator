"""Atomic whole-case claims on light05; no retry or game construction."""
import argparse,json,os,re
from sam_common import ROOT,utc
def claim(worker):
 assert re.fullmatch(r'127x0[134]-[a-zA-Z0-9_-]+',worker)
 if (ROOT/'STOP').exists():return None
 assert json.loads((ROOT/'preflight/receipt.json').read_text())['passed']
 for stage in ('upgrades','max','current'):
  if stage=='max' and not (ROOT/'preflight/replay.json').exists():continue
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
 p=argparse.ArgumentParser();p.add_argument('--worker',required=True);args=p.parse_args();print(json.dumps(claim(args.worker)))

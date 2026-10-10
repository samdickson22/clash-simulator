"""Produce smoke admission from hashes, timing and metadata; outcomes remain sealed."""
import argparse
from pathlib import Path
from common import read,write,sha,utc,plan
from health import health

def main():
 p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--root',type=Path,required=True);a=p.parse_args()
 descriptors=[read(p)['descriptor'] for p in a.root.glob('*/complete.json')]
 assert len(descriptors)==8 and {d['population'] for d in descriptors}=={'smoke'}
 assert {d['index'] for d in descriptors}==set(range(8))
 assert all(d['seed']==plan()['seed_ranges']['smoke']['base']+d['index'] for d in descriptors)
 result=health(a.root,validate=True);assert result['passed'] and result['counts']['smoke_hub_complete']==8 and result['counts']['games']==64
 receipt=a.job/'smoke-admission.json';write(receipt,dict(**result,source_hashes={str(p):sha(p) for p in sorted(a.root.glob('*/complete.json'))},outcomes_read=False))
 write(a.job/'SMOKE-PASS',dict(utc=utc(),receipt_sha256=sha(receipt),health_only=True))
if __name__=='__main__':main()

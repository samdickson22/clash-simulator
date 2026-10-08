"""Tiny synthetic backup transfer under the lease wrapper; no real model."""
import argparse
import json
from pathlib import Path
import socket
from lease_lifecycle_v4 import offload


def main(output):
    if socket.gethostname().split('.')[0]!='127x15':raise ValueError('Designated transfer test host only')
    output.mkdir(exist_ok=False);run=output/'synthetic-run';(run/'model').mkdir(parents=True)
    (run/'model/last.pt').write_bytes(b'synthetic-checkpoint-transfer-only\n')
    (run/'model/manifest.json').write_text(json.dumps(dict(synthetic_only=True,heldout_opened=False)))
    journal=output/'journal';journal.mkdir()
    result=offload(run,journal,'127x01')
    assert result['status']=='verified' and result['verification']['verified']
    assert result['checkpoint_count']==1 and result['verification']['files']==2
    result.update(synthetic_only=True,checks=2)
    (output/'complete.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    main(p.parse_args().output)

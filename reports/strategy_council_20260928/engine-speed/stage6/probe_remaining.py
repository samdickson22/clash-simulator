"""Read-only first-case inventory for unqualified cards on one pinned build.

Each failure is retained. This probe cannot qualify a group or admission.
"""
import argparse
import hashlib
import json
from pathlib import Path
import traceback

import clasher_core
from differential import CARDS, config
from stage2 import fingerprint, focused_case


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();folder=Path(__file__).resolve().parent
    qualified=set()
    for name in ('early-manifest.json','early2-manifest.json','arena8-r9-manifest.json'):
        qualified.update(json.loads((folder/name).read_text())['cards'])
    cards=[row['canonical'] for row in json.loads((folder/'scope.json').read_text())['remaining']
           if row['canonical'] not in qualified|{'Hunter','ElectroWizard','IceWizard','AxeMan'}]
    native=Path(clasher_core.__file__).resolve();assert native.parent==folder/'native'
    pins=dict(source=fingerprint(),native=hashlib.sha256(native.read_bytes()).hexdigest(),
              driver=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    declaration=dict(pins=pins,cards=cards,ticks=2200,cases=1)
    out=dict(**declaration,results={})
    if args.output.exists():
        old=json.loads(args.output.read_text());assert all(old[k]==v for k,v in declaration.items());out=old
    for card in cards:
        if card in out['results']:continue
        try:
            cfg=config(tuple(dict.fromkeys((*CARDS,card))))
            result=focused_case(card,0,cfg,ticks=2200)
        except (KeyboardInterrupt,SystemExit):raise
        except BaseException:
            result=dict(ok=False,kind='exception',traceback=traceback.format_exc())
        assert fingerprint()==pins['source']
        assert hashlib.sha256(native.read_bytes()).hexdigest()==pins['native']
        out['results'][card]=result
        tmp=args.output.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2)+'\n');tmp.replace(args.output)
        print(card,{k:v for k,v in result.items() if k not in ('python','rust','field_diff','actions','traceback')},flush=True)
    print('probe complete',len(out['results']),'cards; not a qualification',flush=True)


if __name__=='__main__':main()

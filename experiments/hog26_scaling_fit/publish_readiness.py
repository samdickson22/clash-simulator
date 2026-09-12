"""Publish fitting readiness only from matching completed memory evidence."""
import argparse
import json
from pathlib import Path

import torch
from readiness import sha, validate_memory_reports


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('neural','tree','plan','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise ValueError('refusing existing readiness file')
    implementation={p.name:sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}
    reports={phase:{'path':str(getattr(args,phase).resolve()),'sha256':sha(getattr(args,phase))}
             for phase in ('neural','tree')}
    audit=validate_memory_reports(reports,implementation=implementation,
        plan_sha256=sha(args.plan),runtime={'torch':torch.__version__,'threads':1,'device':'cpu'})
    result={'status':'passed','implementation':implementation,'collection_plan_sha256':sha(args.plan),
            'combined_games':1536,'data_audit':audit,'memory_verified':True,'memory_reports':reports,
            'scope':'Readiness for fixed diagnostic scaling comparison only; no acceptance or policy updates.',
            'memory_scope':'Neural maximal step plus largest tree preprocessing/one-iteration probe; supervised fitting retains RSS guard.'}
    with args.output.open('x') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')


if __name__=='__main__':
    main()

"""Recompute all authenticated validation cells before accepting an event proposal.

This verifies epoch/global/per-card event selection only. Body threshold fitting,
the final combined replay, calibration and the final seal remain separate.
No heldout input or opening authority. Recomputed evidence survives failures.
"""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from validation_admission_v4 import read,sha,validate_run
from validation_select_v4 import select_run


def verify_run(args):
    readiness=validate_run(args.run,args.source,args.split,args.phase_state,args.phase_exit)
    selection=args.selection
    proposal=read(selection/'event-selection-proposal.json')
    manifest=read(selection/'manifest.json');complete=read(selection/'complete.json')
    if (proposal.get('schema')!='clasher.v4.event-selection-proposal.v1'
            or manifest.get('schema')!='clasher.v4.validation-selection-input.v1'
            or manifest.get('readiness')!=readiness or manifest.get('grid_sha256')!=sha(args.grid)
            or proposal.get('manifest_sha256')!=sha(selection/'manifest.json')
            or complete.get('proposal_sha256')!=sha(selection/'event-selection-proposal.json')
            or complete.get('cells')!=216):raise ValueError('Selection proposal provenance differs')
    for record in (proposal,manifest,complete):
        if record.get('heldout_payloads_opened') is not False or record.get('selection_seal') is not False:
            raise ValueError('Unsealed validation-only selection required')
    if any(r.get('heldout_opening_authorized') is not False for r in (proposal,complete)):
        raise ValueError('Event proposal cannot grant heldout authority')
    names={f'epoch-{e:02d}-threshold-{t}.json' for e in range(1,25) for t in range(1,10)}
    if set(proposal.get('scores_sha256',{}))!=names:raise ValueError('Complete score evidence required')
    pins={n:sha(selection/n) for n in names|{'manifest.json','complete.json','event-selection-proposal.json'}}
    if any(pins[n]!=d for n,d in proposal['scores_sha256'].items()):raise ValueError('Stored scores changed')
    if 'body_selections' in proposal:
        bodies=proposal['body_selections']
        if set(bodies)!={str(i) for i in range(1,25)}:raise ValueError('Complete body evidence required')
        for e,proof in bodies.items():
            prefix=f'body-epoch-{int(e):02d}'
            root=selection/prefix
            bp=read(root/'body-selection-proposal.json');bc=read(root/'complete.json')
            body_names={f'body-threshold-{i}.json' for i in range(1,10)}
            if (proof['proposal_sha256']!=sha(root/'body-selection-proposal.json')
                    or proof['completion_sha256']!=sha(root/'complete.json')
                    or proof['ranking']!=bp.get('ranking')
                    or bc.get('proposal_sha256')!=proof['proposal_sha256']
                    or bp.get('manifest_sha256')!=sha(root/'manifest.json')
                    or set(bp.get('scores_sha256',{}))!=body_names
                    or any(sha(root/n)!=v for n,v in bp['scores_sha256'].items())):
                raise ValueError('Stored body evidence changed')
            for n in body_names|{'manifest.json','complete.json','body-selection-proposal.json'}:
                pins[f'{prefix}/{n}']=sha(root/n)
    if args.output.exists():raise ValueError('Fresh verification output required')
    args.output.mkdir()
    recomputed=select_run(SimpleNamespace(run=args.run,source=args.source,split=args.split,
        phase_state=args.phase_state,phase_exit=args.phase_exit,grid=args.grid,
        output=args.output/'recomputed-selection'))
    # Equality includes all 216 recomputed score hashes, ranking, threshold support,
    # full fit/population/source provenance and the exact selected checkpoint.
    if recomputed!=proposal:raise ValueError('Event proposal differs from authenticated recomputation')
    if any(sha(selection/n)!=digest for n,digest in pins.items()):raise ValueError('Original selection changed during verification')
    chosen=recomputed['ranking']['candidate']
    result=dict(schema='clasher.v4.event-selection-verification.v1',readiness=readiness,
        epoch=chosen['epoch'],global_threshold=chosen['threshold'],
        event_thresholds=recomputed['card_thresholds']['thresholds'],
        grid_body_threshold=recomputed['body_threshold'],checkpoint_sha256=recomputed['checkpoint_sha256'],
        input_sha256=pins,grid_sha256=sha(args.grid),verifier_sha256=sha(Path(__file__)),
        recomputed_proposal_sha256=sha(args.output/'recomputed-selection/event-selection-proposal.json'),
        event_selection_verified=True,body_selection_verified='body_selections' in recomputed,selection_seal=False,
        heldout_payloads_opened=False,heldout_opening_authorized=False,
        pending=['body threshold fitting','combined validation replay','calibration','final selection seal'])
    if result['body_selection_verified']:
        result['body_selections'] = recomputed['body_selections']
        result['pending'].remove('body threshold fitting')
    with (args.output/'event-selection-verified.json').open('x') as f:
        json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    with (args.output/'complete.json').open('x') as f:
        json.dump(dict(verification_sha256=sha(args.output/'event-selection-verified.json'),
            selection_seal=False,heldout_opening_authorized=False,heldout_payloads_opened=False),f,indent=2)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('run','source','split','phase-state','phase-exit','grid','selection','output'):
        p.add_argument('--'+name,type=Path,required=True)
    verify_run(p.parse_args())

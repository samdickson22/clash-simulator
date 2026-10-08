"""Seal v2 selections and calibrated release; no model inference or heldout IO."""
import argparse
import json
from pathlib import Path
from imitation.t5.guards import sha,write_once,canonical_hash

RUNS={'main-2026100821':2026100821,'main-2026100822':2026100822}


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('run','combine','release'))
    p.add_argument('--input',nargs='+',required=True);p.add_argument('--output',required=True)
    p.add_argument('--run');p.add_argument('--manifest',required=True);p.add_argument('--selection');p.add_argument('--v1-report')
    a=p.parse_args();manifest_hash=sha(a.manifest)
    if a.mode=='run':
        import torch
        root=Path(a.input[0]);complete=json.loads((root/'complete.json').read_text())
        segments=[json.loads(l) for l in (root/'segments.jsonl').read_text().splitlines()]
        assert not complete['stopped_by_signal'] and segments[-1]['status']=='complete','paused/failed run is not complete'
        assert complete['epoch']>=6 or complete['bad_epochs']>=3,'training has not met a stopping rule'
        choices=[json.loads(l) for l in (root/'train.jsonl').read_text().splitlines() if json.loads(l)['event']=='dev']
        best=min(choices,key=lambda r:(r['ema_joint_nll'],r['step']))
        checkpoint=root/f"best-dev-step-{best['step']:08d}.pt";ckpt=torch.load(checkpoint,map_location='cpu',weights_only=True)
        assert ckpt['args']['seed']==RUNS[a.run] and ckpt['hashes']['T11_manifest']==manifest_hash
        assert ckpt['state']['best_dev']==best['ema_joint_nll']
        result=dict(run=a.run,seed=RUNS[a.run],variant='main',step=best['step'],dev_joint_nll=best['ema_joint_nll'],
                    checkpoint=str(checkpoint),checkpoint_sha256=sha(checkpoint),manifest_sha256=manifest_hash,
                    complete_sha256=sha(root/'complete.json'),train_log_sha256=sha(root/'train.jsonl'),
                    segments_sha256=sha(root/'segments.jsonl'),stopping_state=complete)
    elif a.mode=='combine':
        items=[json.loads(Path(n).read_text()) for n in a.input];runs={r['run']:r for r in items}
        assert len(items)==2 and set(runs)==set(RUNS) and all(r['manifest_sha256']==manifest_hash for r in items)
        primary=min(items,key=lambda r:(r['dev_joint_nll'],r['seed']))['run']
        result=dict(manifest_sha256=manifest_hash,primary=primary,runs=runs,selection='pooled natural EMA dev joint NLL only')
    else:
        assert a.v1_report and a.selection,'published v1 result is required before heldout release'
        report=Path(a.v1_report);assert report.is_file() and report.stat().st_size>0
        selection=json.loads(Path(a.selection).read_text());assert selection['manifest_sha256']==manifest_hash and set(selection['runs'])==set(RUNS)
        items=[json.loads(Path(n).read_text()) for n in a.input];assert len(items)==2 and {x['run'] for x in items}==set(RUNS)
        runs={}
        for name,item in zip(a.input,items):
            run=item['run'];assert item['role']=='dev' and item['selection_sha256']==sha(a.selection)
            assert item['checkpoint_sha256']==selection['runs'][run]['checkpoint_sha256']
            runs[run]=dict(checkpoint_sha256=item['checkpoint_sha256'],calibration=item,
                           temperature_file_sha256=sha(name),temperature_content_sha256=canonical_hash(item))
        result=dict(manifest_sha256=manifest_hash,selection_sha256=sha(a.selection),primary=selection['primary'],runs=runs,
                    v1_report=str(report.resolve()),v1_report_sha256=sha(report))
    write_once(a.output,result)


if __name__=='__main__':main()

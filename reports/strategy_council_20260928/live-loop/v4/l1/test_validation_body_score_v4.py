"""File-backed body-score guards; synthetic replay/cleaner after refusal test."""
import argparse
from copy import deepcopy
import gzip
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import validation_body_score_v4 as scoring
from test_body_scoring_v4 import obj, pred


def main(root):
    checks = 0
    def check(ok):
        nonlocal checks
        assert ok
        checks += 1
    def refuses(fn):
        nonlocal checks
        try: fn()
        except ValueError: checks += 1
        else: raise AssertionError('Expected refusal')
    def put(path, value):
        path.write_text(json.dumps(value))
    def putrows(path, values):
        path.write_text(''.join(json.dumps(v)+'\n' for v in values))
    with patch.object(scoring, 'load_replay', side_effect=ValueError('Producer incomplete')):
        refuses(lambda: scoring.score_run(SimpleNamespace()))
    root.mkdir()
    source, replay = root/'source', root/'replay'
    source.mkdir(); replay.mkdir(); (source/'ep').mkdir()
    folder = source/'ep'
    frames = [dict(seq=i, tick_lo=t, tick_hi=t) for i,t in enumerate((9,10,16))]
    putrows(folder/'frames.jsonl', frames)
    for filename in ('objects.jsonl.gz','rich-objects.jsonl.gz'):
        with gzip.open(folder/filename,'wt') as f:
            f.write(json.dumps(dict(tick=10,objects=[obj()]))+'\n')
    receipt = dict(episode='ep',split='validation',frames=3,
        files={p.name:scoring.sha(p) for p in folder.iterdir()})
    put(folder/'receipt.json', receipt)
    admission = dict(validation_receipt_sha256={'ep':scoring.sha(folder/'receipt.json')})
    outputs = [dict(source_seq=i,payload=dict(episode_id='ep',tracks=[pred(),pred(track_id=1)])) for i in range(3)]
    output_path = replay/'ep-outputs.jsonl'
    putrows(output_path,outputs)
    manifest = dict(epoch=7,body_threshold=.6)
    put(replay/'manifest.json',manifest)
    def loaded():
        put(replay/'complete.json',dict(files_sha256={output_path.name:scoring.sha(output_path)}))
        return dict(episodes=['ep'],admission=admission,manifest=manifest,thresholds={'default':.5},
            replay_manifest_sha256=scoring.sha(replay/'manifest.json'),
            replay_completion_sha256=scoring.sha(replay/'complete.json'))
    args = SimpleNamespace(source=source,replay=replay)
    class SyntheticCleaner:
        def __init__(self,*args):pass
        def clean(self,ordinary,rich):return ordinary
    with patch('labels_v4.BodyLabels',SyntheticCleaner), patch.object(scoring,'load_replay',return_value=loaded()) as gate:
        result = scoring.score_run(args)
        check(result['micro']['matched']==1 and result['micro']['false_positive']==1)
        check(result['micro']['unscorable_frames']==2 and result['micro']['ignored_predictions']==4)
        check(result['micro']['phantom_rate']==.5 and result['micro']['drop_rate']==0)
        check(result['epoch']==7 and result['body_threshold']==.6)
        check(result['selection_seal'] is False and result['heldout_opening_authorized'] is False)
        check(set(result['truth_payloads']['ep'])=={'frames.jsonl','objects.jsonl.gz','rich-objects.jsonl.gz'})
        for filename in ('objects.jsonl.gz','rich-objects.jsonl.gz','frames.jsonl'):
            file=folder/filename; original=file.read_bytes(); file.write_bytes(original+b'changed')
            refuses(lambda:scoring.score_run(args)); file.write_bytes(original)
        bad=deepcopy(outputs);bad[1]['source_seq']=0;putrows(output_path,bad)
        gate.return_value=loaded(); refuses(lambda:scoring.score_run(args))
        bad=deepcopy(outputs);bad[1]['payload']['tracks'][1]['track_id']=0;putrows(output_path,bad)
        gate.return_value=loaded(); refuses(lambda:scoring.score_run(args))
        putrows(output_path,outputs[:-1]);gate.return_value=loaded()
        refuses(lambda:scoring.score_run(args))
        putrows(output_path,outputs);gate.return_value=loaded()
        receipt['split']='heldout';put(folder/'receipt.json',receipt)
        admission['validation_receipt_sha256']['ep']=scoring.sha(folder/'receipt.json')
        refuses(lambda:scoring.score_run(args))
    print(json.dumps(dict(checks=checks,passed=True,scope='synthetic file guards; admission and cleaner mocked',
                          selection_seal=False,heldout_payloads_opened=False)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)

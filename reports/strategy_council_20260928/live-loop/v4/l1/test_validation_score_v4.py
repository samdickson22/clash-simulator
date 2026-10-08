"""Synthetic file-backed score test; formal admission mocked only after refusal."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import validation_score_v4 as scoring


def main(root):
    checks = 0
    def check(value):
        nonlocal checks
        assert value
        checks += 1
    def refuses(fn):
        nonlocal checks
        try:
            fn()
        except ValueError:
            checks += 1
        else:
            raise AssertionError('Expected refusal')
    def put(path, data):
        path.write_text(json.dumps(data))
    def putrows(path, data):
        path.write_text(''.join(json.dumps(row)+'\n' for row in data))
    original = scoring.validate_run
    def reject(*args):
        raise ValueError('Producer incomplete')
    scoring.validate_run = reject
    refuses(lambda: scoring.score_run(SimpleNamespace(run=None, source=None, split=None, phase_state=None, phase_exit=None)))
    root.mkdir()
    source, replay = root/'source', root/'replay'
    source.mkdir(); replay.mkdir(); (source/'ep').mkdir()
    frames = [dict(seq=i, produced_at=100+i*.1, tick_lo=i*2, tick_hi=i*2+1,
                   bracket_extrapolated=False) for i in range(3)]
    events = [dict(event_id='e', accepted=True, card='Fireball', kind='flight', side=0, tile=[3.5,13.5], exec_tick=2),
              dict(event_id='a', accepted=True, card='Champion', kind='champion ability', side=1, tile=[1.,1.], exec_tick=2)]
    putrows(source/'ep/frames.jsonl', frames); putrows(source/'ep/events.jsonl', events)
    receipt = dict(episode='ep', split='validation', frames=3, accepted_events=2,
                   files={name:scoring.sha(source/'ep'/name) for name in ('frames.jsonl','events.jsonl')})
    put(source/'ep/receipt.json', receipt)
    admission = {'validation_receipt_sha256':{'ep':scoring.sha(source/'ep/receipt.json')}}
    scoring.validate_run = lambda *args:admission
    scoring.card_kinds = lambda cards:{c:'spell' for c in cards}
    times = scoring.frame_times(frames)
    candidates = [dict(card='Fireball', side=0, x_tiles=3.5, y_tiles=13.5, existence_q=.7,
                       execution_timestamp_ms=50., available_timestamp_ms=-999.)]*2
    outputs = [dict(source_seq=i, payload=dict(episode_id='ep',timestamp_ms=stamp,
                event_candidates=candidates if i == 1 else [])) for i,stamp in enumerate(times)]
    completions = [dict(episode_id='ep',source_seq=i,timestamp_ms=stamp,service_ms=20.,
                        available_timestamp_ms=stamp+20) for i,stamp in enumerate(times)]
    putrows(replay/'ep-outputs.jsonl', outputs); putrows(replay/'ep-completion.jsonl', completions)
    manifest = dict(schema='clasher.v4.validation-replay.v1', readiness=admission, epoch=1,
        replay_mode='grid',event_thresholds={'default':.5},threshold_map_sha256=None,
        threshold=.5, body_threshold=.7, device='cuda', precision='fp32', calibration={}, heldout_payloads_opened=False,
        selection_seal=False, driver_sha256=scoring.sha(Path(scoring.__file__).with_name('validation_replay_v4.py')))
    put(replay/'manifest.json', manifest)
    complete = dict(manifest_sha256=scoring.sha(replay/'manifest.json'),
        heldout_payloads_opened=False,selection_seal=False,
        files_sha256={p.name:scoring.sha(p) for p in replay.glob('*.jsonl')},
        episodes={'ep':dict(frames=3,final_available_timestamp_ms=completions[-1]['available_timestamp_ms'])})
    put(replay/'complete.json', complete)
    args = SimpleNamespace(run=None, source=source, split=None, phase_state=None, phase_exit=None, replay=replay)
    result = scoring.score_run(args)
    check(result['point']['opponent']['matched'] == 1 and result['point']['opponent']['false_positive'] == 1)
    check(result['point']['placement']['spell']['hits'] == 1)
    check(result['point']['champion_abilities']['truth'] == 1 and result['point']['all_sides']['truth'] == 1)
    check(result['conservative']['opponent']['matched'] == 1)
    check(result['selection_seal'] is False and result['heldout_payloads_opened'] is False)
    check(result['body_threshold']==.7)
    check(result['replay_mode']=='grid' and result['event_thresholds']=={'default':.5})
    mixed=deepcopy(manifest);mixed.update(replay_mode='combined',event_thresholds={'default':.5,'Fireball':.7},threshold_map_sha256='a'*64)
    put(replay/'manifest.json',mixed)
    changed=deepcopy(complete);changed['manifest_sha256']=scoring.sha(replay/'manifest.json');put(replay/'complete.json',changed)
    combined=scoring.score_run(args)
    check(combined['replay_mode']=='combined' and combined['event_thresholds']==mixed['event_thresholds'])
    for key,value in [('replay_mode','grid'),('threshold_map_sha256',None),('event_thresholds',{'default':.4}),('event_thresholds',{'default':.5,'Fireball':True})]:
        bad=deepcopy(mixed);bad[key]=value;put(replay/'manifest.json',bad)
        changed['manifest_sha256']=scoring.sha(replay/'manifest.json');put(replay/'complete.json',changed)
        refuses(lambda:scoring.score_run(args))
    put(replay/'manifest.json',manifest);put(replay/'complete.json',complete)
    for value in (None,True,.55):
        bad=deepcopy(manifest);bad['body_threshold']=value;put(replay/'manifest.json',bad)
        changed=deepcopy(complete);changed['manifest_sha256']=scoring.sha(replay/'manifest.json')
        put(replay/'complete.json',changed)
        refuses(lambda:scoring.score_run(args))
    put(replay/'manifest.json',manifest);put(replay/'complete.json',complete)
    # Changed bytes are refused before scoring.
    file = replay/'ep-outputs.jsonl'; saved = file.read_bytes(); file.write_bytes(saved+b'\n')
    refuses(lambda: scoring.score_run(args)); file.write_bytes(saved)
    # Even re-hashed evidence must retain exact frame order.
    bad = deepcopy(completions); bad[1]['source_seq'] = 0
    putrows(replay/'ep-completion.jsonl',bad)
    changed = deepcopy(complete); changed['files_sha256']['ep-completion.jsonl']=scoring.sha(replay/'ep-completion.jsonl')
    put(replay/'complete.json',changed)
    refuses(lambda: scoring.score_run(args))
    putrows(replay/'ep-completion.jsonl',completions); put(replay/'complete.json',complete)
    bad = deepcopy(complete); del bad['files_sha256']['ep-completion.jsonl']; put(replay/'complete.json',bad)
    refuses(lambda: scoring.score_run(args)); put(replay/'complete.json',complete)
    file=source/'ep/events.jsonl'; saved=file.read_bytes(); file.write_bytes(saved+b'\n')
    refuses(lambda: scoring.score_run(args)); file.write_bytes(saved)
    bad = deepcopy(events); bad.append(deepcopy(events[0]))
    refuses(lambda: scoring.mapped_truth(frames,bad,'ep',{'Fireball':'spell'}))
    bad = deepcopy(events); bad[0]['exec_tick'] = 1000
    refuses(lambda: scoring.mapped_truth(frames,bad,'ep',{'Fireball':'spell'}))
    scoring.validate_run = original
    print(dict(checks=checks,passed=True,scope='synthetic file fixtures; no real model or formal gate'),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)

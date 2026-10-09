"""Full validation body cell from authenticated shared capture; no selection authority."""
import argparse,gzip,json
from pathlib import Path
from body_scoring_v4 import BodyTruth,POLICY,score_frame,summarize
from record_capture_admission_v4 import authenticate_record_capture
from clock_free_records_v4 import body_frames
from portable_fit_admission_v4 import validate_portable
from validation_admission_v4 import read,sha
from validation_replay_v4 import frame_times
from validation_score_v4 import rows


def score_body_records(a):
    ready=validate_portable(a.bundle,a.bundle_sha256,a.source,a.split,a.phase_state,a.phase_exit)
    admitted=authenticate_record_capture(a.capture,complete_sha=a.complete_sha256,readiness=ready,bundle=a.bundle,
        plan=a.plan,plan_sha=a.plan_sha256,host=a.host,equality=a.equality,equality_sha=a.equality_sha256)
    if type(a.body) is not int or a.body not in range(1,10):raise ValueError('Registered body branch required')
    code=Path(__file__).resolve().parent;truth_source=a.bundle/'fit/model/source'
    files=[code/n for n in ('clock_free_body_score_v4.py','record_capture_admission_v4.py','portable_fit_admission_v4.py',
        'clock_free_records_v4.py','decoder_records_v4.py','body_scoring_v4.py','labels_v4.py',
        'validation_replay_v4.py','validation_score_v4.py','scoring_v4.py','execution_clock_v4.py')]
    files += [truth_source/'gamedata.json',truth_source/'body-catalog.json']
    sources={str(p):sha(p) for p in files}
    from labels_v4 import BodyLabels,read_objects
    cleaner=BodyLabels(truth_source/'gamedata.json',truth_source/'body-catalog.json')
    per_match={};all_counts=[];truth_files={}
    for ep,expected_frames in sorted(admitted['episodes'].items()):
        folder=a.source/ep;receipt=read(folder/'receipt.json')
        if sha(folder/'receipt.json')!=ready['validation_receipt_sha256'][ep] or receipt['split']!='validation':
            raise ValueError('Validation isolation changed')
        pins={n:receipt['files'][n] for n in ('frames.jsonl','objects.jsonl.gz','rich-objects.jsonl.gz')}
        if any(sha(folder/n)!=d for n,d in pins.items()):raise ValueError('Validation truth changed')
        prefix=f'body-{a.body}/{ep}'
        raw=a.capture/(prefix+'-decoder.jsonl.gz')
        with gzip.open(raw,'rt') as f:records=[json.loads(line) for line in f]
        frames=rows(folder/'frames.jsonl')
        if len(frames)!=expected_frames or len(records)!=len(frames):
            raise ValueError('Full source frame alignment required')
        decoded=body_frames(records,episode=ep,expected_times=frame_times(frames),body_threshold=a.body/10)
        truth=BodyTruth(cleaner.clean(read_objects(folder/'objects.jsonl.gz'),read_objects(folder/'rich-objects.jsonl.gz')))
        counts=[]
        for i,(frame,tracks) in enumerate(zip(frames,decoded)):
            if frame['seq']!=i:raise ValueError('Frame ordering changed')
            counts.append(score_frame(tracks,truth.at((frame['tick_lo']+frame['tick_hi'])/2)))
        per_match[ep]=summarize(counts);all_counts.extend(counts);truth_files[ep]=pins
        if (any(sha(folder/n)!=d for n,d in pins.items()) or
                any(sha(a.capture/n)!=admitted['files_sha256'][n] for n in
                    (prefix+'-decoder.jsonl.gz',))):
            raise ValueError('Scoring inputs changed')
        print(json.dumps(dict(epoch=admitted['epoch'],body=a.body/10,matches=len(per_match))),flush=True)
    if any(sha(Path(p))!=d for p,d in sources.items()) or sha(a.capture/'complete.json')!=a.complete_sha256:
        raise ValueError('Scorer/capture evidence changed')
    return dict(schema='clasher.v4.clock-free-body-score.v1',epoch=admitted['epoch'],body_threshold=a.body/10,
        event_thresholds={'default':.5},readiness=ready,capture_admission=admitted,policy=POLICY,
        micro=summarize(all_counts),per_match=per_match,sources=sources,truth_payloads=truth_files,
        clocks_read=False,selection_seal=False,heldout_payloads_opened=False,
        heldout_opening_authorized=False,scope='full clock-free source-frame body branch; no event scoring or heldout authority')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('bundle','source','split','phase-state','phase-exit','capture','plan','equality','output'):
        p.add_argument('--'+n,type=Path,required=True)
    for n in ('bundle-sha256','complete-sha256','plan-sha256','host','equality-sha256'):
        p.add_argument('--'+n,required=True)
    p.add_argument('--body',type=int,choices=range(1,10),required=True);a=p.parse_args()
    result=score_body_records(a)
    with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')

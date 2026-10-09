"""Clock-free views of admitted decoder records for Amendment12 preparation.

No file loading or admission. Never supply completion journals here. The caller
must authenticate the full validation population, branch and all record hashes.
"""
from copy import deepcopy
from dataclasses import asdict
import math


def checked_records(records, *, episode, expected_times):
    records=list(records);times=list(expected_times)
    if not records or len(records)!=len(times):
        raise ValueError('Complete recorded frame population required')
    previous=None
    for i,(r,t) in enumerate(zip(records,times)):
        if (type(t) not in (int,float) or not math.isfinite(t)
                or (i==0 and t!=0) or (previous is not None and t<=previous)
                or r.get('schema')!='clasher.v4.decoder-frame.v1'
                or r.get('episode_id')!=episode or type(r.get('source_seq')) is not int
                or r['source_seq']!=i or r.get('timestamp_ms')!=t):
            raise ValueError('Record/source frame identity changed')
        if any(k in r for k in ('available_timestamp_ms','service_ms','clock')):
            raise ValueError('Quarantined clock fields forbidden')
        previous=t
    return records


def body_frames(records, *, episode, expected_times, body_threshold):
    if type(body_threshold) not in (int,float) or body_threshold not in [i/10 for i in range(1,10)]:
        raise ValueError('Registered body setting required')
    from clasher.vision.l1_v4 import BodyTracker
    tracker=BodyTracker(high=body_threshold)
    return [tracker.update(deepcopy(r['bodies']),r['timestamp_ms'])[0]
            for r in checked_records(records,episode=episode,expected_times=expected_times)]


def event_predictions(records, *, episode, expected_times, spells, threshold):
    if type(threshold) not in (int,float) or threshold not in [i/10 for i in range(1,10)]:
        raise ValueError('Registered global threshold required')
    from decoder_records_v4 import RecordedEventFusion
    fusion=RecordedEventFusion(spells,{'default':threshold},{})
    result=[]
    for r in checked_records(records,episode=episode,expected_times=expected_times):
        stamp=r['timestamp_ms']
        # This ABI argument only populates an output field; it never affects
        # thresholding/NMS. Strip it immediately. It is NOT a scoring clock.
        events=fusion.update(r['event_peaks'],stamp,stamp,r['causal_own_hud_cards'])
        for event in events:
            out=asdict(event);out.pop('available_timestamp_ms')
            out.update(episode_id=episode,source_seq=r['source_seq'],kind='card_play',
                       production_timestamp_ms=stamp)
            result.append(out)
    return result

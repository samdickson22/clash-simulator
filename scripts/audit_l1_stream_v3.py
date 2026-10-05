"""Audit continuous video timing and produce isolated training/evaluation labels."""
import argparse
from bisect import bisect_right
from collections import Counter
import json
from pathlib import Path

import cv2
import numpy as np

from clasher.vision.l1_hud_v3 import StreamHudReader
from clasher.vision.l1_timing_v3 import fit_timing
from collect_l1_rendered import REPORT, append, progress


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit_episode(dataset,entry,out):
    ep=entry['episode_id'];source=dataset/'evaluation_only'/ep
    frames=read(source/'frames.jsonl');obs=read(source/'observations.jsonl')
    anchors=read(source/'timing.jsonl') if (source/'timing.jsonl').exists() else []
    anchors+=obs;anchors.sort(key=lambda r:r['start_ns'])
    timestamps=np.array([(r['start_ns']+r['end_ns'])/2e9 for r in anchors])
    ticks=np.array([r['tick'] for r in anchors])
    if np.any(np.diff(ticks)<0):raise ValueError(f'{ep}: nonmonotone native ticks')
    hud=StreamHudReader(REPORT/'v1/model/hud.npz')
    video=cv2.VideoCapture(str(dataset/'videos'/f'{ep}.mp4'))
    if not video.isOpened():raise ValueError('Cannot decode H.264')
    clocks=[]
    for row in frames:
        ok,image=video.read()
        if not ok:raise ValueError('Video truncated before metadata')
        public=hud.read(image)
        clocks.append(dict(row,clock=public['clock'],clock_confidence=public['clock_confidence'],clock_phase=public['clock_phase']))
    if video.read()[0]:raise ValueError('Video has unlabelled frames')
    video.release()
    timing=fit_timing([dict(command='resume')]+[dict(command='observe',start_ns=r['start_ns'],
        end_ns=r['end_ns'],result=dict(tick=r['tick'])) for r in anchors],clocks)
    (out/'timing.json').write_text(json.dumps(timing,indent=2)+'\n')
    lag=timing['clock_lag_ms']/1000
    # This remains an empirical uncertainty band, never an exact fence claim.
    uncertainty=(timing['native_local_validation_max_ms']+
        max(max(abs(e['lag_low_ms']-timing['clock_lag_ms']),
                abs(e['lag_high_ms']-timing['clock_lag_ms'])) for e in timing['clock_edges']))/1000
    origin=frames[0]['received_mono_s']-frames[0]['timestamp_ms']/1000
    obs_times=[(r['start_ns']+r['end_ns'])/2e9 for r in obs]
    for row in frames:
        production=row['produced_epoch_s']+((row['mono_before_ns']+row['mono_after_ns'])/2-row['wall_ns'])/1e9
        estimated=np.interp(production-lag,timestamps,ticks)
        lo=np.interp(production-lag-uncertainty,timestamps,ticks)
        hi=np.interp(production-lag+uncertainty,timestamps,ticks)
        index=max(0,min(len(obs)-2,bisect_right(obs_times,production-lag)-1))
        before,after=obs[index],obs[index+1]
        append(out/'frames.jsonl',dict(frame_index=row['frame_index'],estimated_tick=float(estimated),
            tick_interval=[int(np.floor(lo)),int(np.ceil(hi))],timestamp_ms=row['timestamp_ms'],
            native_before=before,native_after=after,timing_certified=False))
        append(out/'inputs.jsonl',{k:row[k] for k in ('episode_id','frame_index','timestamp_ms','video')})
    accepted=[];incomplete_windows=[]
    for e in read(source/'events.jsonl'):
        if not e['accepted']:continue
        j=int(np.searchsorted(ticks,e['tick']))
        if not 0<j<len(anchors):raise ValueError('Deployment outside timing anchors')
        interval=[(anchors[j-1]['start_ns']/1e9-origin)*1000,(anchors[j]['end_ns']/1e9-origin)*1000]
        e=dict(e,episode_id=ep,event_time_interval_ms=interval)
        if frames[-1]['timestamp_ms']<interval[1]+500:
            incomplete_windows.append(e['sequence'])
        append(out/'events.jsonl',e);accepted.append(e)
    commands=read(source/'commands.jsonl') if (source/'commands.jsonl').exists() else []
    handled={e['sequence'] for e in read(source/'events.jsonl')}
    unresolved=[e['sequence'] for e in commands if e['sequence'] not in handled and e['tick']<=ticks[-1]]
    summary=dict(episode_id=ep,frames=len(frames),accepted_events=len(accepted),
        fps=timing['fps'],native_p95_ms=timing['native_local_validation_p95_ms'],
        pixel_interval_halfwidth_ms=uncertainty*1000,timing_certified=False,
        reason='Empirical clock/host timing bounds have not established per-frame coverage',
        incomplete_event_windows=incomplete_windows,unresolved_scheduled_commands=unresolved,
        card_sides=dict(Counter(f"{e['player_id']}:{e['card']}" for e in accepted)))
    (out/'complete.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('dataset',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();cv2.setNumThreads(1)
    a.output.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((a.dataset/'manifest.json').read_text())
    completed={r['episode_id']:r for path in a.dataset.glob('episodes-*.jsonl') for r in read(path)}
    summaries=[]
    for entry in manifest['matches']:
        if entry['episode_id'] not in completed:continue
        out=a.output/entry['episode_id'];out.mkdir()
        summaries.append(audit_episode(a.dataset,entry,out))
    result=dict(episodes=len(summaries),events=sum(r['accepted_events'] for r in summaries),
        all_completed=len(summaries)==len(manifest['matches']),timing_certified=False)
    (a.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    progress(f"v3 audit: {result['episodes']} episodes, {result['events']} accepted events; empirical timing only, certification pending.")


if __name__=='__main__':main()

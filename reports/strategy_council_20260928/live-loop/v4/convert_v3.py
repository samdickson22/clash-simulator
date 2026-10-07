"""Subsample actual timestamps to ~10 FPS and emit v3 training/audit layout."""
import argparse
import bisect
import gzip
import json
import shutil
from pathlib import Path
from fractions import Fraction
from common import append,sha,write


def convert(source, output):
    import av
    source,output=Path(source),Path(output)
    if output.exists():raise ValueError('Converter requires a fresh output')
    receipt=json.loads((source/'receipt.json').read_text())
    for name,digest in receipt['files'].items():
        if sha(source/name)!=digest:raise ValueError('Input hash mismatch')
    ep=receipt['episode'];output.mkdir(parents=True)
    (output/'videos').mkdir();audit=output/'audit'/ep;audit.mkdir(parents=True)
    frames=[json.loads(l) for l in (source/'frames.jsonl').read_text().splitlines()]
    keep=[];due=frames[0]['produced_at']
    for f in frames:
        if f['produced_at']+.000001>=due:
            keep.append(f);due+=.1
            if due<f['produced_at']-.1:due=f['produced_at']+.1
    selected={f['seq']:i for i,f in enumerate(keep)}
    out=av.open(str(output/'videos'/f'{ep}.mp4'),'w');stream=out.add_stream('libx264',rate=10)
    stream.width=540;stream.height=1140;stream.pix_fmt='yuv420p';stream.time_base=Fraction(1,90000)
    stream.codec_context.time_base=Fraction(1,90000);stream.options={'crf':'23','preset':'veryfast','threads':'1'}
    decoded=0
    with av.open(str(source/'video.mp4')) as video:
        for i,frame in enumerate(video.decode(video=0)):
            decoded+=1
            if i not in selected:continue
            frame.pts=round((frames[i]['produced_at']-keep[0]['produced_at'])*90000);frame.time_base=Fraction(1,90000)
            for packet in stream.encode(frame):out.mux(packet)
    for packet in stream.encode():out.mux(packet)
    out.close()
    assert decoded==len(frames)
    with gzip.open(source/'evaluation-only.jsonl.gz','rt') as f:truth=[json.loads(l) for l in f]
    times=[r['observed_at'] for r in truth]
    # Resolve names from the frozen per-match deck population.
    from clasher.data import CardDataLoader
    from clasher.rl.native_public_observation import PUBLIC_REFERENCE_CARDS
    from clasher.rl.c56_scripted import C56_ADDED_CARDS
    loader=CardDataLoader();names={loader.get_card(n)._raw_entry['id']:n for n in set(PUBLIC_REFERENCE_CARDS)|C56_ADDED_CARDS}
    def native(row):
        obs=row['observation'];players=[]
        for p in sorted(obs['players'],key=lambda x:x['owner']):
            hand=[None]*4
            for c in p['hand']:hand[c['handIndex']]=names[c['cardId']]
            players.append(dict(elixir=p['elixir'],hand=hand,cycle=[names[c['cardId']] for c in p['cycle']]))
        return dict(tick=obs['tick'],players=players)
    for i,f in enumerate(keep):
        j=bisect.bisect_right(times,f['produced_mono']);lo=truth[max(0,j-1)];hi=truth[min(len(truth)-1,j)]
        stamp=(f['produced_at']-keep[0]['produced_at'])*1000
        append(audit/'frames.jsonl',dict(frame_index=i,estimated_tick=(f['tick_lo']+f['tick_hi'])/2,
          tick_interval=[f['tick_lo'],f['tick_hi']],timestamp_ms=stamp,native_before=native(lo),native_after=native(hi),timing_certified=False))
        append(audit/'inputs.jsonl',dict(episode_id=ep,frame_index=i,timestamp_ms=stamp,video=f'videos/{ep}.mp4'))
        append(audit/'v4-frame-map.jsonl',dict(frame_index=i,source_seq=f['seq'],source=f))
    events=[json.loads(l) for l in (source/'events.jsonl').read_text().splitlines()]
    converted=[]
    for e in events:
        if not e['accepted'] or e['kind']=='champion ability':continue
        ticks=[r['observation']['tick'] for r in truth];j=bisect.bisect_left(ticks,e['exec_tick'])
        lo=truth[max(0,j-1)];hi=truth[min(len(truth)-1,j)]
        v=dict(e,episode_id=ep,tick=e['exec_tick'],player_id=e['side'],x_tiles=e['tile'][0],y_tiles=e['tile'][1],
          event_time_interval_ms=[(lo['observed_at']-keep[0]['produced_mono'])*1000,(hi['observed_at']-keep[0]['produced_mono'])*1000],v4_source=e)
        append(audit/'events.jsonl',v);converted.append(v)
    write(audit/'complete.json',dict(episode_id=ep,frames=len(keep),accepted_events=len(converted),timing_certified=False))
    write(output/'manifest.json',dict(schema='clasher.l1.stream.v3',cards=sorted(names.values()),ids={v:k for k,v in names.items()},
      matches=[dict(episode_id=ep,seed=receipt['seed'],split=receipt['split'],decks=receipt['decks'])]))
    with av.open(str(output/'videos'/f'{ep}.mp4')) as video:count=sum(1 for _ in video.decode(video=0))
    # Round trip source labels exactly, not just a count or a schema check.
    mapped=[json.loads(l) for l in (audit/'v4-frame-map.jsonl').read_text().splitlines()]
    assert [r['source'] for r in mapped]==keep and count==len(keep)
    assert [v['v4_source'] for v in converted]==[e for e in events if e['accepted'] and e['kind']!='champion ability']
    result=dict(passed=True,source_frames=len(frames),converted_frames=count,events_roundtripped=len(converted),
       source_sha256=sha(source/'receipt.json'),output=str(output))
    write(output/'roundtrip.json',result);return result

def convert_corpus(sources, output):
    """Build one v3 dataset from finalized v4 matches; manifest commits last."""
    output=Path(output)
    if output.exists():raise ValueError('Corpus output must be fresh')
    output.mkdir(parents=True);(output/'videos').mkdir();(output/'audit').mkdir()
    manifest=None;results=[];seen=set()
    for source in sources:
        receipt=json.loads((Path(source)/'receipt.json').read_text());ep=receipt['episode']
        if ep in seen:raise ValueError('Duplicate episode in corpus')
        seen.add(ep);scratch=output/('.converting-'+ep)
        result=convert(source,scratch);entry=json.loads((scratch/'manifest.json').read_text())
        if manifest is None:manifest=dict(entry,matches=[])
        if (entry['cards'],entry['ids'])!=(manifest['cards'],manifest['ids']):raise ValueError('Corpus roster differs')
        manifest['matches'].extend(entry['matches'])
        (scratch/'videos'/f'{ep}.mp4').replace(output/'videos'/f'{ep}.mp4')
        (scratch/'audit'/ep).replace(output/'audit'/ep)
        write(output/'audit'/ep/'roundtrip.json',result)
        shutil.rmtree(scratch);results.append(result)
    if not results:raise ValueError('No finalized v4 matches')
    write(output/'roundtrip.json',dict(passed=True,matches=len(results),frames=sum(r['converted_frames'] for r in results),events=sum(r['events_roundtripped'] for r in results)))
    write(output/'manifest.json',manifest)
    return dict(matches=len(results),output=str(output))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if (a.source/'receipt.json').exists():print(convert(a.source,a.output))
    else:
        sources=[r.parent for r in sorted(a.source.glob('*/receipt.json')) if json.loads(r.read_text()).get('schema')=='clasher.live-v4.match.v1' and json.loads(r.read_text()).get('split')!='smoke']
        print(convert_corpus(sources,a.output))

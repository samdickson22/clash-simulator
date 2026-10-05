"""Recapture complete late event windows without changing frozen scored inputs."""
import hashlib
import json
from pathlib import Path
import time
import subprocess
import sys

import cv2
import numpy as np

from clasher.data import CardDataLoader
from clasher.vision.l1_stream import GrpcScreenStream
from collect_l1_rendered import REPORT,capture,append,progress,digest
from smoke_reference_battle import request


def main():
    v2=REPORT/'v2';dataset=v2/'dataset';output=v2/'tail-windows'
    receipt=json.loads((v2/'emulator/complete.json').read_text())
    # The existing launch receipt and completed owned replay establish ownership.
    if not (v2/'stream-dataset/complete.json').exists():raise ValueError('Wait for owned continuous replay')
    output.mkdir(exist_ok=False);(output/'frames').mkdir()
    manifest=json.loads((dataset/'manifest.json').read_text())
    events=[json.loads(l) for l in (dataset/'evaluation_only/events.jsonl').read_text().splitlines()]
    loader=CardDataLoader();ids={n:loader.get_card(n)._raw_entry['id'] for m in manifest['matches'] for d in m['decks'] for n in d}
    call=lambda c:request(receipt['probe_port'],c)
    discovery=Path.home()/f"Library/Caches/TemporaryItems/avd/running/pid_{receipt['pid']}.ini"
    windows=[]
    with GrpcScreenStream(receipt['grpc_port'],REPORT/'v1/grpc',discovery) as stream:
        for m in manifest['matches']:
            if m['split']!='heldout':continue
            own=[e for e in events if e['episode_id']==m['episode_id']]
            late=[e for e in own if e['tick']+30>manifest['config']['collection']['heldout_end_tick']]
            if not late:continue
            start=min(e['tick']-6 for e in late);end=max(e['tick']+30 for e in late)
            seq=call('configure-native '+json.dumps(m['config'],separators=(',',':')))['sequence']
            deadline=time.monotonic()+40
            while time.monotonic()<deadline:
                s=call('status')
                if s['nativeRenderLoaded']==seq and s['nativeRenderReady']:break
                time.sleep(.1)
            else:raise TimeoutError('Tail replay startup')
            tick=call('pause')['tick'];call('speed 1');call('render on');call(f'advance-native {340-tick}')
            for e in own:
                call(f"replay-schedule-card {e['player_id']} {ids[e['card']]} {round(e['x_tiles']*1000)} {round(e['y_tiles']*1000)} {e['tick']}")
            call('speed 4');tick=340
            while tick<start:
                step=min(200,start-tick);r=call(f'advance-native {step}');tick=r['tick']
            for tick in range(start,end+1):
                if tick>start:
                    r=call('advance-native 1')
                    if r['tick']!=tick:raise ValueError('Tail tick mismatch')
                jpg,obs,pair=capture(call,receipt['serial'],tick,stream)
                name=f'frames/{m["episode_id"]}-{tick:05}.jpg';(output/name).write_bytes(jpg)
                append(output/'frames.jsonl',dict(episode_id=m['episode_id'],tick=tick,image=name,
                    jpeg_sha256=hashlib.sha256(jpg).hexdigest(),**{k:v for k,v in pair.items() if k!='tick'}))
            windows.extend(dict(episode_id=m['episode_id'],tick=e['tick'],player_id=e['player_id'],card=e['card'],
                start_tick=start,end_tick=end,source='independent deterministic command replay',
                scored_inputs_unchanged=True) for e in late)
            progress(f'v2 independently recaptured {len(late)} late deploy windows in {m["episode_id"]}: ticks {start}..{end}. Frozen scored inputs unchanged.')
    (output/'windows.json').write_text(json.dumps(windows,indent=2)+'\n')
    (output/'complete.json').write_text(json.dumps(dict(windows=len(windows),render_tick_certified=False))+'\n')
    progress('v2 starting continuous event-boundary replay; long native advances between commands avoid one-tick control overhead. JPEG quality 55 keeps total new data bounded.')
    subprocess.run([sys.executable,'scripts/collect_l1_stream_v2.py','--mode','event-boundaries',
        '--jpeg-quality','55','--output',str(v2/'fast-stream-dataset')],check=True)


if __name__=='__main__':main()

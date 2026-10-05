"""Launcher-only transport smoke. Never interprets these as in-game measurements."""
import json
import time
import numpy as np
from official_loop import ROOT,Input,Capture,ScreenStates,adb
from recording import Recorder


def stats(xs):
    return {'samples':len(xs),'mean':float(np.mean(xs)),'p50':float(np.quantile(xs,.5)),
            'p95':float(np.quantile(xs,.95)),'p99':float(np.quantile(xs,.99))}

def main():
    adb('shell','input','keyevent','KEYCODE_HOME')
    rows=[];inputs=[]
    controller=Input(ROOT/'benchmark-input.jsonl')
    # Neutral wallpaper taps. Identical command shape to card-slot then arena.
    for _ in range(10):
        inputs.append(controller._run(['input','tap','20','400',';','input','tap','30','500'],'two_tap_transport_only'))
    with Recorder(ROOT/'recordings/launcher-smoke.mp4',max_bytes=10_000_000) as recorder:
        def sink(frame):
            recorder(frame)
            rows.append({'seq':frame.sequence,'mono':frame.received_monotonic,
                         'age_ms':1000*(frame.received_at-frame.produced_at)})
        with Capture(sink) as stream:
            first=stream.read()
            for _ in range(10):
                controller.drag(360,1130,360,400,400)
                time.sleep(.25)
                controller.drag(360,400,360,1130,400)
                time.sleep(.25)
            last=stream.read()
            (ROOT/'evidence/transport-final.png').write_bytes(adb('exec-out','screencap','-p').stdout)
            recognized=ScreenStates().recognize(last.pixels)
    elapsed=rows[-1]['mono']-rows[0]['mono']
    report={'scope':'Android launcher/app-drawer gesture smoke, not Clash Royale gameplay',
            'frames':len(rows),'seconds':elapsed,'fps':(len(rows)-1)/elapsed,
            'screenshot_production_to_receipt_ms':stats([r['age_ms'] for r in rows]),
            'two_tap_command_completion_ms':stats([r['command_ms'] for r in inputs]),
            'game_render_latency_ms':None,'card_acceptance_latency_ms':None,
            'recorded_frames':recorder.frames,'video_bytes':(ROOT/'recordings/launcher-smoke.mp4').stat().st_size,
            'unknown_screen_result':recognized}
    (ROOT/'transport-benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()

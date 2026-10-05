"""Measure continuous 1x offline screenshot production and delivery."""
import argparse
import concurrent.futures
import json
from pathlib import Path
import subprocess
import time

import numpy as np

from smoke_reference_battle import request
from clasher.vision.l1_stream import GrpcScreenStream
from clasher.vision.l1_perception import clock_digits

ADB=Path.home()/'.cache/clasher-native-reference/android-sdk/platform-tools/adb'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('ownership','dataset','proto','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();receipt=json.loads(a.ownership.read_text())
    devices=subprocess.check_output([str(ADB),'devices'],text=True)
    emulator_count=sum(line.startswith('emulator-') for line in devices.splitlines())
    command=subprocess.check_output(['ps','-p',str(receipt['pid']),'-o','command='],text=True)
    if 'clasher_reference_api35' not in command or f"-port {receipt['serial'].split('-')[-1]}" not in command:
        raise ValueError('Owned emulator identity changed')
    for firewall in ('iptables','ip6tables'):
        subprocess.run([str(ADB),'-s',receipt['serial'],'shell',firewall,'-C','OUTPUT','-m',
                        'owner','--uid-owner',str(receipt['app_uid']),'!','-o','lo','-j','REJECT'],
                       check=True,capture_output=True,timeout=20)
    port=receipt['probe_port'];call=lambda c:request(port,c)
    config=json.loads((a.dataset/'manifest.json').read_text())['matches'][0]['config']
    config['rndSeed']=261005999
    sequence=call('configure-native '+json.dumps(config,separators=(',',':')))['sequence']
    deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        status=call('status')
        if status['nativeRenderLoaded']==sequence and status['nativeRenderReady']:break
        time.sleep(.1)
    else:raise TimeoutError('Native renderer startup')
    tick=call('pause')['tick'];call('speed 1');call('render on')
    call(f'advance-native {200-tick}')
    discovery=Path.home()/f"Library/Caches/TemporaryItems/avd/running/pid_{receipt['pid']}.ini"
    ages=[];times=[];sequences=[]
    def advance_match():
        result=None
        for block in range(6):
            if block:
                current=call('observe')
                for player in current['players']:
                    choices=[c for c in player['hand'] if c['cost']<=player['elixir']]
                    if choices:
                        card=choices[block%len(choices)]
                        call(f"replay-schedule-card {player['owner']} {card['cardId']} {3500 if block%2 else 14500} {13500 if player['owner']==0 else 18500} {current['tick']+1}")
            result=call('advance-native 200')
            if result['ended']:break
        return result
    with GrpcScreenStream(receipt['grpc_port'],a.proto,discovery) as stream:
        previous=stream.read()
        for _ in range(30):
            if clock_digits(previous.pixels):break
            call('advance-native 20')
            previous=stream.read(after_time=time.perf_counter()+.12)
        else:raise RuntimeError('Benchmark intro did not reveal the public HUD')
        obs=call('observe')
        for player in obs['players']:
            card=next(c for c in player['hand'] if c['cost']<=player['elixir'])
            call(f"replay-schedule-card {player['owner']} {card['cardId']} 3500 {13500 if player['owner']==0 else 18500} {obs['tick']+1}")
        time.sleep(1)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            advancing=pool.submit(advance_match)
            while not advancing.done():
                frame=stream.read(after_sequence=previous.sequence,timeout=10)
                age=(time.time()-frame.produced_at)*1000
                if not 0<=age<10000:raise ValueError('Unusable emulator timestamp')
                ages.append(age);times.append(frame.decoded_at);sequences.append(frame.sequence)
                previous=frame
            result=advancing.result()
    report=dict(frames=len(times),seconds=times[-1]-times[0],fps=(len(times)-1)/(times[-1]-times[0]),
                screenshot_production_to_sanitized_receipt_mean_ms=float(np.mean(ages)),
                screenshot_production_to_sanitized_receipt_p95_ms=float(np.quantile(ages,.95)),
                screenshot_production_to_sanitized_receipt_p99_ms=float(np.quantile(ages,.99)),
                consumer_dropped_frames=int(sum(np.diff(sequences)-1)),final_tick=result['tick'],
                host_emulators_at_start=emulator_count,
                transport='emulator gRPC RGB888, source-resolution privacy mask before resize',
                rendered_tick_to_decode_p95_ms=None,render_tick_certified=False,
                scope='1x native stepping in ten-second segments with repeated deployments and short controller pauses; no perception/search. Emulator screenshot timestamp is not a game tick fence.',
                fps_gate=(len(times)-1)/(times[-1]-times[0])>=10,
                render_tick_latency_gate=False)
    a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':main()

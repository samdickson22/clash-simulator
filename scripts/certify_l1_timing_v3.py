"""Measure continuous 1x renderer timing without modifying the probe or APK."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time

import cv2

from collect_l1_rendered import ADB, BASE, REPORT, append, progress
from clasher.vision.l1_perception import HudReader
from clasher.vision.l1_stream import GrpcScreenStream
from smoke_reference_battle import request


def verify_owner(receipt):
    command = subprocess.check_output(['ps', '-p', str(receipt['pid']), '-o', 'command='], text=True)
    if 'clasher_reference_api35' not in command or '-port '+receipt['serial'].split('-')[-1] not in command:
        raise ValueError('Owned emulator identity mismatch')
    for firewall in ('iptables', 'ip6tables'):
        subprocess.run([str(ADB), '-s', receipt['serial'], 'shell', firewall, '-C',
                        'OUTPUT', '-m', 'owner', '--uid-owner', str(receipt['app_uid']),
                        '!', '-o', 'lo', '-j', 'REJECT'], check=True, capture_output=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--ownership', type=Path, default=REPORT/'v3/emulator/complete.json')
    p.add_argument('--seconds', type=float, default=80)
    p.add_argument('--poll-seconds', type=float, default=.04)
    p.add_argument('--fps', type=float, default=10.)
    a = p.parse_args()
    cv2.setNumThreads(1)
    receipt = json.loads(a.ownership.read_text())
    verify_owner(receipt)
    a.output.mkdir(parents=True, exist_ok=False)
    (a.output/'frames').mkdir()
    stop = threading.Event()

    def call(command):
        start = time.perf_counter_ns()
        result = request(receipt['probe_port'], command)
        end = time.perf_counter_ns()
        append(a.output/'requests.jsonl', dict(command=command, start_ns=start, end_ns=end, result=result))
        return result

    config = json.loads(BASE.read_text())['config']
    config.update(rndSeed=261007001, endTick=7200)
    sequence = call('configure-native '+json.dumps(config, separators=(',', ':')))['sequence']
    deadline = time.perf_counter()+45
    while time.perf_counter()<deadline:
        status = call('status')
        if status['nativeRenderLoaded']==sequence and status['nativeRenderReady']:
            break
        time.sleep(.1)
    else:
        raise TimeoutError('Native renderer startup')
    tick = call('pause')['tick']
    call('speed 1')
    call('render on')
    call(f'advance-native {340-tick}')
    obs = call('observe')
    for player in obs['players']:
        card = min(player['hand'], key=lambda c: c['cost'])
        side = player['owner']
        scheduled = call(f"replay-schedule-card {side} {card['cardId']} 6500 {11500 if side==0 else 20500} 401")
        append(a.output/'deployments.jsonl', dict(side=side, card=card, tick=401, sequence=scheduled['sequence']))
    hud = HudReader(REPORT/'v1/model/hud.npz')
    discovery = Path.home()/f"Library/Caches/TemporaryItems/avd/running/pid_{receipt['pid']}.ini"

    def observe():
        while not stop.is_set():
            before = time.perf_counter()
            call('observe')
            stop.wait(max(0., a.poll_seconds-(time.perf_counter()-before)))

    samples = 0
    try:
        with GrpcScreenStream(receipt['grpc_port'], REPORT/'v1/grpc', discovery) as stream:
            first = stream.read()
            call('resume')
            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(observe)
                try:
                    last = first.sequence
                    next_capture = time.perf_counter()
                    while time.perf_counter()-started<a.seconds:
                        if future.done():
                            future.result()
                        frame = stream.read(after_sequence=last)
                        last = frame.sequence
                        if frame.decoded_at<next_capture:
                            continue
                        next_capture += 1/a.fps
                        if next_capture<frame.decoded_at:
                            next_capture=frame.decoded_at+1/a.fps
                        # Simultaneous wall/monotonic anchors convert emulator epoch PTS.
                        mono_before = time.perf_counter_ns()
                        wall = time.time_ns()
                        mono_after = time.perf_counter_ns()
                        public = hud.read(frame.pixels)
                        ok, jpg = cv2.imencode('.jpg', frame.pixels, [cv2.IMWRITE_JPEG_QUALITY, 55])
                        if not ok:
                            raise ValueError('JPEG encode failed')
                        image = f'frames/{samples:06}.jpg'
                        (a.output/image).write_bytes(jpg.tobytes())
                        append(a.output/'frames.jsonl', dict(index=samples, sequence=frame.sequence,
                            produced_epoch_s=frame.produced_at, received_mono_s=frame.decoded_at,
                            mono_before_ns=mono_before, wall_ns=wall, mono_after_ns=mono_after,
                            clock=public['clock'], clock_confidence=public['clock_confidence'],
                            image=image, sha256=hashlib.sha256(jpg).hexdigest()))
                        samples += 1
                finally:
                    stop.set()
                    future.result()
    finally:
        stop.set()
        call('pause')
        verify_owner(receipt)
    (a.output/'complete.json').write_text(json.dumps(dict(frames=samples, seconds=a.seconds,
        poll_seconds=a.poll_seconds, target_fps=a.fps, render_tick_certified=False))+'\n')
    progress(f'v3 timing capture: {samples} frames, {a.seconds:g} seconds continuous resume at 1x; analysis pending.')


if __name__=='__main__':
    main()

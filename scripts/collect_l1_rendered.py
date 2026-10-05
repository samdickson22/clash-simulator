"""Collect bounded, paused offline-render frames. Never starts a game network."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np

from smoke_reference_battle import request
from clasher.data import CardDataLoader
from clasher.rl.native_public_observation import PUBLIC_REFERENCE_CARDS
from clasher.rl.live_inference_contract import assert_no_privileged_payload
from clasher.vision.l1 import Geometry, public_pixels
from clasher.vision.l1_perception import clock_digits

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/strategy_council_20260928/live-loop/l1'
BASE = ROOT / 'artifacts/worktree-data/clasher-simulator-fidelity-20260913/reports/calibration_development_20260915/expanded-deck-development/forward-0/plan.json'
ADB = Path.home() / '.cache/clasher-native-reference/android-sdk/platform-tools/adb'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def append(path, row):
    with path.open('a') as f:
        f.write(json.dumps(row, separators=(',', ':'), allow_nan=False)+'\n')


def progress(message):
    with (REPORT/'PROGRESS.md').open('a') as f:
        f.write(f'\n{time.strftime("%Y-%m-%d %H:%M:%S")}: {message}\n')
    print(message, flush=True)


def visible_clock(tick):
    # Stock replay timer: tick 200 visibly reads 2:51; 260 reads 2:48.
    return max(0, (180 if tick <= 3600 else 300) - max(0, (tick-1)//20))


def capture(call, serial, expected_tick, stream=None):
    status = call('status')
    if not status['paused'] or status['renderSuppressed'] or status['mode'] != 'native-render':
        raise RuntimeError('Capture requires paused native rendering')
    before = call('observe')
    if before['tick'] != expected_tick or before.get('truncated') or before.get('finalized'):
        raise RuntimeError('Unexpected/incomplete native frame')
    time.sleep(.12)  # Let the stock renderer present the completed simulation step.
    started = time.perf_counter()
    transport = {}
    if stream is None:
        raw = subprocess.check_output([str(ADB), '-s', serial, 'exec-out', 'screencap', '-p'], timeout=30)
        safe = public_pixels(cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR))
    else:
        frame = stream.read(after_time=started)
        safe = frame.pixels
        transport = dict(decoded_sequence=frame.sequence, decoded_at=frame.decoded_at,
                         transport=type(stream).__name__, render_tick_certified=False,
                         screenshot_produced_at=frame.produced_at)
    after = call('observe')
    if before != after:
        raise RuntimeError('Observe changed across screencap; frame rejected')
    ok, jpg = cv2.imencode('.jpg', safe, [cv2.IMWRITE_JPEG_QUALITY, 87])
    if not ok:
        raise RuntimeError('JPEG encoding failed')
    return jpg.tobytes(), before, dict(tick=expected_tick, observe_sha256=digest(before),
                                     before_after_equal=True, paused=True,
                                     capture_seconds=time.perf_counter()-started, **transport)


def public_targets(obs, names, geometry):
    own = next(p for p in obs['players'] if p['owner'] == 1)
    hand = ['empty']*4
    for c in own['hand']:
        hand[c['handIndex']] = names[c['cardId']]
    entities = []
    excluded = 0
    for obj in obs['objects']:
        # Ordinary observe cannot certify projectile phase or visible effect
        # identity. Do not relabel arrows as their originating troop.
        if obj.get('hp') is None or obj.get('hp', 0) <= 0:
            excluded += 1
            continue
        card = names.get(obj['cardId'])
        if obj['cardId'] == -1:
            card = 'KingTower' if obj['x'] == 9000 else 'Tower'
        if card is None:
            raise ValueError('Undeclared card')
        x, y = obj['x']/1000, obj['y']/1000
        entities.append(dict(card=card, player_id=obj['owner'], x_tiles=x, y_tiles=y,
                             pixel_box=geometry.box(card, x, y),
                             hp_fraction=obj['hp']/obj['maxHp'],
                             kind='building' if card in ('KingTower','Tower','Cannon','Tesla') else 'troop'))
    targets = dict(visible_clock_seconds=visible_clock(obs['tick']), own_hand=hand,
                   own_next_card=names[own['nextCard']['cardId']], own_elixir=float(int(own['elixir'])),
                   entities=entities)
    assert_no_privileged_payload(targets)
    return targets, excluded


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--port', type=int, default=26789)
    p.add_argument('--serial', default='emulator-5580')
    p.add_argument('--matches', type=int, default=7)
    p.add_argument('--ticks', type=int, default=3600)
    p.add_argument('--cadence', type=int, default=40)
    p.add_argument('--resume', action='store_true')
    p.add_argument('--seed-base',type=int,default=261004100)
    p.add_argument('--training-only',action='store_true')
    p.add_argument('--prioritize-card',choices=PUBLIC_REFERENCE_CARDS)
    p.add_argument('--ownership',type=Path,default=REPORT/'emulator/complete.json')
    p.add_argument('--v1',action='store_true',help='Stream capture, variable steps, visibility uncertainty')
    p.add_argument('--frames-per-match',type=int,default=300)
    p.add_argument('--grpc-proto',type=Path)
    p.add_argument('--grpc-discovery',type=Path)
    p.add_argument('--exclude-decks',type=Path,action='append',default=[])
    p.add_argument('--stop-after-matches',type=int)
    args = p.parse_args()
    if args.matches < (1 if args.training_only else 5) or args.cadence < 2 or not 240 <= args.ticks <= 6000:
        p.error('Need train/validation/heldout matches and bounded cadence/ticks')
    # Require this run's ownership receipt and verify firewall before every run.
    receipt = json.loads(args.ownership.read_text())
    if (receipt['serial'], receipt['probe_port']) != (args.serial, args.port):
        raise ValueError('Owned emulator receipt mismatch')
    running=subprocess.check_output(['ps','-p',str(receipt['pid']),'-o','command='],text=True)
    if 'clasher_reference_api35' not in running or f'-port {args.serial.split("-")[-1]}' not in running:
        raise ValueError('Owned emulator PID no longer matches the launch receipt')
    for firewall in ('iptables', 'ip6tables'):
        subprocess.run([str(ADB), '-s', args.serial, 'shell', firewall, '-C', 'OUTPUT', '-m',
                        'owner', '--uid-owner', str(receipt['app_uid']), '!', '-o', 'lo',
                        '-j', 'REJECT'], check=True, capture_output=True, timeout=20)
    args.output.mkdir(parents=True, exist_ok=args.resume)
    (args.output/'frames').mkdir(exist_ok=args.resume)
    (args.output/'evaluation_only').mkdir(exist_ok=args.resume)
    if (args.output/'complete.json').exists():
        raise ValueError('Dataset is already complete')
    loader = CardDataLoader()
    names = {loader.get_card(n)._raw_entry['id']: n for n in PUBLIC_REFERENCE_CARDS}
    ids = {v:k for k,v in names.items()}
    geo = Geometry(REPORT/'calibration.json')
    call = lambda command: request(args.port, command)
    configs = []
    seen_decks = set()
    if args.v1:
        seen_decks.update(tuple(sorted(d)) for e in json.loads((REPORT/'dataset/manifest.json').read_text())['matches']
                          for d in e['decks'])
        for path in args.exclude_decks:
            seen_decks.update(tuple(sorted(d)) for e in json.loads(path.read_text())['matches'] for d in e['decks'])
    for m in range(args.matches):
        seed = args.seed_base+m
        rng = random.Random(seed)
        c = json.loads(BASE.read_text())['config']
        c['rndSeed'] = seed
        c['endTick'] = 7200
        decks = []
        for owner in (0,1):
            while True:
                pool = (sorted(set(PUBLIC_REFERENCE_CARDS)-set(configs[0]['decks'][owner]))
                        if m == 1 else list(PUBLIC_REFERENCE_CARDS))
                deck = rng.sample(pool, 8)
                key = tuple(sorted(deck))
                if key not in seen_decks:
                    seen_decks.add(key)
                    break
            decks.append(deck)
            c['battle'][f'deck{owner}']['sp'] = [{'d':ids[n]} for n in deck]
        split = 'train' if args.training_only or m < args.matches-3 else 'validation' if m == args.matches-3 else 'heldout'
        configs.append(dict(episode_id=f'l1-{seed}', seed=seed, split=split, decks=decks, config=c))
    manifest=dict(
        schema='clasher.l1.dataset.v1', matches=configs, cadence_ticks=args.cadence,
        tick_seconds=.05, target_ticks=args.ticks, jpeg_size=[540,1140],
        source_attestation=receipt['attestation_sha256'], dataset_limit_bytes=3*1024**3,
        boxes='weak class extents at calibrated ground anchors; not exact sprite boxes',
        effect_policy='unverified hp-less objects excluded; spells remain a detection gap',
        frame_inputs='sanitized JPEG only; labels and evaluation_only never inference inputs',
    )
    if args.v1:
        manifest.update(schema='clasher.l1.dataset.v2', cadence_ticks=[2,4,6,8],
                        frames_per_match=args.frames_per_match,
                        style_policy=['balanced','bridge','backline','spread'],
                        visibility_policy='per-label uncertain; overlap and retractable-body reasons',
                        pairing_scope='paused equality plus fresh decode; no compositor fence')
    if args.resume:
        if json.loads((args.output/'manifest.json').read_text()) != manifest:
            raise ValueError('Resume configuration differs from frozen manifest')
    else:
        (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    def previous(name):
        path=args.output/name
        return [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []
    completed={r['episode_id'] for r in previous('episodes.jsonl')}
    prior_rows=previous('labels.jsonl')
    prior_events=previous('evaluation_only/events.jsonl')
    total_bytes = sum(p.stat().st_size for p in (args.output/'frames').glob('*.jpg'))
    stream = None
    if args.v1:
        if not args.grpc_proto or not args.grpc_discovery:
            p.error('v1 requires the gRPC stream; H.264 failed freshness smoke')
        from clasher.vision.l1_stream import GrpcScreenStream
        stream = GrpcScreenStream(receipt['grpc_port'],args.grpc_proto,args.grpc_discovery)
        from clasher.vision.l1_perception import HudReader
        pairing_hud = HudReader(REPORT/'model/hud.npz')
        import atexit
        atexit.register(stream.close)
    selected=configs[:args.stop_after_matches] if args.stop_after_matches else configs
    for entry in selected:
        if entry['episode_id'] in completed:
            continue
        rng = random.Random(entry['seed'])
        partial=[r for r in prior_rows if r['episode_id']==entry['episode_id']]
        first_tick = 200 + 20*(entry['seed']%2)
        if partial:
            if args.v1:
                raise ValueError('v1 resume requires a completed-episode boundary')
            s = call('status')
            start_tick=int(partial[-1]['frame_id'])+args.cadence
            if not s['paused'] or s['mode']!='native-render' or s['tick']!=start_tick:
                raise ValueError('Partial resume requires the untouched paused next frame')
            # A partial capture retry does not replay or duplicate actions.
            # Future policy draws use an explicitly recorded fresh sub-seed.
            rng.seed(entry['seed']+9999999)
            append(args.output/'resume.jsonl',dict(episode_id=entry['episode_id'],tick=start_tick,
                future_policy_seed=entry['seed']+9999999,reason='retry rejected visible-clock frame'))
        else:
            result = call('configure-native '+json.dumps(entry['config'], separators=(',',':')))
            deadline = time.monotonic()+30
            while time.monotonic() < deadline:
                s = call('status')
                if s['nativeRenderLoaded'] == result['sequence'] and s['nativeRenderReady']:
                    break
                time.sleep(.1)
            else:
                raise TimeoutError('Native scene failed to load')
            paused = call('pause')
            call('speed 1')
            call('render on')
            if paused['tick'] >= first_tick:
                raise ValueError('Startup missed first sampling boundary')
            call(f"advance-native {first_tick-paused['tick']}")
            start_tick=first_tick
            if args.v1:
                for warmup in range(30):
                    jpg,_,_=capture(call,args.serial,start_tick,stream)
                    image=cv2.imdecode(np.frombuffer(jpg,np.uint8),cv2.IMREAD_COLOR)
                    if clock_digits(image) and pairing_hud.read(image)['clock']==visible_clock(start_tick):
                        break
                    call('advance-native 20');start_tick+=20
                else:
                    raise RuntimeError('No visible HUD after bounded 1x warmup; no labels saved')
        call('speed 4')
        episode = entry['episode_id']
        frames = len(partial)
        existing_events=[e for e in prior_events if e['episode_id']==episode]
        events_total = len(existing_events)
        uses = {n:0 for n in PUBLIC_REFERENCE_CARDS}
        for e in existing_events:uses[e['card']]+=1
        target=start_tick
        while target <= args.ticks:
            if shutil.disk_usage(args.output).free < 6*1024**3 or total_bytes > 2.9*1024**3:
                raise RuntimeError('Disk guard reached; stopping without deleting other work')
            for attempt in range(8):
                jpg, obs, pairing = capture(call, args.serial, target, stream)
                decoded=cv2.imdecode(np.frombuffer(jpg,np.uint8),cv2.IMREAD_COLOR)
                clock_ok=bool(clock_digits(decoded))
                if args.v1:
                    seen_clock=pairing_hud.read(decoded)['clock']
                    pairing['visible_clock_verified']=seen_clock==visible_clock(target)
                    pairing['visible_clock_seconds']=seen_clock
                    clock_ok=clock_ok and pairing['visible_clock_verified']
                if clock_ok:
                    break
                # The stock intro animates on presentation time even while
                # simulation is paused. Never play or label through it.
                time.sleep(1)
            else:
                raise RuntimeError('Public clock hidden by presentation; refusing invisible labels')
            filename = f'{episode}-{target:05}.jpg'
            (args.output/'frames'/filename).write_bytes(jpg)
            total_bytes += len(jpg)
            targets, excluded = public_targets(obs, names, geo)
            if args.v1:
                for i,entity in enumerate(targets['entities']):
                    box=entity['pixel_box']
                    overlaps=any(i!=j and min(box[2],other['pixel_box'][2])>max(box[0],other['pixel_box'][0])
                                 and min(box[3],other['pixel_box'][3])>max(box[1],other['pixel_box'][1])
                                 for j,other in enumerate(targets['entities']))
                    entity['visibility']='uncertain'
                    entity['visibility_reasons']=['no_sprite_visibility_or_compositor_fence']
                    if overlaps: entity['visibility_reasons'].append('projected_box_overlap')
                    if entity['card']=='Tesla': entity['visibility_reasons'].append('may_be_retracted')
            row = dict(episode_id=episode, frame_id=str(target), timestamp_ms=target*50,
                       split=entry['split'], image='frames/'+filename, targets=targets)
            append(args.output/'labels.jsonl', row)
            append(args.output/'pairing.jsonl', dict(episode_id=episode, frame_id=str(target),
                                                   jpeg_sha256=hashlib.sha256(jpg).hexdigest(), **pairing))
            # Private values are evaluation truth only, never detector/HUD labels.
            opp = next(p for p in obs['players'] if p['owner']==0)
            append(args.output/'evaluation_only/truth.jsonl', dict(
                episode_id=episode, frame_id=str(target), tick=target,
                opponent_elixir=opp['elixir'],
                own_elixir_exact=next(p['elixir'] for p in obs['players'] if p['owner']==1),
                opponent_hand=[names[c['cardId']] for c in opp['hand']],
                opponent_cycle=[names[c['cardId']] for c in opp['cycle']],
                excluded_unverified_effects=excluded))
            frames += 1
            cadence=rng.choice([2,4,6,8]) if args.v1 else args.cadence
            if obs['ended'] or target+cadence > args.ticks or (args.v1 and frames>=args.frames_per_match):
                break
            scheduled = []
            # One public scripted action per owner every two sampling intervals.
            if (args.v1 and target//40 != (target-cadence)//40) or (not args.v1 and (target-first_tick) % (args.cadence*2) == 0):
                for player in obs['players']:
                    choices = [c for c in player['hand'] if c['cost'] <= player['elixir']]
                    if not choices:
                        continue
                    choices.sort(key=lambda c: (
                        names[c['cardId']] != args.prioritize_card if args.prioritize_card else False,
                        uses[names[c['cardId']]]+rng.random()*2))
                    card = choices[0]
                    owner, name = player['owner'], names[card['cardId']]
                    x = rng.choice([3500, 5500, 12500, 14500])
                    if name in ('Fireball', 'Zap'):
                        x, y = rng.choice([3500,14500]), 25500 if owner==0 else 6500
                    else:
                        y = rng.choice([9500,11500,13500]) if owner==0 else rng.choice([18500,20500,22500])
                        if args.v1:
                            style=entry['seed']%4
                            if style==1:y=14500 if owner==0 else 17500
                            elif style==2:y=4500 if owner==0 else 27500
                            elif style==3:x=rng.randrange(2000,16001,1000)
                    rec = call(f"replay-schedule-card {owner} {card['cardId']} {x} {y} {target+1}")
                    scheduled.append((player,card,x,y,rec))
            if scheduled:
                call('advance-native 1')
                after = call('observe')
                for before, card, x, y, rec in scheduled:
                    after_player = next(p for p in after['players'] if p['owner']==before['owner'])
                    remaining = {c['handIndex']:c['cardId'] for c in after_player['hand']}
                    accepted = (remaining.get(card['handIndex']) != card['cardId'] and
                                after_player['elixir'] < before['elixir'] - card['cost'] + .1)
                    status = call(f"replay-schedule-status {rec['sequence']}")
                    if accepted:
                        name = names[card['cardId']]
                        uses[name] += 1
                        events_total += 1
                        append(args.output/'evaluation_only/events.jsonl', dict(
                            episode_id=episode, tick=target+1, player_id=before['owner'], card=name,
                            x_tiles=x/1000,y_tiles=y/1000, acceptance='hand_change_and_elixir_spend',
                            schedule_state=status['state']))
                advance = call(f'advance-native {cadence-1}')
            else:
                advance = call(f'advance-native {cadence}')
            if advance['ended']:
                break
            target+=cadence
        append(args.output/'episodes.jsonl', dict(episode_id=episode, split=entry['split'],
                                                frames=frames, events=events_total, uses=uses,
                                                final_tick=call('observe')['tick']))
        progress(f'Collected {episode} {entry["split"]}: {frames} paired JPEGs, {events_total} accepted plays; dataset JPEG bytes {total_bytes}.')
    (args.output/'complete.json').write_text(json.dumps(dict(status='complete', jpeg_bytes=total_bytes,
                                                           matches=len(selected)), indent=2)+'\n')
    if stream is not None:
        stream.close()


if __name__ == '__main__':
    main()

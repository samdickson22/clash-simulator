"""Launch replay diagnostics or connect to an already running owned renderer."""
import argparse
import json
from pathlib import Path
from .capture import admit_replay
from .loading import ROOT, COUNCIL, V4
from .runtime import run


def public_metadata(prior):
    data = json.loads((ROOT/'gamedata.json').read_text())['items']['spells']
    costs = {row['name']: float(row['manaCost']) for row in data if row.get('manaCost', 0) > 0}
    for action, body in {'Archers': 'Archer', 'IceGolem': 'IceGolemite', 'IceSpirit': 'IceSpirits'}.items():
        costs[action] = costs[body]
    cards = {c for deck in json.loads(Path(prior).read_text())['decks'] for c in deck['cards']}
    if cards-costs.keys():
        raise ValueError('Prior contains unknown public cards')
    bodies = {}
    aliases = {'Archers': 'Archer', 'IceGolem': 'IceGolemite', 'IceSpirit': 'IceSpirits'}
    for row in data:
        if row['name'] not in costs:
            continue
        # Static metadata only. A body may belong to several playable cards.
        source = row.get('summonCharacterData') or {}
        name = source.get('name') if isinstance(source, dict) else None
        for identity in {name, aliases.get(row['name'], row['name'])}-{None}:
            bodies.setdefault(identity, set()).add(row['name'])
    mapping = {name: tuple((card, 1/len(cs)) for card in sorted(cs)) for name, cs in bodies.items()}
    return costs, mapping


def main():
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--replay', type=Path)
    source.add_argument('--grpc-port', type=int)
    p.add_argument('--split', type=Path)
    p.add_argument('--episode', default='live-v4')
    p.add_argument('--own-deck', help='Eight comma-separated public own card names')
    p.add_argument('--proto-dir', type=Path)
    p.add_argument('--discovery', type=Path)
    p.add_argument('--prior', type=Path, required=True, help='Frozen train-only deck catalog')
    p.add_argument('--perception', choices=('v3', 'v4'), default='v3')
    p.add_argument('--body', type=Path)
    p.add_argument('--hud', type=Path)
    p.add_argument('--events', type=Path)
    p.add_argument('--selection', type=Path)
    p.add_argument('--checkpoint', type=Path)
    p.add_argument('--calibration', type=Path)
    p.add_argument('--device', choices=('cpu', 'mps'), default='cpu')
    p.add_argument('--geometry', type=Path, default=COUNCIL/'live-loop/l1/calibration.json')
    p.add_argument('--imgsz', type=int, default=416)
    p.add_argument('--frames', type=int, default=0)
    p.add_argument('--backend', default='offline-renderer-grpc', help='Timing profile for P3 and P4')
    p.add_argument('--backend-timing', type=Path, default=V4/'actuation/backend-timing.json')
    p.add_argument('--delay-hook', help='Experimental module:function override of the adopted S6 scorer')
    p.add_argument('--mock-input', action='store_true')
    p.add_argument('--qualification', type=Path, help='Post-T2/T7/S6 qualification receipt required for real taps')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--fault-stage', choices=('P1', 'P2', 'P3'))
    p.add_argument('--fault-seconds', type=float, default=.65)
    a = p.parse_args()
    if a.replay:
        if a.split is None:
            p.error('--replay requires --split')
        admitted = admit_replay(a.replay, a.split)
        own_deck = admitted.pop('own_deck')
        config_source = dict(admitted, kind='replay')
        actuator = {'kind': 'mock', 'tap_seconds': .02}
    else:
        if not a.own_deck or not a.proto_dir or not a.discovery:
            p.error('gRPC requires --own-deck, --proto-dir and --discovery')
        own_deck = a.own_deck.split(',')
        config_source = dict(kind='grpc', port=a.grpc_port, proto_dir=str(a.proto_dir),
                             discovery=str(a.discovery), episode=a.episode, render_backend='host')
        actuator = dict(config_source, kind='mock' if a.mock_input else 'grpc')
        if not a.mock_input:
            if not a.qualification:
                p.error('Real input requires the completed --qualification receipt')
            if a.backend != 'offline-renderer-grpc' or a.delay_hook:
                p.error('Real gRPC input requires its gRPC timing profile and the adopted S6 scorer')
            qualification = json.loads(a.qualification.read_text())
            if not all(qualification.get(key) is True for key in ('verifier_pass', 'perception_pass', 'delay_planner_pass')):
                p.error('Real input qualification gates are incomplete')
    if a.perception == 'v3' and (not a.body or not a.hud):
        p.error('v3 fallback requires --body and --hud')
    if a.perception == 'v4' and (not a.checkpoint or not a.calibration):
        p.error('v4 requires --checkpoint and --calibration')
    costs, bodies = public_metadata(a.prior)
    config = dict(source=config_source, frames=a.frames, backend=a.backend, timing_path=str(a.backend_timing),
                  perception=dict(kind=a.perception, device=a.device, imgsz=a.imgsz,
                      **{k: str(getattr(a, k)) if getattr(a, k) else None for k in
                         ('body', 'hud', 'events', 'selection', 'geometry', 'checkpoint', 'calibration')}),
                  belief=dict(own_deck=own_deck, prior=str(a.prior), costs=costs, body_cards=bodies,
                              recall=.90, precision=.90, resource_calibration=.11040000000000028),
                  planner=dict(kind='rust', delay_aware=True, delay_hook=a.delay_hook), actuator=actuator)
    if a.fault_stage:
        config['fault'] = dict(stage=a.fault_stage, seconds=a.fault_seconds, after=20)
    result = run(config, a.output)
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result['failures'] else 0)


if __name__ == '__main__':
    main()

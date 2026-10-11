"""PREREG-K4S synthetic block tree for reducer/verifier tests only (marked SYNTHETIC; never real games).

  python synthetic.py --out DIR [--seed N] [--lose K4S-160=0.1 ...] [--replace primary-0005 ...]
Writes DIR/SYNTHETIC, DIR/<id>/complete.json (+games/*.json) for every logical block, and DIR/ledger.json.
Each listed --replace block is written as lost (exit only, no complete.json) and its replacement completes.
"""
import argparse, hashlib, json, random
from pathlib import Path
from schedule import blocks, replacement
from common import read, plan
PLAN = plan()

BASE_LOSS = {'K4-200': .20, 'K4S-200': .21, 'K4-180': .23, 'K4S-180': .21, 'K4-160': .28, 'K4S-160': .20,
             'K4S-140': .22, 'K4S-120': .26, 'K4-140': .47, 'K4-120': .89}
DRAW = .02


def game(desc, arm, rng, p, decks):
    u = rng.random()
    seat = desc['seat']
    winner = None if u < DRAW else (1-seat if u < DRAW+p[arm] else seat)
    loss = int(winner is not None and winner != seat)
    stat = dict(hit=rng.random() < .3, fallback=False, student_default=arm.startswith('K4S') and rng.random() < .1, coarse_complete=True,
                wall_overrun=False, action=2304 if rng.random() < .7 else 5, unpruned_candidate_count=10, wall_seconds=.1, positive_overrun_ms=0., delayed_ticks=0,
                sd1_p_play=.4 if arm.startswith('K4S') else None)
    own, opp = decks
    spec = PLAN['arms'][arm]
    meta = dict(terminal=True, winner=winner, seat=seat, seed=desc['seed'], cell=desc['cell'], own_deck=own, opponent_deck=opp,
                population=desc['population'], seed_index=desc['index'], arm=arm, study='PREREG-K4S confirmatory; SEALED',
                block_id=desc['id'], rotation=desc['rotation'], replacement_k=desc.get('replacement_k'),
                speed_cell=spec['speed_cell'], budget_ms=spec['budget_ms'], deadline_seconds=spec['deadline_seconds'], reserve_ms=8,
                inference_scale=spec['inference_scale'], scale_mode=spec['scale_mode'], default_source=spec['default_source'],
                s_default_rule=spec['s_default_rule'], kernel=spec['kernel'], threads=spec['threads'], coarse_horizon=spec['coarse_horizon'],
                opponent=spec['opponent'], c_star=PLAN['c_star'], freeze_manifest_sha256='0'*64, runtime_pin_sha256='1'*64,
                sd1_manifest_sha256='2'*64, sd1_checkpoint_sha256=PLAN['student']['checkpoint_sha256'],
                sd1_calibration_sha256=PLAN['student']['calibration_sha256'], sd1_threshold=PLAN['student']['threshold'],
                opponent_checkpoint_sha256=PLAN['policy']['checkpoint_sha256'], native_sha256=PLAN['source_reference']['native_sha256'])
    return dict(cohort=arm, loss=float(loss), metadata=meta, search_ab=dict(deadline_stats=[stat, dict(stat, hit=False)], gc_maintenance=[dict(seconds=.001, generation=0, during_decision=False)]))


def write_block(root, desc, rng, p, host='127x01'):
    d = root/desc['id']; (d/'games').mkdir(parents=True)
    decks_file = read(Path(__file__).parent/'guard-decks.json')
    if desc['population'] == 'primary':
        decks = (decks_file['primary'][desc['own_index']], decks_file['primary'][desc['opponent_index']])
    else:
        decks = (decks_file['l2'][desc['own_index']], decks_file['guard'][desc['opponent_index']]['cards'])
    shas = {}
    for arm in desc['order']:
        name = f"{desc['id']}-d27-{arm}.json"; raw = json.dumps(game(desc, arm, rng, p, decks)).encode()
        (d/'games'/name).write_bytes(raw); shas[name] = hashlib.sha256(raw).hexdigest()
    (d/'complete.json').write_text(json.dumps(dict(descriptor=desc, host=host, slot_cores=[0, 1, 2, 3, 4], games=shas, interference=dict(interfered=False))))


def build(out, seed=1, lose=None, replace=()):
    out = Path(out); out.mkdir(parents=True); (out/'SYNTHETIC').write_text('synthetic test tree; not real games\n')
    p = dict(BASE_LOSS, **(lose or {})); rng = random.Random(seed); ledger = []
    for desc in blocks():
        if desc['id'] in replace:
            r = replacement(desc, ledger)
            ledger.append(dict(utc='synthetic', lost=desc, replacement=r, reason='synthetic', evidence_sha256=None))
            write_block(out, r, rng, p)
        else:
            write_block(out, desc, rng, p)
    (out/'ledger.json').write_text(json.dumps(dict(sealed=True, events=ledger)))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--lose', nargs='*', default=[]); ap.add_argument('--replace', nargs='*', default=[]); a = ap.parse_args()
    build(a.out, a.seed, {k: float(v) for k, v in (x.split('=') for x in a.lose)}, set(a.replace))

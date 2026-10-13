"""FSC (U3/U4, exploration, NEVER ADOPTABLE): write the configs and worklists from the X4S2 pins.

Every arm spec is copied by value from X4S2 plan.json / plan-ext.json at 1501be97f and asserted equal.
Only the descriptive fields, the arm set and the seed ranges change. Population X only; no G worklist.
Usage (on 05, stdlib): make_config.py --base BASE [--out DIR]
"""
import argparse, copy, hashlib, json
from pathlib import Path

PIN = '1501be97f'
HERE = Path(__file__).resolve().parent
J04 = '/mpac/sdicks02/jobs/clasher/fsc-04-20261013'
# Index segments of the one fresh X bank (dispatch order per host; see PLAN.md).
S1 = range(0, 2400)       # 03: K4-200 / K4S-200 (primary)
S2 = range(2400, 3900)    # 04: K4-180 / K4S-180
S3 = range(3900, 5900)    # 03 top-up: K4-200 / K4S-200
S4 = range(5900, 7900)    # 04 top-up: K4-200 / K4S-200
COUNT = 7900
A200, A180 = ['K4-200', 'K4S-200'], ['K4-180', 'K4S-180']


PIN_SHA256 = {'plan.json': '078d5bbce2bc6b402041d772cb5e37738ceb07f61903e71243d0b683c3b9b5b0',
              'plan-ext.json': '31c5cd4a12faf9f5f46f2bf5cee02d89971d0fe9a76ff97c8b48333c3a5b816f'}


def pinned(name):
    raw = (HERE.parent/'x4s2'/name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PIN_SHA256[name], name
    return json.loads(raw)


def dump(path, obj, indent=2):
    path.write_text(json.dumps(obj, indent=indent)+'\n')


def wl(rng, blocks):
    return dict(range=rng, blocks=[dict(pop='X', index=i, arms=arms) for seg, arms in blocks for i in seg])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', type=int, required=True)
    ap.add_argument('--out', type=Path, default=HERE)
    a = ap.parse_args()
    base, ext = pinned('plan.json'), pinned('plan-ext.json')
    assert all(ext['arms'][k] == v for k, v in base['arms'].items())
    cfg = copy.deepcopy(base)
    cfg['purpose'] = ('FSC (U3/U4) exploration, NEVER ADOPTABLE: full-speed cost of always-on S-default '
                      '(K4S-200 minus K4-200) and the 0.9x pair (K4S-180 minus K4-180) on fresh X-population seeds')
    cfg['arms'] = {k: base['arms'][k] for k in A200}
    cfg['seed_ranges'] = {
        'X-reporting': dict(base=a.base, count=COUNT, name='FSC X reporting (fresh)'),
        'smoke': dict(base=a.base+10_000_000, count=8, name='FSC smoke (fresh)'),
        'qualification': dict(base=a.base+20_000_000, count=8, name='FSC STOP test (fresh)')}
    cfg['seed_reservation'] = dict(block_start=a.base, block_stop_exclusive=a.base+100_000_000,
                                   note='FSC fresh block, the next unused 1e8 block on the X4S2 grid chosen by pick_seed_block.py')
    cfg['bootstrap'] = dict(reps=5000, seed=2026101301, unit='paired seed', confidence=0.95)
    cfg['compute'] = dict(hosts={h: dict(physical_cpus='0-59', supervisor_cpu=62, hard_stop='supervisor start + 8 h (code)')
                                 for h in ('127x03', '127x04')},
                          slots='12 disjoint 5-physical-core slots; 10 if a console user is present', nice=19,
                          scheduler='SCHED_OTHER', cuda='disabled', max_threads_per_host=60)
    cfg['phases'] = {'03': dict(arms=A200, indices=f'{S1.start}..{S1.stop-1} then {S3.start}..{S3.stop-1}'),
                     '04': dict(arms=dict(first=A180, then=A200), indices=f'{S2.start}..{S2.stop-1} (180) then {S4.start}..{S4.stop-1} (200)')}
    cfg['ordering'] = dict(blocks='both arms of a seed consecutively on one 5-core slot, rotated by index (X4S2 run.py)',
                           interrupted='a block with a .started marker and no proof is retired; see READOUT.md for the prefix rule')
    cfg['decision_rules'] = dict(primary='see READOUT.md (pre-declared)')
    for k in ('qualification', 'scaling'):
        cfg.pop(k, None)
    cfg['source_reference'] = dict(base['source_reference'], X4S2_harness=PIN)
    cfg['populations'] = base['populations']  # X decks used; G entry kept only because run.py asserts on it
    cfg04 = copy.deepcopy(cfg)
    cfg04['arms'] = dict(cfg['arms'], **{k: ext['arms'][k] for k in A180})
    for c in (cfg, cfg04):
        for k, v in c['arms'].items():
            assert v == (base['arms'].get(k) or ext['arms'][k])
    out = a.out
    dump(out/'plan-fsc.json', cfg)
    dump(out/'plan-fsc-04.json', cfg04)
    # 04 only: X4S2 plan.json (read by run.py for the checkpoints and threshold) with the two checkpoint paths
    # pointed at the 04 job's inputs; nothing else differs.
    p04 = copy.deepcopy(base)
    p04['policy']['checkpoint'] = f'{J04}/inputs/main02.pt'
    p04['student']['checkpoint'] = f'{J04}/inputs/R3a.pt'
    dump(out/'harness/plan-04.json', p04)
    dump(out/'wl-03.json', wl('reporting', [(S1, A200), (S3, A200)]), None)
    dump(out/'wl-04.json', wl('reporting', [(S2, A180), (S4, A200)]), None)
    dump(out/'wl-smoke-03.json', wl('smoke', [(range(8), A200)]), None)
    dump(out/'wl-smoke-04.json', wl('smoke', [(range(4), A180), (range(4, 8), A200)]), None)
    dump(out/'wl-stoptest-03.json', wl('qualification', [(range(8), A200)]), None)
    dump(out/'wl-stoptest-04.json', wl('qualification', [(range(8), A180)]), None)
    print(json.dumps(dict(base=a.base, count=COUNT, out=str(out))))


if __name__ == '__main__':
    main()

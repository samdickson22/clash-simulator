"""Regression self-test for the fc config cut and the native-failure guards of lopp_fast (exploration, ~1 min CPU):

    CLASHER_BOT_RUNTIME=... python -m bot.search.lopp_safety_test [--fixture FIXTURE.json]
    python -m bot.search.lopp_safety_test --extract FAIL.json --out FIXTURE.json   # captured root -> fixture

The fixture is the PERC-emp:LIVE-K4L-R-gs-rw-fc-w200-t4-p4 root (HEADLINE v1 case 2, tick 1410) where misperception
put an ElectroSpirit (a card in neither deck) on the board: the old fc cut (hand + cycle only) dropped its card, and
the pinned native panicked in electro_land (c56.rs:265, config.cards[key].chain). It holds no game tables: entities
are (name, payload key, class, owner, x, y, hp fraction, facing), rebuilt from R.templates as fair_player.root does.
1. With the old cut the pinned native panics on the fixture (the fixture still exercises the bug); with config_need
   (_ConfigJson.dumps and the pool's ConfigCache) no candidate panics and every rollout_e1 value (3 styles) equals
   the full-config root's, bit for bit.
2. Thread path: reduce_fast on the old-cut root (4 threads) fails the decision -> sdefault plays the cutoff default.
3. Pool path: a worker that panics (old-cut root shipped whole) reports it and stays alive; the decision fails ->
   default; the next decision on the same pool equals the serial values.
4. A killed pool worker fails the decision -> default; get_pool replaces the pool; the next decision equals the
   serial values.
--crafted (the LIVE LEAD's crafted-fc-root.json, 127x05:/mpac/sdicks02/jobs/clasher/live-panic-fix/; 2.7 MB with
game tables, not committed): its full-config root rebuilt through ConfigCache and through _ConfigJson must give
its recorded full-config rollout_e1 value (-0.10562149106854207) bit for bit.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import random
import signal
from pathlib import Path
from types import SimpleNamespace

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'c56-electro-missing.json'
DELAY, HORIZON, INTERVAL, ELIXIR_WEIGHT = 27, 160, 10, 1.0
PINNED = '44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2'


def extract(fail_path, out_path):
    """A capture (repro_k4l.py: snapshot, seat, tick, candidates) -> table-free fixture."""
    d = json.loads(Path(fail_path).read_text())
    s = json.loads(d['snapshot'])
    ents = [dict(name=e['stats']['name'], payload_key=e['stats'].get('payload_key', ''), cls=e['class'],
                 owner=e['owner'], x=e['x'], y=e['y'], hp_frac=e['hp'] / e['stats']['max_hp'],
                 facing=e.get('facing', [0, 0])) for e in s['entities']]
    fix = dict(source=f'{Path(fail_path).name}: PERC-emp:LIVE-K4L-R-gs-rw-fc-w200-t4-p4 (HEADLINE), tick '
                      f'{d["tick"]}, pinned native panic c56.rs:265 (ElectroSpirit not in the cut config)',
               tick=d['tick'], seat=d['seat'], candidates=d['candidates'], sudden_death=s['sudden_death'],
               players=[{k: p[k] for k in ('hand', 'cycle', 'elixir', 'last_card', 'last_cost', 'refill')}
                        for p in s['players']], entities=ents)
    Path(out_path).write_text(json.dumps(fix, indent=1) + '\n')
    print('fixture', out_path, len(json.dumps(fix)), 'bytes')


def payload(R, fix):
    """The fixture as an R.root payload dict (config last, as fair_player.root)."""
    by = {}
    for t in R.templates.values():
        by.setdefault((t['stats']['name'], t['stats'].get('payload_key', ''), t['class']), t)
        by.setdefault((t['stats']['name'], t['class']), t)
    ents = []
    for f in fix['entities']:
        e = copy.deepcopy(by.get((f['name'], f['payload_key'], f['cls'])) or by[f['name'], f['cls']])
        e.update(id=len(ents) + 1, owner=f['owner'], x=f['x'], y=f['y'], hp=f['hp_frac'] * e['stats']['max_hp'],
                 alive=True, target=None, deploy=0., stagger=0., facing=f['facing'], age=1000, birth=fix['tick'] - 1,
                 lane=1 if f['x'] < 9 else 2, clock=dict(interval=max(1, e['stats']['interval']),
                                                         load=e['stats']['load'], timeline=0, remaining=0, finish=0),
                 cooldown=0., active=True)
        ents.append(e)
    state = random.Random(1410).getstate()[1]
    return dict(tick=fix['tick'], next_id=len(ents) + 1, players=fix['players'], entities=ents, pending_casts=[],
                sudden_death=fix['sudden_death'], rng=dict(state=list(state[:-1]), index=state[-1]),
                game_over=False, winner=None, config=R.config)


def old_cut(R, obj):
    """The pre-fix fc rule: only the cards in either player's hand or cycle."""
    cards = R.config['cards']
    need = {c for p in obj['players'] for c in p['hand'] + p['cycle'] if c in cards}
    return json.dumps(dict(obj, config=dict(R.config, cards={k: v for k, v in cards.items() if k in need})))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fixture', type=Path, default=FIXTURE)
    ap.add_argument('--extract')
    ap.add_argument('--out')
    ap.add_argument('--model', default='pool')
    ap.add_argument('--crafted', type=Path)
    a = ap.parse_args()
    if a.extract:
        return extract(a.extract, a.out)
    import torch
    torch.set_num_threads(1)
    from bot.players.base import WAIT
    from bot.players.runtime import Runtime, sha256
    from bot.search import lopp, lopp_fast
    from bot.search.lopp_fast import ConfigCache, _ConfigJson, get_pool, reduce_fast, split_snapshot
    from bot.search.oppmodel import STYLES
    rt = Runtime()
    import clasher_core
    import sdefault
    R, native = rt.R, rt.R.native
    pinned = sha256(rt.native_dir / 'clasher_core.abi3.so') == PINNED
    fix = json.loads(a.fixture.read_text())
    seat, cands = fix['seat'], fix['candidates']
    obj = payload(R, fix)
    full = clasher_core.BattleState(json.dumps(obj))
    old = clasher_core.BattleState(old_cut(R, obj))
    shim = _ConfigJson(R.config, False)
    shim.cut = True
    new = clasher_core.BattleState(shim.dumps(obj))
    head, cfg_text, tail = split_snapshot(full.snapshot())
    pool_root = clasher_core.BattleState(ConfigCache(cfg_text).payload(head, tail))
    out = dict(native_pinned=pinned, candidates=len(cands))
    if a.crafted:
        c = json.loads(a.crafted.read_text())
        r = c['rollout_e1_args']
        args = (r['seat'], r['action'], r['style'], r['command_delay'], r['opponent_delay'], r['horizon'],
                r['interval'], r['elixir_weight'], r['budget'])
        h, ctext, t = split_snapshot(c['full_payload'])
        via_pool = native.rollout_e1(clasher_core.BattleState(ConfigCache(ctext).payload(h, t)), *args)
        d = json.loads(c['full_payload'])
        cfg = d.pop('config')
        cshim = _ConfigJson(cfg, False)
        cshim.cut = True
        via_shim = native.rollout_e1(clasher_core.BattleState(cshim.dumps(dict(d, config=cfg))), *args)
        out['crafted'] = dict(expected=c['results']['full'], pool_cut=via_pool, shim_cut=via_shim)
        assert via_pool == via_shim == c['results']['full'], out

    def values(root):
        vals, panics = [], 0
        for style in STYLES:
            for c in cands:
                try:
                    vals.append(native.rollout_e1(root.clone(), seat, c, style, DELAY, DELAY, HORIZON, INTERVAL,
                                                  ELIXIR_WEIGHT, 1e6))
                except BaseException as ex:
                    if lopp.fatal(ex):
                        raise
                    vals.append(None)
                    panics += 1
        return vals, panics

    ref, out['full_panics'] = values(full)
    _, out['old_cut_panics'] = values(old)
    got, out['new_cut_panics'] = values(new)
    pgot, out['pool_cut_panics'] = values(pool_root)
    out['new_cut_cards'] = len(json.loads(shim.dumps(obj))['config']['cards'])
    out['electro_kept'] = 'ElectroSpirit' in json.loads(shim.dumps(obj))['config']['cards']
    out['new_cut_equal_full'] = got == ref
    out['pool_cut_equal_full'] = pgot == ref
    assert out['full_panics'] == out['new_cut_panics'] == out['pool_cut_panics'] == 0, out
    assert out['new_cut_equal_full'] and out['pool_cut_equal_full'], out
    if pinned:
        assert out['old_cut_panics'] > 0, 'fixture no longer exercises the pinned native panic'

    # A fake K4C core: what reduce_fast reads.
    core = SimpleNamespace(command_delay=DELAY, opponent_delay=DELAY, native=native,
                           config=SimpleNamespace(horizon=HORIZON, interval=INTERVAL, elixir_weight=ELIXIR_WEIGHT),
                           info=SimpleNamespace(tick=fix['tick'], packet=SimpleNamespace(
                               observation=SimpleNamespace(global_features=[0.] * 5 + [0.5]))))
    spec = dict(model=a.model, models=[a.model], sample=True, switch=None, interval=5, seed=[7, fix['tick']],
                rowwise=True, bias=0., own=False, offset=0)
    make_opp = lambda j=0: lopp_fast.opponent_from_spec(spec, j)
    default = next(c for c in cands if c < WAIT)

    def decide(root, pool, threads=4):
        """score_candidates of lopp_fast._FastMixin with a cutoff default `default`."""
        core.last = core.deadline_stats = None
        action, info = reduce_fast(core, root, seat, cands, make_opp=make_opp, opp_spec=spec, threads=threads,
                                   pool=pool)
        action = WAIT if action is None else action
        return sdefault.apply_default(core, action, default, cands), info, core.last

    _, _, serial = decide(full, None, threads=1)
    n0 = sum(lopp.FAILURES.values())
    out['thread_panic'] = 'skipped (native is total)'
    if pinned:
        act, info, _ = decide(old, None)
        out['thread_panic'] = dict(action_is_default=act == default, failure=info.get('native_failure'))
        assert act == default and info.get('native_failure') == 'native_thread', out

    pool = get_pool(4, native, a.model, getattr(R, 'meta', None), R.config)
    whole = lopp_fast.LearnedPool(4, native, (a.model,), getattr(R, 'meta', None), None)   # ships roots whole
    try:
        if pinned:
            # every key in one worker chunk on the old-cut root: some rollout reaches electro_land
            whole_root = clasher_core.BattleState(old_cut(R, obj))
            whole.begin(whole_root, seat, dict(delay=DELAY, opp_delay=DELAY, horizon=HORIZON, interval=INTERVAL,
                                               elixir_weight=ELIXIR_WEIGHT, tick0=fix['tick']), spec, None)
            whole.submit(0, 'w', [c for c in cands if c != 2400])
            whole.collect()
            out['pool_panic'] = dict(errors=len(whole.errors), workers_alive=all(p.is_alive() for p in whole.procs))
            assert whole.errors and not whole.broken and all(p.is_alive() for p in whole.procs), out
            act, info, _ = decide(whole_root, whole, threads=1)
            out['pool_panic_decision'] = dict(action_is_default=act == default, failure=info.get('native_failure'))
            assert act == default and info.get('native_failure') in ('native_thread', 'native_pool'), out
        act, info, last = decide(full, whole)
        out['pool_after_panic_equal_serial'] = last == serial and info.get('native_failure') is None
        assert out['pool_after_panic_equal_serial'], out

        act, info, last = decide(full, pool)
        assert last == serial, 'healthy pool != serial'
        os.kill(pool.procs[1].pid, signal.SIGKILL)
        pool.procs[1].join(5)
        act, info, _ = decide(full, pool)
        out['killed_worker'] = dict(action_is_default=act == default, failure=info.get('native_failure'))
        assert act == default and info.get('native_failure') == 'pool_dead', out
        fresh = get_pool(4, native, a.model, getattr(R, 'meta', None), R.config)
        act, info, last = decide(full, fresh)
        out['recreated'] = dict(new_pool=fresh is not pool, equal_serial=last == serial,
                                failure=info.get('native_failure'))
        assert fresh is not pool and last == serial and info.get('native_failure') is None, out
    finally:
        whole.close()
        get_pool(4, native, a.model, getattr(R, 'meta', None), R.config).close()
    out['failures'] = dict(lopp.FAILURES)
    out['failures_counted'] = sum(lopp.FAILURES.values()) - n0
    out['ok'] = True
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()

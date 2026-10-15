"""577-fixture native gate, one native per process (the native is whatever `clasher_core` resolves to on PYTHONPATH).

    PYTHONPATH=<native dir>:<engine-rs src>:<r1>/src:<bot repo> python parity_fixtures.py --out OUT.jsonl --workers N

Per train+val fixture (bot.fidelity.rs_parity's set):
- rs: bot.fidelity.rs_parity.run_one unchanged (Python<->Rust lockstep digest gate; first mismatch);
- rust_only: the same imported Rust start state and recorded plays applied to Rust alone, stepped to the
  recording's end/game over; sha256 chain over every tick's digest(), the apply_action results, and the full
  snapshot() every 100 ticks + at the end. Equal chains across two natives = bit-identical full trajectories.
"""
import argparse
import hashlib
import json
from multiprocessing import Pool


def rust_only(ep):
    import clasher_core
    from differential import config, snapshot
    from bot.fidelity import rs_parity as rp
    from bot.fidelity.fixture import load_fixture, load_split
    fix = load_fixture(rp.D / "t1-trainval" / ep, load_split(rp.D / "t1-split.json"))
    try:
        b = rp._py_battle(fix)
        cards = tuple(sorted({rp._name(rp.ID2N[i]) for s in (0, 1) for i in fix.initial_order[s]}))
        if cards not in rp._CFG:
            rp._CFG[cards] = config(cards)
        r = clasher_core.BattleState(snapshot(b, rp._CFG[cards]))
    except Exception as ex:
        return dict(error=repr(ex)[:300])
    plays = sorted((p for p in fix.plays if p.kind != "champion ability"), key=lambda p: (p.exec_tick, p.side, p.slot))
    h = hashlib.sha256(r.snapshot().encode())
    pi, t, actions = 0, fix.start_tick, []
    while t < fix.end_tick:
        while pi < len(plays) and plays[pi].exec_tick - 1 <= t:
            p = plays[pi]
            try:
                ok = bool(r.apply_action(p.side, rp._name(p.card), p.tile[0], p.tile[1]))
            except Exception as ex:
                ok = 'err:' + type(ex).__name__
            actions.append(ok)
            h.update(repr(ok).encode())
            pi += 1
        r.step(1)
        t += 1
        h.update(str(r.digest()).encode())
        if (t - fix.start_tick) % 100 == 0:
            h.update(r.snapshot().encode())
    final = r.snapshot()
    h.update(final.encode())
    return dict(ticks=t - fix.start_tick, chain=h.hexdigest(), final=hashlib.sha256(final.encode()).hexdigest(),
                accepted=sum(a is True for a in actions), plays=len(actions))


def one(ep):
    from bot.fidelity import rs_parity as rp
    res = dict(episode=ep, rs=rp.run_one(ep))
    res['rust_only'] = rust_only(ep)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    import clasher_core
    from bot.fidelity import rs_parity as rp
    from bot.fidelity.fixture import load_split
    sp = load_split(rp.D / "t1-split.json")
    eps = sorted(e for e in sp if sp[e] in ('train', 'validation') and (rp.D / "t1-trainval" / e).exists())
    if a.limit:
        eps = eps[:a.limit]
    print(json.dumps(dict(native=clasher_core.__file__, fixtures=len(eps))), flush=True)
    with Pool(a.workers) as pool, open(a.out, 'w') as fh:
        for r in pool.imap(one, eps):
            fh.write(json.dumps(r, sort_keys=True) + '\n')
            fh.flush()


if __name__ == '__main__':
    main()

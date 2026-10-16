"""Root-level card-scope parity (adapted from reports/bot/learned-opponent/native-total-tools/parity_roots.py).

    CLASHER_BOT_RUNTIME=<root> CLASHER_BOT_RUNTIME_PINS=<pins> python parity_scope_roots.py --roots DIR --out OUT.jsonl

For a fixed sample of recorded real search roots (C56 games, record_roots.py), the root is rebuilt with THIS
runtime's R.config (scope c56 or full) in two variants: `full` = head + json.dumps(R.config) + tail (what
Resources.root ships) and `cut` = lopp_fast.ConfigCache(json.dumps(R.config)).payload(head, tail) (what the fc
pool workers parse). Then, with this runtime's R.native (NativeScripts from R.meta), every value is written exactly:
rollout_e1 (WAIT, timed WAIT, up to 4 legal plays x 3 styles, frozen no-deadline budget), evaluate, evaluation_parts,
public_view / public_mask of both seats, digest, select_action x 3 styles, apply_discrete + step 40, step 1/49/150.
Snapshots are hashed WITHOUT their config (head + tail; split_snapshot), since the config text is what the scope
changes; `config_sha` records it separately. Two scopes agree iff the files match apart from header and config_sha.
"""
import argparse
import gzip
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
STYLES = ('balanced', 'pressure', 'defense')


def sha(s):
    return hashlib.sha256(s.encode() if isinstance(s, str) else bytes(s)).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--roots', required=True)
    ap.add_argument('--sample', type=int, default=300)
    ap.add_argument('--out', required=True)
    ap.add_argument('--shard', default='0/1', help='i/n: this process takes sample[i::n]')
    a = ap.parse_args()
    si, sn = map(int, a.shard.split('/'))
    from bot.players.runtime import Runtime
    rt = Runtime()
    import clasher_core
    from bot.live.native_parity import rollout_args
    from bot.search.lopp_fast import ConfigCache, split_snapshot
    R, args = rt.R, rollout_args(rt.R)
    native = R.native

    def body(snap):
        head, cfg, tail = split_snapshot(snap)
        return sha(head + tail)

    text = json.dumps(R.config)
    cache = ConfigCache(text)
    d = Path(a.roots)
    rows = []
    for p in sorted(d.glob('roots-*.jsonl.gz')):
        with gzip.open(p, 'rt') as fh:
            rows += [json.loads(line) for line in fh]
    rng = random.Random(20261015)
    sample = sorted(rng.sample(range(len(rows)), min(a.sample, len(rows))))
    with open(a.out, 'w') as out:
        out.write(json.dumps(dict(native=clasher_core.__file__, native_sha256=sha(Path(clasher_core.__file__).read_bytes()),
                                  scope=getattr(R, 'card_scope', 'c56'), cards=len(R.config['cards']),
                                  config_sha=sha(text), recorded_config=sorted({r['config'] for r in rows}),
                                  roots_total=len(rows), sampled=len(sample), args=args)) + '\n')
        for k in sample[si::sn]:
            r = rows[k]
            seat = r['seat']
            for variant, payload in (('full', r['head'] + text + r['tail']), ('cut', cache.payload(r['head'], r['tail']))):
                root = clasher_core.BattleState(payload)
                rec = dict(k=k, index=r['index'], tick=r['tick'], seat=seat, variant=variant, digest=str(root.digest()))
                mask = list(native.public_mask(root, seat))
                legal = [i for i in range(2304) if mask[i]]
                prng = random.Random(k)
                plays = sorted(prng.sample(legal, min(4, len(legal))))
                actions = [2304, 2401] + plays
                rec['actions'] = actions
                rec['rollout_e1'] = [float(native.rollout_e1(root, seat, act, s, args['command_delay'], args['opponent_delay'],
                                                             args['horizon'], args['interval'], args['elixir_weight'], 1e6)).hex()
                                     for act in actions for s in STYLES]
                rec['evaluate'] = float(native.evaluate(root, seat, args['elixir_weight'])).hex()
                rec['parts'] = [float(x).hex() for x in native.evaluation_parts(root)]
                rec['view'] = [sha(native.public_view(root, s)) for s in (0, 1)]
                rec['mask'] = [sha(json.dumps([bool(x) for x in native.public_mask(root, s)])) for s in (0, 1)]
                sel = []
                for s in STYLES:
                    c = root.clone()
                    sel.append([int(native.select_action(c, seat, s)), str(c.digest())])
                rec['select'] = sel
                if plays:
                    c = root.clone()
                    ok = native.apply_discrete(c, seat, plays[0])
                    c.step(40)
                    rec['apply'] = [repr(ok), str(c.digest()), body(c.snapshot())]
                c = root.clone()
                steps = []
                for n in (1, 49, 150):
                    c.step(n)
                    steps.append([str(c.digest()), body(c.snapshot())])
                rec['step'] = steps
                rec['root_body'] = body(root.snapshot())
                rec['config_sha'] = sha(split_snapshot(root.snapshot())[1])
                out.write(json.dumps(rec, sort_keys=True) + '\n')
            out.flush()


if __name__ == '__main__':
    main()

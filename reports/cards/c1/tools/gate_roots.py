"""Root-level native parity: one native per process (selected by CLASHER_DELAY_NATIVE_DIR via bot Runtime).

    CLASHER_DELAY_NATIVE_DIR=<dir> python parity_roots.py --roots DIR --sample 300 --out OUT.jsonl

For a fixed sample of recorded real search roots (record_roots.py), each in two variants: `full` (the recorded
snapshot = R.root's config) and `cut` (bot.search.lopp_fast.ConfigCache: hand+cycle cards only, what the pool
workers build). Per variant, every value is written exactly (float.hex / sha256 of strings):
- rollout_e1 for WAIT 2304, timed WAIT 2401 and up to 4 legal plays (fixed per root) x 3 styles, frozen
  no-deadline budget (native_parity.rollout_args);
- evaluate(seat), evaluation_parts, public_view/public_mask of both seats, digest;
- select_action(clone, seat, style) for 3 styles;
- apply_discrete(clone, seat, first legal play) then step 40, and step(1), step(50), step(200) from the root:
  digest + sha256(snapshot()).
Two natives agree iff the OUT files are byte-identical apart from the header line.
"""
import argparse
import gzip
import hashlib
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, os.environ['C1_GATE_BOT_ROOT'])
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
    rt = Runtime(verify=False)
    import clasher_core
    from bot.live.native_parity import rollout_args
    from bot.search.lopp_fast import ConfigCache
    R, args = rt.R, rollout_args(rt.R)
    native = R.native
    d = Path(a.roots)
    rows = []
    for p in sorted(d.glob('roots-*.jsonl.gz')):
        with gzip.open(p, 'rt') as fh:
            rows += [json.loads(line) for line in fh]
    rng = random.Random(20261015)
    sample = sorted(rng.sample(range(len(rows)), min(a.sample, len(rows))))
    configs = {}
    with open(a.out, 'w') as out:
        out.write(json.dumps(dict(native=clasher_core.__file__, native_sha256=sha(Path(clasher_core.__file__).read_bytes()),
                                  roots_total=len(rows), sampled=len(sample), args=args, runtime_root=str(rt.root),
                                  runtime_pins=os.environ['CLASHER_BOT_RUNTIME_PINS'])) + '\n')
        for k in sample[si::sn]:
            r = rows[k]
            if r['config'] not in configs:
                text = (d / f"config-{r['config'][:16]}.json").read_text()
                assert sha(text) == r['config']
                configs[r['config']] = (text, ConfigCache(text))
            text, cache = configs[r['config']]
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
                rec['legal_actions'] = legal
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
                    rec['apply'] = [repr(ok), str(c.digest()), sha(c.snapshot())]
                c = root.clone()
                steps = []
                for n in (1, 49, 150):
                    c.step(n)
                    steps.append([str(c.digest()), sha(c.snapshot())])
                rec['step'] = steps
                rec['root_snapshot'] = sha(root.snapshot())
                out.write(json.dumps(rec, sort_keys=True) + '\n')
            out.flush()


if __name__ == '__main__':
    main()

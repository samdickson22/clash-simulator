"""Regression roots from the K4L/LIVE panic (bot-k4l-fix): one native per process (CLASHER_DELAY_NATIVE_DIR).

    CLASHER_DELAY_NATIVE_DIR=<dir> python regress.py --dir REGRESS_DIR --out OUT.json

- crafted-fc-root.json: rollout_e1(rollout_e1_args) on fc_payload and on full_payload (value as repr + float.hex);
- fail-*.json: the captured cut-config snapshot; rollout_e1 for every recorded candidate x 3 styles with the
  crafted file's args, step(400) on a clone, public_view/public_mask/evaluate/select_action for both seats.
Every call is caught as BaseException (PanicException is not an Exception).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, '/mpac/sdicks02/repos/clasher-bot')
STYLES = ('balanced', 'pressure', 'defense')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from bot.players.runtime import Runtime
    rt = Runtime(verify=False)
    import clasher_core
    native = rt.R.native
    d = Path(a.dir)
    crafted = json.loads((d / 'crafted-fc-root.json').read_text())
    g = crafted['rollout_e1_args']

    def call(f):
        try:
            v = f()
            return dict(ok=True, value=repr(v), hex=float(v).hex()) if isinstance(v, float) else dict(ok=True)
        except BaseException as ex:
            return dict(ok=False, error=f'{type(ex).__name__}: {str(ex)[:120]}')

    def e1(state, seat, action, style):
        return native.rollout_e1(state, seat, action, style, g['command_delay'], g['opponent_delay'], g['horizon'],
                                 g['interval'], g['elixir_weight'], g['budget'])
    rep = dict(native=clasher_core.__file__, crafted={})
    for key in ('fc_payload', 'full_payload'):
        st = clasher_core.BattleState(crafted[key])
        rep['crafted'][key] = call(lambda: e1(st, g['seat'], g['action'], g['style']))
    for p in sorted(d.glob('fail-*.json')):
        f = json.loads(p.read_text())
        st = clasher_core.BattleState(f['snapshot'])
        seat = int(f['seat'])
        cands = f['candidates'] if isinstance(f['candidates'], list) else json.loads(f['candidates'])
        res = {}
        for c in cands:
            for s in STYLES:
                res[f'rollout_e1[{c},{s}]'] = call(lambda c=c, s=s: e1(st, seat, int(c), s))

        def stepper():
            c = st.clone(); c.step(400)
        res['step400'] = call(stepper)
        for s in (0, 1):
            res[f'public_view[{s}]'] = call(lambda s=s: native.public_view(st.clone(), s))
            res[f'public_mask[{s}]'] = call(lambda s=s: native.public_mask(st.clone(), s))
            res[f'evaluate[{s}]'] = call(lambda s=s: native.evaluate(st, s, g['elixir_weight']))
            for sty in STYLES:
                res[f'select_action[{s},{sty}]'] = call(lambda s=s, sty=sty: native.select_action(st.clone(), s, sty))
        rep[p.name] = dict(tick=f['tick'], seat=seat, calls=len(res), ok=sum(r['ok'] for r in res.values()),
                           panics=sum('PanicException' in r.get('error', '') for r in res.values()),
                           other_errors=sorted({r['error'] for r in res.values() if not r['ok'] and 'PanicException' not in r['error']}),
                           values={k: r.get('hex') for k, r in res.items() if r.get('hex')})
    Path(a.out).write_text(json.dumps(rep, indent=1, sort_keys=True))
    print(json.dumps({k: (v if k != 'values' else None) for k, v in rep.items()}, default=str)[:3000])


if __name__ == '__main__':
    main()

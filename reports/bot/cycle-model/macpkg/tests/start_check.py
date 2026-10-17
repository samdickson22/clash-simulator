"""Session-start behaviour of the package translator (fleet only): python start_check.py TREE OUT.json"""
import io, json, os, sys, contextlib
tree, out = sys.argv[1:3]
from bot.players.runtime import Runtime
from bot.live.translate import LiveTranslator
import bot.live.translate as T
assert T.__file__.startswith(tree), T.__file__
rt = Runtime()
deck = ['Knight', 'Archers', 'Fireball', 'Zap', 'Giant', 'Musketeer', 'Valkyrie', 'MiniPekka']
good = os.path.join(tree, 'reports/bot/cycle-model/preal-v1.json')
cases = dict(off={}, soft_valid=dict(BOT_CYCLE_MODEL='soft', BOT_CYCLE_PREAL=good), soft_unset=dict(BOT_CYCLE_MODEL='soft'),
             soft_missing=dict(BOT_CYCLE_MODEL='soft', BOT_CYCLE_PREAL=good + '.missing'),
             bad_spec=dict(BOT_CYCLE_MODEL='soft:bogus=1', BOT_CYCLE_PREAL=good))
res = {}
for k, env in cases.items():
    for v in ('BOT_CYCLE_MODEL', 'BOT_CYCLE_PREAL'):
        os.environ.pop(v, None)
    os.environ.update(env)
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            tr = LiveTranslator(rt, deck)
        res[k] = dict(started=True, tags=[s for s in tr.stats if s.startswith('cycle_model:')], stderr=err.getvalue().strip())
    except Exception as ex:
        res[k] = dict(started=False, error=f'{type(ex).__name__}: {ex}'[:300])
json.dump(res, open(out, 'w'), indent=1)
print(json.dumps(res, indent=1))

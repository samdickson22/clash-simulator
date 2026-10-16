"""Build Runtime under the selected pins; print scope sizes, timing, and a sha of each R component."""
import hashlib, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
t = time.time()
from bot.players.runtime import Runtime
rt = Runtime()
R = rt.R
h = lambda o: hashlib.sha256(json.dumps(o, sort_keys=True, default=repr).encode()).hexdigest()[:16]
print(json.dumps(dict(build_s=round(time.time() - t, 1), scope=getattr(R, 'card_scope', 'c56'), cards=len(R.config['cards']),
      meta_cards=len(R.meta['cards']), meta_bodies=len(R.meta['bodies']), costs=len(R.costs), templates=len(R.templates),
      config=h(R.config), meta=h(R.meta), costs_h=h(R.costs),
      templates_h=h(sorted((repr(k), v) for k, v in R.templates.items())), conflicts=getattr(R, "scope_conflicts", None)), default=repr))
if len(sys.argv) > 1:   # dump the C56 reference lists (run under r1-total)
    d = Path(sys.argv[1])
    (d / 'c56_cards.json').write_text(json.dumps(sorted(R.config['cards'])))
    (d / 'c56_bodies.json').write_text(json.dumps(sorted({t['stats']['name'] for t in R.templates.values()})))

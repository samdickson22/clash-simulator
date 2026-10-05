"""Retain the first latent Golden Knight route mismatch, without oracle edits."""
import inspect,json,hashlib
from pathlib import Path
import cloudpickle
import stage2
from differential import CARDS,config
folder=Path(__file__).resolve().parent
code=inspect.getsource(stage2.focused_case)
needle='        rcpu += time.process_time() - start\n'
addition="        if 258 in b.entities and b.tick >= 1780:\n            state=json.loads(r.snapshot())\n            entity=next(e for e in state['entities'] if e['id']==258)\n            route=getattr(b.entities[258],'_native_ground_route_cells',None) or []\n            if [list(c) for c in route] != entity['route']:\n                folder=Path('reports/strategy_council_20260928/engine-speed/stage6')\n                pins=dict(source=fingerprint())\n                root=folder/f'golden-route-root{b.tick}-r14.pkl'\n                root.write_bytes(cloudpickle.dumps((b,cfg,pins)))\n                root.with_suffix('.meta.json').write_text(json.dumps(dict(root_sha256=hashlib.sha256(root.read_bytes()).hexdigest(),reference={n:h for n,h in json.loads((folder/'entry.json').read_text())['sha256'].items() if (n.startswith('src/clasher/') and not n.startswith('src/clasher/vision/')) or n=='gamedata.json'}),indent=2)+chr(10))\n                result=detail(b,r)\n                root.with_suffix('.json').write_text(json.dumps(result,indent=2)+chr(10))\n                print('latent route',b.tick,route,entity['route'],flush=True)\n                return dict(ok=False,kind='latent route',tick=b.tick)\n"
code=code.replace(needle,needle+addition)
namespace=dict(vars(stage2));namespace.update(cloudpickle=cloudpickle)
exec(code,namespace)
print(namespace['focused_case']('GoldenKnight',0,config((*CARDS,'GoldenKnight'))),flush=True)

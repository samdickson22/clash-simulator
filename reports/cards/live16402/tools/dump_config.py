"""Build Runtime under the selected root/pins and dump what the engine and policy see per card (job dir only: the
dump holds stat values, never commit it).

    CLASHER_BOT_RUNTIME=<root> CLASHER_BOT_RUNTIME_PINS=<pins> python -B dump_config.py OUT.json
OUT: {card: R.config['cards'][card]} plus every other R.config table, R.meta, R.costs (verify=True: pins checked).
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
t = time.time()
from bot.players.runtime import Runtime  # noqa: E402

rt = Runtime()
R = rt.R
dump = dict(config={k: v for k, v in R.config.items() if isinstance(v, dict)}, meta=R.meta,
            costs={repr(k): v for k, v in R.costs.items()} if isinstance(R.costs, dict) else repr(R.costs))
Path(sys.argv[1]).write_text(json.dumps(dump, sort_keys=True, default=repr))
print(json.dumps(dict(build_s=round(time.time() - t, 1), cards=len(R.config['cards']), pins=sorted(rt.pins))))

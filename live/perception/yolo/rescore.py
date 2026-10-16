"""Re-score stored eval_yolo.py outputs offline (no model run): drop KataCR spell/object/non-unit predictions, recompute metrics.

  python rescore.py --katacr-src SRC IN.json OUT.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_yolo import NON_UNIT, score  # noqa: E402

a = sys.argv[1:]
src = a[a.index('--katacr-src')+1]; a = [x for i, x in enumerate(a) if x != '--katacr-src' and (i == 0 or a[i-1] != '--katacr-src')]
sys.path.insert(0, src)
from katacr.constants.label_list import spell_unit_list, object_unit_list  # noqa: E402
d = json.loads(Path(a[0]).read_text())
emp = d.get('empty_preds') or {}
res = score(d['rows'], emp, drop=NON_UNIT | set(spell_unit_list) | set(object_unit_list))
if not emp:
    res['empty'] = d['empty']; res['empty_note'] = 'empty-frame predictions not stored in the input; empty FP copied unchanged'
res.update(rows=d['rows'], weights=d.get('weights'), rescored_from=a[0])
Path(a[1]).write_text(json.dumps(res, indent=1))

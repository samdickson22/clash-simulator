"""Synthetic cache safety checks; run on a permitted fleet worker only."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import cache_budget as b


def rejects(fn):
    try:fn()
    except (ValueError,RuntimeError):return
    raise AssertionError('Unsafe cache growth accepted')


def main():
    code=Path(__file__).parent
    for name in ('build_cache.py','cache_budget.py','stage_training.py','sync_pixel_cache.py'):
        ast.parse((code/name).read_text())
    assert b.approved_root('127x01')==Path('/mpac/sdicks02/repos/clasher-v4-cache')
    assert b.approved_root('127x18')==Path('/mpac/sdicks02/repos/clasher-lease/data/v4-cache')
    for host in ('127x05','127x02','127x07','127x09','127x10','127x12','127x15','127x17'):
        rejects(lambda:b.approved_root(host))
    rejects(lambda:b.validate_root('/mpac/sdicks02/repos/clasher-v4-data/cache'))
    with patch.object(b.socket,'gethostname',return_value='127x04'):
        rejects(lambda:b.validate_root('/mpac/sdicks02/repos/clasher-v4-cache'))
    with patch.object(b,'HOST_RESERVATIONS',{h:300_000_000_000 for h in ('127x01','127x16','127x18','127x04')}):
        rejects(lambda:b.validate_root(b.approved_root()))
    with patch.object(b,'used_bytes',return_value=290_000_000_000),patch.object(b.shutil,'disk_usage',return_value=SimpleNamespace(free=800_000_000_000)):
        b.require_growth('.',10_000_000_000)
        rejects(lambda:b.require_growth('.',10_000_000_001))
        rejects(lambda:b.require_growth('.',0,budget=301_000_000_000))
    with patch.object(b,'used_bytes',return_value=0),patch.object(b.shutil,'disk_usage',return_value=SimpleNamespace(free=210_000_000_000)):
        b.require_growth('.',10_000_000_000)
        rejects(lambda:b.require_growth('.',10_000_000_001))
    print(json.dumps(dict(pass_=True,checks=22,heldout_opened=False)),flush=True)


if __name__=='__main__':main()

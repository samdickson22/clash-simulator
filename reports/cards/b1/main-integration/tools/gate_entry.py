"""Bind the owned combined bot package before an immutable gate entrypoint.

The old root helper inserts a shared checkout at sys.path[0]. Preloading the
explicit owned package keeps all of its submodule resolution on the measured
combined source, without editing that helper or the pinned arm.
"""
from pathlib import Path
import runpy
import sys

repo = Path(sys.argv[1]).resolve(strict=True)
helper = Path(sys.argv[2]).resolve(strict=True)
if not str(repo).startswith('/mpac/sdicks02/jobs/clasher/cards/b1/review-r1-'):
    raise SystemExit('owned run repository required')
if helper.parent != Path('/mpac/sdicks02/jobs/clasher/cards/b1/gate-tools'):
    raise SystemExit('immutable gate helper required')
if helper.name not in ('parity_fixtures.py', 'parity_roots.py'):
    raise SystemExit('unexpected gate helper')
sys.path.insert(0, str(repo))
import bot
if Path(bot.__file__).resolve() != repo/'bot/__init__.py':
    raise SystemExit('bot package came from another source')
sys.argv = [str(helper), *sys.argv[3:]]
runpy.run_path(str(helper), run_name='__main__')

"""Read existing research modules without running their bootstrap side effects."""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
COUNCIL = ROOT/'reports/strategy_council_20260928'
V4 = COUNCIL/'live-loop/v4'


def module(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def actuator_module():
    return module('clasher_live_v4_actuator', V4/'actuator.py')


def delay_module():
    frozen = COUNCIL/'search-noise-s6'
    own = module('clasher_live_s6_own', frozen/'own_state.py')
    with imports(aliases={'own_state': own}):
        return module('clasher_live_s6_delay', frozen/'delay.py')


@contextmanager
def imports(paths=(), aliases=None):
    old_path = sys.path[:]
    old_modules = {k: sys.modules.get(k) for k in (aliases or {})}
    sys.path[:0] = [str(p) for p in paths]
    sys.modules.update(aliases or {})
    try:
        yield
    finally:
        sys.path[:] = old_path
        for name, value in old_modules.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


def tracker_class():
    frozen = COUNCIL/'search-noise-s4'
    derived = module('clasher_live_derived', COUNCIL/'engine-speed/stage5/derived_public_state.py')
    with imports(aliases={'bootstrap': ModuleType('bootstrap'), 'derived_public_state': derived}):
        elt = module('clasher_live_elt_dependency', frozen/'elt.py')
        d1 = module('clasher_live_d1', frozen/'derived_d1.py')
        with imports(aliases={'elt': elt, 'derived_d1': d1}):
            v2 = module('clasher_live_tracker_v2', frozen/'tracker_v2.py')
            with imports(aliases={'tracker_v2': v2}):
                return module('clasher_live_tracker_v3', frozen/'tracker_v3.py').TrackerV3

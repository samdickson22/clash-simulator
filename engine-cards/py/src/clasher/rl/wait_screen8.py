"""W adapter: native offline default ON; live public-root default OFF."""
import time

WAIT = 2304
TIMED_WAITS = {2400: 10, 2401: 20, 2402: 40}


def score_candidates(core, root, seat, candidates, *, trace=False, deadline=None):
    if core.backend != 'native':
        raise ValueError('W-screen8 requires the native public-root backend')
    if trace:
        raise ValueError('W-screen8 does not expose rollout traces')
    if getattr(core, 'pending', ()):
        raise ValueError('W-screen8 requires an available capacity-one channel')
    if not hasattr(core.native, 'score_wait_screen8'):
        raise ValueError('W-screen8 requires a separately built W native library')
    if deadline is None and core.config.deadline_seconds is not None:
        deadline = time.monotonic() + core.config.deadline_seconds
    budget = None if deadline is None else max(0., deadline-time.monotonic())
    delay = getattr(core, 'command_delay', 27)
    scores = core.native.score_wait_screen8(root, seat, candidates, core.wait_own_elixir,
        delay, delay, core.config.horizon, core.config.interval,
        core.config.elixir_weight, budget)
    best = None
    for i, value in enumerate(scores):
        if value is not None and (best is None or value > scores[best]+1e-9):
            best = i
    action = WAIT if best is None else candidates[best]
    core.last = dict(candidates=list(candidates), scores=scores, traces=[])
    core.selected_wait_ticks = TIMED_WAITS.get(action, 0)
    core.deadline_stats = dict(completed=sum(v is not None for v in scores),
                              candidates=len(candidates), fallback_wait=best is None)
    return action


def load_native(directory=None):
    """Load the opt-in library before legacy resource imports prepend paths."""
    import importlib
    from pathlib import Path
    import sys
    requested = None if directory is None else Path(directory).resolve(strict=True)
    loaded = sys.modules.get('clasher_core')
    if loaded is not None and requested is not None:
        if Path(loaded.__file__).resolve().parent != requested:
            raise ValueError('clasher_core is already loaded from another path; use a fresh process')
    old_path = sys.path[:]
    try:
        if requested is not None:
            sys.path.insert(0, str(requested))
        native = importlib.import_module('clasher_core')
    finally:
        sys.path[:] = old_path
    if requested is not None and Path(native.__file__).resolve().parent != requested:
        raise ValueError('W native library was not found in the configured versioned directory')
    if not hasattr(native.NativeScripts, 'score_wait_screen8'):
        raise ValueError('W-screen8 requires a separately built W native library')
    return native

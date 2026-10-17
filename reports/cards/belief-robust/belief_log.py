"""Run tail_profile.py with a belief-update logger (cards/belief-robust analysis only; no code-tree change).
    python belief_log.py LOG.jsonl tail_profile.py ARGS..."""
import json, runpy, sys, time
log, script, argv = sys.argv[1], sys.argv[2], sys.argv[2:]
import bot.fullpool.belief as B
orig_make = B.fullpool_belief_class
fh = open(log, 'a')

def make(*a, **k):
    cls = orig_make(*a, **k)
    if getattr(cls, '_logged', False):
        return cls
    upd = cls.update

    def update(self, tick, events, *args, **kw):
        r0, s0, t0 = getattr(self, 'rebuilds', 0), getattr(self, 'rebuild_slices', 0), time.monotonic()
        try:
            return upd(self, tick, events, *args, **kw)
        finally:
            fh.write(json.dumps(dict(tick=tick, n=len(events), deadline=kw.get('deadline') is not None,
                                     ms=round(1000 * (time.monotonic() - t0), 2), rebuilds=getattr(self, 'rebuilds', 0),
                                     rebuilt=getattr(self, 'rebuilds', 0) - r0, stale=bool(getattr(self, 'stale', False)),
                                     slices=getattr(self, 'rebuild_slices', 0) - s0,
                                     job=getattr(self, '_job', None) is not None)) + '\n'); fh.flush()
    cls.update, cls._logged = update, True
    return cls

B.fullpool_belief_class = make
sys.argv = argv
runpy.run_path(script, run_name='__main__')

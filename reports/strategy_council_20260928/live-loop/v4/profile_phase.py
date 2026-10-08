"""Fleet-only CPU profile; both comparators are fast (NOT parity evidence)."""
import cProfile,pstats,sys
from pathlib import Path
from types import SimpleNamespace
import tracker_parity as harness
OriginalBelief = harness.Belief
harness.Belief = lambda config: OriginalBelief(dict(config, frozen_tracker=False))
harness.args = SimpleNamespace(split=sys.argv[2])
p=cProfile.Profile();p.enable()
harness.phase(Path(sys.argv[1]),1200)
p.disable();pstats.Stats(p).sort_stats('tottime').print_stats(35)

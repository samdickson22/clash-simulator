"""Run the original 24 P16 replay audit with ELT checked at every observation.

The audit's environment, recorded actions and terminal equality checks stay intact.
Only its derived-state class and output destination are adapted in memory.
"""
import bootstrap
from bootstrap import HERE,ROOT
import importlib.util,json,sys
from pathlib import Path
from elt import Candidate
from tracker_v2 import TrackerV2
from derived_d1 import DerivedD1, PublicEvent as D1Event

SRP=ROOT/'reports/strategy_council_20260928/srp-public'
spec=importlib.util.spec_from_file_location('p16_exact_reference',SRP/'derived_public_state.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
class Checked(reference.DerivedPublicState):
    def __init__(self,prior,costs):
        super().__init__(prior,costs)
        self.elt=TrackerV2(prior,costs)
        self.d1=DerivedD1(costs)
        self.checked=0
    def update(self,tick,history):
        for t,name in history[len(self.history):]:
            self.elt.observe(Candidate(t,((name,1.),),1.))
            self.d1.accept(D1Event(t,'card',name))
        super().update(tick,history)
        self.elt.advance(tick)
        state=self.elt.exact.projected()[0]
        self.d1.advance(tick)
        assert state.elixir==self.d1.elixir
        assert state.refill==self.d1.refill
        for i,n in enumerate(self.d1.queue):
            if n is not None: assert state.derived()["cycle_positions"][i]==n
        assert len(self.elt.exact.hypotheses)==1
        assert abs(state.elixir-self.elixir_units/10000)<1e-8
        assert state.refill==self.refill and state.queue_len==self.queue_len
        exact=self.derived();got=state.derived()
        for key in ('hand','cycle','next_card'):
            if exact[key] is not None:
                assert (sorted(exact[key],key=lambda x:x or '')==sorted(got[key],key=lambda x:x or '') if key=='hand' else exact[key]==got[key]),(tick,key,exact,got)
        self.checked+=1
sys.path.insert(0,str(SRP))
# srp-public/public_planner imports the P16 API, while ELT retains its C56 adapter.
sys.modules['derived_public_state']=reference
code=(SRP/'audit_derived.py').read_text()
code=code.replace('from derived_public_state import DerivedPublicState','DerivedPublicState = CHECKED_CLASS')
code=code.replace("(HERE/'results'/f'derived-audit-{args.worker}.json')", "(OUTPUT/f'derived-audit-{args.worker}.json')")
output=HERE/'replay-tests';output.mkdir(exist_ok=True)
namespace={'__name__':'__main__','__file__':str(SRP/'audit_derived.py'),'CHECKED_CLASS':Checked,'OUTPUT':output}
exec(compile(code,str(SRP/'audit_derived.py'),'exec'),namespace)

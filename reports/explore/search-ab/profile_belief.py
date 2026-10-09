"""Public-event preparation profile using only the train prior and static costs."""
import cProfile,json,pstats,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'reports/strategy_council_20260928/engine-speed/stage5'))
from derived_public_state import DerivedPublicState,PublicEvent
prior=json.loads((root/'reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json').read_text())
cat=json.loads((root/'reports/explore/search-ab/budget-full-127x04/catalog.json').read_text());aliases={'BarbLog':'Log','BlowdartGoblin':'BlowdartGoblin','Wallbreakers':'Wallbreakers'};costs={n:cat['cards'].get(aliases.get(n,n),{}).get('cost',1.) for d in prior['decks'] for n in d['cards']}
b=DerivedPublicState(prior,costs);name='Log';states=len(b.states);p=cProfile.Profile();start=time.perf_counter();p.enable();b.update(100,[PublicEvent(90,'card',name)]);b.sample(__import__('numpy').random.default_rng(2**48+90010));p.disable();elapsed=time.perf_counter()-start
out=root/'reports/explore/search-ab/receipts';p.dump_stats(str(out/'belief-profile.pstats'));pstats.Stats(p).sort_stats('tottime').print_stats(15)
(out/'belief-profile.json').write_text(json.dumps(dict(utc=time.time(),train_prior_states=states,states_after_event=len(b.states),event=name,update_and_sample_seconds=elapsed,purpose='latency diagnosis only; no reporting/tuning decisions or outcomes'))+'\n');print(elapsed)

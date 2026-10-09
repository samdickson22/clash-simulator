"""One train-prior simulator smoke game, separate from reporting and tuning."""
import cProfile,pstats,json
from pathlib import Path
from clasher.analysis.loss_review import simulate as s
s.initialize();s.OPTIONS=dict(out='reports/explore/search-ab/profile',trace=False,max_ticks=180,reserve_weight=1,decision_budget=.18,full_decision_latency=True)
deck=s.PRIOR['decks'][0]['cards'];p=cProfile.Profile();p.enable()
r=s.run_game((0,2**48+90010,27,deck,deck,'balanced','0'))
p.disable();p.dump_stats('reports/explore/search-ab/receipts/preparation-profile.pstats');pstats.Stats(p).sort_stats('tottime').print_stats(20)
print(json.dumps(r))

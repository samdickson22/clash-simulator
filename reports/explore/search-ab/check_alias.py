"""Public-card coverage smoke, outside reporting and tuning seeds."""
import json,sys
from pathlib import Path
from clasher.analysis.loss_review import simulate as s
s.initialize();sys.path.insert(0,str(s.COUNCIL/'search-noise-s6'))
from delay import DelayAwarePlanner
from fair_player import observe
from stage2_matches import battle
from clasher.analysis.loss_review.search_ab import planner_class
r=s.RES;deck=max((d for d in s.PRIOR['decks'] if 'BlowdartGoblin' in d['cards']),key=lambda d:d['frequency'])['cards'];b=battle(dict(seed=2**48+90003,decks=[deck,deck]),r.builder.loader)
b.players[0].hand=['BlowdartGoblin']+[n for n in deck if n!='BlowdartGoblin'][:3];b.players[0].elixir=10
info=observe(b,r.builder,0,[]);p=planner_class(DelayAwarePlanner)(r.builder,r.bots,backend='native',seed=2**48+90004,native=r.native,native_config=r.config,command_delay=27,delay_aware=True,coverage=True,catalog=s.CAT);p.info=info;p.costs=r.costs
c,mask=p.candidates(info.packet);ob=info.packet.observation
rows=[dict(slot=i,public_name=n,token=int(ob.hand_ids[i]),token_name=r.builder.token_names[int(ob.hand_ids[i])],catalog_identified=r.builder.token_names[int(ob.hand_ids[i])] in s.CAT['cards'],cost=r.costs[n],legal_tiles=int(sum(mask[i*576:(i+1)*576])),represented=any(a<2304 and a//576==i for a in c)) for i,n in enumerate(info.own['hand'])]
out=dict(seed=2**48+90003,own_elixir=10,candidates=c,hand=rows)
path=Path('reports/explore/search-ab/receipts/alias-check.json');path.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))

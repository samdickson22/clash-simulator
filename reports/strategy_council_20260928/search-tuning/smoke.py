"""Two current/current games check world-deck pairing and runtime receipts."""
from experiment import *

verify();ctx=Context();r=Resources(ctx);rows=[]
for g in range(2):
    s=dict(stage='smoke',role='hog26',style='search',game=g,seed=BASE+11000000)
    row=play(ctx,r,CURRENT,s);rows.append(row)
    write(HERE/'games/smoke'/f'current-current-{g}.json',row)
    print(g,row['outcome'],row['wall_s'],flush=True)
assert rows[0]['world_decks']==rows[1]['world_decks']
assert sum(r['score'] for r in rows)==1.
assert not any(any(r['failed']) for r in rows)
write(HERE/'smoke.json',dict(passed=True,seconds_per_game=np.mean([r['wall_s'] for r in rows]),timing=timing(rows)))
progress('Two full current/current paired-seat smoke games passed.')

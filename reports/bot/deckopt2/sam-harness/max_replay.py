"""Extra unscored MAX repeat without blocking the priority upgrade bank."""
import json,subprocess
import sam_worker as worker
from sam_common import ROOT,OLD,DECKS,utc,sha,dump
def replay(rt,strong,vocab):
 config=json.loads((OLD/'fullpool/player-config.json').read_text())
 meta=dict(scenario='unscored MAX repeat',candidates=DECKS,candidate_plans={n:dict(levels={c:16 for c in d}) for n,d in DECKS.items()},tower_level=16,player_config=config)
 case=dict(id='max-repeat',index=0,seed=730173,seat=0,source_index=None,opponent='R3a',opponent_deck=DECKS['baseline'],opponent_levels={c:16 for c in DECKS['baseline']},own_permutation=list(range(8)))
 from fullpool_clean import problems
 rows=[]
 for i in range(2):
  row=worker.game(rt,strong,vocab,meta,{},case,'sam',config['players'][1],ROOT/f'preflight/max-repeat-{i}.json',dict(stage='preflight',repeat=i))
  assert not problems(row),problems(row);rows.append(row)
 assert rows[0]['result']['command_sha256']==rows[1]['result']['command_sha256']
 assert rows[0]['result']['state_hash']==rows[1]['result']['state_hash']
 receipt=dict(utc=utc(),passed=True,command_sha256=rows[0]['result']['command_sha256'],state_hash=rows[0]['result']['state_hash'],worker_sha256=sha(ROOT/'sam_worker.py'),card_levels=16,tower_levels=[16,16])
 dump(ROOT/'preflight/replay.json',receipt);subprocess.run(['rsync','-a',str(ROOT/'preflight/replay.json'),f'127x05:{ROOT}/preflight/'],check=True)
 print(json.dumps(receipt),flush=True)
worker.smoke=replay
if __name__=='__main__':worker.main()

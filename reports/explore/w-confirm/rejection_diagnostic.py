"""Replay an unchanged reporting case to explain a command rejection, not retune it."""
import json
from pathlib import Path
import sys
import run

job=run.ROOT.parent
run.initialize()
from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace

original=BattleState.deploy_card
events=[]
def deploy(self,actor,name,position):
    before=dict(tick=self.tick,actor=actor,card=name,elixir=self.players[actor].elixir,
                hand=list(self.players[actor].hand),refill=self.players[actor].next_card_refill_cooldown_ms,
                x=position.x,y=position.y)
    accepted=original(self,actor,name,position)
    if not accepted:
        before['physical_action_legal']=bool(DiscreteTileActionSpace(mask_version=2).legal_action_mask(self,actor)[
            actor_action(self,actor,name,position)])
        before['tower_flags']=list(self._tower_alive_flags())
        events.append(before)
        print(json.dumps(dict(rejection=before)),flush=True)
    return accepted

def actor_action(b,actor,name,position):
    slot=b.players[actor].hand.index(name)
    x,y=position.x,position.y
    if actor:x,y=18-x,32-y
    return slot*576+int(y)*18+int(x)

BattleState.deploy_card=deploy
schedule=json.loads((job/'reporting/schedule.json').read_text())
run.OPTIONS=dict(out=str(job/'rejection-diagnostic'),max_ticks=6001)
for case in schedule['cases']:
    if case[0]==95 and case[2] in ('0','WW'):
        run.run_game(case)
        path=Path(run.OPTIONS['out'])/'games'/f'sim-{case[0]:04d}-d27-{case[2]}.json'
        actual=json.loads(path.read_text());expected=json.loads((job/'reporting/games'/path.name).read_text())
        assert actual['metadata']==expected['metadata'] and actual['stats']==expected['stats'],case[:3]
(job/'rejection-diagnostic/events.json').write_text(json.dumps(dict(replays_exact=True,events=events),indent=2)+'\n')

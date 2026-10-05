"""Candidate S1: LogicSummoner's one-unit symmetric anchor nudge is not applied when the placement search
relocated the requested ground anchor to another tile."""
from clasher.battle import BattleState
_od=BattleState.deploy_card; _or=BattleState.resolve_ground_troop_anchor; _os=BattleState._apply_symmetric_deploy_snap
def dc(self,pid,name,pos):
    self._ds_displaced=False
    try: return _od(self,pid,name,pos)
    finally: self._ds_displaced=False
def rg(self,position,player_id,card_stats):
    r=_or(self,position,player_id,card_stats)
    import math
    if r is not None and (int(r.x),int(r.y))!=(math.floor(position.x),math.floor(position.y)):
        self._ds_displaced=True
    return r
def sn(self,position,player_id,card_stats):
    if getattr(self,'_ds_displaced',False): return position
    return _os(self,position,player_id,card_stats)
BattleState.deploy_card=dc; BattleState.resolve_ground_troop_anchor=rg; BattleState._apply_symmetric_deploy_snap=sn

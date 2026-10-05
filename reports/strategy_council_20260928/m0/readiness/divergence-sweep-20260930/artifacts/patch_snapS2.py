"""Candidate S2: the symmetric nudge's x decision is taken from the requested (pre-search) anchor."""
from clasher.battle import BattleState
from clasher.arena import Position
_od=BattleState.deploy_card; _os=BattleState._apply_symmetric_deploy_snap
def dc(self,pid,name,pos):
    self._ds_req=pos
    try: return _od(self,pid,name,pos)
    finally: self._ds_req=None
def sn(self,position,player_id,card_stats):
    out=_os(self,position,player_id,card_stats)
    req=getattr(self,'_ds_req',None)
    if req is None or out is position: return out
    xr=round(req.x*1000); half=round(self.arena.width*1000)//2
    x=round(position.x*1000) - (1 if xr<half else 0)
    return Position(x/1000.0, out.y)
BattleState.deploy_card=dc; BattleState._apply_symmetric_deploy_snap=sn

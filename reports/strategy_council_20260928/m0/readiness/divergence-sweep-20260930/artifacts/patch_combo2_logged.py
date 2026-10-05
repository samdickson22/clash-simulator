"""T+K+B+S2 as monkeypatches on pre src (equivalent to the landed code) with precise application logging."""
import dsweep_gates as G
from clasher.entities import Entity, Troop, Building
from clasher.battle import BattleState
from clasher.arena import Position
# T
_onc=Entity._note_combat_target
def _note_combat_target(self,target,*,preserve_hit=False):
    prev=getattr(self,'_last_combat_target_id',None)
    if (target is not None and prev is not None and prev!=target.id and self._ordinary_clock is None
        and getattr(getattr(self,'card_stats',None),'name',None) in ('Tower','KingTower')
        and self.is_within_attack_engagement_reach(target)):
        if not preserve_hit: G.fire('aT',self.battle_state.tick)
        preserve_hit=True
    return _onc(self,target,preserve_hit=preserve_hit)
Entity._note_combat_target=_note_combat_target
# K
_ok=Troop._update_knockback_movement
def k(self,bs):
    if self._knockback_target is not None and self._knockback_reset_hit_on_movement and self.is_stunned():
        G.fire('aK',bs.tick)
        self._knockback_reset_hit_on_movement=False
        try: _ok(self,bs)
        finally:
            if self._knockback_target is not None: self._knockback_reset_hit_on_movement=True
        return
    return _ok(self,bs)
Troop._update_knockback_movement=k
# B (precise: compare scan result with and without killed buildings)
_ou=Troop._update_native_avoidance
def u(self,bs):
    grid=getattr(bs,'_native_avoidance_grid',None)
    dead=[e for e in bs.entities.values() if isinstance(e,Building) and not e.is_alive] if grid is not None else []
    if not dead: return _ou(self,bs)
    av0=self._native_avoidance; r0=list(getattr(self,'_native_ground_route_cells',None) or [])
    _ou(self,bs); a_off=(self._native_avoidance,list(getattr(self,'_native_ground_route_cells',None) or []))
    self._native_avoidance=av0
    if hasattr(self,'_native_ground_route_cells'): self._native_ground_route_cells=list(r0)
    for e in dead: e.is_alive=True
    try: _ou(self,bs)
    finally:
        for e in dead: e.is_alive=False
    if (self._native_avoidance,list(getattr(self,'_native_ground_route_cells',None) or []))!=a_off: G.fire('aB',bs.tick)
Troop._update_native_avoidance=u
# S2
_od=BattleState.deploy_card; _os=BattleState._apply_symmetric_deploy_snap
def dc(self,pid,name,pos):
    self._ds_req=Position(pos.x,pos.y)
    try: return _od(self,pid,name,pos)
    finally: self._ds_req=None
def sn(self,position,player_id,card_stats,**kw):
    out=_os(self,position,player_id,card_stats)
    req=getattr(self,'_ds_req',None)
    if req is None or out is position: return out
    xr=round(req.x*1000); half=round(self.arena.width*1000)//2
    x=round(position.x*1000)-(1 if xr<half else 0)
    new=Position(x/1000.0,out.y)
    if round(new.x*1000)!=round(out.x*1000): G.fire('aS',self.tick)
    return new
BattleState.deploy_card=dc; BattleState._apply_symmetric_deploy_snap=sn

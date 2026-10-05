"""Behavior-neutral detectors: record first tick each candidate gate would change behavior."""
import dsweep_gates as G
from clasher.entities import Entity, Troop
_onc=Entity._note_combat_target
def _note_combat_target(self,target,*,preserve_hit=False):
    prev=getattr(self,'_last_combat_target_id',None)
    if (target is not None and prev is not None and prev!=target.id and self._ordinary_clock is None
        and getattr(getattr(self,'card_stats',None),'name',None) in ('Tower','KingTower')
        and self.is_within_attack_engagement_reach(target) and not preserve_hit):
        G.fire('T',self.battle_state.tick if getattr(self,'battle_state',None) else -1)
    return _onc(self,target,preserve_hit=preserve_hit)
Entity._note_combat_target=_note_combat_target
_ou=Troop._update_native_avoidance
def u(self,bs):
    if (self.is_stunned() and self._knockback_target is None and getattr(self, "_mk_leap_phase", None) not in {"airborne","landing"}
        and self._native_movement_component_stopped() and self._native_avoidance!=0):
        G.fire('Z',bs.tick)
    return _ou(self,bs)
Troop._update_native_avoidance=u
_ok=Troop._update_knockback_movement
def k(self,bs):
    if self._knockback_target is not None and self._knockback_reset_hit_on_movement and self.is_stunned() and self._attack_finish_elapsed_ms<=0:
        G.fire('K',bs.tick)
    return _ok(self,bs)
Troop._update_knockback_movement=k
from clasher.entities import Building
_ou2=Troop._update_native_avoidance
def u2(self,bs):
    if not self._native_movement_component_stopped() or (self.deploy_delay_remaining > 0 and not self.is_stunned()):
        if any(isinstance(e,Building) and not e.is_alive for e in bs.entities.values()):
            G.fire('B',bs.tick)
    return _ou2(self,bs)
Troop._update_native_avoidance=u2
from clasher.battle import BattleState
import math as _m
_ord=BattleState.resolve_ground_troop_anchor
def _rg(self,position,player_id,card_stats):
    r=_ord(self,position,player_id,card_stats)
    if r is not None and (int(r.x),int(r.y))!=(_m.floor(position.x),_m.floor(position.y)):
        G.fire('S',self.tick)
    return r
BattleState.resolve_ground_troop_anchor=_rg
_onw=Troop._native_movement_waypoint
def _nw(self,target_entity,battle_state=None):
    prev=getattr(self,'_native_navigation_target_id',None)
    if (prev is not None and prev!=target_entity.id and not self.is_air_unit
        and getattr(self,'_ground_path_cache_key',None) is not None and getattr(self,'_native_ground_route_cells',None)):
        G.fire('N',battle_state.tick if battle_state is not None else -1)
    return _onw(self,target_entity,battle_state)
Troop._native_movement_waypoint=_nw
from clasher.kinematics import normalized_vector_logic_units as _nvl
from clasher.kinematics import tiles_to_logic_units as _t2l

from clasher.unit_traits import uses_air_collision_plane as _uacp
_ou3=Troop._update_native_avoidance
def u3(self,bs):
    grid=getattr(bs,'_native_avoidance_grid',None)
    if grid is not None and (not self._native_movement_component_stopped() or (self.deploy_delay_remaining > 0 and not self.is_stunned())):
        dead=[e for e in bs.entities.values() if isinstance(e,Building) and not e.is_alive]
        if dead:
            fx,fy=_nvl(self._facing_x_units,self._facing_y_units,256)
            if fx or fy:
                px=_t2l(self.position.x)+fx; py=_t2l(self.position.y)+fy
                pr=min(500,max(0,_t2l(self.get_collision_radius())))
                for o in dead:
                    if _uacp(o)!=_uacp(self): continue
                    qr=pr+max(0,_t2l(o.get_collision_radius()))
                    dx=_t2l(o.position.x)-px; dy=_t2l(o.position.y)-py
                    if dx*dx+dy*dy<=qr*qr: G.fire('B2',bs.tick); break
    return _ou3(self,bs)
Troop._update_native_avoidance=u3
_ord2=BattleState.resolve_ground_troop_anchor
def _rg2(self,position,player_id,card_stats):
    r=_ord2(self,position,player_id,card_stats)
    if r is not None:
        half=_t2l(self.arena.width)//2
        if (_t2l(position.x)<half)!=(_t2l(r.x)<half): G.fire('S2p',self.tick)
    return r
BattleState.resolve_ground_troop_anchor=_rg2

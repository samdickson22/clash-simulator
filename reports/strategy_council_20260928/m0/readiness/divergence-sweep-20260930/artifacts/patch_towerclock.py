"""Candidate C: Crown Towers use the ordinary native two-clock (load + hit timeline) combat model."""
from clasher import ordinary_combat_clock as occ
from clasher.cards.ice_spirit import IceSpiritFreeze
from clasher.mechanics.mechanic_base import BaseMechanic
_os=occ.supported
def supported(entity):
    stats=entity.card_stats
    if stats is not None and getattr(stats,'name',None) in {'Tower','KingTower'} and entity.entity_kind in (0,1):
        hit=int(getattr(stats,'hit_speed',0) or 0); load=int(getattr(stats,'load_time',0) or 0)
        if not 0<=load<=hit or hit<=0: return False
        if getattr(stats,'first_hit_time',None)!=hit-load: return False
        return True
    return _os(entity)
occ.supported=supported

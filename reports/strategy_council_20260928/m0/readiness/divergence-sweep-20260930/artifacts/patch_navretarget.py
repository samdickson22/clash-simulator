"""Candidate N: a walking retarget to a different navigation target rebuilds the ground route from the current
cell even when the new target's goal cell equals the old one."""
from clasher.entities import Troop
_ow=Troop._native_movement_waypoint
def w(self,target_entity,battle_state=None):
    prev=getattr(self,'_native_navigation_target_id',None)
    if prev is not None and prev!=target_entity.id and not self.is_air_unit:
        self._ground_path_cache_key=None
    return _ow(self,target_entity,battle_state)
Troop._native_movement_waypoint=w

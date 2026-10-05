"""Candidate K: a physical push whose first movement frame lands while the unit is stunned/frozen does not stop
the unit's hit (native keeps the frozen attack timeline through the push)."""
from clasher.entities import Troop
_ok=Troop._update_knockback_movement
def k(self,bs):
    if self._knockback_target is not None and self._knockback_reset_hit_on_movement and self.is_stunned():
        self._knockback_reset_hit_on_movement = False
    return _ok(self,bs)
Troop._update_knockback_movement=k

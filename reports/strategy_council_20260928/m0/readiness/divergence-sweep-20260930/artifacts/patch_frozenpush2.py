"""Candidate K2: a push's hit stop is deferred while the unit is stunned; it applies on the first push movement
frame after the thaw, and is dropped if the push ends while the unit is still stunned."""
from clasher.entities import Troop
_ok=Troop._update_knockback_movement
def k(self,bs):
    if self._knockback_target is not None and self._knockback_reset_hit_on_movement and self.is_stunned():
        self._knockback_reset_hit_on_movement=False
        try: _ok(self,bs)
        finally:
            if self._knockback_target is not None: self._knockback_reset_hit_on_movement=True
        return
    return _ok(self,bs)
Troop._update_knockback_movement=k

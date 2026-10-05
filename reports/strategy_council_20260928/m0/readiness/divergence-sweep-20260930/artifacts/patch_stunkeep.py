"""Candidate Z: a stunned (Zap/freeze) character whose movement component is stopped retains its avoidance
accumulator instead of decaying it."""
from clasher.entities import Troop
_ou=Troop._update_native_avoidance
def u(self,bs):
    if (self.is_stunned() and self._knockback_target is None and getattr(self, "_mk_leap_phase", None) not in {"airborne","landing"}
        and self._native_movement_component_stopped()):
        return
    return _ou(self,bs)
Troop._update_native_avoidance=u

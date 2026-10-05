"""Candidate Z2: a stunned (Zap/freeze) character outside pushback neither scans nor decays its avoidance
accumulator; it resumes with the retained value when the stun ends."""
from clasher.entities import Troop
_ou=Troop._update_native_avoidance
def u(self,bs):
    if (self.is_stunned() and self._knockback_target is None and getattr(self, "_mk_leap_phase", None) not in {"airborne","landing"}
        and self._death_spawn_travel_ticks_remaining <= 0):
        return
    return _ou(self,bs)
Troop._update_native_avoidance=u

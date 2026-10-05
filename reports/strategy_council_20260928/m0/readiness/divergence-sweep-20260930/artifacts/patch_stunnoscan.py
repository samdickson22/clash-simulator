"""Candidate Y: a stunned (Zap/freeze) character outside pushback does not run the avoidance scan; its
accumulator only decays (as a stopped character's does), even if it was walking or deploying when frozen."""
from clasher.entities import Troop
_ou=Troop._update_native_avoidance
def u(self,bs):
    if (self.is_stunned() and self._knockback_target is None and getattr(self, "_mk_leap_phase", None) not in {"airborne","landing"}
        and self._death_spawn_travel_ticks_remaining <= 0):
        self._decay_native_avoidance(); return
    return _ou(self,bs)
Troop._update_native_avoidance=u

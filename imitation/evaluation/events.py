"""Public event sensor using T2's accepted-event hooks, without its truth audit."""
from .paths import setup
setup()
from sidecar_observer import SidecarObserver


class PublicRecorder(SidecarObserver):
    def bind(self, battle):
        self.battle = battle
        self.seats = {id(p): s for s, p in enumerate(battle.players)}
        self.public_events = []

    def event(self, seat, event):
        self.public_events.append(dict(seat=seat, **event.__dict__))

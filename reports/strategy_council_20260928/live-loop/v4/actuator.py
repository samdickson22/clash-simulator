"""Pixel-only actuation state machine. No probe or hidden-state dependencies."""
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class Hud:
    produced_at: float  # host monotonic seconds
    hand: tuple[str, ...]
    elixir: float
    next_card: str | None = None


@dataclass
class Pending:
    card: str
    cost: float
    slot: int
    tile: tuple[float, float]
    before: Hud
    submitted_at: float
    attempts: int = 1
    retry_at: float | None = None


class Actuator:
    """Caller supplies fresh pixel HUD and performs returned tap requests.

    Reserve exactly one spend, including across a retry. Old images cannot
    erase that reservation. Unknown transport outcomes follow verification,
    never immediate resend. A confirmed spend remains fenced until a post-play
    HUD is incorporated. Expiry releases the reservation and holds the card.
    """
    def __init__(self, margin=0.0, verify_seconds=.6, backend='offline-renderer-grpc', timing_path=None):
        self.margin = margin
        timing_path = Path(timing_path) if timing_path is not None else Path(__file__).parent / 'actuation/backend-timing.json'
        timing = json.loads(timing_path.read_text())['backends'][backend]
        self.verify_seconds = timing['p99_ms'] / 1000 + verify_seconds
        self.pending = None
        self.hold_until = {}
        self.confirmed = None

    def effective(self, hud):
        if self.pending:
            p = self.pending
            return max(0., min(hud.elixir, p.before.elixir - p.cost)), tuple(
                p.before.next_card if i == p.slot else c for i, c in enumerate(p.before.hand))
        if self.confirmed and hud.produced_at <= self.confirmed.produced_at:
            return self.confirmed.elixir, self.confirmed.hand
        return hud.elixir, hud.hand

    def submit(self, card, cost, tile, hud, now):
        if self.pending: return {'state': 'blocked', 'reason': 'pending'}
        if not 0 <= now-hud.produced_at <= .060: return {'state': 'blocked', 'reason': 'stale'}
        if self.confirmed and hud.produced_at <= self.confirmed.produced_at:
            return {'state': 'blocked', 'reason': 'pre-confirmation HUD'}
        if now < self.hold_until.get(card, 0): return {'state': 'blocked', 'reason': 'hold'}
        elixir, hand = self.effective(hud)
        if card not in hand: return {'state': 'blocked', 'reason': 'card absent'}
        if elixir < cost+self.margin: return {'state': 'blocked', 'reason': 'insufficient elixir'}
        slot = hand.index(card)
        self.pending = Pending(card, cost, slot, tile, hud, now)
        return {'state': 'tap', 'slot': slot, 'tile': tile, 'attempt': 1}

    def observe(self, hud, now):
        p = self.pending
        if not p: return {'state': 'idle'}
        fresh = hud.produced_at > p.submitted_at and 0 <= now-hud.produced_at <= .060
        # Accept only two independent HUD changes from a post-submission image.
        drop = p.before.elixir-hud.elixir
        if fresh and hud.hand[p.slot] != p.card and drop > 0 and abs(drop-p.cost) <= 1:
            self.confirmed = hud
            self.pending = None
            return {'state': 'accepted', 'card': p.card, 'attempts': p.attempts,
                    'latency_ms': (now-p.submitted_at)*1000}
        # Each attempt reserves through its backend-relative deadline + 200 ms.
        last_attempt = p.submitted_at if p.attempts == 1 else p.retry_at
        deadline = last_attempt + self.verify_seconds
        if now >= deadline + .2:
            reason = ('insufficient elixir' if hud.elixir < p.cost+self.margin else
                      'card absent' if p.card not in hud.hand else 'unknown')
            self.pending = None
            self.hold_until[p.card] = now+1
            return {'state': 'failed', 'reason': reason, 'attempts': p.attempts}
        if p.attempts == 1 and now > deadline:
            if p.retry_at is None: p.retry_at = deadline+.150
            if now >= p.retry_at and fresh and p.card in hud.hand and hud.elixir >= p.cost+self.margin:
                p.slot = hud.hand.index(p.card)
                p.attempts = 2
                p.retry_at = now
                return {'state': 'tap', 'slot': p.slot, 'tile': p.tile, 'attempt': 2}
        return {'state': 'pending'}

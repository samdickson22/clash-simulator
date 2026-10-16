"""Uniform player interface: Player.act(PublicView) -> Decision.

Action ids are the repo's DiscreteTileActionSpace ids in the acting seat's own
frame: slot*576 + tile (tile = row*18 + col on the 18x32 tile grid, own king at
the bottom), WAIT = 2304. Ability presses (2305) are disabled on both sides, as
in every X4S/S1/K harness. Timed waits are returned as `wait_ticks`.

The view carries only public, opponent-derivable state (fair-information rule):
the contract-v5 public packet, the player's own HUD, and the accepted public
event stream. Unrevealed opponent cards and engine RNG never appear in it; the
search player samples them from its own belief.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

WAIT = 2304
POLICY_INTERVAL = 5     # every player is polled every 5 ticks (frozen gate(c) cadence)
SEARCH_INTERVAL = 10    # search runs at ticks divisible by 10 when its channel is free
START_TICK = 90


@dataclass(frozen=True)
class MatchContext:
    seat: int
    seed: int                 # the match seed; players derive their private seeds from it
    own_order: tuple          # own deck in initial hand+cycle order (own information)
    command_delay: int = 27
    opponent_delay: int = 27


@dataclass(frozen=True)
class PublicView:
    tick: int
    seat: int
    info: Any                 # fair_player.Information: v5 packet + own HUD + accepted enemy cards
    reserved: Any             # same, with own unexecuted reservations applied (CommandQueue.own_packet)
    public_events: list       # accepted public events of both seats (D1 input), dict rows
    pending: tuple            # own unexecuted reservations
    can_act: bool             # channel free, no timed wait running, not delayed by lateness


@dataclass
class Decision:
    action: int = WAIT
    wait_ticks: int = 0
    stats: dict = field(default_factory=dict)


class Player(Protocol):
    name: str
    deadline_seconds: float | None   # wall budget charged by honest lateness; None = untimed

    def start(self, ctx: MatchContext) -> None: ...
    def act(self, view: PublicView) -> Decision: ...
    def close(self) -> None: ...

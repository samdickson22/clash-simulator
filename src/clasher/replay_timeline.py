"""Lossless form identities for replay actions awaiting state reconstruction."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ReplayCard(StrictRecord):
    key: str = Field(min_length=1)
    level: int = Field(ge=1, le=20)


class ReplayAction(StrictRecord):
    source_index: int = Field(ge=0)
    tick: int = Field(ge=0)
    side: Literal["team", "opponent"]
    kind: Literal["play_card", "activate_ability"]
    card_key: str | None = None
    deck_candidates: tuple[str, ...] = ()
    active_form: str | None = None
    ability_source_authoritative: bool | None = None
    ability_candidates: tuple[str, ...] = ()
    native_xy: tuple[float, float] | None = None

    @model_validator(mode="after")
    def require_placement(self):
        if self.kind == "play_card":
            if not self.card_key or self.native_xy is None:
                raise ValueError(
                    "placement requires recorded card and native coordinates"
                )
            x, y = self.native_xy
            if not (0 <= x <= 18000 and 0 <= y <= 32000):
                raise ValueError("placement outside declared native arena")
        if self.ability_source_authoritative and len(self.ability_candidates) != 1:
            raise ValueError(
                "authoritative ability source requires exactly one candidate"
            )
        return self


class ReplayTimeline(StrictRecord):
    schema_version: Literal[1] = 1
    payload_sha256: str
    team_deck: tuple[ReplayCard, ...]
    opponent_deck: tuple[ReplayCard, ...]
    actions: tuple[ReplayAction, ...]

    @model_validator(mode="after")
    def validate_timeline(self):
        for deck in (self.team_deck, self.opponent_deck):
            if len(deck) != 8 or len({card.key for card in deck}) != 8:
                raise ValueError("timeline requires two distinct eight-card decks")
        indices = set()
        last_tick = -1
        for action in self.actions:
            if action.source_index in indices:
                raise ValueError("duplicate source event index")
            indices.add(action.source_index)
            if action.tick < last_tick:
                raise ValueError("source events are not chronological")
            last_tick = action.tick
            deck = self.team_deck if action.side == "team" else self.opponent_deck
            if not set(action.deck_candidates) <= {card.key for card in deck}:
                raise ValueError("event candidates contradict its own deck")
        return self

    def reconstruction_gaps(self) -> tuple[str, ...]:
        gaps = {"entity_observations_not_reconstructed", "ruleset_not_verified"}
        for action in self.actions:
            if action.kind == "play_card":
                if action.active_form is None:
                    gaps.add("active_form_unresolved")
                if len(action.deck_candidates) != 1:
                    gaps.add("deck_slot_unresolved")
            elif (
                not action.ability_source_authoritative
                or len(action.ability_candidates) != 1
            ):
                gaps.add("ability_source_unresolved")
        return tuple(sorted(gaps))


def import_replay_payload(payload: dict) -> ReplayTimeline:
    """Preserve source identities; do not guess forms, levels, or ability owners."""

    def deck(side: str):
        players = payload["battle"][side]["players"]
        if len(players) != 1:
            raise ValueError("only single-player sides are supported")
        return tuple(
            ReplayCard(key=c["card_key"], level=c["level"]) for c in players[0]["deck"]
        )

    actions = []
    for event in payload["events"]:
        xy = (event.get("coordinates") or {}).get("native_world_units")
        form = event.get("form_at_play")
        actions.append(
            ReplayAction(
                source_index=event["source_index"],
                tick=event["replay_tick_20hz"],
                side=event["side"],
                kind=event["kind"],
                card_key=event.get("card_key"),
                deck_candidates=tuple(event.get("deck_card_key_candidates") or ()),
                active_form=None if form in (None, "unknown") else form,
                ability_source_authoritative=event.get("ability_source_authoritative"),
                ability_candidates=tuple(event.get("ability_source_candidates") or ()),
                native_xy=None if xy is None else (xy["x"], xy["y"]),
            )
        )
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return ReplayTimeline(
        payload_sha256=digest,
        team_deck=deck("team"),
        opponent_deck=deck("opponent"),
        actions=tuple(actions),
    )

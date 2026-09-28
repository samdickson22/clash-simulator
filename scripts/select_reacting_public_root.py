"""Apply a predeclared development root rule without reading outcome utility."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from clasher.data import CardDataLoader
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.public_match_archive import digest, load_match_archive


class SelectionRule(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    owner: int = Field(ge=0, le=1)
    earliest_tick: int = Field(ge=90)
    latest_tick: int | None = Field(default=None, ge=90)
    card_ids: list[int] = Field(min_length=1)
    x_offsets: list[int] = Field(min_length=1)
    response_seeds: list[int] = Field(min_length=1)
    event_selection_seed: int | None = Field(default=None, ge=0)
    include_delay_one: bool = False
    response_styles_by_owner: tuple[str, str] | None = None


def first_root(commands, rule, loader):
    if rule.latest_tick is not None and rule.latest_tick < rule.earliest_tick:
        raise ValueError("selection window ends before it starts")
    eligible = [
        c
        for c in commands
        if c["owner"] == rule.owner
        and c["submitted_tick"] >= rule.earliest_tick
        and (rule.latest_tick is None or c["submitted_tick"] <= rule.latest_tick)
        and c["native_acceptance_spend_evidence"] is True
        and loader.get_card(c["name"])._raw_entry["id"] in rule.card_ids
    ]
    if not eligible:
        raise ValueError(
            "No root meets the frozen rule; do not choose a substitute retrospectively"
        )
    eligible.sort(key=lambda c: c["submitted_tick"])
    if rule.event_selection_seed is not None:
        return random.Random(rule.event_selection_seed).choice(eligible)
    return eligible[0]


def select_protocol(
    capture: Path, rule: SelectionRule, *, rule_sha256: str, expected_role="development"
):
    loader = CardDataLoader(capture / "gamedata.json")
    source = json.loads((capture / "result.json").read_text())
    if source["failure"] is not None or not source["producer_sources_unchanged"]:
        raise ValueError("Root source collection failed")
    command = first_root(source["commands"], rule, loader)
    tick = command["submitted_tick"]
    seat = capture / f"seat{rule.owner}"
    with np.load(seat / "observations.npz", allow_pickle=False) as archive:
        tokens = tuple(json.loads(str(archive["metadata"].item()))["token_names"])
    receipt, _sequence, decisions, masks = load_match_archive(
        seat,
        token_names=tokens,
        source_path=capture / "result.json",
        ruleset_path=capture / "gamedata.json",
        producer_path=capture / "producer-source.zip",
    )
    if receipt.provenance.role != expected_role:
        raise ValueError("Source archive role differs from selector role")
    index = next(i for i, d in enumerate(decisions) if d.submission_tick == tick)
    assert (
        decisions[index].action == command["action"] and masks[index, command["action"]]
    )
    space = DiscreteTileActionSpace()
    decoded = space.decode_action(command["action"], rule.owner)
    assert [decoded.position.x, decoded.position.y] == command["xy"]
    candidates = [
        {"name": "wait", "action": None, "delay_ticks": 0},
        {
            "name": "recorded",
            "action": {"card": command["name"], "xy": command["xy"]},
            "delay_ticks": 0,
        },
    ]
    exclusions = []
    for offset in rule.x_offsets:
        if offset == 0:
            raise ValueError("Neighbor offsets must be nonzero")
        x, y = command["xy"][0] + offset, command["xy"][1]
        if not 0 <= x < 18:
            exclusions.append({"offset": offset, "reason": "outside arena"})
            continue
        action = space.encode_action(decoded.slot, int(x), int(y), rule.owner)
        if not masks[index, action]:
            exclusions.append(
                {"offset": offset, "reason": "public mask rejects placement"}
            )
            continue
        candidates.append(
            {
                "name": f"neighbor_{offset:+d}",
                "action": {"card": command["name"], "xy": [x, y]},
                "delay_ticks": 0,
            }
        )
    if rule.include_delay_one:
        candidates.append(
            {
                "name": "delay_1",
                "action": {"card": command["name"], "xy": command["xy"]},
                "delay_ticks": 1,
            }
        )
    opponents = [
        c
        for c in source["commands"]
        if c["owner"] == 1 - rule.owner and c["submitted_tick"] == tick
    ]
    assert len(opponents) <= 1
    opponent = (
        None
        if not opponents
        else {"card": opponents[0]["name"], "xy": opponents[0]["xy"]}
    )
    protocol = {
        "role": expected_role,
        "root_tick": tick,
        "owner": rule.owner,
        "cadence_ticks": 30,
        "response_seeds": rule.response_seeds,
        "opponent_root_action": opponent,
        "candidates": candidates,
        "utility": f"lexicographic owner{rule.owner} terminal result then own-minus-enemy remaining tower HP",
        "horizon": "completed playable episode and native finalized winner, deadline6001",
        "response_model": "fixed-public-geometry-v1 with per-decision RNG(seed,tick,owner)",
        "root_duplicate_group_id": receipt.provenance.duplicate_group_id,
        "source_sha256": digest(capture / "result.json"),
        "selection_rule_sha256": rule_sha256,
        "selector_sha256": digest(Path(__file__)),
        "candidate_exclusions": exclusions,
        "limitation": "Opened development root and weak fixed controller; no acceptance claim",
    }
    if rule.response_styles_by_owner is not None:
        if len(rule.response_seeds) != 1:
            raise ValueError("deterministic public responses require one seed label")
        if any(
            s not in ("balanced", "pressure", "defense")
            for s in rule.response_styles_by_owner
        ):
            raise ValueError("unknown public response style")
        protocol["response_styles_by_owner"] = list(rule.response_styles_by_owner)
        protocol["response_model"] = "public-scripted-v1 deterministic styles"
    if expected_role == "acceptance":
        protocol["limitation"] = (
            "Prospective reference comparison; not official-client or human-strength evidence"
        )
    return protocol


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--rule", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rule = SelectionRule.model_validate_json(args.rule.read_text())
    protocol = select_protocol(args.capture, rule, rule_sha256=digest(args.rule))
    with args.output.open("x") as f:
        f.write(json.dumps(protocol, indent=2) + "\n")
    print("root", protocol["root_tick"], "candidates", len(protocol["candidates"]))


if __name__ == "__main__":
    main()

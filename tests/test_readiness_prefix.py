"""Offline native-transport doubles verify irreversible prefix collection order."""

import copy
import json
from dataclasses import replace

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.player import PlayerState
from clasher.rl.public_observation import exact_public_observation
from clasher.rl.public_scripted_opponent import SUPPORTED_CARDS
from clasher.rl.readiness_prefix import collect_prefix
from clasher.rl.readiness_root_bank import RootRequest
from clasher.rl.structured_obs import StructuredObservationBuilder

DECK = (
    "Cannon",
    "Skeletons",
    "HogRider",
    "Fireball",
    "Log",
    "Musketeer",
    "IceGolem",
    "IceSpirit",
)


class NativeDouble:
    def __init__(self, *, threat=True, reject=False, wrong_tick=False):
        self.calls = []
        self.tick = 0
        self.pending = []
        self.resources = [100000, 100000]
        self.threat = threat
        self.spawned = False
        self.reject = reject
        self.wrong_tick = wrong_tick
        self.battle = BattleState(
            players=[
                PlayerState(o, deck=list(DECK), hand=list(DECK[:4]), elixir=10)
                for o in (0, 1)
            ]
        )
        self.builder = StructuredObservationBuilder(
            card_vocab=sorted(SUPPORTED_CARDS),
            canonical_lane_globals=True,
            public_entity_levels=True,
            card_semantics_version=4,
        )

    def ordinary(self):
        return {
            "tick": self.tick,
            "generation": 1,
            "stateEpoch": 1,
            "truncated": False,
            "ended": False,
            "players": [
                {
                    "owner": o,
                    "elixirRaw": self.resources[o],
                    "deck": [
                        {
                            "deckSlot": i,
                            "cardId": self.builder.loader.get_card(n)._raw_entry["id"],
                            "commandCardId": self.builder.loader.get_card(n)._raw_entry[
                                "id"
                            ],
                        }
                        for i, n in enumerate(DECK)
                    ],
                    "hand": [
                        {
                            "handIndex": i,
                            "cardId": self.builder.loader.get_card(n)._raw_entry["id"],
                            "cost": self.builder.loader.get_card(n).mana_cost,
                        }
                        for i, n in enumerate(DECK[:4])
                    ],
                }
                for o in (0, 1)
            ],
        }

    def command(self, text):
        self.calls.append(text)
        if text.startswith("configure "):
            return {"ok": True}
        if text == "observe":
            return copy.deepcopy(self.ordinary())
        if text.startswith("replay-schedule-card "):
            _, owner, card, _x, _y, tick = text.split()
            cost = next(
                c["cost"]
                for c in self.ordinary()["players"][int(owner)]["hand"]
                if c["cardId"] == int(card)
            )
            self.pending.append((int(owner), cost))
            return {
                "ok": True,
                "kind": "card",
                "registeredAtTick": self.tick,
                "executeTick": int(tick),
                "generation": 1,
                "stateEpoch": 1,
                "sequence": len(self.pending),
            }
        if text.startswith("step "):
            self.tick += int(text.split()[1])
            for owner, cost in self.pending:
                if not self.reject:
                    self.resources[owner] -= cost * 10000
            self.pending = []
            return {"ok": True}
        raise AssertionError(text)

    def frame(self):
        value = self.ordinary()
        if self.wrong_tick:
            value["tick"] += 1
        return {
            "ordinary": value,
            "rich": {"schema": "native-rich-telemetry.v3"},
            "level_source": {},
        }

    def project(self, frame, history):
        if self.threat and self.tick >= 95 and not self.spawned:
            self.battle._spawn_unit_at_position(
                Position(3.5, 11.5),
                1,
                self.battle.card_loader.get_card("HogRider"),
                deploy_delay_override=0,
                snap_to_valid=False,
            )
            self.spawned = True
        return [
            exact_public_observation(
                replace(
                    self.builder.build_actor(self.battle, o), own_last_play=history[o]
                )
            )
            for o in (0, 1)
        ]


def root():
    return RootRequest(
        family_id="synthetic-prefix",
        source_episode_id="synthetic-prefix",
        root_owner=0,
        episode_seed=7,
        decks=(DECK, DECK),
        prefix_styles=("pressure", "pressure"),
        focal_card="Cannon",
        context="own_half_threat",
        start_tick=90,
        stop_tick=100,
    )


def run(native, output, claim=lambda: None, verify=lambda: None):
    return collect_prefix(
        root(),
        {"rndSeed": 7},
        output=output,
        role="opened_development",
        builder=native.builder,
        command=native.command,
        read_frame=native.frame,
        project=native.project,
        claim=claim,
        verify_producer=verify,
    )


def test_claim_precedes_mkdir_and_configure_and_selected_root_has_no_action(tmp_path):
    native = NativeDouble()
    output = tmp_path / "episode"

    def claim():
        assert not output.exists() and not native.calls

    result = run(native, output, claim)
    assert result["status"] == "selected"
    assert result["game_complete"] is False
    assert result["packet_ticks"] == [90, 95]
    assert result["selection"]["root_tick"] == 95
    assert len([c for c in native.calls if c.startswith("configure")]) == 1
    assert all(c["submitted_tick"] == 90 for c in result["commands"])
    assert all(
        c["native_acceptance_spend_evidence"] is True for c in result["commands"]
    )
    assert native.tick == 95
    assert (output / "root-frame.json").exists()
    assert (output / "seat0-public.npz").exists()
    assert "native_final" not in result and "winner" not in result


def test_failed_claim_never_creates_capture_or_configures(tmp_path):
    native = NativeDouble()

    def reject():
        raise ValueError("already claimed")

    with pytest.raises(ValueError, match="already claimed"):
        run(native, tmp_path / "episode", reject)
    assert not native.calls and not (tmp_path / "episode").exists()


def test_missing_eligibility_is_retained_without_replacement_or_horizon_extension(
    tmp_path,
):
    native = NativeDouble(threat=False)
    result = run(native, tmp_path / "episode")
    assert result["status"] == "no_eligible_root"
    assert result["prefix_complete"] is True and result["game_complete"] is False
    assert result["packet_ticks"] == [90, 95, 100]
    assert native.tick == 100
    assert len([c for c in native.calls if c.startswith("configure")]) == 1
    assert not (tmp_path / "episode" / "root-frame.json").exists()


def test_command_rejection_is_failure_with_submission_evidence_and_no_fallback(
    tmp_path,
):
    native = NativeDouble(reject=True)
    result = run(native, tmp_path / "episode")
    assert result["status"] == "failed"
    assert "no fallback" in result["failure"]["message"]
    assert native.tick == 91
    assert len(result["commands"]) == 2
    assert not any(c["native_acceptance_spend_evidence"] for c in result["commands"])
    assert (tmp_path / "episode" / "submissions.jsonl").read_text()
    assert not (tmp_path / "episode" / "accepted-commands.jsonl").read_text()
    assert json.loads((tmp_path / "episode" / "result.json").read_text()) == result


def test_bad_native_tick_is_retained_as_failed_prefix(tmp_path):
    native = NativeDouble(wrong_tick=True)
    result = run(native, tmp_path / "episode")
    assert result["status"] == "failed"
    assert "expected native tick 90" in result["failure"]["message"]
    assert result["packet_ticks"] == []
    assert native.tick == 90


def test_source_drift_after_prefix_cannot_claim_selected_completion(tmp_path):
    native = NativeDouble()
    count = 0

    def verify():
        nonlocal count
        count += 1
        if count == 2:
            raise ValueError("source changed")

    result = run(native, tmp_path / "episode", verify=verify)
    assert result["status"] == "failed"
    assert result["producer_sources_unchanged"] is False
    assert result["prefix_complete"] is False


def test_transport_receipt_retains_exact_commands_and_spend_snapshots(tmp_path):
    import gzip

    native = NativeDouble()
    result = run(native, tmp_path / "episode")
    with gzip.open(tmp_path / "episode" / "transport.jsonl.gz", "rt") as stream:
        rows = [json.loads(line) for line in stream]
    assert len(rows) == 1
    row = rows[0]
    assert (row["tick"], row["before"]["tick"], row["after"]["tick"]) == (90, 90, 91)
    assert row["commands"] == [r["submitted_command"] for r in result["commands"]]
    assert row["receipts"] == [r["schedule_receipt"] for r in result["commands"]]
    for selected in row["selected"]:
        owner = selected["owner"]
        delta = (
            row["before"]["players"][owner]["elixirRaw"]
            - row["after"]["players"][owner]["elixirRaw"]
        ) / 10000
        assert delta == selected["cost"]


def test_declared_reserve_only_changes_root_owner_prefix_action(tmp_path):
    native = NativeDouble()
    native.battle.players[0].elixir = 7
    native.battle.players[1].elixir = 7
    request = RootRequest(**{**root().model_dump(), "prefix_owner_min_elixir": 8})
    output = tmp_path / "episode"
    result = collect_prefix(
        request,
        {"rndSeed": 7},
        output=output,
        role="opened_development",
        builder=native.builder,
        command=native.command,
        read_frame=native.frame,
        project=native.project,
        claim=lambda: None,
        verify_producer=lambda: None,
    )
    assert result["status"] == "selected"
    assert result["selection"]["root_tick"] == 95
    assert [c["owner"] for c in result["commands"]] == [1]
    decisions = json.loads((output / "decisions.json").read_text())
    own = next(d for d in decisions if d["owner"] == 0)
    other = next(d for d in decisions if d["owner"] == 1)
    assert own["action"] == 2304 and own["ordinary_action"] != 2304
    assert own["prefix_reserve_applied"] is True
    assert other["action"] != 2304 and other["prefix_reserve_applied"] is False
    # The reserve does not alter root candidate legality or force8elixir at root.
    assert result["selection"]["candidates"][0]["action_id"] != 2304

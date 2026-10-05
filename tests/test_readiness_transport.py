"""Retained command evidence is independently checked, never inferred from flags."""

import copy
import gzip
import json
from pathlib import Path

import pytest

from clasher.data import CardDataLoader
from clasher.rl.readiness_transport import (
    audit_native_transport_row,
    compact_transport_snapshot,
)


@pytest.fixture
def rows(tmp_path):
    fixtures = Path(__file__).parent / "fixtures"
    snapshots = json.loads(
        (fixtures / "native_hand_refill_15_535_86.json").read_text()
    )["snapshots"]
    before = next(s for s in snapshots if s["tick"] == 110)
    after = next(s for s in snapshots if s["tick"] == 111)
    data = tmp_path / "gamedata.json"
    data.write_bytes(
        gzip.decompress(
            (fixtures / "native_gamedata_15_535_86_daa58b28.json.gz").read_bytes()
        )
    )
    row = {
        "tick": 110,
        "selected": [
            {"owner": i, "action": 2304, "name": None, "cost": None, "xy": None}
            for i in (0, 1)
        ],
        "receipts": [],
        "commands": [],
        "before": compact_transport_snapshot(before),
        "after": compact_transport_snapshot(after),
    }
    decision = {
        "tick": 110,
        "actions": [2304, 2304],
        "native_frame": {"ordinary": before},
    }
    return row, decision, CardDataLoader(data)


def test_actual_waiting_refill_snapshots_pass_without_a_fake_command(rows):
    audit_native_transport_row(*rows)


def with_synthetic_play(rows):
    row, decision, loader = copy.deepcopy(rows)
    # Synthetic command/spend over the real HUD geometry: a checker unit test,
    # not a native execution or a measurement receipt.
    row["selected"][0] = {
        "owner": 0,
        "action": 687,
        "name": "Skeletons",
        "cost": 1,
        "xy": [3.5, 6.5],
    }
    decision["actions"][0] = 687
    row["after"]["players"][0]["elixirRaw"] = (
        row["before"]["players"][0]["elixirRaw"] - 10000
    )
    row["commands"] = ["replay-schedule-card 0 26000010 3500 6500 111"]
    row["receipts"] = [
        {
            "ok": True,
            "sequence": 1,
            "kind": "card",
            "registeredAtTick": 110,
            "executeTick": 111,
            "generation": row["before"]["generation"],
            "stateEpoch": row["before"]["stateEpoch"],
        }
    ]
    return row, decision, loader


def test_exact_selected_card_coordinates_receipt_and_spend_agree(rows):
    audit_native_transport_row(*with_synthetic_play(rows))


@pytest.mark.parametrize(
    "mutation",
    [
        "tick",
        "command",
        "coordinate",
        "missing_receipt",
        "no_spend",
        "shifted_slot",
        "secret_wait",
    ],
)
def test_transport_contradictions_reject_even_if_a_producer_would_claim_success(
    rows, mutation
):
    row, decision, loader = with_synthetic_play(rows)
    if mutation == "tick":
        row["receipts"][0]["executeTick"] = 112
    elif mutation == "command":
        row["commands"][0] = "replay-schedule-card 0 26000003 3500 6500 111"
    elif mutation == "coordinate":
        row["selected"][0]["xy"] = [4.5, 6.5]
    elif mutation == "missing_receipt":
        row["receipts"] = []
    elif mutation == "no_spend":
        row["after"]["players"][0]["elixirRaw"] = row["before"]["players"][0][
            "elixirRaw"
        ]
    elif mutation == "shifted_slot":
        row["selected"][0]["action"] = 111
        decision["actions"][0] = 111
    else:
        row["selected"][1]["name"] = "Giant"
    with pytest.raises(ValueError):
        audit_native_transport_row(row, decision, loader)


def test_scalar_packet_roundtrip_and_sealed_action_binding(tmp_path):
    from clasher.battle import BattleState
    from clasher.rl.native_public_observation import (
        NativeProjectileCatalog,
        public_reference_builder,
    )
    from clasher.rl.public_observation import reference_public_observation
    from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
    from clasher.rl.readiness_execution import file_sha, packet_sha
    from clasher.rl.readiness_transport import (
        audit_scalar_decisions,
        public_packet_record,
        restore_public_packet,
    )

    catalog_path = Path(__file__).parent / "fixtures/native_projectiles_15_535_86.csv"
    catalog = NativeProjectileCatalog.from_csv(
        catalog_path, expected_sha256=file_sha(catalog_path)
    )
    loader = CardDataLoader()
    builder = public_reference_builder(loader, catalog, public_contract_version=4)
    battle = BattleState(card_loader=loader)
    for player in battle.players:
        player.hand = ["HogRider", "Cannon", "Fireball", "Skeletons"]
        player.elixir = 10
    battle.tick = 90
    packets = [
        reference_public_observation(builder.build_actor(battle, owner))
        for owner in (0, 1)
    ]
    for packet in packets:
        assert packet_sha(
            restore_public_packet(public_packet_record(packet))
        ) == packet_sha(packet)
    opponent = PublicScriptedOpponent(builder, style="pressure").select_action(
        packets[1]
    )
    row = {
        "tick": 90,
        "actions": [2304, opponent],
        "public_packets": [public_packet_record(p) for p in packets],
        "public_sha256": [packet_sha(p) for p in packets],
    }
    provenance = {
        "catalog_path": str(catalog_path),
        "catalog_sha256": file_sha(catalog_path),
        "root_owner": 0,
        "root_action_id": 2304,
        "root_tick": 90,
        "job": {"condition": "balanced/pressure"},
    }
    with gzip.open(tmp_path / "decisions.jsonl.gz", "wt") as stream:
        stream.write(json.dumps(row) + "\n")
    assert audit_scalar_decisions(tmp_path, loader, provenance=provenance) == 1
    # Relabeling a legitimate wait stream as another root candidate must fail.
    with pytest.raises(ValueError, match="sealed root candidate"):
        audit_scalar_decisions(
            tmp_path, loader, provenance={**provenance, "root_action_id": 237}
        )
    # A changed opponent style/action cannot hide behind a consistent log pair.
    row["actions"][1] = 2304
    with gzip.open(tmp_path / "decisions.jsonl.gz", "wt") as stream:
        stream.write(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="continuation styles"):
        audit_scalar_decisions(tmp_path, loader, provenance=provenance)

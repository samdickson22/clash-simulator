"""Spell damage attribution against native combat events recorded in evidence v2.

level-extension-evidence-v2 cast Fireball five times per probe; every cast hit
an attacking troop, yet coverage never saw it and the verifier reported
"native level/type coverage is incomplete". Native names the caster's King
Tower as a Fireball hit's ``source`` and the Fireball projectile as its
``immediateSource``; the collector and verifier read ``source.cardId`` only.
The fixture holds unmodified rows from those frames.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import sys

import pytest

from clasher.data import CardDataLoader
from clasher.dynamic_spells import create_spell_from_json
from clasher.paths import gamedata_path, project_root
from clasher.rl.readiness_level_extension import SPELL_CHECKS, _spell_damage_attribution

ROOT = project_root()
sys.path.insert(0, str(ROOT / "scripts"))

import level_extension_common as common  # noqa: E402

FIXTURE = ROOT / "tests/fixtures/level_extension_native_spell_events_15_535_86.json"
RECORDED = json.loads(FIXTURE.read_text())
LOADER = CardDataLoader(gamedata_path())
SPELL_IDS = {LOADER.get_card(name)._raw_entry["id"]: name for name in SPELL_CHECKS}


def recorded_rows():
    for probe, record in RECORDED["probes"].items():
        for row in record["events"]:
            yield int(probe), record, row


def legacy_source_only(event):
    """The v2 collector/native-final-v7 verifier rule: ``source.cardId`` only."""
    source, target = event.get("source") or {}, event.get("target") or {}
    return (
        event.get("kind") == "damage" and event.get("pool") == "hitpoints"
        and source.get("validated") is True and target.get("validated") is True
        and source.get("cardId") in SPELL_IDS
        and isinstance(target.get("cardId"), int) and 26000000 <= target["cardId"] < 28000000
    )


def fireball(probe: int) -> dict:
    return next(r["event"] for p, _record, r in recorded_rows() if p == probe and r["expected"] == "Fireball")


def test_fixture_rows_are_unmodified_native_rows():
    for probe, record in RECORDED["probes"].items():
        path = ROOT / record["frames"]["path"]
        if not path.exists():
            pytest.skip("evidence-v2 frames are not present in this checkout")
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["frames"]["sha256"]
        events = {}
        with gzip.open(path, "rt") as stream:
            for line in stream:
                for event in json.loads(line)["rich"]["combatEvents"]["events"]:
                    events[event["sequence"]] = event
        for row in record["events"]:
            assert events[row["event"]["sequence"]] == row["event"], (probe, row["frame_tick"])


def test_recorded_native_spell_hits_are_attributed_to_their_caster_and_spell():
    for probe, record, row in recorded_rows():
        event = row["event"]
        found = common.native_spell_attribution(event, SPELL_IDS)
        verifier = _spell_damage_attribution(event, SPELL_IDS)
        if row["expected"] is None:
            assert found is None and verifier is None, (probe, row["frame_tick"])
            continue
        assert found is not None, (probe, row["expected"])
        assert SPELL_IDS[found["card_id"]] == row["expected"]
        assert found["owner"] == record["caster"]
        assert verifier == (record["caster"], found["card_id"])
        expected_via = "king_tower_projectile" if row["expected"] == "Fireball" else "source"
        assert found["attribution"] == expected_via
        # The native damage equals the verifier's level-scaled value.
        spell = create_spell_from_json(LOADER.get_card(row["expected"])._raw_entry,
                                       level=record["plan"]["card_level"])
        assert event["requestedAmount"] == spell.damage


def test_v2_source_only_rule_misses_every_recorded_fireball():
    """Regression for v2: Zap and Log counted, Fireball never did."""
    for _probe, _record, row in recorded_rows():
        if row["expected"] in ("Zap", "Log"):
            assert legacy_source_only(row["event"])
        elif row["expected"] == "Fireball":
            event = row["event"]
            assert not legacy_source_only(event)
            assert event["source"]["cardId"] == -1 and event["source"]["objectKind"] == 5
            assert event["immediateSource"]["cardId"] == 28000000
            assert event["immediateSource"]["objectKind"] == 4


def test_coverage_driver_counts_a_recorded_fireball_for_the_defender():
    for probe, record, row in recorded_rows():
        if row["expected"] != "Fireball":
            continue
        driver = common.CoverageDriver(LOADER, attacker=record["attacker"],
                                       card_level=record["plan"]["card_level"])
        frame = {
            "ordinary": {"tick": row["frame_tick"], "objects": []},
            "level_source": {"levels": {}},
            "rich": {"combatEvents": {"complete": True, "hookSetAttested": True, "events": [row["event"]]}},
        }
        driver.observe(frame)
        assert driver.spells_seen == {"Fireball": row["frame_tick"]}, probe
        coverage = driver.coverage()
        assert coverage["spells_first_damage_attribution"] == {"Fireball": "king_tower_projectile"}
        # The attacker seat's own Fireball would not count for the defender.
        other = common.CoverageDriver(LOADER, attacker=1 - record["attacker"],
                                      card_level=record["plan"]["card_level"])
        other.observe(frame)
        assert other.spells_seen == {}


@pytest.mark.parametrize("mutation", [
    "princess_source", "owner_mismatch", "tower_arrow", "not_projectile", "unvalidated_immediate",
    "shield_pool", "crown_target",
])
def test_king_tower_projectile_attribution_is_narrow(mutation):
    event = copy.deepcopy(fireball(0))
    assert common.native_spell_attribution(event, SPELL_IDS) is not None
    if mutation == "princess_source":
        event["source"]["position"] = [3500, 25500]
    elif mutation == "owner_mismatch":
        event["immediateSource"]["owner"] = 0
    elif mutation == "tower_arrow":
        event["immediateSource"]["cardId"] = -1
    elif mutation == "not_projectile":
        event["immediateSource"]["objectKind"] = 3
    elif mutation == "unvalidated_immediate":
        event["immediateSource"]["validated"] = False
    elif mutation == "shield_pool":
        event["pool"] = "built_in_shield"
    elif mutation == "crown_target":
        event["target"]["cardId"] = -1
    assert common.native_spell_attribution(event, SPELL_IDS) is None
    assert _spell_damage_attribution(event, SPELL_IDS) is None


def test_all_v2_fireball_hitpoint_hits_are_now_attributed():
    """Every recorded v2 Fireball HP hit (5 casts per probe; in probes 0/2 two hit
    only the Dark Prince's built-in shield, which is not hitpoints damage)."""
    base = ROOT / "reports/strategy_council_20260928/m0/level-extension-evidence-v2/native"
    if not (base / "probe-0/frames.jsonl.gz").exists():
        pytest.skip("evidence-v2 frames are not present in this checkout")
    for probe in range(4):
        caster = 1 - probe % 2
        seen: dict[int, dict] = {}
        with gzip.open(base / f"probe-{probe}/frames.jsonl.gz", "rt") as stream:
            for line in stream:
                for row in common.spell_damage_events(json.loads(line)["rich"], SPELL_IDS):
                    seen.setdefault(row["event"]["sequence"], row)
        fireballs = [r for r in seen.values() if SPELL_IDS[r["card_id"]] == "Fireball"]
        assert len(fireballs) == (3, 5, 3, 5)[probe], probe
        assert {r["owner"] for r in seen.values()} == {caster}
        assert {r["attribution"] for r in fireballs} == {"king_tower_projectile"}

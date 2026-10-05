"""Synthetic evidence tests; these fixtures never grant a real admission."""

import copy
import gzip
import json
import runpy
from pathlib import Path

import pytest

from clasher.data import CardDataLoader
from clasher.dynamic_spells import create_spell_from_json
from clasher.paths import gamedata_path, project_root
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.readiness_execution import canonical_sha, file_sha
from clasher.rl.readiness_level_extension import (
    ANCHORS,
    BODY_CHECKS,
    PROBE_PLANS,
    SESSION_FREQUENCY,
    SESSION_SCHEMA,
    SPELL_CHECKS,
    FilePin,
    LevelExtensionDeclaration,
    LevelExtensionReceipt,
    LevelFamilyScope,
    LevelProbeDeclaration,
    NativeLevelPlan,
    NativeLevelProbe,
    VerifiedLevelExtension,
    configure_native_levels,
    verify_level_extension_receipt,
)
from clasher.rl.training_readiness_v2 import APPROVED_STRATEGY_SHA
from clasher.tower_scaling import tower_stat

LEVEL_DIR = project_root() / "reports/strategy_council_20260928/m0/level-extension"
DECK = (*BODY_CHECKS, *SPELL_CHECKS, "HogRider")
ATTESTATION = {"synthetic_test_only": True}
ATTESTATION_SHA = canonical_sha({"ok": True, "attestation": ATTESTATION})
IDENTITY = {"generation": 1, "stateEpoch": 1, "synthetic_test_only": True}
LOADER = CardDataLoader()
SPACE = DiscreteTileActionSpace()


def cid(name):
    return LOADER.get_card(name)._raw_entry["id"]


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")
    return FilePin(path=str(path), sha256=file_sha(path))


def write_lines(path, rows):
    data = "".join(json.dumps(row) + "\n" for row in rows).encode()
    path.write_bytes(gzip.compress(data) if path.name.endswith(".gz") else data)
    return FilePin(path=str(path), sha256=file_sha(path))


def tower_hp(level, slot):
    return tower_stat("KingTower" if slot == 2 else "PrincessTower", "hitpoints", level)


def ending(path, tick, levels_by_owner, enemy, deficit):
    """Crown-anchored ending frame; `levels_by_owner[o][slot]` sets maximum HP."""
    objects = []
    for (owner, x, y), slot in ANCHORS.items():
        hp = tower_hp(levels_by_owner[owner][slot], slot)
        if owner == enemy and slot == 1:
            hp -= deficit
        objects.append({"cardId": -1, "owner": owner, "x": x, "y": y, "hp": hp})
    return write(path, {"tick": tick, "objects": objects})


def hand(first):
    rest = [n for n in ("HogRider", "Knight", "Zap", "Cannon") if n != first][:3]
    return [
        {"handIndex": i, "cardId": cid(n), "cost": 3}
        for i, n in enumerate((first, *rest))
    ]


def players(first0, first1, elixir=100000):
    return [
        {"owner": 0, "elixirRaw": elixir, "hand": hand(first0)},
        {"owner": 1, "elixirRaw": elixir, "hand": hand(first1)},
    ]


def transport(tick, plays, receipts_start):
    """One re-auditable decision/transport pair with real schedule receipts."""
    selected, commands, receipts = [], [], []
    for owner, name in enumerate(plays):
        if name is None:
            selected.append(
                {"owner": owner, "action": 2304, "name": None, "cost": None, "xy": None}
            )
            continue
        action = 300
        pos = SPACE.decode_action(action, owner).position
        xy = [pos.x, pos.y]
        selected.append(
            {"owner": owner, "action": action, "name": name, "cost": 3, "xy": xy}
        )
        commands.append(
            f"replay-schedule-card {owner} {cid(name)} {round(xy[0] * 1000)} "
            f"{round(xy[1] * 1000)} {tick + 1}"
        )
        receipts.append(
            {
                "ok": True,
                "kind": "card",
                "registeredAtTick": tick,
                "executeTick": tick + 1,
                "generation": 1,
                "stateEpoch": 1,
                "sequence": receipts_start + len(receipts),
            }
        )
    firsts = [name or "HogRider" for name in plays]
    before = {
        "tick": tick,
        "generation": 1,
        "stateEpoch": 1,
        "players": players(*firsts),
    }
    after_players = players(*firsts)
    for owner, name in enumerate(plays):
        if name is not None:
            after_players[owner]["elixirRaw"] -= 30000
    after = {
        "tick": tick + 1,
        "generation": 1,
        "stateEpoch": 1,
        "players": after_players,
    }
    row = {
        "tick": tick,
        "before": before,
        "after": after,
        "selected": selected,
        "receipts": receipts,
        "commands": commands,
    }
    actions = [choice["action"] for choice in selected]
    return before, row, actions


def probe_files(tmp_path, i, plan, *, mutate=None):
    """Raw native frames, session, decisions and command rows for one probe."""
    rows, decisions, frames = [], [], []
    plays = [
        (BODY_CHECKS[k], SPELL_CHECKS[k] if k < len(SPELL_CHECKS) else None)
        for k in range(len(BODY_CHECKS))
    ]
    sequence = 0
    for k, pair in enumerate(plays):
        before, row, actions = transport(5 * k, pair, sequence)
        sequence += len(row["receipts"])
        rows.append(row)
        ordinary = {
            "tick": 5 * k,
            "generation": 1,
            "stateEpoch": 1,
            "objects": [],
            "players": copy.deepcopy(before["players"]),
        }
        decisions.append(
            {
                "tick": 5 * k,
                "native_frame": {"ordinary": copy.deepcopy(ordinary)},
                "actions": actions,
            }
        )
        frames.append({"ordinary": ordinary, "levels": {}, "events": []})
    # Tick-zero full Crown observation, also retained in the decision frame.
    for (owner, x, y), slot in ANCHORS.items():
        level = plan.tower_levels(owner)[slot]
        hp = tower_hp(level, slot)
        oid = len(frames[0]["ordinary"]["objects"]) + 1
        frames[0]["ordinary"]["objects"].append(
            {
                "nativeObjectId": oid,
                "owner": owner,
                "cardId": -1,
                "x": x,
                "y": y,
                "hp": hp,
                "maxHp": hp,
            }
        )
        frames[0]["levels"][str(oid)] = level
    decisions[0]["native_frame"]["ordinary"] = copy.deepcopy(frames[0]["ordinary"])
    final = {"tick": 20, "generation": 1, "stateEpoch": 1, "objects": [], "players": []}
    final_levels, events = {}, []
    for name in (*BODY_CHECKS, "HogRider"):
        card = copy.copy(LOADER.get_card(name))
        card.level = plan.card_level
        oid = 100 + len(final["objects"])
        final["objects"].append(
            {
                "nativeObjectId": oid,
                "owner": 0,
                "cardId": card._raw_entry["id"],
                "x": 8000,
                "y": 12000,
                "hp": card.scaled_hitpoints,
                "maxHp": card.scaled_hitpoints,
            }
        )
        final_levels[str(oid)] = plan.card_level
    for name in SPELL_CHECKS:
        spell = create_spell_from_json(
            LOADER.get_card(name)._raw_entry, level=plan.card_level
        )
        events.append(
            {
                "kind": "damage",
                "pool": "hitpoints",
                "generation": 1,
                "stateEpoch": 1,
                "requestedAmount": spell.damage,
                "source": {"validated": True, "cardId": cid(name), "owner": 1},
                "target": {"validated": True, "cardId": 26000000, "owner": 0},
            }
        )
    frames.append({"ordinary": final, "levels": final_levels, "events": events})
    lines = []
    for read_index, frame in enumerate(frames, start=1):
        lines.append(
            {
                "ordinary": frame["ordinary"],
                "level_source": {
                    "ordinary": frame["ordinary"],
                    "levels": frame["levels"],
                    "attestation": ATTESTATION,
                    "reader_sha256": "b" * 64,
                    "verified_session": {
                        "schema": SESSION_SCHEMA,
                        "session_id": str(i),
                        "read_index": read_index,
                        "runtime_identity": IDENTITY,
                    },
                },
                "rich": {
                    "combatEvents": {
                        "events": frame["events"],
                        "complete": True,
                        "hookSetAttested": True,
                    }
                },
            }
        )
    session = {
        "schema": SESSION_SCHEMA,
        "session_id": str(i),
        "status": "verified",
        "failures": [],
        "verification_frequency": SESSION_FREQUENCY,
        "expected_attestation_sha256": ATTESTATION_SHA,
        "start_attestation_sha256": ATTESTATION_SHA,
        "end_attestation_sha256": ATTESTATION_SHA,
        "runtime_identity": IDENTITY,
        "reader_sha256": "b" * 64,
        "reads_completed": len(lines),
    }
    if mutate is not None:
        mutate(lines=lines, session=session, decisions=decisions, rows=rows)
    return {
        "frames": write_lines(tmp_path / f"frames-{i}.jsonl.gz", lines),
        "verified_read_session": write(tmp_path / f"session-{i}.json", session),
        "transport_decisions": write_lines(
            tmp_path / f"decisions-{i}.jsonl.gz", decisions
        ),
        "transport_rows": write_lines(tmp_path / f"transport-{i}.jsonl.gz", rows),
    }


def scalar_study(tmp_path, base_sha, declaration_sha, *, mutate=None, extra=None):
    """Two independently recomputable independent-card scalar cases."""
    cases = []
    for index, (body_level, spell_level, towers) in enumerate(
        [(10, 12, [10, 12]), (12, 10, [12, 11])]
    ):
        seat = {
            **{n: body_level for n in BODY_CHECKS},
            **{n: spell_level for n in SPELL_CHECKS},
            "HogRider": 11,
        }
        levels = [seat, {n: 11 for n in DECK}]
        observation = {"towers": [], "bodies": [], "spells": []}
        for owner in (0, 1):
            for slot in range(3):
                observation["towers"].append(
                    {
                        "owner": owner,
                        "slot": slot,
                        "level": towers[owner],
                        "maxHp": tower_hp(towers[owner], slot),
                    }
                )
        for name in BODY_CHECKS:
            card = copy.copy(LOADER.get_card(name))
            card.level = body_level
            observation["bodies"].append(
                {
                    "owner": 0,
                    "card": name,
                    "level": body_level,
                    "maxHp": card.scaled_hitpoints,
                }
            )
        for name in SPELL_CHECKS:
            spell = create_spell_from_json(
                LOADER.get_card(name)._raw_entry, level=spell_level
            )
            observation["spells"].append(
                {
                    "owner": 0,
                    "card": name,
                    "level": spell_level,
                    "requestedAmount": spell.damage,
                }
            )
        case = {
            "card_levels": levels,
            "tower_levels": towers,
            "root_owner": 0,
            "observation": observation,
            "branches": [],
        }
        for candidate in range(2):
            case["branches"].append(
                {
                    "candidate": candidate,
                    "root_tick": 100,
                    "ending_levels": [[towers[0]] * 3, [towers[1]] * 3],
                    "deficit": 1000 - 300 * candidate,
                }
            )
        cases.append(case)
    if mutate is not None:
        mutate(cases)
    for index, case in enumerate(cases):
        case["observation"] = write(
            tmp_path / f"scalar-observation-{index}.json", case["observation"]
        ).model_dump(mode="json")
        for branch in case["branches"]:
            pin = ending(
                tmp_path / f"scalar-end-{index}-{branch['candidate']}.json",
                branch["root_tick"] + 200,
                branch.pop("ending_levels"),
                1 - case["root_owner"],
                branch.pop("deficit"),
            )
            branch["ending_frame"] = pin.model_dump(mode="json")
    return write(
        tmp_path / "scalar-study.json",
        {
            "schema": "readiness-bounded-scalar-adaptation-v2",
            "base_admission_sha256": base_sha,
            "native_declaration_sha256": declaration_sha,
            "gamedata_sha256": file_sha(gamedata_path()),
            "cases": cases,
            **(extra or {}),
        },
    )


def fixture(tmp_path, *, probe_mutations=None, deficit=None):
    original = json.loads(
        (
            project_root()
            / "reports/strategy_council_20260928/m0/root-bank/native-configs/configs/episode-00.json"
        ).read_text()
    )
    for owner in (0, 1):
        original["battle"][f"deck{owner}"]["sp"] = [{"d": cid(n)} for n in DECK]
    configs = [configure_native_levels(original, p) for p in PROBE_PLANS]
    proto = runpy.run_path(str(project_root() / "tests/test_training_readiness_v2.py"))[
        "protocol"
    ]()
    nominal = write(tmp_path / "nominal.json", proto.model_dump(mode="json"))
    base = write(
        tmp_path / "base.json",
        {"protocol_sha256": proto.sha256, "synthetic_test_only": True},
    )
    declaration = LevelExtensionDeclaration(
        base_admission_sha256=base.sha256,
        native_attestation_sha256=ATTESTATION_SHA,
        gamedata_sha256=file_sha(gamedata_path()),
        probes=tuple(
            LevelProbeDeclaration(plan=p, config_sha256=canonical_sha(c))
            for p, c in zip(PROBE_PLANS, configs)
        ),
    )
    declared = write(tmp_path / "declaration.json", declaration.model_dump(mode="json"))
    probes = []
    for i, (plan, config) in enumerate(zip(PROBE_PLANS, configs)):
        mutate = (probe_mutations or {}).get(i)
        probes.append(
            NativeLevelProbe(
                config=write(tmp_path / f"config-{i}.json", config),
                **probe_files(tmp_path, i, plan, mutate=mutate),
            )
        )
    branches = []
    for p, plan in enumerate(PROBE_PLANS):
        levels = [plan.tower_levels(0), plan.tower_levels(1)]
        for c in range(2):
            for a in range(2):
                for e in ("scalar", "reference"):
                    amount = 1000 - 300 * a if deficit is None else deficit(p, a, e)
                    pin = ending(
                        tmp_path / f"end-{p}-{c}-{a}-{e}.json",
                        300,
                        levels,
                        1 - p % 2,
                        amount,
                    )
                    branches.append(
                        {
                            "probe": p,
                            "condition": c,
                            "candidate": a,
                            "engine": e,
                            "root_tick": 100,
                            "root_owner": p % 2,
                            "public_legal": True,
                            "config_sha256": declaration.probes[p].config_sha256,
                            "ending_frame": pin.model_dump(mode="json"),
                        }
                    )
    rankings = write(
        tmp_path / "rankings.json",
        {
            "schema": "readiness-level-rankings-v1",
            "declaration_sha256": declared.sha256,
            "horizon_ticks": 200,
            "conditions": ["balanced/pressure", "defense/balanced"],
            "branches": branches,
        },
    )
    files = [
        project_root() / "src/clasher/rl/readiness_level_extension.py",
        project_root() / "src/clasher/rl/readiness_transport.py",
        project_root() / "src/clasher/rl/native_command_checks.py",
        *[
            project_root() / "src/clasher" / n
            for n in (
                "tower_scaling.py",
                "balance.py",
                "stat_scaling.py",
                "data.py",
                "dynamic_spells.py",
            )
        ],
    ]
    receipt = LevelExtensionReceipt(
        declaration=declared,
        base_admission=base,
        nominal_protocol=nominal,
        ranking_checks=rankings,
        gamedata=FilePin(path=str(gamedata_path()), sha256=file_sha(gamedata_path())),
        source_pins={str(p): file_sha(p) for p in files},
        probes=tuple(probes),
    )
    path = tmp_path / "extension.json"
    path.write_text(receipt.model_dump_json(indent=2) + "\n")
    return path, receipt, base


def independent(tmp_path, receipt, base, *, mutate=None, extra=None):
    scalar = scalar_study(
        tmp_path, base.sha256, receipt.declaration.sha256, mutate=mutate, extra=extra
    )
    evidence = write(tmp_path / "decision-evidence.json", {"synthetic_test_only": True})
    decision = write(
        tmp_path / "decision.json",
        {
            "schema": "readiness-level-randomization-decision-v1",
            "status": "approved",
            "strategy_sha256": APPROVED_STRATEGY_SHA,
            "base_admission_sha256": base.sha256,
            "native_declaration_sha256": receipt.declaration.sha256,
            "level_sampling_scope": "independent_cards",
            "scalar_adaptation_sha256": scalar.sha256,
            "decision_evidence": evidence.model_dump(mode="json"),
        },
    )
    return receipt.model_copy(
        update={"protocol_decision": decision, "scalar_adaptation": scalar}
    ), scalar


def rewrite(path, receipt):
    path.write_text(receipt.model_dump_json())


def verify(path, base):
    return verify_level_extension_receipt(path, base_admission_sha256=base.sha256)


def test_normalizer_uses_owner_full_crown_hp_at_actual_levels():
    assert (
        NativeLevelPlan(card_level=10, king_levels=(10, 10)).starting_crown_hp(0)
        == 9964
    )
    assert (
        NativeLevelPlan(card_level=11, king_levels=(11, 11)).starting_crown_hp(0)
        == 10928
    )
    assert (
        NativeLevelPlan(card_level=12, king_levels=(12, 12)).starting_crown_hp(0)
        == 11996
    )
    scope = LevelFamilyScope(
        root_owner=0, levels=NativeLevelPlan(card_level=10, king_levels=(12, 10))
    )
    assert scope.starting_crown_hp == 10876
    assert scope.normalized_margin(500, 300) == 200 / 10876
    with pytest.raises(ValueError):
        scope.normalized_margin(-1, 0)


def test_prospective_configs_are_unexecuted_and_encode_declared_plans():
    manifest = json.loads((LEVEL_DIR / "prospective-configs/manifest.json").read_text())
    assert manifest["training_permission"] is None
    assert manifest["native_scope"] == "uniform_cards_asymmetric_kings"
    assert manifest["status"] in {
        "draft_missing_nominal_admission",
        "declared_not_executed",
    }
    assert manifest["independent_acceptance_family_count"] == 0
    assert len(manifest["probes"]) == 4
    for row, plan in zip(manifest["probes"], PROBE_PLANS, strict=True):
        path = LEVEL_DIR / "prospective-configs" / row["config_path"]
        config = json.loads(path.read_text())
        assert NativeLevelPlan.model_validate_json(json.dumps(row["plan"])) == plan
        assert canonical_sha(config) == row["config_sha256"]
        assert file_sha(path) == row["config_file_sha256"]
        assert configure_native_levels(config, plan) == config
        assert row["starting_crown_hp_by_owner"] == [
            plan.starting_crown_hp(o) for o in (0, 1)
        ]
    # No extension evidence or admission exists for these unexecuted probes.
    assert not list(LEVEL_DIR.rglob("*receipt*"))
    assert not list(LEVEL_DIR.rglob("*admission*"))


def test_uniform_native_evidence_does_not_grant_independent_training(tmp_path):
    path, receipt, base = fixture(tmp_path)
    verified = verify(path, base)
    assert isinstance(verified, VerifiedLevelExtension)
    assert verified.verified_levels == (10, 11, 12)
    assert verified.nominal_levels == (11,)
    assert verified.native_level_scope == "uniform_cards_asymmetric_kings"
    assert verified.native_measured_card_levels == (10, 12)
    assert verified.native_measured_king_levels == (10, 12)
    assert verified.native_independent_card_parity is False
    assert verified.level_sampling_scope == "uniform_cards"
    assert verified.mixed_level_training_levels == ()
    assert verified.receipt_sha256 == file_sha(path)
    # The unverified receipt itself exposes no admitted scope.
    assert not hasattr(receipt, "verified_levels")
    assert not hasattr(receipt, "level_sampling_scope")


def test_changed_native_artifact_and_wrong_base_revoke_extension(tmp_path):
    path, receipt, base = fixture(tmp_path)
    with pytest.raises(ValueError, match="another base"):
        verify_level_extension_receipt(path, base_admission_sha256="0" * 64)
    Path(receipt.probes[0].frames.path).write_text("{}\n")
    with pytest.raises(ValueError, match="artifact changed"):
        verify(path, base)


def test_scaling_must_use_the_pinned_ruleset(tmp_path, monkeypatch):
    import clasher.rl.readiness_level_extension as module

    path, receipt, base = fixture(tmp_path)
    other = write(tmp_path / "other-gamedata.json", {"synthetic_test_only": True})
    monkeypatch.setattr(module, "gamedata_path", lambda: Path(other.path))
    with pytest.raises(ValueError, match="pinned ruleset"):
        verify(path, base)
    monkeypatch.undo()
    pins = dict(receipt.source_pins)
    pins.pop(str(project_root() / "src/clasher/balance.py"))
    rewrite(path, receipt.model_copy(update={"source_pins": pins}))
    with pytest.raises(ValueError, match="source pins are required"):
        verify(path, base)


def test_tampered_transport_rows_revoke_extension(tmp_path):
    path, receipt, base = fixture(tmp_path)
    Path(receipt.probes[2].transport_rows.path).write_bytes(gzip.compress(b"{}\n"))
    with pytest.raises(ValueError, match="artifact changed"):
        verify(path, base)


def test_receipt_cannot_self_assert_pass_or_widen_native_scope(tmp_path):
    path, receipt, base = fixture(tmp_path)
    data = json.loads(receipt.model_dump_json())
    for extra in (
        {"status": "passed"},
        {"verified_levels": [10, 11, 12]},
        {"level_sampling_scope": "independent_cards"},
        {"native_level_scope": "independent_cards"},
        {"native_level_scope": "per_card_levels"},
    ):
        path.write_text(json.dumps({**data, **extra}))
        with pytest.raises(ValueError):
            verify(path, base)


def test_repinned_raw_frames_with_wrong_scaled_hp_are_recomputed(tmp_path):
    def wrong_hp(lines, **_):
        body = lines[-1]["ordinary"]["objects"][0]
        body["maxHp"] += 1

    path, _, base = fixture(tmp_path, probe_mutations={3: wrong_hp})
    with pytest.raises(ValueError, match="scalar scaling"):
        verify(path, base)


def test_native_per_card_level_variation_is_not_uniform_scope(tmp_path):
    def hog_at_other_level(lines, **_):
        final = lines[-1]["level_source"]
        hog = final["ordinary"]["objects"][-1]
        assert hog["cardId"] == cid("HogRider")
        final["levels"][str(hog["nativeObjectId"])] = 11

    path, _, base = fixture(tmp_path, probe_mutations={0: hog_at_other_level})
    with pytest.raises(ValueError, match="uniform card level"):
        verify(path, base)
    config = json.loads((tmp_path / "config-0.json").read_text())
    config["battle"]["deck0"]["sp"][0]["l"] = 12
    with pytest.raises(ValueError, match="base-form"):
        configure_native_levels(config, PROBE_PLANS[0])


def test_session_with_failures_or_unverified_reads_is_rejected(tmp_path):
    def failed(session, **_):
        session["failures"] = ["ValueError: identity changed"]

    path, _, base = fixture(tmp_path, probe_mutations={1: failed})
    with pytest.raises(ValueError, match="boundary attestation"):
        verify(path, base)

    def replayed_read(lines, **_):
        lines[2]["level_source"]["verified_session"]["read_index"] = 2

    path, _, base = fixture(tmp_path, probe_mutations={1: replayed_read})
    with pytest.raises(ValueError, match="verified read session"):
        verify(path, base)


def test_transport_is_reaudited_not_trusted(tmp_path):
    def forged_command(rows, **_):
        rows[0]["commands"][0] = rows[0]["commands"][0].replace(
            str(cid("Knight")), str(cid("HogRider"))
        )

    path, _, base = fixture(tmp_path, probe_mutations={0: forged_command})
    with pytest.raises(ValueError, match="commands/receipts"):
        verify(path, base)

    def spell_never_commanded(rows, decisions, **_):
        # Owner one waits instead of playing Zap, but Zap damage still appears.
        before, row, actions = transport(10, ("DarkPrince", None), 4)
        rows[2], decisions[2]["actions"] = row, actions
        decisions[2]["native_frame"]["ordinary"]["players"] = before["players"]

    def keep_frame_bound(lines, decisions, **kwargs):
        spell_never_commanded(decisions=decisions, **kwargs)
        lines[2]["ordinary"] = decisions[2]["native_frame"]["ordinary"]
        lines[2]["level_source"]["ordinary"] = lines[2]["ordinary"]

    path, _, base = fixture(tmp_path, probe_mutations={2: keep_frame_bound})
    with pytest.raises(ValueError, match="re-audited command"):
        verify(path, base)

    def unbound_decision(decisions, **_):
        # Decision and command row agree with each other, but not the native frame.
        decisions[1]["native_frame"]["ordinary"]["objects"].append({"hp": None})

    path, _, base = fixture(tmp_path, probe_mutations={0: unbound_decision})
    with pytest.raises(ValueError, match="bound to its pinned frames"):
        verify(path, base)


def test_missing_native_checks_fail_closed(tmp_path):
    def no_spells(lines, **_):
        lines[-1]["rich"]["combatEvents"]["events"] = []

    path, _, base = fixture(tmp_path, probe_mutations={2: no_spells, 3: no_spells})
    with pytest.raises(ValueError, match="coverage is incomplete"):
        verify(path, base)

    def no_initial_crown(lines, decisions, **_):
        lines[0]["ordinary"]["objects"].pop()
        lines[0]["level_source"]["ordinary"] = lines[0]["ordinary"]
        decisions[0]["native_frame"]["ordinary"] = copy.deepcopy(lines[0]["ordinary"])

    path, receipt, base = fixture(tmp_path, probe_mutations={1: no_initial_crown})
    with pytest.raises(ValueError, match="initial Crown"):
        verify(path, base)
    rewrite(path, receipt.model_copy(update={"probes": receipt.probes[:3]}))
    with pytest.raises(ValueError):
        verify(path, base)


def test_rankings_cannot_be_omitted_harmful_or_impossible(tmp_path):
    path, receipt, base = fixture(tmp_path)
    ranking = receipt.ranking_checks.payload()
    ranking["branches"].pop()
    rewrite(
        path,
        receipt.model_copy(
            update={"ranking_checks": write(tmp_path / "missing-ranking.json", ranking)}
        ),
    )
    with pytest.raises(ValueError, match="branches are missing"):
        verify(path, base)
    # Scalar prefers the alternative the reference engine scores clearly worse.
    path, _, base = fixture(
        tmp_path,
        deficit=lambda p, a, e: 1000 - 900 * a if e == "scalar" else 100 + 900 * a,
    )
    with pytest.raises(ValueError, match="ranking regression"):
        verify(path, base)
    # A tower above its declared maximum cannot inflate a margin.
    path, _, base = fixture(tmp_path, deficit=lambda p, a, e: -500 if a else 0)
    with pytest.raises(ValueError, match="impossible"):
        verify(path, base)


def test_independent_training_needs_recomputed_scalar_evidence(tmp_path):
    path, receipt, base = fixture(tmp_path)
    bound, scalar = independent(tmp_path, receipt, base)
    rewrite(path, bound.model_copy(update={"scalar_adaptation": None}))
    with pytest.raises(ValueError, match="both a protocol decision"):
        verify(path, base)
    rewrite(path, bound)
    verified = verify(path, base)
    assert verified.level_sampling_scope == "independent_cards"
    assert verified.mixed_level_training_levels == (10, 11, 12)
    # Training permission never becomes a native independent-card parity claim.
    assert verified.native_level_scope == "uniform_cards_asymmetric_kings"
    assert verified.native_independent_card_parity is False
    observation = FilePin.model_validate(scalar.payload()["cases"][0]["observation"])
    Path(observation.path).write_text("{}")
    with pytest.raises(ValueError, match="artifact changed"):
        verify(path, base)


def test_self_asserted_scalar_pass_with_failing_raw_data_is_rejected(tmp_path):
    path, receipt, base = fixture(tmp_path)

    def wrong_hp(cases):
        cases[0]["observation"]["bodies"][0]["maxHp"] += 7
        cases[0]["passed"] = True

    asserted = {
        "status": "passed",
        "tested_levels": [10, 11, 12],
        "independent_card_levels": True,
    }
    bound, scalar = independent(
        tmp_path, receipt, base, mutate=wrong_hp, extra=asserted
    )
    assert scalar.payload()["status"] == "passed"
    rewrite(path, bound)
    with pytest.raises(ValueError, match="body HP"):
        verify(path, base)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda cases: cases.pop(), "coverage is incomplete"),
        (
            lambda cases: (
                cases[0]["card_levels"][0].update(HogRider=10)
                or cases[1]["card_levels"][0].update(HogRider=10)
                or [c["card_levels"][1].update({n: 10 for n in DECK}) for c in cases]
            ),
            "coverage is incomplete",
        ),
        (
            lambda cases: [c.update(tower_levels=[11, 11]) for c in cases],
            "Crown level",
        ),
        (
            lambda cases: cases[1]["observation"]["spells"][0].update(level=11),
            "undeclared card level",
        ),
        (
            lambda cases: cases[0]["card_levels"][0].update(Knight=13),
            "out of scope",
        ),
        (
            lambda cases: [
                b.update(deficit=1000) for c in cases for b in c["branches"]
            ],
            "consequential",
        ),
        (lambda cases: cases[0]["branches"].pop(), "two alternatives"),
        (lambda cases: cases[1]["observation"]["towers"].pop(), "six Crown"),
        (lambda cases: cases[1]["observation"].update(towers=[]), "six Crown"),
    ],
)
def test_scalar_mixed_level_invariants_are_recomputed(tmp_path, mutation, message):
    path, receipt, base = fixture(tmp_path)
    bound, _ = independent(tmp_path, receipt, base, mutate=mutation)
    rewrite(path, bound)
    with pytest.raises(ValueError, match=message):
        verify(path, base)

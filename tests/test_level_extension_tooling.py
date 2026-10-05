"""Offline dry run of the level-extension tooling against a scalar-backed fake.

The fake native probe (``level_extension_fake_native``) answers the collector's
probe commands with native-schema frames. These fixtures never grant a real
admission; they show that the collector, scalar study and assembler write
exactly what the pinned verifier recomputes, and that tampering fails closed.
"""

from __future__ import annotations

import copy
import gzip
import json
import runpy
import sys
import types
from pathlib import Path

import pytest

from clasher.data import CardDataLoader
from clasher.paths import gamedata_path, project_root
from clasher.rl.native_public_observation import NativeProjectileCatalog
from clasher.rl.readiness_execution import canonical_sha, file_sha
from clasher.rl.readiness_level_extension import (
    PROBE_PLANS,
    FilePin,
    LevelExtensionReceipt,
    verify_level_extension_receipt,
)

ROOT = project_root()
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import build_level_extension_evidence as builder  # noqa: E402
import collect_level_extension_probes as collector  # noqa: E402
import level_extension_common as common  # noqa: E402
import run_level_extension_scalar_study as scalar  # noqa: E402
from level_extension_fake_native import FAKE_ATTESTATION, FakeNative  # noqa: E402

RC = ROOT / "reports/strategy_council_20260928"
SNAP = RC / "m0/runtime-snapshots/native-final-v4"
LEVEL_DIR = RC / "m0/level-extension"
CATALOG = Path("/Users/sam/.cache/clasher-native-reference/decoded-logic-1e505767/projectiles.csv")
CATALOG_SHA = "c59ef74273b721b861e6a499bc8869a6fc29ad07919884b79ebe859455d6eac5"
DECISION_EVIDENCE = RC / "m0/readiness/level-extension-implementation-decision.json"

pytestmark = pytest.mark.skipif(
    not CATALOG.exists() or not (SNAP / "native-configs/configs/episode-00.json").exists(),
    reason="pinned projectile catalog or v4 runtime snapshot unavailable",
)


def public_views():
    from run_readiness_v2 import public_views as views

    return views


def catalog():
    return NativeProjectileCatalog.from_csv(CATALOG, expected_sha256=CATALOG_SHA)


def prepare_configs(output: Path) -> None:
    argv = sys.argv
    sys.argv = [
        "prepare", "--nominal-config", str(SNAP / "native-configs/configs/episode-00.json"),
        "--gamedata", str(gamedata_path()), "--output", str(output),
    ]
    try:
        runpy.run_path(str(ROOT / "scripts/prepare_readiness_level_extension.py"), run_name="__main__")
    finally:
        sys.argv = argv


def run_pipeline(root: Path, *, independent=True):
    prepare_configs(root / "configs")
    proto = runpy.run_path(str(ROOT / "tests/test_training_readiness_v2.py"))["protocol"]()
    (root / "nominal.json").write_text(proto.model_dump_json(indent=2) + "\n")
    (root / "base.json").write_text(json.dumps({
        "protocol_sha256": proto.sha256, "gamedata_sha256": file_sha(gamedata_path()),
        "synthetic_test_only": True,
    }, indent=2) + "\n")
    (root / "attestation.json").write_text(json.dumps(FAKE_ATTESTATION) + "\n")
    builder.declare(root / "configs/manifest.json", root / "base.json", root / "attestation.json",
                    gamedata_path(), root / "declaration")
    fake = FakeNative(CardDataLoader(gamedata_path()))
    args = types.SimpleNamespace(
        declaration=root / "declaration/declaration.json", configs_manifest=root / "configs/manifest.json",
        gamedata=gamedata_path(), output=root / "native", ranking_root_tick=90, max_probe_tick=3000,
    )
    native = collector.run(args, call=fake, session_factory=fake.session_factory,
                           public_views=public_views(), catalog=catalog(), fast=False)
    rankings = scalar.run_rankings(types.SimpleNamespace(
        declaration=args.declaration, gamedata=gamedata_path(), native_run=root / "native",
        output=root / "scalar-rankings"), catalog())
    study = scalar.run_adaptation(types.SimpleNamespace(
        declaration=args.declaration, gamedata=gamedata_path(), base_admission=root / "base.json",
        output=root / "scalar-adaptation"), catalog())
    receipt = builder.assemble(assemble_args(root, "assembled", independent=independent))
    return {"root": root, "native": native, "rankings": rankings, "study": study, "receipt": receipt,
            "fake": fake}


def assemble_args(root: Path, name: str, *, independent=True):
    return types.SimpleNamespace(
        declaration=root / "declaration/declaration.json", base_admission=root / "base.json",
        nominal_protocol=root / "nominal.json", gamedata=gamedata_path(), native_run=root / "native",
        scalar_rankings=root / "scalar-rankings",
        scalar_adaptation=root / "scalar-adaptation" if independent else None,
        independent_cards_decision_evidence=DECISION_EVIDENCE if independent else None,
        output=root / name,
    )


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    return run_pipeline(tmp_path_factory.mktemp("level-extension-dry-run"))


def verify(receipt_path: Path, root: Path):
    return verify_level_extension_receipt(receipt_path, base_admission_sha256=file_sha(root / "base.json"))


def write_pin(path: Path, value) -> FilePin:
    path.write_text(json.dumps(value, indent=2) + "\n")
    return FilePin(path=str(path), sha256=file_sha(path))


def write_lines_pin(path: Path, rows) -> FilePin:
    path.write_bytes(gzip.compress("".join(json.dumps(r) + "\n" for r in rows).encode()))
    return FilePin(path=str(path), sha256=file_sha(path))


def receipt_of(pipeline) -> LevelExtensionReceipt:
    return LevelExtensionReceipt.model_validate_json(Path(pipeline["receipt"]).read_text())


def rewrite(path: Path, receipt: LevelExtensionReceipt) -> Path:
    path.write_text(receipt.model_dump_json(indent=2) + "\n")
    return path


def with_probe_frames(pipeline, tmp_path, index, mutate) -> Path:
    """A producer that edits raw frames and honestly re-pins them."""
    receipt = receipt_of(pipeline)
    frames = common.read_jsonl(Path(receipt.probes[index].frames.path))
    mutate(frames)
    new_pin = write_lines_pin(tmp_path / f"frames-{index}.jsonl.gz", frames)
    probes = list(receipt.probes)
    probes[index] = probes[index].model_copy(update={"frames": new_pin})
    return rewrite(tmp_path / "receipt.json", receipt.model_copy(update={"probes": tuple(probes)}))


def with_scalar_study(pipeline, tmp_path, mutate) -> Path:
    """Re-pin a modified scalar study and a matching approved decision."""
    receipt = receipt_of(pipeline)
    study = receipt.scalar_adaptation.payload()
    mutate(study, tmp_path)
    study_pin = write_pin(tmp_path / "scalar-adaptation.json", study)
    decision = receipt.protocol_decision.payload()
    decision["scalar_adaptation_sha256"] = study_pin.sha256
    decision_pin = write_pin(tmp_path / "decision.json", decision)
    return rewrite(tmp_path / "receipt.json", receipt.model_copy(
        update={"scalar_adaptation": study_pin, "protocol_decision": decision_pin}))


# ------------------------------------------------------------ positive path


def test_prospective_configs_are_bound_to_the_v4_runtime():
    manifest = json.loads((LEVEL_DIR / "prospective-configs/manifest.json").read_text())
    attempt = json.loads((RC / "m0/readiness/tier-a-fresh-v4/declaration.json").read_text())
    assert manifest["gamedata_sha256"] == file_sha(SNAP / "gamedata.json") == attempt["gamedata_sha256"]
    assert manifest["gamedata_sha256"].startswith("daa58b28")
    assert manifest["source_config_sha256"] == file_sha(SNAP / "native-configs/configs/episode-00.json")
    assert manifest["status"] == "draft_missing_nominal_admission"
    record = json.loads((LEVEL_DIR / "config-supersession.json").read_text())
    assert record["old"]["gamedata_sha256"].startswith("3d99987c")
    assert record["new"]["manifest_sha256"] == file_sha(LEVEL_DIR / "prospective-configs/manifest.json")
    for side in ("old", "new"):
        directory = LEVEL_DIR / record[side]["directory"]
        for row in record[side]["probes"]:
            path = directory / row["config_path"]
            assert file_sha(path) == row["config_file_sha256"]
            assert canonical_sha(json.loads(path.read_text())) == row["config_sha256"]
    # The regenerated configs cannot be declared against another ruleset.
    with pytest.raises(ValueError, match="another ruleset"):
        builder.declare(LEVEL_DIR / "prospective-configs/manifest.json", DECISION_EVIDENCE,
                        DECISION_EVIDENCE, gamedata_path(), Path("/nonexistent/never-created"))


def test_dry_run_collector_output_passes_the_pinned_verifier(pipeline):
    root = pipeline["root"]
    verified = verify(Path(pipeline["receipt"]), root)
    assert verified.verified_levels == (10, 11, 12)
    assert verified.native_level_scope == "uniform_cards_asymmetric_kings"
    assert verified.native_measured_card_levels == (10, 12)
    assert verified.native_measured_king_levels == (10, 12)
    assert verified.native_independent_card_parity is False
    assert verified.level_sampling_scope == "independent_cards"
    assert verified.mixed_level_training_levels == (10, 11, 12)
    check = json.loads((root / "assembled/local-verifier-check.json").read_text())
    assert check["verified"]["level_sampling_scope"] == "independent_cards"
    native = pipeline["native"]
    assert native["failures"] == 0 and native["producer_sources_unchanged"] is True
    assert [p["status"] for p in native["probes"]] == ["coverage_complete"] * 4
    assert len(pipeline["rankings"]["branches"]) == 16 and not pipeline["rankings"]["failures"]
    assert len(pipeline["study"]["cases"]) == len(scalar.CASES)
    # The fake only received probe commands a real reference supports.
    assert set(pipeline["fake"].commands) <= {
        "attest", "status", "configure", "observe", "observe-rich", "step", "replay-schedule-card"}


def test_uniform_scope_without_protocol_decision(pipeline, tmp_path):
    root = pipeline["root"]
    receipt = receipt_of(pipeline).model_copy(update={"protocol_decision": None, "scalar_adaptation": None})
    verified = verify(rewrite(tmp_path / "uniform.json", receipt), root)
    assert verified.level_sampling_scope == "uniform_cards"
    assert verified.mixed_level_training_levels == ()


def test_raw_files_have_the_verifier_form_and_no_verdicts(pipeline):
    root = pipeline["root"]
    for index in range(4):
        probe = root / "native" / f"probe-{index}"
        frames = common.read_jsonl(probe / "frames.jsonl.gz")
        decisions = common.read_jsonl(probe / "decisions.jsonl.gz")
        transport = common.read_jsonl(probe / "transport.jsonl.gz")
        session = json.loads((probe / "read-session.json").read_text())
        assert frames[0]["ordinary"]["tick"] == 0
        assert set(frames[0]) == {"ordinary", "rich", "level_source"}
        assert len(decisions) == len(transport) > 0
        assert session["status"] == "verified" and session["reads_completed"] == len(frames)
        ticks = {f["ordinary"]["tick"] for f in frames}
        assert all(d["tick"] in ticks for d in decisions)
        root_record = json.loads((probe / "ranking-root.json").read_text())
        assert root_record["root_owner"] == index % 2
        assert [c["role"] for c in root_record["candidates"]] == list(common.RANKING_ROLES)
    for path in (root / "native").rglob("*.json"):
        text = path.read_text()
        assert '"passed"' not in text and '"verified_levels"' not in text


def test_both_seats_carry_body_checks_and_crowns_are_asymmetric(pipeline):
    coverage = [p["coverage"] for p in pipeline["native"]["probes"]]
    assert {c["attacker"] for c in coverage} == {0, 1}
    assert all(c["complete"] for c in coverage)
    for index, plan in enumerate(PROBE_PLANS):
        frames = common.read_jsonl(pipeline["root"] / "native" / f"probe-{index}" / "frames.jsonl.gz")
        crowns = sorted((o["owner"], o["maxHp"]) for o in frames[0]["ordinary"]["objects"] if o["cardId"] == -1)
        kings = [max(hp for owner, hp in crowns if owner == seat) for seat in (0, 1)]
        assert kings[0] != kings[1], plan


# Tick-0 Crowns the native reference reported for probe 0 (cards 10, Kings
# 10/12) on emulator-5580, keyed by integer object ID as the reader returns them.
PROBE0_TICK0_CROWNS = (
    (5000000, 0, 9000, 3000, 4392, 10), (5000001, 0, 3500, 6500, 2786, 10),
    (5000002, 0, 14500, 6500, 2786, 10), (5000003, 1, 9000, 29000, 5304, 12),
    (5000004, 1, 3500, 25500, 2786, 10), (5000005, 1, 14500, 25500, 2786, 10),
)


def probe0_reader_frame(level_overrides=None):
    level_overrides = level_overrides or {}
    objects = [{"nativeObjectId": i, "owner": o, "cardId": -1, "x": x, "y": y, "hp": hp, "maxHp": hp}
               for i, o, x, y, hp, _ in PROBE0_TICK0_CROWNS]
    levels = {i: level_overrides.get(i, level) for i, *_, level in PROBE0_TICK0_CROWNS}
    ordinary = {"tick": 0, "generation": 1, "stateEpoch": 1, "objects": objects}
    return {"ordinary": ordinary, "rich": {}, "level_source": {"ordinary": ordinary, "levels": levels}}


def test_reader_integer_level_keys_match_the_declared_plan():
    """v1 regression: integer-keyed reader levels were looked up by string key."""
    loader = CardDataLoader(gamedata_path())
    common.check_native_levels(probe0_reader_frame(), PROBE_PLANS[0], loader)
    stored = json.loads(json.dumps(probe0_reader_frame()))
    common.check_native_levels(stored, PROBE_PLANS[0], loader)
    with pytest.raises(ValueError, match="Crown level differs"):
        common.check_native_levels(probe0_reader_frame({5000003: 10}), PROBE_PLANS[0], loader)
    with pytest.raises(ValueError, match="Crown level differs"):
        common.check_native_levels(probe0_reader_frame(), PROBE_PLANS[1], loader)


def test_serialized_level_map_rejects_ambiguous_identities():
    assert common.serialized_level_map({5000000: 10, "5000001": 12}) == {"5000000": 10, "5000001": 12}
    for bad in ({5: 10, "5": 10}, {"05": 10}, {-1: 10}, {"x": 10}, {5.0: 10}, {True: 10}):
        with pytest.raises(ValueError, match="native level object identity"):
            common.serialized_level_map(bad)


def test_native_link_frame_is_identical_to_its_stored_form():
    frame = probe0_reader_frame()
    ordinary = frame["ordinary"]

    class Session:
        def read_levels(self, ordinary=None):
            return {"ordinary": frame["ordinary"], "levels": dict(frame["level_source"]["levels"]),
                    "reader_sha256": "0" * 64}

    for fast in (True, False):
        link = collector.NativeLink(lambda command: copy.deepcopy(ordinary) if command == "observe" else {},
                                    None, fast)
        link.session = Session()
        read = link.read_frame()
        assert json.loads(json.dumps(read)) == read
        assert set(read["level_source"]["levels"]) == {str(i) for i, *_ in PROBE0_TICK0_CROWNS}


# ------------------------------------------------------------ negative cases


def test_repinned_wrong_body_hp_is_recomputed(pipeline, tmp_path):
    knight = CardDataLoader(gamedata_path()).get_card("Knight")._raw_entry["id"]

    def wrong(frames):
        # The final frame carries no transport decision, so only HP recomputation can catch it.
        frame = frames[-1]
        body = next(o for o in frame["ordinary"]["objects"] if o["cardId"] == knight and o.get("hp"))
        body["maxHp"] += 1
        frame["level_source"]["ordinary"] = frame["ordinary"]

    with pytest.raises(ValueError, match="differs from scalar scaling"):
        verify(with_probe_frames(pipeline, tmp_path, 0, wrong), pipeline["root"])


def test_body_at_another_level_breaks_uniform_scope(pipeline, tmp_path):
    def other_level(frames):
        frame = frames[-1]
        body = next(o for o in frame["ordinary"]["objects"] if o["cardId"] != -1 and o.get("hp"))
        frame["level_source"]["levels"][str(body["nativeObjectId"])] = 11

    with pytest.raises(ValueError, match="uniform card level"):
        verify(with_probe_frames(pipeline, tmp_path, 2, other_level), pipeline["root"])


def test_missing_spell_telemetry_fails_coverage(pipeline, tmp_path):
    receipt = receipt_of(pipeline)
    probes = list(receipt.probes)
    for index in (0, 1):
        frames = common.read_jsonl(Path(probes[index].frames.path))
        for frame in frames:
            frame["rich"]["combatEvents"]["events"] = []
        probes[index] = probes[index].model_copy(
            update={"frames": write_lines_pin(tmp_path / f"frames-{index}.jsonl.gz", frames)})
    path = rewrite(tmp_path / "receipt.json", receipt.model_copy(update={"probes": tuple(probes)}))
    with pytest.raises(ValueError, match="coverage is incomplete"):
        verify(path, pipeline["root"])


def test_incomplete_combat_telemetry_is_rejected(pipeline, tmp_path):
    def incomplete(frames):
        for frame in frames:
            frame["rich"]["combatEvents"]["complete"] = False

    with pytest.raises(ValueError, match="complete and epoch-bound"):
        verify(with_probe_frames(pipeline, tmp_path, 1, incomplete), pipeline["root"])


def test_missing_or_harmful_ranking_branches_are_rejected(pipeline, tmp_path):
    receipt = receipt_of(pipeline)
    rankings = receipt.ranking_checks.payload()
    rankings["branches"].pop()
    path = rewrite(tmp_path / "missing.json", receipt.model_copy(
        update={"ranking_checks": write_pin(tmp_path / "rankings-missing.json", rankings)}))
    with pytest.raises(ValueError, match="branches are missing"):
        verify(path, pipeline["root"])
    # Reference endings where every alternative ties cannot show consequence.
    rankings = receipt.ranking_checks.payload()
    for n, row in enumerate(rankings["branches"]):
        ending = FilePin.model_validate(row["ending_frame"]).payload()
        for obj in ending.get("ordinary", ending)["objects"]:
            obj["hp"] = obj["maxHp"]  # untouched Crowns: every alternative ties
        row["ending_frame"] = json.loads(write_pin(tmp_path / f"flat-{n}.json", ending).model_dump_json())
    path = rewrite(tmp_path / "flat.json", receipt.model_copy(
        update={"ranking_checks": write_pin(tmp_path / "rankings-flat.json", rankings)}))
    with pytest.raises(ValueError, match="consequential"):
        verify(path, pipeline["root"])


def test_scalar_study_raw_values_are_recomputed(pipeline, tmp_path):
    def wrong_spell_level(study, directory):
        case = study["cases"][0]
        observation = FilePin.model_validate(case["observation"]).payload()
        observation["spells"][0]["level"] = 11
        case["observation"] = json.loads(write_pin(directory / "obs.json", observation).model_dump_json())

    with pytest.raises(ValueError, match="undeclared card level"):
        verify(with_scalar_study(pipeline, tmp_path, wrong_spell_level), pipeline["root"])

    def self_asserted(study, directory):
        study["status"] = "passed"
        case = study["cases"][1]
        observation = FilePin.model_validate(case["observation"]).payload()
        observation["bodies"][0]["maxHp"] += 3
        case["observation"] = json.loads(write_pin(directory / "obs2.json", observation).model_dump_json())

    second = tmp_path / "second"
    second.mkdir()
    with pytest.raises(ValueError, match="body HP"):
        verify(with_scalar_study(pipeline, second, self_asserted), pipeline["root"])


def test_scalar_study_needs_two_informative_cases(pipeline, tmp_path):
    def ties(study, directory):
        for case in study["cases"]:
            first = FilePin.model_validate(case["branches"][0]["ending_frame"])
            for branch in case["branches"][1:]:
                branch["ending_frame"] = json.loads(first.model_dump_json())
        del directory

    with pytest.raises(ValueError, match="consequential rankings"):
        verify(with_scalar_study(pipeline, tmp_path, ties), pipeline["root"])


def test_assembler_rejects_edited_native_crown_projection(pipeline, tmp_path):
    root = pipeline["root"]
    rows = json.loads((root / "native/native-rankings.json").read_text())["branches"]
    ending = FilePin.model_validate(rows[0]["ending_frame"]).payload()
    ending["ordinary"]["objects"][0]["hp"] -= 1
    row = copy.deepcopy(rows[0])
    row["ending_frame"] = json.loads(write_pin(tmp_path / "ending.json", ending).model_dump_json())
    with pytest.raises(ValueError, match="re-derive"):
        builder.check_native_crown_projection(row)


def test_collector_refuses_wrong_attestation_or_config(pipeline, tmp_path):
    root = pipeline["root"]
    fake = FakeNative(CardDataLoader(gamedata_path()))

    def lying(command):
        if command == "attest":
            return {"ok": True, "attestation": {"other": True}}
        return fake(command)

    args = types.SimpleNamespace(
        declaration=root / "declaration/declaration.json", configs_manifest=root / "configs/manifest.json",
        gamedata=gamedata_path(), output=tmp_path / "never", ranking_root_tick=90, max_probe_tick=300,
    )
    with pytest.raises(ValueError, match="attestation differs"):
        collector.run(args, call=lying, session_factory=fake.session_factory, public_views=public_views(),
                      catalog=catalog(), fast=False)
    assert not (tmp_path / "never").exists()
    configs = tmp_path / "configs"
    configs.mkdir()
    manifest = json.loads((root / "configs/manifest.json").read_text())
    for row in manifest["probes"]:
        config = json.loads((root / "configs" / row["config_path"]).read_text())
        config["rndSeed"] += 1
        (configs / row["config_path"]).write_text(json.dumps(config, indent=2) + "\n")
        row["config_file_sha256"] = file_sha(configs / row["config_path"])
    (configs / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    args.configs_manifest = configs / "manifest.json"
    with pytest.raises(ValueError, match="differs from the declaration"):
        collector.run(args, call=fake, session_factory=fake.session_factory, public_views=public_views(),
                      catalog=catalog(), fast=False)


def test_assembler_refuses_another_base_admission(pipeline, tmp_path):
    root = pipeline["root"]
    other = tmp_path / "other-base.json"
    other.write_text(json.dumps({"synthetic_test_only": True, "other": 1}) + "\n")
    args = assemble_args(root, "never")
    args.base_admission = other
    args.output = tmp_path / "never"
    with pytest.raises(ValueError, match="another base admission"):
        builder.assemble(args)


# ------------------------------------------- v3: native spell attribution


def test_fake_native_attributes_fireball_like_the_reference(pipeline):
    """The dry run must not hide the v2 failure: Fireball's source is a King Tower."""
    fireball = CardDataLoader(gamedata_path()).get_card("Fireball")._raw_entry["id"]
    rows = []
    for index in range(4):
        for frame in common.read_jsonl(pipeline["root"] / "native" / f"probe-{index}" / "frames.jsonl.gz"):
            rows.extend(e for e in frame["rich"]["combatEvents"]["events"]
                        if e["immediateSource"]["cardId"] == fireball)
    assert rows
    assert all(e["source"]["cardId"] == -1 and e["source"]["objectKind"] == 5 for e in rows)
    for probe in pipeline["native"]["probes"]:
        assert probe["coverage"]["spells_first_damage_attribution"]["Fireball"] == "king_tower_projectile"
        assert probe["status"] == "coverage_complete"


def test_source_only_verifier_rule_reproduces_the_v2_coverage_failure(pipeline, monkeypatch):
    """With the native-final-v7 rule (source.cardId only) the same evidence fails on Fireball."""
    import clasher.rl.readiness_level_extension as level

    def source_only(event, spell_ids):
        source, target = event.get("source") or {}, event.get("target") or {}
        if (event.get("kind") == "damage" and event.get("pool") == "hitpoints"
                and source.get("validated") is True and target.get("validated") is True
                and source.get("cardId") in spell_ids
                and isinstance(target.get("cardId"), int) and 26000000 <= target["cardId"] < 28000000):
            return source.get("owner"), source["cardId"]
        return None

    monkeypatch.setattr(level, "_spell_damage_attribution", source_only)
    with pytest.raises(ValueError, match="coverage is incomplete"):
        verify(Path(pipeline["receipt"]), pipeline["root"])


def ranking_rows(pipeline):
    root = pipeline["root"]
    native = json.loads((root / "native/native-rankings.json").read_text())["branches"]
    scalar_rows = json.loads((root / "scalar-rankings/scalar-rankings.json").read_text())["branches"]
    return root, native, scalar_rows


def test_ranking_provenance_accepts_own_engine_files(pipeline):
    root, native, scalar_rows = ranking_rows(pipeline)
    builder.check_ranking_provenance(native, scalar_rows, root / "native", root / "scalar-rankings")


def test_ranking_provenance_rejects_swapped_or_duplicated_engines(pipeline):
    root, native, scalar_rows = ranking_rows(pipeline)
    dirs = (root / "native", root / "scalar-rankings")

    def relabel(rows, engine):
        return [{**copy.deepcopy(r), "engine": engine} for r in rows]

    cases = {
        # scalar results presented as native, native as scalar
        "swapped": (relabel(scalar_rows, "reference"), relabel(native, "scalar")),
        # scalar results used for both engines
        "scalar twice": (relabel(scalar_rows, "reference"), scalar_rows),
        # native results used for both engines
        "native twice": (native, relabel(native, "scalar")),
    }
    for name, (reference_rows, scalar_side) in cases.items():
        with pytest.raises(ValueError):
            builder.check_ranking_provenance(reference_rows, scalar_side, *dirs)
            pytest.fail(name)
    # Directory swap: each file is outside the run it is claimed for.
    with pytest.raises(ValueError, match="outside its run"):
        builder.check_ranking_provenance(native, scalar_rows, dirs[1], dirs[0])
    # One scalar ending shared by a native row with the same label.
    mixed = copy.deepcopy(native)
    mixed[0]["ending_frame"] = copy.deepcopy(scalar_rows[0]["ending_frame"])
    with pytest.raises(ValueError):
        builder.check_ranking_provenance(mixed, scalar_rows, root, root)

"""Independent audit of native prefix captures for m0-native-prefix-development-v2.

Read-only. Recomputes every check from recorded evidence using the immutable
runtime snapshot (never the collector's own summary flags):

  * ledger claim nonce/output path <-> capture-receipt.json identity, and the
    ledger capture record equals the on-disk receipt;
  * every artifact hash (no missing or extra files);
  * config / root-request / root-bank / manifest / generator hashes against
    snap/declaration.json (root bank also regenerated from its master seed);
  * five-tick public cadence with no gaps from tick 90 to the root tick;
  * re-projection of every stored native frame into both public perspectives,
    matching the recorded per-decision packet hashes and seat npz archives;
  * prefix controller replay and the declared root-owner reserve rule;
  * first-eligible root selection, recomputed both with an explicit
    per-tick eligibility loop and with the snapshot's select_root;
  * accepted-command receipts reconstruct transport
    (decisions <-> submissions <-> transport <-> accepted-commands);
  * verified native read session closure and per-frame session binding;
  * game_complete false everywhere; producer-source.zip contents equal pins.

Run (from any cwd):
  SNAP=reports/strategy_council_20260928/m0/runtime-snapshots/native-development-v1
  CLASHER_ROOT=$SNAP PYTHONPATH=$SNAP/src:$SNAP/scripts $SNAP/.venv/bin/python -B audit.py

Writes only results.json next to this file. Never touches the emulator, adb or
the ledger (sqlite is opened with mode=ro).
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import os
import sqlite3
import sys
import time
import traceback
import zipfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
COUNCIL = HERE.parents[2]  # reports/strategy_council_20260928
SNAP = COUNCIL / "m0/runtime-snapshots/native-development-v1"
LEDGER = COUNCIL / "readiness-v2.sqlite"
ATTEMPT = "m0-native-prefix-development-v2"
BATCHES = [
    COUNCIL / "m0/readiness/native-prefix-development-v2",
    COUNCIL / "m0/readiness/native-prefix-development-v2-remaining",
    COUNCIL / "m0/readiness/native-prefix-development-v2-tail",
]
CATALOG = Path(
    "/Users/sam/.cache/clasher-native-reference/decoded-logic-1e505767/projectiles.csv"
)
KNOWN_INTERRUPTED = "m260928903-episode-15"

os.environ.setdefault("CLASHER_ROOT", str(SNAP))
for p in (SNAP / "scripts", SNAP / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
sys.dont_write_bytecode = True

import numpy as np  # noqa: E402

import clasher  # noqa: E402
from clasher.data import CardDataLoader  # noqa: E402
from clasher.rl.action_space import DiscreteTileActionSpace  # noqa: E402
from clasher.rl.native_command_checks import validate_command_step  # noqa: E402
from clasher.rl.native_frame_storage import validate_native_frame_storage  # noqa: E402
from clasher.rl.native_public_observation import (  # noqa: E402
    PUBLIC_REFERENCE_CARDS,
    NativeProjectileCatalog,
    NativePublicObservationAdapter,
    NativePublicScope,
    public_reference_builder,
)
from clasher.rl.own_card_history import AcceptedOwnPlay  # noqa: E402
from clasher.rl.public_action_mask import (  # noqa: E402
    PublicActionMaskBuilder,
    PublicActionMaskInput,
)
from clasher.rl.public_policy_contract import PublicPolicySequence  # noqa: E402
from clasher.rl.public_reference_checks import reference_token_maps  # noqa: E402
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent  # noqa: E402
from clasher.rl.readiness_capture_ownership import AttemptDeclaration  # noqa: E402
from clasher.rl.readiness_execution import (  # noqa: E402
    CAPTURE_FILES,
    canonical_sha,
    packet_sha,
)
from clasher.rl.readiness_root_bank import (  # noqa: E402
    RootBank,
    RootRequest,
    context_matches,
    generate_root_bank,
    select_root,
)
from clasher.rl.training_readiness_v2 import generate_candidates  # noqa: E402
from run_readiness_v2 import public_views  # noqa: E402

assert Path(clasher.__file__).resolve().is_relative_to(SNAP.resolve()), clasher.__file__

WAIT = 2304


def fsha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Checks:
    def __init__(self):
        self.items: dict[str, dict] = {}

    def add(self, name: str, ok: bool, detail=None):
        ok = bool(ok)
        if name in self.items:
            prev = self.items[name]
            prev["ok"] = prev["ok"] and ok
            if not ok and detail is not None:
                prev.setdefault("failures", []).append(detail)
            return
        entry = {"ok": ok}
        if detail is not None and (not ok or not isinstance(detail, str)):
            entry["detail" if ok else "failures"] = detail if ok else [detail]
        self.items[name] = entry

    @property
    def ok(self) -> bool:
        return all(v["ok"] for v in self.items.values())

    def failed(self):
        return {k: v for k, v in self.items.items() if not v["ok"]}


# --------------------------------------------------------------------------- setup
def load_context(g: Checks):
    decl_raw = json.loads((SNAP / "declaration.json").read_text())
    declaration = AttemptDeclaration.model_validate_json((SNAP / "declaration.json").read_text())
    db = sqlite3.connect(f"file:{LEDGER}?mode=ro", uri=True)
    arow = db.execute(
        "SELECT design_sha, record FROM attempts WHERE attempt_id=?", (ATTEMPT,)
    ).fetchone()
    g.add("ledger_attempt_present", arow is not None)
    ledger_decl = json.loads(arow[1])
    g.add("ledger_attempt_equals_snapshot_declaration", ledger_decl == decl_raw)
    g.add(
        "ledger_design_sha_equals_declaration_sha",
        arow[0] == declaration.sha256,
        {"ledger": arow[0], "recomputed": declaration.sha256},
    )
    claims = {}
    for fam, nonce, out, rec in db.execute(
        "SELECT family_id, nonce, output_path, record FROM episode_claims WHERE attempt_id=?",
        (ATTEMPT,),
    ):
        r = json.loads(rec)
        g.add(
            "ledger_claim_columns_match_record",
            r["nonce"] == nonce and r["output_path"] == out and r["family_id"] == fam,
            fam,
        )
        claims[fam] = r
    captures = {
        fam: json.loads(rec)
        for fam, rec in db.execute(
            "SELECT family_id, record FROM captures WHERE attempt_id=?", (ATTEMPT,)
        )
    }
    other = {
        t: db.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in ("root_seals", "branch_claims", "branch_results", "exposures", "admissions")
    }
    db.close()

    # Snapshot pins still intact (the runtime we re-execute is the pinned one).
    bad = [p for p, h in declaration.source_pins.items() if fsha(Path(p)) != h]
    g.add("snapshot_source_pins_intact", not bad, bad[:10] or f"{len(declaration.source_pins)} files")
    badi = []
    for p, h in declaration.input_pins.items():
        pp = Path(p)
        if not pp.exists() or fsha(pp) != h:
            badi.append(p)
    g.add("snapshot_input_pins_intact", not badi, badi[:10] or f"{len(declaration.input_pins)} files")
    g.add(
        "declaration_pre_protocol_source_pins_equal",
        declaration.pre_protocol.source_pins == declaration.source_pins,
    )

    manifest_path = SNAP / "native-configs/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    g.add("manifest_sha_matches_declaration", fsha(manifest_path) == declaration.converter_manifest_sha256)
    bank_path = SNAP / "native-configs/root-bank.json"
    bank = RootBank.model_validate_json(bank_path.read_text())
    g.add("root_bank_canonical_sha_matches_declaration",
          canonical_sha(bank.model_dump(mode="json")) == declaration.root_bank_sha256)
    g.add("root_bank_file_sha_matches_manifest", fsha(bank_path) == manifest["root_bank_file_sha256"])
    regenerated = generate_root_bank(bank.master_seed)
    g.add("root_bank_regenerates_from_master_seed",
          regenerated.model_dump(mode="json") == bank.model_dump(mode="json"),
          {"master_seed": bank.master_seed})
    g.add("generator_sha_matches_declaration",
          fsha(SNAP / "src/clasher/rl/readiness_root_bank.py") == declaration.generator_sha256)
    gamedata = Path(manifest["gamedata_path"])
    g.add("gamedata_sha_matches_declaration",
          fsha(gamedata) == declaration.gamedata_sha256 == manifest["gamedata_sha256"])
    g.add("catalog_sha_matches_declaration",
          fsha(CATALOG) == declaration.catalog_sha256
          and declaration.catalog_sha256 in declaration.input_pins.values())
    g.add("declaration_has_32_episodes", len(declaration.episodes) == 32)
    g.add("ledger_has_no_branch_seal_exposure_or_admission_rows", not any(other.values()), other)

    # Pinned public builder, identical to the collector's construction.
    loader = CardDataLoader(gamedata)
    catalog = NativeProjectileCatalog.from_csv(CATALOG, expected_sha256=declaration.catalog_sha256)
    builder = public_reference_builder(loader, catalog, card_semantics_version=4, public_contract_version=4)
    adapter = NativePublicObservationAdapter(
        builder,
        NativePublicScope("15.535.86", declaration.gamedata_sha256),
        card_names=tuple(PUBLIC_REFERENCE_CARDS),
        projectile_catalog=catalog,
    )
    maps = reference_token_maps(builder, PUBLIC_REFERENCE_CARDS, catalog)
    return dict(
        decl_raw=decl_raw, declaration=declaration, claims=claims, captures=captures,
        manifest=manifest, bank=bank, loader=loader, builder=builder, adapter=adapter,
        maps=maps, zip_cache={},
    )


def audit_zip(ctx, path: Path) -> tuple[bool, dict]:
    digest = fsha(path)
    if digest in ctx["zip_cache"]:
        return ctx["zip_cache"][digest]
    decl = ctx["declaration"]
    expected = {}
    snap = SNAP.resolve()
    for name, h in decl.source_pins.items():
        p = Path(name).resolve()
        rel = str(p.relative_to(snap)) if p.is_relative_to(snap) else f"external/{h}/{p.name}"
        expected[rel] = h
    problems = []
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if names != set(expected) | {"attempt-declaration.json"}:
            problems.append({"missing": sorted(set(expected) - names)[:5],
                             "extra": sorted(names - set(expected) - {"attempt-declaration.json"})[:5]})
        for rel, h in expected.items():
            if rel in names and hashlib.sha256(z.read(rel)).hexdigest() != h:
                problems.append({"hash_mismatch": rel})
        if "attempt-declaration.json" in names:
            embedded = json.loads(z.read("attempt-declaration.json"))
            if embedded != ctx["decl_raw"]:
                problems.append("embedded attempt-declaration differs from snapshot declaration")
    result = (not problems, {"sha256": digest, "entries": len(expected), "problems": problems})
    ctx["zip_cache"][digest] = result
    return result


def read_frames(path: Path):
    frames, truncated = [], None
    try:
        with gzip.open(path, "rt") as s:
            for line in s:
                frames.append(json.loads(line))
    except (EOFError, OSError, zlib.error, json.JSONDecodeError) as e:
        truncated = f"{type(e).__name__}: {e}"
    return _tamper(path, frames), truncated


def read_jsonl(path: Path, gz=False):
    opener = gzip.open if gz else open
    with opener(path, "rt") as s:
        return _tamper(path, [json.loads(line) for line in s if line.strip()])


# Negative-probe hook: maps a file name to an in-memory transform. Empty in the
# real audit; used only by --negative-probes (never modifies files on disk).
TAMPER: dict = {}


def _tamper(path: Path, value):
    fn = TAMPER.get(path.name)
    return fn(copy.deepcopy(value)) if fn else value


def load_json(path: Path):
    return _tamper(path, json.loads(path.read_text()))


def compact(snapshot):
    return {
        **{k: snapshot[k] for k in ("tick", "generation", "stateEpoch")},
        "players": [{k: p[k] for k in ("owner", "elixirRaw", "hand")} for p in snapshot["players"]],
    }


# ------------------------------------------------------------------ capture audit
def audit_capture(ctx, family_id: str, claim: dict, ledger_capture: dict | None, batch_row: dict | None):
    c = Checks()
    decl = ctx["declaration"]
    out = Path(claim["output_path"])
    episode = next(e for e in decl.episodes if e.family_id == family_id)
    receipt = load_json(out / "capture-receipt.json")
    status = receipt["status"]
    info = {"family_id": family_id, "output": str(out), "claim_nonce": claim["nonce"], "status": status}

    # 1. ledger claim <-> receipt identity
    c.add("claim_output_path_is_this_dir", Path(claim["output_path"]).resolve() == out.resolve())
    for k_r, k_c in (("claim_nonce", "nonce"), ("design_sha256", "design_sha256"),
                     ("family_id", "family_id"), ("config_sha256", "config_sha256"),
                     ("native_attestation_sha256", "native_attestation_sha256")):
        c.add("receipt_identity_matches_claim", receipt[k_r] == claim[k_c], k_r)
    c.add("claim_design_sha_is_attempt", claim["design_sha256"] == decl.sha256)
    c.add("claim_config_sha_is_declared", claim["config_sha256"] == episode.config_sha256)
    c.add("claim_attestation_is_declared", claim["native_attestation_sha256"] == decl.native_attestation_sha256)
    c.add("claim_manifest_is_declared", claim["converter_manifest_sha256"] == decl.converter_manifest_sha256)
    c.add("claim_source_episode_is_declared", claim["source_episode_id"] == episode.source_episode_id)
    c.add("ledger_capture_record_equals_receipt_file", ledger_capture == receipt,
          None if ledger_capture == receipt else "ledger capture missing or differs")
    if batch_row is not None:
        c.add("batch_result_row_matches",
              batch_row.get("claim_nonce", claim["nonce"]) == claim["nonce"]
              and Path(batch_row["output"]).resolve() == out.resolve()
              and batch_row["status"] == status, batch_row)

    # 2. artifact hashes
    files = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()} - {"capture-receipt.json"}
    listed = set(receipt["artifact_hashes"])
    c.add("artifact_set_equals_dir_contents", files == listed,
          {"unlisted": sorted(files - listed), "missing": sorted(listed - files)})
    mism = [n for n, h in receipt["artifact_hashes"].items() if (out / n).exists() and fsha(out / n) != h]
    c.add("artifact_hashes_match", not mism, mism)
    c.add("gamedata_hash_is_declared",
          receipt["artifact_hashes"].get("gamedata.json") == decl.gamedata_sha256)

    # producer source
    zpath = out / "producer-source.zip"
    zok, zinfo = audit_zip(ctx, zpath)
    c.add("producer_source_zip_matches_source_pins", zok, zinfo["problems"] or None)
    info["producer_source_sha256"] = zinfo["sha256"]
    batch_zip = out.parent / "producer-source.zip"
    c.add("producer_source_zip_equals_batch_copy", fsha(batch_zip) == zinfo["sha256"])

    # 3. config / root request
    plan = load_json(out / "plan.json")
    cfg_file = json.loads(Path(episode.config_path).read_text())
    c.add("config_file_sha_matches_declaration", fsha(Path(episode.config_path)) == episode.config_file_sha256)
    c.add("plan_config_sha_matches_declaration", canonical_sha(plan["config"]) == episode.config_sha256)
    c.add("plan_config_equals_declared_config_file", plan["config"] == cfg_file)
    c.add("plan_root_request_sha_matches_declaration",
          canonical_sha(plan["root_request"]) == episode.root_request_sha256)
    bank_req = next(r for r in ctx["bank"].requests if r.family_id == family_id)
    c.add("plan_root_request_equals_bank_request", plan["root_request"] == bank_req.model_dump(mode="json"))
    c.add("root_owner_matches_declaration", plan["root_request"]["root_owner"] == episode.root_owner)
    c.add("plan_protocol_fields",
          plan["decision_stride"] == 5 and plan["command_delay"] == 1
          and plan["startup_wait_ticks"] == 90 and plan["game_complete"] is False
          and plan["public_contract_version"] == 4
          and plan["evidence_role"] == decl.evidence_role
          and plan["decks"] == plan["root_request"]["decks"])
    root = RootRequest.model_validate_json(json.dumps(plan["root_request"]))
    c.add("root_request_declared_reserve8_stop3600_cadence5",
          root.prefix_owner_min_elixir == 8 and root.stop_tick == 3600 and root.cadence_ticks == 5
          and root.start_tick == 90)
    manifest_entry = next(e for e in ctx["manifest"]["episodes"] if e["family_id"] == family_id)

    # initial state
    initial = load_json(out / "initial.json")
    c.add("initial_tick_zero_complete", initial.get("tick") == 0 and initial.get("truncated") is False)
    for owner in (0, 1):
        pl = next(p for p in initial["players"] if p["owner"] == owner)
        ids = [cd["cardId"] for cd in sorted(pl["deck"], key=lambda cd: cd["deckSlot"])]
        c.add("initial_decks_match_declared_order", ids == manifest_entry["native_card_ids"][owner], owner)

    # 4. frames and cadence
    frames, truncated = read_frames(out / "native-frames.jsonl.gz")
    info["frames"] = len(frames)
    info["frames_truncated"] = truncated
    ticks = [f["ordinary"]["tick"] for f in frames]
    if status == "failed":
        return finish_failed(ctx, c, info, receipt, out, frames, truncated, ticks, ledger_capture)

    c.add("frames_gzip_complete", truncated is None, truncated)
    packet_ticks = load_json(out / "packet-ticks.json")
    result = load_json(out / "result.json")
    c.add("frame_ticks_equal_packet_ticks", ticks == packet_ticks == result["packet_ticks"])
    expected_ticks = list(range(90, (ticks[-1] if ticks else 90) + 1, 5))
    c.add("five_tick_cadence_no_gaps_from_90", ticks == expected_ticks,
          {"first": ticks[:1], "last": ticks[-1:], "n": len(ticks)})
    c.add("scan_window_within_declared", bool(ticks) and ticks[-1] <= root.stop_tick)
    storage_src = fsha(SNAP / "src/clasher/rl/native_frame_storage.py")
    bad_storage = []
    for f in frames:
        try:
            rec = validate_native_frame_storage(f)
            if rec is None or rec.producer_source_sha256 != storage_src:
                bad_storage.append(f["ordinary"]["tick"])
        except Exception as e:  # noqa: BLE001
            bad_storage.append((f["ordinary"]["tick"], str(e)[:120]))
    c.add("compact_frame_storage_valid", not bad_storage, bad_storage[:5])
    c.add("frames_not_ended_or_finalized",
          all(f["ordinary"]["ended"] is False and f["ordinary"]["finalized"] in (False, None) for f in frames))
    c.add("level_source_matches_ordinary", all(f["level_source"]["ordinary"] == f["ordinary"] for f in frames))

    # 5. native read session
    session = load_json(out / "native-read-session.json")
    att = decl.native_attestation_sha256
    c.add("native_read_session_closed_verified",
          session["status"] == "verified" and session["failures"] == []
          and session["expected_attestation_sha256"] == att
          and session["start_attestation_sha256"] == att
          and session["end_attestation_sha256"] == att,
          {k: session.get(k) for k in ("status", "failures")})
    c.add("native_read_session_reads_equal_frames", session["reads_completed"] == len(frames),
          {"reads_completed": session["reads_completed"], "frames": len(frames)})
    vs_ok = True
    for i, f in enumerate(frames, start=1):
        vs = f["level_source"].get("verified_session") or {}
        if (vs.get("session_id") != session["session_id"] or vs.get("read_index") != i
                or vs.get("runtime_identity") != session["runtime_identity"]
                or f["level_source"].get("reader_sha256") != session["reader_sha256"]):
            vs_ok = False
            break
    c.add("frames_bound_to_verified_session_in_order", vs_ok)
    rid = session["runtime_identity"]
    c.add("frames_same_native_epoch_as_session",
          all(f["ordinary"]["generation"] == rid["generation"] and f["ordinary"]["stateEpoch"] == rid["stateEpoch"]
              for f in frames))

    # 6. evidence logs
    decisions = load_json(out / "decisions.json")
    submissions = read_jsonl(out / "submissions.jsonl")
    accepted = read_jsonl(out / "accepted-commands.jsonl")
    transport = read_jsonl(out / "transport.jsonl.gz", gz=True)

    # 7. re-projection, controller replay, reserve, selection
    builder, adapter, maps, loader = ctx["builder"], ctx["adapter"], ctx["maps"], ctx["loader"]
    space = DiscreteTileActionSpace()
    masks = PublicActionMaskBuilder(builder)
    prefix_controllers = [PublicScriptedOpponent(builder, style=s) for s in root.prefix_styles]
    root_controller = PublicScriptedOpponent(builder, style="balanced")
    indep_controller = PublicScriptedOpponent(builder, style="balanced")
    focal_token = builder.token_id(root.focal_card, namespace="card_action")
    dec_by_tick: dict[int, list] = {}
    for d in decisions:
        dec_by_tick.setdefault(d["observation_tick"], []).append(d)
    acc_sorted = sorted(accepted, key=lambda r: (r["execution_tick"], r["owner"]))
    history = [None, None]
    acc_i = 0
    observations = [[], []]
    root_views = []
    eligibility = []  # (tick, context, has_candidates, focal_in)
    first_eligible = None
    reproj_mismatch, ctrl_mismatch, reserve_viol, native_reserve_viol, illegal = [], [], [], [], []
    compared = 0
    for f in frames:
        t = f["ordinary"]["tick"]
        while acc_i < len(acc_sorted) and acc_sorted[acc_i]["submitted_tick"] < t:
            r = acc_sorted[acc_i]
            history[r["owner"]] = AcceptedOwnPlay(r["name"], r["cost"])
            acc_i += 1
        views = public_views(f, adapter, maps, history)
        for o in (0, 1):
            views[o].validate()
            observations[o].append(views[o])
        rv = views[root.root_owner]
        root_views.append((t, rv))
        # explicit, independent first-eligible scan
        if t >= root.start_tick and first_eligible is None:
            ctx_ok = context_matches(root.context, indep_controller, rv)
            cands = ()
            if ctx_ok:
                try:
                    cands = generate_candidates(indep_controller, rv)
                except ValueError as e:
                    if not str(e).startswith("ineligible root:"):
                        raise
            focal_in = bool(cands) and focal_token in {x.card_token for x in cands}
            eligibility.append({"tick": t, "context": bool(ctx_ok), "candidates": len(cands), "focal": focal_in})
            if focal_in:
                first_eligible = t
        if t == ticks[-1]:
            c.add("no_decisions_at_final_packet", t not in dec_by_tick)
            break
        ds = sorted(dec_by_tick.get(t, []), key=lambda d: d["owner"])
        if [d["owner"] for d in ds] != [0, 1]:
            ctrl_mismatch.append((t, "missing decisions"))
            continue
        for o, d in enumerate(ds):
            if packet_sha(views[o]) != d["public_packet_sha256"]:
                reproj_mismatch.append((t, o))
            compared += 1
            mask = masks.build(PublicActionMaskInput.from_confidence_observation(views[o]))
            ordinary = prefix_controllers[o].select_action(views[o])
            if ordinary != d["ordinary_action"]:
                ctrl_mismatch.append((t, o, ordinary, d["ordinary_action"]))
            # reserve rule, recomputed independently of apply_prefix_owner_reserve
            if o == root.root_owner:
                conf = float(views[o].global_feature_confidence[5])
                elixir = float(views[o].observation.global_features[5]) * 10
                expect = WAIT if (conf <= 0 or elixir < root.prefix_owner_min_elixir) else d["ordinary_action"]
                native_elixir = next(p for p in f["ordinary"]["players"] if p["owner"] == o)["elixirRaw"] / 10000
                if d["action"] != WAIT and native_elixir < root.prefix_owner_min_elixir - 1e-9:
                    native_reserve_viol.append((t, native_elixir))
            else:
                expect = d["ordinary_action"]
            if d["action"] != expect or d["prefix_reserve_applied"] != (d["action"] != d["ordinary_action"]):
                reserve_viol.append((t, o, d["action"], expect))
            if not mask[d["action"]]:
                illegal.append((t, o))
    c.add("reprojected_packets_match_recorded_decision_hashes", not reproj_mismatch, reproj_mismatch[:5])
    c.add("prefix_controller_replay_matches", not ctrl_mismatch, ctrl_mismatch[:5])
    c.add("reserve_rule_applied_exactly", not reserve_viol, reserve_viol[:5])
    c.add("root_owner_never_played_below_native_reserve", not native_reserve_viol, native_reserve_viol[:5])
    c.add("prefix_actions_legal_under_public_mask", not illegal, illegal[:5])
    c.add("decision_count", len(decisions) == 2 * (len(frames) - 1), {"decisions": len(decisions)})
    info["packets_reprojected"] = 2 * len(root_views)
    info["decision_hashes_compared"] = compared
    info["eligibility_scan_ticks"] = len(eligibility)
    c.add("all_accepted_consumed_before_final_packet", acc_i == len(acc_sorted))
    info["reserve_applied_count"] = sum(1 for d in decisions if d["prefix_reserve_applied"])

    # npz archives equal re-projected sequences
    for o in (0, 1):
        seq = PublicPolicySequence.from_observations(builder, observations[o])
        with np.load(out / f"seat{o}-public.npz", allow_pickle=False) as z:
            meta = json.loads(str(z["metadata"].item()))
            same = set(z.files) - {"metadata"} == set(seq.arrays) and all(
                np.array_equal(z[k], v) and z[k].dtype == v.dtype for k, v in seq.arrays.items())
            same = same and meta.get("token_names") == list(seq.token_names)
        c.add("seat_npz_equals_reprojection", same, o)

    # selection: explicit scan and snapshot select_root
    replay = select_root(root, root_controller, ((t, v) for t, v in root_views if t >= root.start_tick))
    rec_sel = result["selection"]
    c.add("select_root_replay_equals_recorded_selection", replay.model_dump(mode="json") == rec_sel,
          {"replay_status": replay.status, "replay_tick": replay.root_tick})
    if status == "selected":
        c.add("first_eligible_is_recorded_root", first_eligible == rec_sel["root_tick"] == ticks[-1],
              {"first_eligible": first_eligible, "recorded": rec_sel["root_tick"]})
        c.add("no_earlier_eligible_root",
              all(not e["focal"] for e in eligibility if e["tick"] < rec_sel["root_tick"]))
        c.add("root_packet_hash_matches", packet_sha(root_views[-1][1]) == rec_sel["public_packet_sha256"])
        sf = receipt["selected_family"]
        cb = receipt["capture_binding"]
        c.add("receipt_family_matches_selection",
              sf["public_packet_sha256"] == rec_sel["public_packet_sha256"]
              and sf["candidates"] == rec_sel["candidates"]
              and sf["original_recommendation"] == rec_sel["original_recommendation"]
              and sf["root_owner"] == episode.root_owner
              and sf["independence_id"] == episode.source_episode_id
              and sf["role"] == decl.evidence_role and sf["family_id"] == family_id)
        root_frame = load_json(out / "root-frame.json")
        c.add("root_frame_is_final_stored_frame", root_frame == frames[-1])
        c.add("capture_binding_consistent",
              cb["root_tick"] == rec_sel["root_tick"]
              and cb["root_frame_sha256"] == canonical_sha(root_frame)
              and cb["config_sha256"] == episode.config_sha256
              and Path(cb["capture_path"]).resolve() == out.resolve()
              and set(cb["input_hashes"]) == set(CAPTURE_FILES)
              and all(fsha(out / n) == h for n, h in cb["input_hashes"].items()))
        root_sha = canonical_sha({"config_sha256": cb["config_sha256"], "root_tick": cb["root_tick"],
                                  "root_frame_sha256": cb["root_frame_sha256"]})
        c.add("root_sha_recomputes", root_sha == sf["root_sha256"])
        info.update(root_tick=rec_sel["root_tick"], focal_card=root.focal_card, context=root.context,
                    root_owner=root.root_owner, candidates=[x["role"] for x in rec_sel["candidates"]],
                    earlier_context_matches=sum(e["context"] for e in eligibility[:-1]),
                    earlier_context_matches_without_focal=sum(
                        e["context"] and not e["focal"] for e in eligibility[:-1]))
    elif status == "no_eligible_root":
        c.add("no_eligible_root_window_exhausted",
              first_eligible is None and ticks[-1] == root.stop_tick)
    c.add("result_status_consistent",
          result["status"] == status and result["failure"] is None
          and result["producer_sources_unchanged"] is True and result["prefix_complete"] is True
          and result["configured"] is True and receipt["prefix_complete"] is True
          and result["family_id"] == family_id)

    # 8. transport reconstruction
    frame_by_tick = {f["ordinary"]["tick"]: f for f in frames}
    sub_by_tick: dict[int, list] = {}
    for s in submissions:
        sub_by_tick.setdefault(s["submitted_tick"], []).append(s)
    c.add("transport_ticks_equal_non_final_packets", [r["tick"] for r in transport] == ticks[:-1])
    reconstructed_accepted = []
    tproblems = []
    for r in transport:
        t = r["tick"]
        f = frame_by_tick.get(t)
        if f is None:
            tproblems.append((t, "no frame"))
            continue
        before = f["ordinary"]
        if r["before"] != compact(before):
            tproblems.append((t, "before != stored frame"))
        try:
            validate_command_step(r["before"], r["after"], r["receipts"])
        except ValueError as e:
            tproblems.append((t, f"validate_command_step: {e}"))
        ds = sorted(dec_by_tick.get(t, []), key=lambda d: d["owner"])
        subs = sub_by_tick.get(t, [])
        exp_sel, exp_cmds, exp_receipts = [], [], []
        si = 0
        for d in ds:
            dec = space.decode_action(d["action"], d["owner"])
            if dec.is_no_op:
                exp_sel.append({"owner": d["owner"], "action": d["action"], "name": None, "cost": None, "xy": None})
                if d.get("accepted") is not None:
                    tproblems.append((t, "wait marked accepted"))
                continue
            hud = next(p for p in before["players"] if p["owner"] == d["owner"])
            hand = next(h for h in hud["hand"] if h["handIndex"] == dec.slot)
            name = builder.card_name_for_token_id(int(observations[d["owner"]][ticks.index(t)].observation.hand_ids[dec.slot]))
            native_id = loader.get_card(name)._raw_entry["id"]
            x, y = round(dec.position.x * 1000), round(dec.position.y * 1000)
            cmd = f"replay-schedule-card {d['owner']} {native_id} {x} {y} {t + 1}"
            if si >= len(subs):
                tproblems.append((t, "missing submission"))
                continue
            s = subs[si]
            si += 1
            ok = (hand["cardId"] == native_id and s["owner"] == d["owner"] and s["action"] == d["action"]
                  and s["name"] == name and s["native_card_id"] == native_id and s["native_xy"] == [x, y]
                  and s["xy"] == [dec.position.x, dec.position.y] and s["cost"] == hand["cost"]
                  and s["scheduled_execution_tick"] == t + 1 and s["submitted_command"] == cmd)
            if not ok:
                tproblems.append((t, "submission/decision/HUD mismatch", d["owner"]))
            exp_sel.append({"owner": d["owner"], "action": d["action"], "name": name, "cost": hand["cost"],
                            "xy": [dec.position.x, dec.position.y]})
            exp_cmds.append(cmd)
            exp_receipts.append(s["schedule_receipt"])
            old = next(p for p in r["before"]["players"] if p["owner"] == d["owner"])
            new = next(p for p in r["after"]["players"] if p["owner"] == d["owner"])
            delta = (old["elixirRaw"] - new["elixirRaw"]) / 10000
            acc = delta >= s["cost"] - 0.1
            if acc is not True or d.get("accepted") is not True:
                tproblems.append((t, "not accepted", d["owner"], delta))
            # The slot may be empty while the next card cycles in; either way the
            # played card must have left that slot.
            newhand = next((h for h in new["hand"] if h["handIndex"] == dec.slot), None)
            if newhand is not None and newhand["cardId"] == native_id:
                tproblems.append((t, "played card still in slot after execution", d["owner"]))
            reconstructed_accepted.append({**s, "execution_tick": r["after"]["tick"], "native_spend_delta": delta,
                                           "native_acceptance_spend_evidence": acc})
        if si != len(subs):
            tproblems.append((t, "extra submissions"))
        if r["selected"] != exp_sel or r["commands"] != exp_cmds or r["receipts"] != exp_receipts:
            tproblems.append((t, "transport selected/commands/receipts mismatch"))
        nxt = t + 5
        if nxt in frame_by_tick and r["after"]["tick"] != t + 1:
            tproblems.append((t, "after tick"))
    c.add("transport_reconstructs_from_decisions_submissions_frames", not tproblems, tproblems[:8])
    c.add("submissions_all_ticks_covered", set(sub_by_tick) <= set(ticks[:-1]))
    c.add("accepted_commands_equal_reconstruction", accepted == reconstructed_accepted,
          {"accepted": len(accepted), "reconstructed": len(reconstructed_accepted)})
    c.add("result_commands_equal_accepted_log", result["commands"] == accepted)
    seqs = [rc["sequence"] for r in transport for rc in r["receipts"]]
    c.add("schedule_sequences_strictly_increasing", seqs == sorted(set(seqs)))
    info["accepted_commands"] = len(accepted)

    # 9. game_complete false
    c.add("game_complete_false_everywhere",
          receipt["game_complete"] is False and result["game_complete"] is False and plan["game_complete"] is False)
    info["checks"] = c.items
    info["pass"] = c.ok
    info["failed_checks"] = sorted(c.failed())
    return info


def finish_failed(ctx, c, info, receipt, out, frames, truncated, ticks, ledger_capture):
    c.add("failed_receipt_shape",
          receipt["prefix_complete"] is False and receipt["selected_family"] is None
          and receipt["capture_binding"] is None and bool(receipt["failure"])
          and receipt["game_complete"] is False)
    c.add("ledger_records_failed", ledger_capture is not None and ledger_capture["status"] == "failed")
    for missing in ("result.json", "native-read-session.json", "root-frame.json", "decisions.json",
                    "packet-ticks.json", "seat0-public.npz", "seat1-public.npz"):
        c.add("no_completion_artifact", not (out / missing).exists(), missing)
    cf = out / "collector-failure.json"
    if cf.exists():
        cfj = json.loads(cf.read_text())
        c.add("collector_failure_consistent",
              cfj["status"] == "failed" and cfj["claimed"] is True
              and cfj.get("native_read_session_closed_verified") is False
              and cfj["failure"] == receipt["failure"])
    c.add("partial_frames_cadence_prefix", ticks == list(range(90, 90 + 5 * len(ticks), 5)),
          {"n": len(ticks), "last": ticks[-1:]})
    tr_frames, tr_err = [], None
    try:
        tr_frames = read_jsonl(out / "transport.jsonl.gz", gz=True)
    except (EOFError, OSError, zlib.error, json.JSONDecodeError) as e:
        tr_err = f"{type(e).__name__}: {e}"
    info.update(partial_transport_records=len(tr_frames), transport_truncated=tr_err,
                partial_submissions=len(read_jsonl(out / "submissions.jsonl")),
                partial_accepted=len(read_jsonl(out / "accepted-commands.jsonl")),
                failure=receipt["failure"])
    c.add("partial_evidence_is_incomplete_not_selected",
          truncated is not None or tr_err is not None or not (out / "result.json").exists())
    c.add("game_complete_false_everywhere", receipt["game_complete"] is False)
    info["checks"] = c.items
    info["pass"] = c.ok  # passes == correctly recorded as failed/incomplete
    info["failed_checks"] = sorted(c.failed())
    return info


# ----------------------------------------------------------- negative probes
def _flip_reserved(decisions):
    for d in decisions:
        if d["prefix_reserve_applied"]:
            d["action"] = d["ordinary_action"]
            d["prefix_reserve_applied"] = False
            return decisions
    raise ValueError("no reserve decision to flip")


def _drop_first(rows):
    return rows[1:]


def _edit_first_command(rows):
    for r in rows:
        if r["commands"]:
            r["commands"][0] = r["commands"][0].rsplit(" ", 1)[0] + " 99999"
            return rows
    raise ValueError("no command")


def _later_root(result):
    result["selection"]["root_tick"] += 5
    return result


def _session_failed(session):
    session["status"] = "failed"
    return session


def _game_complete(result):
    result["game_complete"] = True
    return result


def _hash_flip(decisions):
    decisions[0]["public_packet_sha256"] = "0" * 64
    return decisions


def _ordinary_flip(decisions):
    d = decisions[0]
    d["ordinary_action"] = (d["ordinary_action"] + 1) % 2304
    d["action"] = d["ordinary_action"]
    d["prefix_reserve_applied"] = False
    return decisions


PROBES = {
    "drop_middle_frame": ("native-frames.jsonl.gz", lambda f: f[: len(f) // 2] + f[len(f) // 2 + 1 :]),
    "drop_root_frame": ("native-frames.jsonl.gz", lambda f: f[:-1]),
    "reserve_violation": ("decisions.json", _flip_reserved),
    "decision_packet_hash_altered": ("decisions.json", _hash_flip),
    "controller_action_altered": ("decisions.json", _ordinary_flip),
    "accepted_command_removed": ("accepted-commands.jsonl", _drop_first),
    "submission_removed": ("submissions.jsonl", _drop_first),
    "transport_command_altered": ("transport.jsonl.gz", _edit_first_command),
    "selection_moved_later": ("result.json", _later_root),
    "session_not_verified": ("native-read-session.json", _session_failed),
    "game_complete_true": ("result.json", _game_complete),
}


def negative_probes(ctx, families_by_id):
    """Each in-memory tamper must be detected by at least one semantic check."""
    out = {}
    for fam in ("m260928903-episode-00", "m260928903-episode-16"):
        claim = ctx["claims"][fam]
        cap = ctx["captures"].get(fam)
        for name, (fname, fn) in PROBES.items():
            TAMPER.clear()
            TAMPER[fname] = fn
            try:
                info = audit_capture(ctx, fam, claim, cap, None)
                detected = info["pass"] is False
                failed = info["failed_checks"]
            except Exception as e:  # noqa: BLE001 - a crash also counts as detection
                detected, failed = True, [f"exception {type(e).__name__}: {str(e)[:100]}"]
            finally:
                TAMPER.clear()
            out[f"{fam}:{name}"] = {"detected": detected, "failed_checks": failed}
            print("probe", fam, name, "DETECTED" if detected else "MISSED", failed[:4], flush=True)
    return out


# ------------------------------------------------------------------------- main
def main():
    started = time.time()
    g = Checks()
    ctx = load_context(g)
    decl = ctx["declaration"]
    batch_rows = {}
    batch_meta = {}
    for b in BATCHES:
        br = b / "batch-result.json"
        if br.exists():
            d = json.loads(br.read_text())
            batch_meta[b.name] = {
                "requested": len(d["requested_families"]),
                "reported": len(d["episodes"]),
                "producer_source_sha256": d["producer_source_sha256"],
                "zip_matches": d["producer_source_sha256"] == fsha(b / "producer-source.zip"),
                "game_complete": d["game_complete"],
            }
            g.add("batch_game_complete_false", d["game_complete"] is False, b.name)
            g.add("batch_zip_sha_matches_summary", batch_meta[b.name]["zip_matches"], b.name)
            for row in d["episodes"]:
                batch_rows[row["family_id"]] = row
    families = []
    for ep in decl.episodes:
        fam = ep.family_id
        claim = ctx["claims"].get(fam)
        cap = ctx["captures"].get(fam)
        if claim is None:
            families.append({"family_id": fam, "status": "unclaimed", "pass": None})
            continue
        out = Path(claim["output_path"])
        if not (out / "capture-receipt.json").exists():
            families.append({"family_id": fam, "status": "claimed_in_progress_or_missing_receipt",
                             "output": str(out), "ledger_capture": bool(cap), "pass": None})
            continue
        try:
            info = audit_capture(ctx, fam, claim, cap, batch_rows.get(fam))
        except Exception as e:  # noqa: BLE001
            info = {"family_id": fam, "status": "audit_error", "pass": False,
                    "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-2000:]}
        if fam == KNOWN_INTERRUPTED:
            info["expected"] = "failed (interrupted claim; must not be selected)"
            info["pass"] = info.get("pass") and info.get("status") == "failed"
        families.append(info)
        print(fam, info.get("status"), "PASS" if info.get("pass") else f"FAIL {info.get('failed_checks') or info.get('error')}",
              flush=True)
    # every ledger claim/capture belongs to a declared episode, one claim per output dir
    declared = {e.family_id for e in decl.episodes}
    g.add("ledger_claims_all_declared", set(ctx["claims"]) <= declared)
    g.add("ledger_captures_have_claims", set(ctx["captures"]) <= set(ctx["claims"]))
    outs = [c["output_path"] for c in ctx["claims"].values()]
    g.add("ledger_claim_outputs_unique", len(outs) == len(set(outs)))
    g.add("no_capture_recorded_selected_for_interrupted",
          ctx["captures"].get(KNOWN_INTERRUPTED, {}).get("status") == "failed")
    counts = {}
    for f in families:
        counts[f["status"]] = counts.get(f["status"], 0) + 1
    summary = {
        "schema": "native-prefix-development-v2-independent-audit.v1",
        "attempt_id": ATTEMPT,
        "generated_unix": int(time.time()),
        "runtime_snapshot": str(SNAP),
        "ledger": str(LEDGER) + " (opened mode=ro)",
        "declared_families": len(decl.episodes),
        "status_counts": counts,
        "audited": sum(1 for f in families if f["pass"] is not None),
        "audited_pass": sum(1 for f in families if f["pass"] is True),
        "audited_fail": [f["family_id"] for f in families if f["pass"] is False],
        "global_pass": g.ok,
        "global_failed_checks": sorted(g.failed()),
        "elapsed_seconds": round(time.time() - started, 1),
    }
    if "--negative-probes" in sys.argv:
        probes = negative_probes(ctx, {f["family_id"]: f for f in families})
        summary["negative_probes_run"] = len(probes)
        summary["negative_probes_missed"] = [k for k, v in probes.items() if not v["detected"]]
    else:
        probes = None
    results = {"summary": summary, "global_checks": g.items, "batches": batch_meta,
               "families": families, "negative_probes": probes}
    (HERE / "results.json").write_text(json.dumps(results, indent=2, default=str) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

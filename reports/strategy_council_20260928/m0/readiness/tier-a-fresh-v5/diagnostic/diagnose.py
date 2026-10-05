#!/usr/bin/env python
"""DIAGNOSTIC preview of Tier A rules for attempt m0-tier-a-fresh-v5.

Opened development evidence, NOT admission. This script never writes the
ledger: it opens readiness-v2.sqlite with ``?mode=ro`` and ``query_only``, never
calls ``evaluate_attempt`` (which records an irreversible exposure), and never
touches emulators or adb.

It reuses the attempt's pinned evaluator (runtime snapshot native-final-v5,
byte-identical to the workspace ``training_readiness_v2.py`` and
``readiness_capture_ownership.py``):

* ``training_readiness_v2.evaluate`` over every recorded branch (families with
  any missing branch come back ``complete=False``, exactly as in the real run);
* ``readiness_capture_ownership._verify_branch_files`` (read-only artifact hash
  and terminal-utility checks) for every recorded branch, unless
  ``--no-verify-files``; ``--audit-transport`` adds the slow transport audit.

For incomplete families it computes interval bounds over the *possible* values
of missing branches (score in {0, .5, 1}, margin in [-1, 1]) and reports a
verdict only when every possible completion agrees; otherwise the verdict is
``undetermined``. Missing branches are never imputed. For complete families
the bound logic collapses to exact values and is cross-checked against
``evaluate``.

Rerun (low priority, from anywhere):
  nice -n 15 /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/m0/runtime-snapshots/native-final-v5/.venv/bin/python -B \
    /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/m0/readiness/tier-a-fresh-v5/diagnostic/diagnose.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
import sys
from collections import Counter
from itertools import product
from pathlib import Path

sys.dont_write_bytecode = True

REPO = Path("/Users/sam/Desktop/code/clasher")
COUNCIL = REPO / "reports/strategy_council_20260928"
SNAP = COUNCIL / "m0/runtime-snapshots/native-final-v5"
ATTEMPT_DIR = COUNCIL / "m0/readiness/tier-a-fresh-v5"
LEDGER = COUNCIL / "readiness-v2.sqlite"
ATTEMPT_ID = "m0-tier-a-fresh-v5"
HERE = Path(__file__).resolve().parent

sys.path.insert(0, str(SNAP / "src"))

from clasher.rl.readiness_capture_ownership import (  # noqa: E402
    BranchClaim,
    CaptureReceipt,
    RootSeal,
    _verify_branch_files,
)
from clasher.rl.training_readiness_v2 import (  # noqa: E402
    ROLES,
    Branch,
    evaluate,
)

ENGINES = ("scalar", "reference")
MATERIAL_SCORE, MATERIAL_MARGIN = 0.25, 0.05
EVENT_SCORE, EVENT_MARGIN = 0.125, 0.01
COVERAGE_MARGIN = 0.01
EPS = 1e-12


# --------------------------------------------------------------------------
# Read-only ledger access
# --------------------------------------------------------------------------


def connect_ro(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path.resolve(strict=True).as_uri() + "?mode=ro", uri=True)
    db.execute("PRAGMA query_only=ON")
    return db


def load_ledger(path: Path, attempt_id: str):
    with connect_ro(path) as db:
        seal_row = db.execute(
            "SELECT record FROM root_seals WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
        if seal_row is None:
            raise SystemExit("attempt has no root seal")
        seal = RootSeal.model_validate_json(seal_row[0])
        claims = db.execute(
            "SELECT c.record, r.branch, r.artifacts FROM branch_claims c "
            "LEFT JOIN branch_results r ON c.nonce=r.nonce WHERE c.attempt_id=?",
            (attempt_id,),
        ).fetchall()
        captures = {
            fid: CaptureReceipt.model_validate_json(rec)
            for fid, rec in db.execute(
                "SELECT family_id, record FROM captures WHERE attempt_id=?",
                (attempt_id,),
            )
        }
        exposures = db.execute(
            "SELECT count(*) FROM exposures WHERE attempt_id=?", (attempt_id,)
        ).fetchone()[0]
    return seal, claims, captures, exposures


# --------------------------------------------------------------------------
# Branch status (recorded / failed / pending / unclaimed)
# --------------------------------------------------------------------------


def runner_log(output_path: str) -> Path | None:
    parent = Path(output_path).parent.name
    m = re.fullmatch(r"branches-reference-shard(\d+)-of\d+(-r\d+)?", parent)
    if m:
        return ATTEMPT_DIR / f"branches-native-shard{m.group(1)}{m.group(2) or ''}.log"
    if parent == "branches-scalar":
        return ATTEMPT_DIR / "branches-scalar.log"
    return None


def unrecorded_status(claim: BranchClaim) -> dict:
    log = runner_log(claim.output_path)
    text = log.read_text(errors="replace") if log and log.exists() else ""
    if "Traceback" in text:
        errors = [ln for ln in text.splitlines() if "Error" in ln]
        return {
            "status": "failed",
            "output_path": claim.output_path,
            "runner_log": str(log),
            "error": errors[-1][:300] if errors else "Traceback",
        }
    return {
        "status": "pending",
        "output_path": claim.output_path,
        "runner_log": str(log) if log else None,
    }


# --------------------------------------------------------------------------
# Card names (for mechanism review only; not part of any verdict)
# --------------------------------------------------------------------------


def card_ids_to_names(gamedata: Path) -> dict[int, str]:
    out: dict[int, str] = {}

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("id"), int) and isinstance(o.get("name"), str):
                out.setdefault(o["id"], o["name"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(json.loads(gamedata.read_text()))
    return out


def candidate_cards(family, capture: CaptureReceipt | None, names_cache: dict):
    """Map each candidate to card name via the sealed root frame's native hand."""
    info = {}
    hand = {}
    if capture is not None and capture.capture_binding is not None:
        cap = Path(capture.capture_binding.capture_path)
        try:
            frame = json.loads((cap / "root-frame.json").read_text())
            player = next(
                p
                for p in frame["ordinary"]["players"]
                if p.get("owner") == family.root_owner
            )
            hand = {c["handIndex"]: c["cardId"] for c in player["hand"]}
            gd = cap / "gamedata.json"
            if gd not in names_cache:
                names_cache[gd] = card_ids_to_names(gd)
            names = names_cache[gd]
        except (OSError, KeyError, StopIteration, ValueError):
            hand, names = {}, {}
    for c in family.candidates:
        if c.role == "wait":
            info[c.role] = {"card": "wait", "action_id": c.action_id}
            continue
        slot, tile = divmod(c.action_id, 576)
        card_id = hand.get(slot)
        info[c.role] = {
            "card": names.get(card_id, f"token{c.card_token}") if hand else f"token{c.card_token}",
            "card_token": c.card_token,
            "hand_slot": slot,
            "action_id": c.action_id,
            "tile_col_row": [tile % 18, tile // 18],
            "public_score": round(c.public_score, 4),
        }
    return info


# --------------------------------------------------------------------------
# Interval-bounded per-family verdicts (exact when complete)
# --------------------------------------------------------------------------


class Bounds:
    """Mean score / margin intervals over all possible completions."""

    def __init__(self, rows, family, conditions):
        self.rows = rows  # {(role, condition, engine): Branch}
        self.family = family
        self.conditions = conditions

    def per_condition(self, engine, role):
        out = []
        for cond in self.conditions:
            b = self.rows.get((role, cond, engine))
            out.append(
                None
                if b is None
                else (
                    b.score,
                    (b.own_remaining_hp - b.enemy_remaining_hp)
                    / self.family.starting_crown_hp,
                )
            )
        return out

    def complete(self, engine, role):
        return all(v is not None for v in self.per_condition(engine, role))

    def score(self, engine, role):
        vals = self.per_condition(engine, role)
        known = sum(v[0] for v in vals if v is not None)
        miss = sum(v is None for v in vals)
        return known / 4, (known + miss) / 4

    def margin(self, engine, role):
        vals = self.per_condition(engine, role)
        known = sum(v[1] for v in vals if v is not None)
        miss = sum(v is None for v in vals)
        return (known - miss) / 4, (known + miss) / 4


def abs_gap(a, b):
    """(lower, upper) bounds of |x - y| for x in a, y in b."""
    lo = max(0.0, a[0] - b[1], b[0] - a[1])
    hi = max(a[1] - b[0], b[1] - a[0])
    return lo, hi


def tri(lo_true: bool, hi_false: bool):
    return True if lo_true else False if hi_false else None


def family_verdicts(bounds: Bounds, score_floor: float, margin_floor: float):
    ref_s = {r: bounds.score("reference", r) for r in ROLES}
    ref_m = {r: bounds.margin("reference", r) for r in ROLES}
    cov_margin = max(margin_floor, COVERAGE_MARGIN)

    def informative(pairs):
        any_true, all_false = False, True
        for a, b in pairs:
            s_lo, s_hi = abs_gap(ref_s[a], ref_s[b])
            m_lo, m_hi = abs_gap(ref_m[a], ref_m[b])
            if s_lo > score_floor + EPS or m_lo > cov_margin + EPS:
                any_true = True
            if s_hi > score_floor + EPS or m_hi > cov_margin + EPS:
                all_false = False
        return tri(any_true, all_false)

    nonwait = [r for r in ROLES if r != "wait"]
    out = {
        "nonwait_informative": informative(
            [(a, b) for a, b in product(nonwait, nonwait) if a != b]
        ),
        "play_wait_informative": informative([(r, "wait") for r in nonwait]),
    }
    scalar_complete = all(bounds.complete("scalar", r) for r in ROLES)
    if not scalar_complete:
        out.update(
            scalar_preferred=None,
            material_failure=None,
            score_regret_bounds=None,
            repeatable_classes_possible=None,
        )
        return out
    scal = {r: (bounds.score("scalar", r)[0], bounds.margin("scalar", r)[0]) for r in ROLES}
    best = max(scal.values())
    preferred = tuple(r for r in ROLES if scal[r] == best)
    best_s_lo = max(ref_s[r][0] for r in ROLES)
    best_s_hi = max(ref_s[r][1] for r in ROLES)
    per = {}
    for p in preferred:
        ds_lo = max(0.0, best_s_lo - ref_s[p][1])
        ds_hi = best_s_hi - ref_s[p][0]
        # Margin regret is only taken against a comparator whose mean score
        # equals p's; bound over roles that could be such a comparator.
        tie_roles = [
            r
            for r in ROLES
            if ref_s[r][1] >= max(best_s_lo, ref_s[p][0]) - EPS
            and ref_s[r][0] <= ref_s[p][1] + EPS
        ]
        dm_hi = max(ref_m[r][1] for r in tie_roles) - ref_m[p][0]
        per[p] = (ds_lo, ds_hi, dm_hi)
    regret_lo = max(v[0] for v in per.values())
    regret_hi = max(v[1] for v in per.values())
    # Margin regret only counts when the preferred class ties the comparator's
    # score; impossible if its score gap is surely > 0 or margin gap is small.
    margin_fail_possible = any(
        not (v[0] > EPS) and v[2] > MATERIAL_MARGIN + EPS for v in per.values()
    )
    material = tri(
        regret_lo >= MATERIAL_SCORE - EPS,
        regret_hi < MATERIAL_SCORE - EPS and not margin_fail_possible,
    )
    # Repeated-harm event: never determined True from bounds (needs the frozen
    # comparator identity); determined False if impossible for every completion.
    possible = []
    for p, (ds_lo, ds_hi, dm_hi) in per.items():
        score_possible = ds_hi >= EVENT_SCORE - EPS and ds_hi > score_floor + EPS
        margin_possible = (
            not (ds_lo > EPS) and dm_hi > EVENT_MARGIN + EPS and dm_hi > margin_floor + EPS
        )
        if score_possible or margin_possible:
            possible.append(p)
    out.update(
        scalar_preferred=preferred,
        material_failure=material,
        score_regret_bounds=[round(regret_lo, 6), round(regret_hi, 6)],
        repeatable_classes_possible=tuple(possible),
    )
    return out


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def r6(x):
    return None if x is None else round(x, 6)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    ap.add_argument("--attempt-id", default=ATTEMPT_ID)
    ap.add_argument("--output", type=Path, default=HERE)
    ap.add_argument("--no-verify-files", action="store_true")
    ap.add_argument(
        "--audit-transport",
        action="store_true",
        help="also run the slow per-branch transport audit (CPU heavy)",
    )
    args = ap.parse_args()

    seal, claim_rows, captures, exposures = load_ledger(args.ledger, args.attempt_id)
    protocol = seal.protocol
    conditions = protocol.conditions
    floors = protocol.floors
    score_floor = floors.score if floors else 0.0
    margin_floor = floors.margin if floors else 0.0

    recorded: dict[tuple, Branch] = {}
    status: dict[tuple, dict] = {}
    verify_failures = []
    for raw_claim, raw_branch, raw_artifacts in claim_rows:
        claim = BranchClaim.model_validate_json(raw_claim)
        key = (claim.family_id, claim.candidate_role, claim.condition, claim.engine)
        if raw_branch is None:
            status[key] = unrecorded_status(claim)
            continue
        branch = Branch.model_validate_json(raw_branch)
        if not args.no_verify_files:
            try:
                _verify_branch_files(
                    claim,
                    branch,
                    json.loads(raw_artifacts),
                    audit_transport=args.audit_transport,
                )
            except Exception as exc:  # report, never drop silently
                verify_failures.append({"key": list(key), "error": repr(exc)[:300]})
                status[key] = {"status": "recorded_but_file_check_failed", "error": repr(exc)[:300]}
                continue
        recorded[key] = branch
        status[key] = {"status": "recorded"}

    # 1. The project's own evaluator over every recorded branch.
    report = evaluate(protocol, tuple(recorded.values()))
    by_family = {r.family_id: r for r in report.families}

    names_cache: dict = {}
    families_out = []
    mismatch_rows = []
    convergent_rows = []
    branch_agree = Counter()
    fam_agree = Counter()
    exposures_all = Counter({r: 0 for r in ROLES})
    above_floor_events = []
    for fam in protocol.families:
        fid = fam.family_id
        rows = {
            (k[1], k[2], k[3]): b for k, b in recorded.items() if k[0] == fid
        }
        missing = []
        for role, cond, eng in product(ROLES, conditions, ENGINES):
            key = (fid, role, cond, eng)
            if key not in recorded:
                st = status.get(key, {"status": "unclaimed"})
                missing.append({"role": role, "condition": cond, "engine": eng, **st})
        bounds = Bounds(rows, fam, conditions)
        verdicts = family_verdicts(bounds, score_floor, margin_floor)
        er = by_family[fid]
        cap = captures.get(fid)
        root_tick = cap.capture_binding.root_tick if cap and cap.capture_binding else None
        cards = candidate_cards(fam, cap, names_cache)

        if verdicts["scalar_preferred"] is not None:
            for p in verdicts["scalar_preferred"]:
                exposures_all[p] += 1

        # Cross-check bound logic against evaluate on complete families.
        if er.complete:
            assert verdicts["nonwait_informative"] == er.nonwait_informative, fid
            assert verdicts["play_wait_informative"] == er.play_wait_informative, fid
            assert verdicts["material_failure"] == er.material_failure, fid
            assert tuple(verdicts["scalar_preferred"]) == er.scalar_preferred, fid
            assert set(er.repeatable_classes) <= set(verdicts["repeatable_classes_possible"]), fid

        # Scalar vs reference per-branch outcome agreement (diagnostic).
        opposite = 0
        pairs = 0
        reversals = []
        margin_diffs = []
        for role, cond in product(ROLES, conditions):
            s, r = rows.get((role, cond, "scalar")), rows.get((role, cond, "reference"))
            if s is None or r is None:
                continue
            pairs += 1
            branch_agree["pairs"] += 1
            branch_agree["same_score"] += s.score == r.score
            if abs(s.score - r.score) == 1.0:
                opposite += 1
                branch_agree["win_loss_reversed"] += 1
                reversals.append(
                    {
                        "role": role,
                        "card": cards[role]["card"],
                        "condition": cond,
                        "scalar": {"score": s.score, "own_hp": s.own_remaining_hp, "enemy_hp": s.enemy_remaining_hp},
                        "reference": {"score": r.score, "own_hp": r.own_remaining_hp, "enemy_hp": r.enemy_remaining_hp},
                    }
                )
            margin_diffs.append(
                abs(
                    (s.own_remaining_hp - s.enemy_remaining_hp)
                    - (r.own_remaining_hp - r.enemy_remaining_hp)
                )
                / fam.starting_crown_hp
            )
        per_role = {}
        for role in ROLES:
            per_role[role] = {"card": cards[role]["card"]}
            for eng in ENGINES:
                per_role[role][eng] = [
                    None if v is None else {"score": v[0], "margin": r6(v[1])}
                    for v in bounds.per_condition(eng, role)
                ]
            for eng in ENGINES:
                if bounds.complete(eng, role):
                    per_role[role][f"{eng}_mean"] = {
                        "score": bounds.score(eng, role)[0],
                        "margin": r6(bounds.margin(eng, role)[0]),
                    }
        if er.complete:
            fam_agree["complete"] += 1
            fam_agree["reference_best_in_scalar_preferred"] += (
                er.reference_comparator in er.scalar_preferred
            )
            fam_agree["zero_regret"] += er.score_regret == 0 and er.margin_regret == 0
            for role in er.above_floor_classes:
                above_floor_events.append(
                    {
                        "family_id": fid,
                        "root_owner": fam.root_owner,
                        "root_tick": root_tick,
                        "scalar_preferred_class": role,
                        "scalar_preferred_card": cards[role],
                        "reference_comparator": er.reference_comparator,
                        "reference_comparator_card": cards[er.reference_comparator],
                        "all_candidates": cards,
                        "score_regret": r6(er.score_regrets[role]),
                        "margin_regret": r6(er.margin_regrets[role]),
                        "score_signs_comparator_minus_candidate": er.score_signs[role],
                        "margin_signs_comparator_minus_candidate": er.margin_signs[role],
                        "repeatable_harm_event": role in er.repeatable_classes,
                        "material_failure_family": er.material_failure,
                    }
                )
        mismatch_rows.append(
            {
                "family_id": fid,
                "paired_branches": pairs,
                "win_loss_reversed": opposite,
                "mean_abs_margin_diff": r6(sum(margin_diffs) / len(margin_diffs)) if margin_diffs else None,
                "root_owner": fam.root_owner,
                "root_tick": root_tick,
                "reversals": reversals,
            }
        )
        # Candidates whose four reference outcomes are identical (diagnostic:
        # the root choice did not change the result under any continuation).
        groups = {}
        for role in ROLES:
            if bounds.complete("reference", role):
                groups.setdefault(tuple(bounds.per_condition("reference", role)), []).append(role)
        convergent = [g for g in groups.values() if len(g) > 1]
        if convergent:
            convergent_rows.append(
                {"family_id": fid, "root_tick": root_tick, "identical_reference_outcomes": convergent,
                 "cards": {r: cards[r]["card"] for g in convergent for r in g}}
            )
        undetermined = [
            name
            for name, v in (
                ("nonwait_coverage", verdicts["nonwait_informative"]),
                ("play_wait_coverage", verdicts["play_wait_informative"]),
                ("material_failure", verdicts["material_failure"]),
            )
            if v is None
        ]
        if not er.complete and verdicts["repeatable_classes_possible"]:
            undetermined.append(
                "repeated_harm:" + ",".join(verdicts["repeatable_classes_possible"])
            )
        families_out.append(
            {
                "family_id": fid,
                "root_owner": fam.root_owner,
                "root_tick": root_tick,
                "complete": er.complete,
                "missing_branches": missing,
                "undetermined_verdicts": undetermined,
                "verdicts": {
                    "nonwait_informative": verdicts["nonwait_informative"],
                    "play_wait_informative": verdicts["play_wait_informative"],
                    "material_failure": verdicts["material_failure"],
                    "scalar_preferred": verdicts["scalar_preferred"],
                    "score_regret_bounds": verdicts["score_regret_bounds"],
                    "repeatable_classes_possible": verdicts["repeatable_classes_possible"],
                },
                "evaluate_family_result": er.model_dump(mode="json"),
                "candidates": per_role,
            }
        )

    def count(field, value):
        return sum(f["verdicts"][field] is value for f in families_out)

    cov_true, cov_none = count("nonwait_informative", True), count("nonwait_informative", None)
    mat_true, mat_none = count("material_failure", True), count("material_failure", None)
    incomplete = [f for f in families_out if not f["complete"]]
    events_complete = dict(report.class_events)
    events_possible_incomplete = Counter(
        p for f in incomplete for p in (f["verdicts"]["repeatable_classes_possible"] or ())
    )
    all_missing = [dict(family_id=f["family_id"], **m) for f in families_out for m in f["missing_branches"]]
    missing_status = Counter(m["status"] for m in all_missing)
    mismatch_rows.sort(key=lambda r: (-r["win_loss_reversed"], -(r["mean_abs_margin_diff"] or 0)))

    results = {
        "schema": "clasher-tier-a-diagnostic-v1",
        "evidence_role": "DIAGNOSTIC opened development evidence; NOT admission; evaluate_attempt not called; no exposure recorded",
        "attempt_id": args.attempt_id,
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "ledger": str(args.ledger),
        "ledger_exposures_for_attempt": exposures,
        "evaluator_source": str(SNAP / "src/clasher/rl/training_readiness_v2.py"),
        "protocol_sha256": protocol.sha256,
        "protocol_status": protocol.status,
        "floors": {"score": score_floor, "margin": margin_floor},
        "file_verification": "skipped" if args.no_verify_files else ("full transport audit" if args.audit_transport else "artifact hashes + terminal utility (no transport audit)"),
        "file_verification_failures": verify_failures,
        "branches": {
            "expected": 32 * 4 * 4 * 2,
            "recorded_by_engine": dict(Counter(k[3] for k in recorded)),
            "missing_by_status": dict(missing_status),
            "missing": all_missing,
        },
        "evaluate_report": {
            "status": report.status,
            "reasons": report.reasons,
            "informative_families_complete_only": report.informative_families,
            "material_failures_complete_only": report.material_failures,
            "class_exposures_complete_only": report.class_exposures,
            "class_events_complete_only": report.class_events,
            "insufficient_class_coverage_complete_only": report.insufficient_class_coverage,
        },
        "summary": {
            "complete_families": 32 - len(incomplete),
            "incomplete_families": [f["family_id"] for f in incomplete],
            "nonwait_coverage": {
                "determined_true": cov_true,
                "determined_false": count("nonwait_informative", False),
                "undetermined": cov_none,
                "range": [cov_true, cov_true + cov_none],
                "required": 16,
                "meets_requirement": True if cov_true >= 16 else (False if cov_true + cov_none < 16 else None),
            },
            "play_wait_coverage_determined_true": count("play_wait_informative", True),
            "material_failures": {
                "determined_true": mat_true,
                "determined_false": count("material_failure", False),
                "undetermined": mat_none,
                "families": [f["family_id"] for f in families_out if f["verdicts"]["material_failure"] is True],
                "undetermined_families": [f["family_id"] for f in families_out if f["verdicts"]["material_failure"] is None],
            },
            "repeated_harm": {
                "events_by_class_complete_families": events_complete,
                "possible_additional_events_by_class_incomplete_families": dict(events_possible_incomplete),
                "automatic_block_complete_only": any(n >= 4 for n in events_complete.values()),
                "automatic_block_possible": any(
                    events_complete[r] + events_possible_incomplete.get(r, 0) >= 4 for r in ROLES
                ),
            },
            "class_exposures": {
                "complete_families": report.class_exposures,
                "including_incomplete_with_complete_scalar": dict(exposures_all),
                "insufficient_coverage_lt4": [r for r in ROLES if exposures_all[r] < 4],
            },
            "scalar_native_agreement": {
                "branch_pairs": branch_agree["pairs"],
                "same_match_score": branch_agree["same_score"],
                "win_loss_reversed": branch_agree["win_loss_reversed"],
                "complete_families": fam_agree["complete"],
                "reference_best_in_scalar_preferred": fam_agree["reference_best_in_scalar_preferred"],
                "zero_regret_families": fam_agree["zero_regret"],
            },
            "above_floor_event_count": len(above_floor_events),
            "attempt_verdict_preview": (
                "cannot pass (declared branches failed); "
                + ("would be BLOCKED on recorded data" if report.status == "blocked" else "no automatic block on recorded data")
            ),
        },
        "above_floor_events": above_floor_events,
        "scalar_reference_divergence_by_family": mismatch_rows,
        "convergent_candidates": convergent_rows,
        "families": families_out,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    (args.output / "README.md").write_text(render_readme(results))
    s = results["summary"]
    print(json.dumps({k: s[k] for k in ("complete_families", "nonwait_coverage", "material_failures", "repeated_harm", "above_floor_event_count", "scalar_native_agreement")}, indent=1))
    print("missing:", dict(missing_status), "file-check failures:", len(verify_failures))


def render_readme(res: dict) -> str:
    s = res["summary"]
    cov, mat, rh = s["nonwait_coverage"], s["material_failures"], s["repeated_harm"]
    ag = s["scalar_native_agreement"]
    lines = [
        "# Tier A diagnostic preview: m0-tier-a-fresh-v5",
        "",
        "**DIAGNOSTIC, opened development evidence, NOT admission.** The attempt cannot pass:",
        "episode-21 `alternate_card` reference branches failed on the out-of-arena Log instrument",
        "edge (`../operational-failure.json`). `evaluate_attempt` is *not* called (it records an",
        "irreversible exposure); the ledger is opened `?mode=ro` with `query_only`.",
        "",
        f"Generated {res['generated_utc']} from `{res['ledger']}`.",
        "This file and `results.json` are regenerated by `diagnose.py`; edits here are overwritten.",
        "",
        "## Rerun",
        "",
        "```",
        "nice -n 15 " + str(SNAP / ".venv/bin/python") + " -B \\",
        "  " + str(HERE / "diagnose.py"),
        "```",
        "",
        "Options: `--no-verify-files` (skip artifact-hash checks), `--audit-transport` (slow full",
        "transport audit), `--output DIR`.",
        "",
        "## Method",
        "",
        "- Evaluator: the attempt's pinned `training_readiness_v2.evaluate` (snapshot native-final-v5,",
        "  byte-identical to the workspace file), run over every recorded branch. Families with any",
        "  missing branch come back `complete=False`, as in the real evaluation.",
        "- Recorded branches are checked with `readiness_capture_ownership._verify_branch_files`",
        f"  ({res['file_verification']}).",
        "- Incomplete families: interval bounds over every possible value of the missing branches",
        "  (score in {0, 0.5, 1}, margin in [-1, 1]). A verdict is reported only when every completion",
        "  agrees; otherwise it is `undetermined`. Nothing is imputed. On complete families the bound",
        "  logic is asserted equal to `evaluate`.",
        f"- Floors from the sealed protocol: score {res['floors']['score']}, margin {res['floors']['margin']}.",
        "  With zero floors, any positive regret is an above-floor event needing mechanism review.",
        "",
        "## Current numbers",
        "",
        f"- Branches recorded: {res['branches']['recorded_by_engine']} of {res['branches']['expected']};"
        f" missing by status: {res['branches']['missing_by_status']}.",
        f"- File-check failures: {len(res['file_verification_failures'])}.",
        f"- Complete families: {s['complete_families']}/32. Incomplete: {', '.join(s['incomplete_families']) or 'none'}.",
        f"- Consequential non-wait coverage: {cov['determined_true']} determined, {cov['undetermined']} undetermined"
        f" (range {cov['range'][0]}-{cov['range'][1]}; need 16) -> meets: {cov['meets_requirement']}.",
        f"- Play-vs-wait discrimination (reported separately): {s['play_wait_coverage_determined_true']} families.",
        f"- Material failures: {mat['determined_true']} determined {mat['families']}; undetermined: {mat['undetermined_families']}.",
        f"- Repeated-harm events (complete families): {rh['events_by_class_complete_families']};"
        f" still possible in incomplete families: {rh['possible_additional_events_by_class_incomplete_families']};"
        f" automatic block now: {rh['automatic_block_complete_only']}, still possible: {rh['automatic_block_possible']}.",
        f"- Class exposures (complete families): {s['class_exposures']['complete_families']};"
        f" incl. incomplete families with complete scalar side: {s['class_exposures']['including_incomplete_with_complete_scalar']};"
        f" insufficient (<4): {s['class_exposures']['insufficient_coverage_lt4']}.",
        f"- Scalar/native agreement (diagnostic): {ag['same_match_score']}/{ag['branch_pairs']} paired branches same match score,"
        f" {ag['win_loss_reversed']} win/loss reversals; reference-best in scalar-preferred set in"
        f" {ag['reference_best_in_scalar_preferred']}/{ag['complete_families']} complete families.",
        f"- `evaluate` status on recorded data: {res['evaluate_report']['status']} ({'; '.join(res['evaluate_report']['reasons'])}).",
        "",
        f"## Above-floor events for mechanism review ({s['above_floor_event_count']})",
        "",
        "| family | owner | root tick | scalar-preferred (card) | reference best (card) | score regret | margin regret | score signs | repeat-harm | material |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for e in res["above_floor_events"]:
        lines.append(
            f"| {e['family_id']} | {e['root_owner']} | {e['root_tick']} | {e['scalar_preferred_class']} ({e['scalar_preferred_card']['card']})"
            f" | {e['reference_comparator']} ({e['reference_comparator_card']['card']}) | {e['score_regret']} | {e['margin_regret']}"
            f" | {list(e['score_signs_comparator_minus_candidate'])} | {e['repeatable_harm_event']} | {e['material_failure_family']} |"
        )
    lines += [
        "",
        "## Incomplete families",
        "",
        "| family | missing branches (status) | undetermined verdicts | score-regret bounds |",
        "|---|---|---|---|",
    ]
    for f in res["families"]:
        if f["complete"]:
            continue
        miss = Counter(f"{m['engine']}/{m['role']}:{m['status']}" for m in f["missing_branches"])
        lines.append(
            f"| {f['family_id']} | {', '.join(f'{k} x{v}' for k, v in miss.items())} | {', '.join(f['undetermined_verdicts']) or 'none'}"
            f" | {f['verdicts']['score_regret_bounds']} |"
        )
    lines += [
        "",
        "## Largest scalar/reference divergence (diagnostic only)",
        "",
        "| family | paired branches | win/loss reversed | mean abs margin diff |",
        "|---|---|---|---|",
    ]
    for r in res["scalar_reference_divergence_by_family"][:8]:
        lines.append(f"| {r['family_id']} | {r['paired_branches']} | {r['win_loss_reversed']} | {r['mean_abs_margin_diff']} |")
    lines += ["", "Win/loss reversals (scalar vs reference, same family/candidate/continuation):", ""]
    for r in res["scalar_reference_divergence_by_family"]:
        for x in r["reversals"]:
            lines.append(
                f"- {r['family_id']} (owner {r['root_owner']}, tick {r['root_tick']}) {x['role']} ({x['card']}) {x['condition']}:"
                f" scalar score {x['scalar']['score']} HP {x['scalar']['own_hp']:.0f}/{x['scalar']['enemy_hp']:.0f},"
                f" reference score {x['reference']['score']} HP {x['reference']['own_hp']:.0f}/{x['reference']['enemy_hp']:.0f}"
            )
    lines += [
        "",
        "## Convergent candidates (diagnostic only)",
        "",
        "Roles with identical reference outcomes in all four continuations; the root choice made no",
        "difference (often the controller plays the other card at the next 5-tick decision).",
        "",
    ]
    for c in res["convergent_candidates"]:
        lines.append(f"- {c['family_id']} (tick {c['root_tick']}): {c['identical_reference_outcomes']} {c['cards']}")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()

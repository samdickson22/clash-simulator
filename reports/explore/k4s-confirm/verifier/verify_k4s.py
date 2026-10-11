#!/usr/bin/env python3
"""Independent integer-count verifier for the PREREG-K4S confirmatory study.

Author: Claude Haiku 5.5, the independent verifier author (not the reducer's author). Written from
PREREG-K4S-DRAFT-r3.md (governs) and K4S-SPEC.md only. It did not read reduce.py. It imports nothing from
the k4s-confirm or t1 trees; it uses only the standard library and numpy.

What it does, in order:
  1. Seal (spec §7): verifies the release receipt against the repository at the receipt's commit, with
     sha256 of each item, before any game file is opened. Otherwise it refuses, unless the tree is marked
     SYNTHETIC and --synthetic is given.
  2. Counting (spec §6.2): block completeness, game SHA-256, arm set == descriptor order, the replacement
     ledger (index, cell, bank and cap rules), and exactly 3000 primary / 900 guard logical blocks, with 600 /
     300 in the subsample.
  3. Integer outcomes: loss = winner is not None and winner != seat; draw = winner is None.
  4. Stratified paired bootstrap (spec §6.3): R = 10,000, default_rng(2026101170); analyses drawn in the order
     primary full, guard full, primary subsample, guard subsample; cells ascending; one index draw per cell,
     shared by all arms.
  5. Exact rational percentile bounds (Fraction; position = (R-1) q with q = 1/40 and 39/40; linear
     interpolation; times 100/n). Rational values govern every gate; floats are display and disagreement checks.
  6. Contrasts (§6.4), hypotheses and the fixed sequence (§6.5), admission, veto, usable cells, validity.
  7. Flags: exact boundary hits, bounds within one count step (100/n pp) of a threshold, float/exact decision
     disagreement, and float/exact value gaps.
  8. Optional --compare against a reducer output: an exact, key-by-key comparison of its verifier_view (spec §6.7),
     see compare_verifier_view. Any missing or extra key, or any difference, is a mismatch.

Exit code: 0 clean, 1 flags only, 2 refusal, errors, or comparison mismatches.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import defaultdict
from fractions import Fraction
from pathlib import Path, PurePosixPath

import numpy as np

# §7 release barrier (K4S-SPEC §7).
COORDINATOR = "0523ae6f-baa3-4d4e-b233-b392671670db"
SEAL_STUDY = "PREREG-K4S"
SEAL_REQUIRED = ("completion", "production_checks", "verifier_receipt", "mac_procedure_manifest")
SEAL_END_PAIR = ("end_reference", "end_recheck")
SEAL_END_ALT = "ratio_unavailable_declaration"
SEAL_TIERS_ALTS = ("tiers_summary", "tiers_release")

# §3.4 bases, sizes and replacement rules. Replacement index = n + cells * k + cell, with k 0-based.
POPS = {
    "primary": dict(base=4503605807370496, n=3000, sub=600, cells=50, rot_div=50, max_k=11),
    "guard": dict(base=4503605817370496, n=900, sub=300, cells=18, rot_div=18, max_k=9),
}
REPLACEMENT_CAP_DIVISOR = 10  # 10% per population: 300 primary, 90 guard

# §1.1, §2.2–2.4, §3.1. Arm: cell c (string), budget ms, kernel, default source, s-default rule.
CORE = ["K4-200", "K4S-200", "K4-180", "K4S-180", "K4-160", "K4S-160", "K4S-140", "K4S-120"]
SUB_ARMS = ["K4-140", "K4-120"]
ALL_ARMS = CORE + SUB_ARMS
ARM_SPEC = {
    "K4-200": dict(c="1.0", budget=200, kernel="K4-anytime", default="v1", rule=None),
    "K4S-200": dict(c="1.0", budget=200, kernel="K4-anytime-sdefault", default="SD1", rule="full"),
    "K4-180": dict(c="0.9", budget=180, kernel="K4-anytime", default="v1", rule=None),
    "K4S-180": dict(c="0.9", budget=180, kernel="K4-anytime-sdefault", default="SD1", rule="full"),
    "K4-160": dict(c="0.8", budget=160, kernel="K4-anytime", default="v1", rule=None),
    "K4S-160": dict(c="0.8", budget=160, kernel="K4-anytime-sdefault", default="SD1", rule="full"),
    "K4S-140": dict(c="0.7", budget=140, kernel="K4-anytime-sdefault", default="SD1", rule="full"),
    "K4S-120": dict(c="0.6", budget=120, kernel="K4-anytime-sdefault", default="SD1", rule="full"),
    "K4-140": dict(c="0.7", budget=140, kernel="K4-anytime", default="v1", rule=None),
    "K4-120": dict(c="0.6", budget=120, kernel="K4-anytime", default="v1", rule=None),
}
RESERVE_MS = 8
PIN_KEYS = ("freeze_manifest_sha256", "runtime_pin_sha256", "opponent_checkpoint_sha256", "native_sha256")
SD1_KEYS = ("sd1_manifest_sha256", "sd1_checkpoint_sha256", "sd1_calibration_sha256", "sd1_threshold")
HUB_HOST = "127x01"

# §5.1, §6.3 bootstrap.
REPS = 10_000
BOOT_SEED = 2026101170
Q_LO = Fraction(1, 40)   # 2.5th percentile
Q_HI = Fraction(39, 40)  # 97.5th percentile

# §1.2, §6.5 margins (pp). Upper bounds only.
VETO_MAX = 5
VALIDITY_LO, VALIDITY_HI = 10, 30
# The fixed order with c* = 0.9 (§1.2). H4 is dropped when c* = 0.8 (§1.3).
HYP_ORDER = [
    ("H1", "B", "0.8"), ("H2", "B", "0.7"), ("H3", "B", "0.6"), ("H4", "A", "0.9"),
    ("H5", "A", "0.8"), ("H6", "A", "0.7"), ("H7", "A", "0.6"),
]
# §6.7 verifier_view: schema name and the cells it reports, in order.
VIEW_SCHEMA = "clasher.k4s.verifier-view.v1"
VIEW_CELLS = ("0.9", "0.8", "0.7", "0.6")
# §6.4: (kind, cell) -> (analysis, arm x, arm y). Δ_ref uses K4-200 as the reference.
CONTRASTS = {
    ("dref", "0.9"): ("P_full", "K4S-180", "K4-200"),
    ("dref", "0.8"): ("P_full", "K4S-160", "K4-200"),
    ("dref", "0.7"): ("P_full", "K4S-140", "K4-200"),
    ("dref", "0.6"): ("P_full", "K4S-120", "K4-200"),
    ("drefg", "0.9"): ("G_full", "K4S-180", "K4-200"),
    ("drefg", "0.8"): ("G_full", "K4S-160", "K4-200"),
    ("drefg", "0.7"): ("G_full", "K4S-140", "K4-200"),
    ("drefg", "0.6"): ("G_full", "K4S-120", "K4-200"),
    ("dsame", "0.8"): ("P_full", "K4S-160", "K4-160"),
    ("dsame", "0.7"): ("P_sub", "K4S-140", "K4-140"),
    ("dsame", "0.6"): ("P_sub", "K4S-120", "K4-120"),
    ("veto", "0.9"): ("P_full", "K4S-180", "K4-180"),
}
# name -> (population, subsample?). The bootstrap draws in this order (§6.3).
ANALYSES = [
    ("P_full", "primary", False),
    ("G_full", "guard", False),
    ("P_sub", "primary", True),
    ("G_sub", "guard", True),
]


class Refusal(Exception):
    """Raised before any game is opened: seal failure, bad flag combination, or a missing release."""


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True)


def default_repo():
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                       cwd=Path(__file__).resolve().parent)
    if r.returncode != 0:
        raise Refusal("cannot find the repository root; pass --repo")
    return Path(r.stdout.strip())


def check_seal(repo, receipt):
    """§7. Every check runs before any game file is opened. Returns the verified item hashes."""
    if receipt.get("coordinator_thread") != COORDINATOR:
        raise Refusal("release receipt coordinator_thread is not the K4S coordinator")
    if receipt.get("study") != SEAL_STUDY:
        raise Refusal(f"release receipt study is not {SEAL_STUDY}")
    for key in ("authorization_message_id", "authorized_at_utc"):
        if not isinstance(receipt.get(key), str) or not receipt[key].strip():
            raise Refusal(f"release receipt has no {key}")
    commit = receipt.get("commit")
    if not isinstance(commit, str) or not commit:
        raise Refusal("release receipt has no commit")
    if git(repo, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}").returncode != 0:
        raise Refusal(f"release commit {commit} does not exist in {repo}")
    if git(repo, "merge-base", "--is-ancestor", commit, "HEAD").returncode != 0:
        raise Refusal(f"release commit {commit} is not an ancestor of HEAD")

    items = receipt.get("items")
    if not isinstance(items, dict):
        raise Refusal("release receipt has no items")
    for name in SEAL_REQUIRED:
        if name not in items:
            raise Refusal(f"release receipt lacks item {name}")
    # Exactly one alternative from each pair: the end reference, and the tiers item (§7 items 2 and 6).
    ends = {n for n in (*SEAL_END_PAIR, SEAL_END_ALT) if n in items}
    if ends not in (set(SEAL_END_PAIR), {SEAL_END_ALT}):
        raise Refusal("release receipt needs exactly one of end_reference + end_recheck, or ratio_unavailable_declaration")
    tiers = {n for n in SEAL_TIERS_ALTS if n in items}
    if len(tiers) != 1:
        raise Refusal("release receipt needs exactly one of tiers_summary or tiers_release")
    allowed = set(SEAL_REQUIRED) | set(SEAL_END_PAIR) | {SEAL_END_ALT} | set(SEAL_TIERS_ALTS)
    unknown = sorted(set(items) - allowed)
    if unknown:
        raise Refusal(f"release receipt has unknown items {unknown}")

    hashes, content = {}, {}
    for name, item in sorted(items.items()):
        if (not isinstance(item, dict) or set(item) != {"path", "sha256"}
                or not isinstance(item["path"], str) or not isinstance(item["sha256"], str)):
            raise Refusal(f"release item {name} needs exactly path and sha256")
        path = item["path"]
        parts = PurePosixPath(path).parts if path else ()
        if not parts or PurePosixPath(path).is_absolute() or ".." in parts:
            raise Refusal(f"release item {name}: path {path!r} is not repo-relative")
        if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise Refusal(f"release item {name}: sha256 is not 64 lowercase hex digits")
        shown = git(repo, "show", f"{commit}:{path}")
        if shown.returncode != 0:
            raise Refusal(f"release item {name}: git show {commit}:{path} failed")
        digest = sha256_bytes(shown.stdout)
        if digest != item["sha256"]:
            raise Refusal(f"release item {name}: sha256 {digest} != declared {item['sha256']}")
        try:
            working = (Path(repo) / path).read_bytes()
        except OSError:
            raise Refusal(f"release item {name}: {path} is missing from the working tree")
        if working != shown.stdout:
            raise Refusal(f"release item {name}: working-tree bytes differ from {commit}:{path}")
        hashes[name] = digest
        content[name] = shown.stdout

    # Completion receipt (§7 item 1): the field names are fixed by K4S-SPEC §7.
    try:
        completion = json.loads(content["completion"])
    except ValueError:
        raise Refusal("completion receipt is not JSON")
    if not isinstance(completion, dict) or completion.get("reporting_complete") is not True \
            or completion.get("outcomes_sealed") is not True:
        raise Refusal("completion receipt is not reporting_complete with outcomes_sealed")
    for field, pop in (("counted_primary_blocks", "primary"), ("counted_guard_blocks", "guard")):
        value = completion.get(field)
        if not is_int(value) or value != POPS[pop]["n"]:
            raise Refusal(f"completion receipt {field} is {value!r}, expected {POPS[pop]['n']}")
    return {"commit": commit, "item_sha256": hashes}


def is_int(value):
    return type(value) is int


def approx(value, target):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and abs(float(value) - target) <= 1e-9


def expected_layout(pop, logical, pops):
    """§3.1: rotation, arm order and the subsample flag for a logical index."""
    spec = pops[pop]
    rho = (logical // spec["rot_div"]) % 8
    rotated = CORE[rho:] + CORE[:rho]
    if logical < spec["sub"]:
        order = rotated[0:3] + ["K4-140"] + rotated[3:6] + ["K4-120"] + rotated[6:8]
        return order, rho, True
    return rotated, rho, False


def resolve_logical(did, descs, errors, seen=()):
    """§3.1 [I-1]: a replacement's logical index is that of the block it ultimately replaces."""
    if did in seen:
        errors.append(f"replacement cycle through {did}")
        return None
    desc = descs.get(did)
    if desc is None:
        errors.append(f"replacement target {did} is in neither the ledger nor the tree")
        return None
    if desc.get("replaces") is None:
        return desc.get("index")
    return resolve_logical(desc["replaces"], descs, errors, seen + (did,))


def check_descriptor(did, desc, logical, errors, pops):
    """Layout, seed, cell and seat for one descriptor, given its logical index."""
    pop = desc.get("population")
    if pop not in pops:
        errors.append(f"{did}: unknown population {pop!r}")
        return
    spec = pops[pop]
    index = desc.get("index")
    if not is_int(index) or desc.get("id") != f"{pop}-{index:04d}":
        errors.append(f"{did}: id/index mismatch")
        return
    if desc.get("seed") != spec["base"] + index:
        errors.append(f"{did}: seed {desc.get('seed')} != base + index")
    if desc.get("cell") != logical % spec["cells"]:
        errors.append(f"{did}: cell {desc.get('cell')} != logical index mod cells")
    if desc.get("seat") != desc.get("cell", -1) % 2:
        errors.append(f"{did}: seat is not cell mod 2")
    order, rho, is_sub = expected_layout(pop, logical, pops)
    if desc.get("order") != order:
        errors.append(f"{did}: order {desc.get('order')} != expected layout {order}")
    if desc.get("rotation") != rho:
        errors.append(f"{did}: rotation {desc.get('rotation')} != {rho}")
    if desc.get("subsample") is not is_sub:
        errors.append(f"{did}: subsample flag {desc.get('subsample')} != {is_sub}")


def load_ledger(path):
    if path is None:
        return []
    doc = json.loads(Path(path).read_bytes())
    events = doc.get("events")
    if not isinstance(events, list):
        raise Refusal("ledger has no events list")
    return events


def check_ledger(events, pops, errors):
    """§3.4: replacement index, cell, bank and cap rules.

    The k of a loss is its 0-based position among the ledger's losses in the same (population, cell), taken in
    blind loss order (the ledger's event order). Returns the lost ids, the replacement ids, the descriptors
    known from the ledger, and the replacement count per population.
    """
    descs = {}
    lost_ids, rep_ids = set(), set()
    for event in events:
        lost = event.get("lost")
        if not isinstance(lost, dict) or "id" not in lost:
            errors.append("ledger event without a lost descriptor")
            continue
        if lost["id"] in lost_ids:
            errors.append(f"ledger lists {lost['id']} as lost twice")
        lost_ids.add(lost["id"])
        descs.setdefault(lost["id"], lost)

    per_cell = defaultdict(int)
    per_pop = defaultdict(int)
    for event in events:
        lost = event["lost"]
        pop, cell = lost.get("population"), lost.get("cell")
        if pop not in pops:
            errors.append(f"ledger lost {lost['id']}: unknown population {pop!r}")
            continue
        spec = pops[pop]
        k = per_cell[(pop, cell)]
        per_cell[(pop, cell)] += 1
        rep = event.get("replacement")
        if rep is None:
            errors.append(f"lost block {lost['id']} has no replacement (unreplaced loss)")
            continue
        if rep.get("id") in rep_ids:
            errors.append(f"replacement {rep.get('id')} listed twice")
        rep_ids.add(rep.get("id"))
        if rep.get("id") in descs and descs[rep["id"]] != rep:
            errors.append(f"conflicting descriptors for {rep['id']}")
        descs.setdefault(rep.get("id"), rep)
        if k > spec["max_k"]:
            errors.append(f"replacement k={k} for {pop} cell {cell} exceeds the bank cap {spec['max_k']}")
        if rep.get("index") != spec["n"] + spec["cells"] * k + cell:
            errors.append(f"replacement {rep.get('id')}: index {rep.get('index')} != n + cells*k + cell (k={k})")
        if rep.get("population") != pop or rep.get("cell") != cell:
            errors.append(f"replacement {rep.get('id')}: population or cell differs from the lost block")
        # §3: replaces is always the logical original, never the immediately lost replacement.
        lost_logical = resolve_logical(lost["id"], descs, errors)
        if lost_logical is not None:
            original = f"{pop}-{lost_logical:04d}"
            if rep.get("replaces") != original:
                errors.append(f"replacement {rep.get('id')}: replaces {rep.get('replaces')} "
                              f"is not the logical original {original}")
        per_pop[pop] += 1
        if per_pop[pop] > spec["n"] // REPLACEMENT_CAP_DIVISOR:
            errors.append(f"{pop} replacements exceed the 10% cap")
    return lost_ids, rep_ids, descs, dict(per_pop)


def judge(label, contract, op, threshold, n, flags):
    """One part of an intersection-union. The exact decision governs; the float decision is compared."""
    exact = contract["_upper"]
    flt = contract["upper_float"]
    thr = Fraction(threshold)
    exact_pass = exact <= thr if op == "<=" else exact < thr
    float_pass = flt <= float(thr) if op == "<=" else flt < float(thr)
    step = Fraction(100, n)
    if exact == thr:
        flags.append(dict(code="exact_boundary", where=label, detail=f"upper bound {exact} == {thr}"))
    if abs(exact - thr) <= step:
        flags.append(dict(code="within_one_step", where=label,
                          detail=f"|upper - {thr}| = {float(abs(exact - thr)):.6f} pp, one step {float(step):.6f} pp"))
    if exact_pass != float_pass:
        flags.append(dict(code="float_exact_decision", where=label,
                          detail=f"exact pass={exact_pass}, float pass={float_pass}"))
    if abs(flt - float(exact)) > 1e-9:
        flags.append(dict(code="float_exact_value", where=label, detail=f"gap {abs(flt - float(exact)):.3e}"))
    return dict(part=label, op=op, threshold=threshold, upper_exact=str(exact), upper_float=flt,
                holds=exact_pass)


def exact_percentile(sorted_vals, q, n):
    """Rational linear percentile of sorted integer count differences, in pp (times 100/n)."""
    reps = len(sorted_vals)
    pos = (reps - 1) * q
    lo = pos.numerator // pos.denominator
    frac = pos - lo
    value = Fraction(sorted_vals[lo])
    if frac:
        value += frac * (sorted_vals[lo + 1] - sorted_vals[lo])
    return value * Fraction(100, n)


def bootstrap(rng, matrix, rows, cells, reps=REPS):
    """§6.3: one index draw per cell, cells ascending, shared by all arms. Returns (reps, arms) counts."""
    rows = np.asarray(rows, dtype=np.int64)
    counts = np.zeros((reps, matrix.shape[1]), dtype=np.int64)
    for cell in range(cells):
        idx = rows[rows % cells == cell]
        if idx.size == 0:
            continue
        draw = rng.integers(0, idx.size, size=(reps, idx.size))
        counts += matrix[idx[draw]].sum(axis=1)
    return counts


def contrast_record(label, analysis, n, arm_x, arm_y, boot, losses, flags):
    diff = boot[:, ALL_ARMS.index(arm_x)] - boot[:, ALL_ARMS.index(arm_y)]
    sorted_vals = np.sort(diff).tolist()
    lo = exact_percentile(sorted_vals, Q_LO, n)
    hi = exact_percentile(sorted_vals, Q_HI, n)
    point = Fraction(100 * (losses[arm_x] - losses[arm_y]), n)
    float_ci = np.percentile(100.0 * diff / n, [2.5, 97.5])
    gap = max(abs(float(lo) - float_ci[0]), abs(float(hi) - float_ci[1]))
    if gap > 1e-9:
        flags.append(dict(code="float_exact_value", where=label, detail=f"CI gap {gap:.3e}"))
    return dict(analysis=analysis, n=n, x=arm_x, y=arm_y, point_pp=float(point), point_exact=str(point),
                lower_exact=str(lo), upper_exact=str(hi),
                lower_float=float(float_ci[0]), upper_float=float(float_ci[1]),
                _lower=lo, _upper=hi)


def public(record):
    return {k: v for k, v in record.items() if not k.startswith("_")}


def parse_test_counts(text):
    parts = [int(p) for p in text.split(",")]
    if len(parts) != 4 or any(p <= 0 for p in parts):
        raise Refusal("--test-counts takes primary_n,primary_sub,guard_n,guard_sub")
    return parts


def build_pops(test_counts):
    pops = {name: dict(spec) for name, spec in POPS.items()}
    if test_counts:
        pn, ps, gn, gs = test_counts
        pops["primary"].update(n=pn, sub=ps)
        pops["guard"].update(n=gn, sub=gs)
    return pops


def check_game(rec, did, pop, desc, arm, errors):
    """§5: per-game fields that must agree with the descriptor and the arm's frozen settings.
    Returns (metadata, winner), or None if the record has no metadata."""
    spec = ARM_SPEC[arm]
    meta = rec.get("metadata")
    tag = f"{did} {arm}"
    if not isinstance(meta, dict):
        errors.append(f"{tag}: no metadata")
        return None

    def need(cond, msg):
        if not cond:
            errors.append(f"{tag}: {msg}")

    need(rec.get("cohort") == arm, "cohort != arm")
    need(meta.get("arm") == arm, "metadata.arm != arm")
    need(meta.get("terminal") is True, "non-terminal game")
    winner = meta.get("winner")
    need(winner is None or (is_int(winner) and winner in (0, 1)), f"bad winner {winner!r}")
    need(is_int(meta.get("seat")) and meta.get("seat") == desc["seat"], "seat != descriptor")
    need(meta.get("seed") == desc["seed"], "seed != descriptor")
    need(meta.get("seed_index") == desc["index"], "seed_index != descriptor index")
    need(meta.get("cell") == desc["cell"], "cell != descriptor cell")
    need(meta.get("population") == pop, "population != descriptor population")
    need(meta.get("block_id") == did, "block_id != descriptor id")
    need(approx(meta.get("speed_cell"), float(spec["c"])), "speed_cell != arm cell")
    need(meta.get("budget_ms") == spec["budget"], "budget_ms != arm budget")
    need(approx(meta.get("deadline_seconds"), spec["budget"] / 1000), "deadline_seconds != budget")
    need(meta.get("reserve_ms") == RESERVE_MS, "reserve_ms != 8")
    need(approx(meta.get("inference_scale"), 1 / float(spec["c"])), "inference_scale != 1/c")
    need(meta.get("scale_mode") == "poll", "scale_mode != poll")
    need(meta.get("default_source") == spec["default"], "default_source != arm default")
    need(meta.get("s_default_rule") == spec["rule"], "s_default_rule != arm rule")
    need(meta.get("kernel") == spec["kernel"], "kernel != arm kernel")
    need(meta.get("threads") == 4, "threads != 4")
    need(meta.get("coarse_horizon") == 160, "coarse_horizon != 160")
    need(str(meta.get("study", "")).startswith("PREREG-K4S"), "study is not PREREG-K4S")
    need(isinstance(meta.get("freeze_manifest_sha256"), str) and meta["freeze_manifest_sha256"],
         "freeze_manifest_sha256 missing (a qualification or smoke record in a counted block)")
    if spec["default"] == "SD1":
        for key in SD1_KEYS:
            need(meta.get(key) is not None, f"{key} missing on an SD1 arm")
    return meta, winner


def reduce_tree(root, pops, events, c_star, errors, flags):
    """Counting, per-game checks and integer outcomes."""
    lost_ids, rep_ids, descs, rep_counts = check_ledger(events, pops, errors)

    blocks = {}
    for entry in sorted(root.iterdir()):
        if entry.is_dir() and (entry / "complete.json").is_file():
            blocks[entry.name] = json.loads((entry / "complete.json").read_bytes())
            desc = blocks[entry.name].get("descriptor", {})
            if entry.name not in lost_ids:
                if desc.get("id") != entry.name:
                    errors.append(f"{entry.name}: descriptor id does not match the directory")
                if entry.name in descs and descs[entry.name] != desc:
                    errors.append(f"{entry.name}: tree descriptor conflicts with the ledger")
                descs.setdefault(entry.name, desc)

    # Every ledger descriptor must also be layout-valid at its logical index.
    for did, desc in sorted(descs.items()):
        logical = resolve_logical(did, descs, errors)
        if logical is not None:
            check_descriptor(did, desc, logical, errors, pops)

    counted = {name: {} for name in pops}
    for did, doc in sorted(blocks.items()):
        if did in lost_ids:
            continue
        desc = doc.get("descriptor", {})
        pop = desc.get("population")
        if pop not in pops:
            errors.append(f"{did}: unknown population")
            continue
        if desc.get("replaces") is not None and did not in rep_ids:
            errors.append(f"{did}: replacement block not in the ledger")
        if desc.get("replaces") is None and not (isinstance(desc.get("index"), int)
                                                 and desc["index"] < pops[pop]["n"]):
            errors.append(f"{did}: outside the reporting range with no replacement link")
        logical = resolve_logical(did, descs, errors)
        if logical is None:
            continue
        if logical in counted[pop]:
            errors.append(f"{pop} logical index {logical} counted twice ({counted[pop][logical]} and {did})")
            continue
        counted[pop][logical] = did

    for pop, spec in pops.items():
        missing = [i for i in range(spec["n"]) if i not in counted[pop]]
        if missing:
            errors.append(f"{pop}: {len(missing)} logical blocks missing, e.g. {missing[:5]}")
        extra = sorted(set(counted[pop]) - set(range(spec["n"])))
        if extra:
            errors.append(f"{pop}: logical indices outside 0..{spec['n'] - 1}: {extra[:5]}")
        sub_count = sum(1 for i in counted[pop] if i < spec["sub"])
        if not missing and sub_count != spec["sub"]:
            errors.append(f"{pop}: {sub_count} subsample blocks, expected {spec['sub']}")

    tables = {}
    pins = defaultdict(set)
    sd1_pins = defaultdict(set)
    c_values = set()
    games_total = 0
    for pop, spec in pops.items():
        n = spec["n"]
        loss = np.zeros((n, len(ALL_ARMS)), dtype=np.int64)
        draw = np.zeros((n, len(ALL_ARMS)), dtype=np.int64)
        present = np.zeros((n, len(ALL_ARMS)), dtype=bool)
        tables[pop] = dict(loss=loss, draw=draw, present=present)
        for logical in sorted(counted[pop]):
            did = counted[pop][logical]
            doc = blocks[did]
            desc = doc["descriptor"]
            order = desc["order"]
            games = doc.get("games", {})
            expect_names = {f"{did}-d27-{arm}.json" for arm in order}
            if set(games) != expect_names or len(games) != len(order):
                errors.append(f"{did}: games {sorted(games)} do not match descriptor order {order}")
                continue
            if doc.get("host") not in (None, HUB_HOST) and "hub_ack" not in doc:
                flags.append(dict(code="hub_ack_unverified", where=did,
                                  detail="non-01 host block with no hub_ack key (not gated; §4.4)"))
            for arm in order:
                fname = f"{did}-d27-{arm}.json"
                path = root / did / "games" / fname
                if not path.is_file():
                    errors.append(f"{did}: missing game file {fname}")
                    continue
                raw = path.read_bytes()
                if sha256_bytes(raw) != games[fname]:
                    errors.append(f"{did}: game {fname} sha256 mismatch")
                    continue
                try:
                    rec = json.loads(raw)
                except ValueError:
                    errors.append(f"{did}: game {fname} is not JSON")
                    continue
                checked = check_game(rec, did, pop, desc, arm, errors)
                if checked is None:
                    continue
                meta, winner = checked
                for key in PIN_KEYS:
                    pins[key].add(json.dumps(meta.get(key)))
                c_values.add(json.dumps(meta.get("c_star")))
                if ARM_SPEC[arm]["default"] == "SD1":
                    for key in SD1_KEYS:
                        sd1_pins[key].add(json.dumps(meta.get(key)))
                col = ALL_ARMS.index(arm)
                present[logical, col] = True
                if winner is None:
                    draw[logical, col] = 1
                else:
                    loss[logical, col] = int(winner != desc["seat"])
                games_total += 1

    for key, values in {**pins, **sd1_pins}.items():
        if len(values) > 1:
            errors.append(f"games disagree on {key}: {sorted(values)}")
    c_seen = {json.loads(v) for v in c_values}
    if c_seen and c_seen != {float(c_star)}:
        flags.append(dict(code="c_star_mismatch", where="games",
                          detail=f"games record c_star {sorted(c_seen, key=str)}; verifier run with {c_star}"))
    return dict(tables=tables, counted=counted, games=games_total, replacements=rep_counts,
                lost=len(lost_ids), blocks=len(blocks))


def analyse(tables, pops, rng):
    """§6.3 bootstrap in the fixed analysis order, plus point losses and draws for arms present on every row."""
    boots, losses, draws, n_of = {}, {}, {}, {}
    for name, pop, is_sub in ANALYSES:
        spec = pops[pop]
        table = tables[pop]
        rows = [i for i in range(spec["n"]) if not is_sub or i < spec["sub"]]
        n_of[name] = len(rows)
        boots[name] = bootstrap(rng, table["loss"], rows, spec["cells"])
        losses[name], draws[name] = {}, {}
        for arm in ALL_ARMS:
            col = ALL_ARMS.index(arm)
            if table["present"][rows, col].all():
                losses[name][arm] = int(table["loss"][rows, col].sum())
                draws[name][arm] = int(table["draw"][rows, col].sum())
    return boots, losses, draws, n_of


def hyp_parts(level, cell):
    """§1.2 parts as (kind, upper threshold in pp, operator)."""
    if level == "B":
        return [("dref", 10, "<="), ("dsame", 0, "<"), ("drefg", 15, "<=")]
    if cell == "0.9":
        return [("dref", 5, "<="), ("drefg", 10, "<=")]
    return [("dref", 5, "<="), ("dsame", 0, "<"), ("drefg", 10, "<=")]


def run_sequence(c_star, contracts, n_of, flags):
    """§1.2 fixed sequence. Testing stops at the first failure; later steps are recorded as not reached.
    Returns {hid: step} in tested order."""
    order = [h for h in HYP_ORDER if not (c_star == "0.8" and h[0] == "H4")]
    steps, stopped = {}, False
    for hid, level, cell in order:
        parts = []
        for kind, thr, op in hyp_parts(level, cell):
            analysis, _, _ = CONTRASTS[(kind, cell)]
            label = f"{hid}.{kind}({cell})"
            parts.append(judge(label, contracts[(kind, cell)], op, thr, n_of[analysis], flags))
        reached = not stopped
        passed = all(p["holds"] for p in parts)
        steps[hid] = dict(hypothesis=f"{level}({cell})", reached=reached,
                          passed=passed if reached else None, parts=parts)
        if reached and not passed:
            stopped = True
    return steps


def usable_cells(admission_by_cell, veto_pass):
    """§1.5: 0.9 needs A(0.9) and the veto; 0.8, 0.7, 0.6 need A or B."""
    usable = {"0.9": admission_by_cell["0.9"] == "A" and veto_pass}
    for cell in ("0.8", "0.7", "0.6"):
        usable[cell] = admission_by_cell[cell] in ("A", "B")
    return usable


def admission(steps, cell):
    """§6.5: 0.9 is A only; 0.8, 0.7, 0.6 are A if the A step passed, else B if the B step passed."""
    def passed(hid):
        return steps.get(hid, {}).get("passed") is True
    if cell == "0.9":
        return "A" if passed("H4") else None
    a_step = {"0.8": "H5", "0.7": "H6", "0.6": "H7"}[cell]
    b_step = {"0.8": "H1", "0.7": "H2", "0.6": "H3"}[cell]
    if passed(a_step):
        return "A"
    if passed(b_step):
        return "B"
    return None


def validity(k4_losses, n, flags):
    """§6.5: passes iff 10n <= 100 * losses(K4-200, primary full) <= 30n (point rate, inclusive)."""
    rate = Fraction(100 * k4_losses, n)
    ok = Fraction(VALIDITY_LO) <= rate <= Fraction(VALIDITY_HI)
    step = Fraction(100, n)
    for bound in (VALIDITY_LO, VALIDITY_HI):
        if rate == bound:
            flags.append(dict(code="exact_boundary", where="validity", detail=f"K4-200 loss rate == {bound}%"))
        if abs(rate - bound) <= step:
            flags.append(dict(code="within_one_step", where="validity",
                              detail=f"|rate - {bound}| within one step {float(step):.6f} pp"))
    return dict(rate_pct_exact=str(rate), rate_pct=float(rate), window=[VALIDITY_LO, VALIDITY_HI],
                status="OK" if ok else "SUSPENDED")


ANALYSIS_ARMS = {name: (ALL_ARMS if is_sub else CORE) for name, _, is_sub in ANALYSES}


def frac_pair(value):
    return [value.numerator, value.denominator]


def build_view(losses, draws, n_of, contracts, hypotheses, admission, usable, veto_pass, validity_ok):
    """§6.7 verifier_view: the fixed block that --compare checks key by key. Bounds are [num, den] pairs."""
    counts = {name: {arm: dict(losses=losses[name][arm], draws=draws[name][arm], n=n_of[name])
                     for arm in ANALYSIS_ARMS[name]}
              for name in ANALYSIS_ARMS}
    contrasts = {f"{analysis}:{kind}@{cell}":
                 dict(lower=frac_pair(contracts[(kind, cell)]["_lower"]),
                      upper=frac_pair(contracts[(kind, cell)]["_upper"]))
                 for (kind, cell), (analysis, _, _) in CONTRASTS.items()}
    sequence = [dict(step=hid, hypothesis=step["hypothesis"], tested=step["reached"], passed=step["passed"])
                for hid, step in hypotheses.items()]
    return dict(schema=VIEW_SCHEMA, counts=counts, contrasts=contrasts, sequence=sequence,
                admitted={cell: admission[cell] for cell in VIEW_CELLS},
                veto_pass=bool(veto_pass), usable_cells=[cell for cell in VIEW_CELLS if usable[cell]],
                validity_inside=bool(validity_ok))


def same_scalar(expected, got):
    """Strict equality: a bool is never an int, an int is never a float, and None matches only None."""
    if expected is None or isinstance(expected, bool):
        return got is expected
    if isinstance(expected, int):
        return type(got) is int and got == expected
    if isinstance(expected, str):
        return type(got) is str and got == expected
    return False


def same_rational(expected, got):
    """A [num, den] pair from the reducer: integers with a nonzero denominator, equal as Fractions."""
    if not (isinstance(got, list) and len(got) == 2 and all(type(x) is int for x in got) and got[1] != 0):
        return False
    return Fraction(*got) == Fraction(*expected)


def _check(t, path, ok, expected, got):
    t["items"] += 1
    if ok:
        t["matched"] += 1
    else:
        t["mismatches"].append(dict(path=path, expected=expected, reducer=got))


def _keys(t, path, expected, got):
    """The key sets must be equal: each missing or extra key is one mismatch. Returns the keys both sides hold."""
    if not isinstance(got, dict):
        _check(t, path, False, "object", type(got).__name__)
        return []
    for key in sorted(set(expected) - set(got)):
        _check(t, f"{path}.{key}", False, "present", "missing")
    for key in sorted(set(got) - set(expected)):
        _check(t, f"{path}.{key}", False, "absent", "extra")
    return sorted(set(expected) & set(got))


def _scalars(t, path, expected, got):
    for key in _keys(t, path, expected, got):
        _check(t, f"{path}.{key}", same_scalar(expected[key], got[key]), expected[key], got[key])


def _sequence(t, path, expected, got):
    """Test order matters: element i of the reducer's sequence is compared with element i of the verifier's."""
    if not isinstance(got, list):
        _check(t, path, False, "list", type(got).__name__)
        return
    _check(t, f"{path}.length", len(got) == len(expected), len(expected), len(got))
    for i, (exp_step, got_step) in enumerate(zip(expected, got)):
        _scalars(t, f"{path}[{i}]", exp_step, got_step)


def compare_verifier_view(mine, reducer):
    """§6.7: the verifier's verifier_view against the reducer's, key by key and exactly. Returns the counts of
    compared items, matched and mismatched, with each mismatch's path and both values. usable_cells is compared as
    a multiset, since §6.7 does not fix its order."""
    t = dict(items=0, matched=0, mismatches=[])
    if not isinstance(mine, dict):
        _check(t, "verifier_view", False, "produced by the verifier", "not produced")
    else:
        got = reducer.get("verifier_view") if isinstance(reducer, dict) else None
        if not isinstance(got, dict):
            _check(t, "verifier_view", False, "object", "missing")
        else:
            for key in _keys(t, "verifier_view", mine, got):
                path, exp_val, got_val = f"verifier_view.{key}", mine[key], got[key]
                if key == "counts":
                    for analysis in _keys(t, path, exp_val, got_val):
                        for arm in _keys(t, f"{path}.{analysis}", exp_val[analysis], got_val[analysis]):
                            _scalars(t, f"{path}.{analysis}.{arm}", exp_val[analysis][arm], got_val[analysis][arm])
                elif key == "contrasts":
                    for name in _keys(t, path, exp_val, got_val):
                        for bound in _keys(t, f"{path}.{name}", exp_val[name], got_val[name]):
                            _check(t, f"{path}.{name}.{bound}", same_rational(exp_val[name][bound],
                                                                              got_val[name][bound]),
                                   exp_val[name][bound], got_val[name][bound])
                elif key == "sequence":
                    _sequence(t, path, exp_val, got_val)
                elif key == "admitted":
                    _scalars(t, path, exp_val, got_val)
                elif key == "usable_cells":
                    ok = isinstance(got_val, list) and all(type(x) is str for x in got_val) \
                        and sorted(got_val) == sorted(exp_val)
                    _check(t, path, ok, exp_val, got_val)
                else:
                    _check(t, path, same_scalar(exp_val, got_val), exp_val, got_val)
    return dict(items=t["items"], matched=t["matched"], mismatched=len(t["mismatches"]),
                mismatches=t["mismatches"])


def run(args):
    root = args.root.resolve()
    marked = (root / "SYNTHETIC").is_file()
    release_info = None
    if args.synthetic:
        if not marked:
            raise Refusal("--synthetic needs a SYNTHETIC file at the tree root")
        if args.release:
            raise Refusal("--synthetic and --release are mutually exclusive")
    else:
        if marked:
            raise Refusal("tree is marked SYNTHETIC; it runs only with --synthetic")
        if args.test_counts:
            raise Refusal("--test-counts is for SYNTHETIC trees only")
        if args.release is None:
            raise Refusal("no release receipt: refusing to open any game file")
        repo = args.repo or default_repo()
        try:
            receipt = json.loads(args.release.read_bytes())
        except (OSError, ValueError) as exc:
            raise Refusal(f"cannot read release receipt: {exc}")
        release_info = check_seal(Path(repo), receipt)
        release_info["receipt_sha256"] = sha256_file(args.release)
    if args.test_counts and not args.synthetic:
        raise Refusal("--test-counts needs --synthetic")

    pops = build_pops(parse_test_counts(args.test_counts) if args.test_counts else None)
    events = load_ledger(args.ledger)
    errors, flags = [], []
    counting = reduce_tree(root, pops, events, args.c_star, errors, flags)
    out = dict(
        study="PREREG-K4S", synthetic=bool(args.synthetic), release=release_info,
        verifier_sha256=sha256_file(Path(__file__)),
        ledger_sha256=sha256_file(args.ledger) if args.ledger else None,
        bootstrap=dict(reps=REPS, seed=BOOT_SEED, q_lo="1/40", q_hi="39/40"),
        c_star=args.c_star,
        counts=dict(games=counting["games"], blocks_in_tree=counting["blocks"], lost=counting["lost"],
                    replacements=counting["replacements"],
                    logical={pop: dict(counted=len(counting["counted"][pop]), required=spec["n"],
                                       subsample=spec["sub"]) for pop, spec in pops.items()}),
    )
    if errors:
        out.update(status="ERRORS", errors=errors)
        return out, 2

    rng = np.random.default_rng(BOOT_SEED)
    boots, losses, draws, n_of = analyse(counting["tables"], pops, rng)
    out["analysis"] = {
        name: dict(population=pop, subsample=is_sub, n=n_of[name],
                   arms={arm: dict(losses=losses[name][arm], draws=draws[name][arm],
                                   wins=n_of[name] - losses[name][arm] - draws[name][arm])
                         for arm in losses[name]})
        for name, pop, is_sub in ANALYSES
    }

    contracts = {}
    for (kind, cell), (analysis, arm_x, arm_y) in CONTRASTS.items():
        contracts[(kind, cell)] = contrast_record(
            f"{kind}({cell})", analysis, n_of[analysis], arm_x, arm_y, boots[analysis], losses[analysis], flags)
    out["contrasts"] = {f"{analysis}:{kind}@{cell}": public(contracts[(kind, cell)])
                        for (kind, cell), (analysis, _, _) in CONTRASTS.items()}

    out["hypotheses"] = run_sequence(args.c_star, contracts, n_of, flags)
    out["sequence"] = list(out["hypotheses"])
    out["admission"] = {cell: admission(out["hypotheses"], cell) for cell in ("0.8", "0.7", "0.6", "0.9")}

    veto = judge("veto(0.9)", contracts[("veto", "0.9")], "<=", VETO_MAX, n_of["P_full"], flags)
    out["veto"] = dict(part=veto, holds=veto["holds"],
                       role="gate" if args.c_star == "0.9" else "descriptive (c*=0.8 drops H4)")
    out["usable_cells"] = usable_cells(out["admission"], veto["holds"])

    out["validity"] = validity(losses["P_full"]["K4-200"], n_of["P_full"], flags)
    if out["validity"]["status"] == "SUSPENDED":
        flags.append(dict(code="validity_suspended", where="K4-200 primary",
                          detail="selection suspended pending the receipts-only review (§5.4)"))
    out["verifier_view"] = build_view(losses, draws, n_of, contracts, out["hypotheses"], out["admission"],
                                      out["usable_cells"], veto["holds"], out["validity"]["status"] == "OK")
    out["flags"] = flags
    out["status"] = out["validity"]["status"]
    return out, (1 if flags else 0)


def build_parser():
    ap = argparse.ArgumentParser(description="Independent PREREG-K4S integer-count verifier.")
    ap.add_argument("--root", required=True, type=Path, help="block tree: <id>/complete.json and <id>/games/")
    ap.add_argument("--ledger", type=Path, help="replacement ledger (optional)")
    ap.add_argument("--release", type=Path, help="release receipt (required unless --synthetic)")
    ap.add_argument("--synthetic", action="store_true", help="only with a SYNTHETIC marker at the root")
    ap.add_argument("--c-star", default="0.9", choices=["0.9", "0.8"], help="0.8 drops H4")
    ap.add_argument("--repo", type=Path, help="repository holding the release commit (default: this repo)")
    ap.add_argument("--compare", type=Path, help="reducer output JSON to compare by meaning")
    ap.add_argument("--out", type=Path, help="write the result JSON here (default: stdout)")
    ap.add_argument("--test-counts", help=argparse.SUPPRESS)  # primary_n,primary_sub,guard_n,guard_sub
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        out, code = run(args)
    except Refusal as exc:
        out, code = dict(status="REFUSED", reason=str(exc)), 2
    if args.compare is not None:
        try:
            reducer = json.loads(args.compare.read_bytes())
        except (OSError, ValueError) as exc:
            out["compare"] = dict(error=f"cannot read reducer output: {exc}")
            code = 2
        else:
            out["compare"] = compare_verifier_view(out.get("verifier_view"), reducer)
            if out["compare"]["mismatched"]:
                code = 2
    text = json.dumps(out, indent=2, default=str)
    if args.out:
        args.out.write_text(text + "\n")
    else:
        sys.stdout.write(text + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())

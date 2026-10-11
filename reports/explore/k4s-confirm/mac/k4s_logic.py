"""Pure, torch-free PREREG-K4S Mac logic (r3 §1.4, §1.5 eligibility, §5.4 Mac side).

Everything here is importable and testable offline: pins, preconditions, the TIERS
receipt readers (read-only), statistics, gates 0-6, the cell mapping, cross-session
reduction, the load-selection rule and the exclusive receipt store. Nothing here
imports torch, the native module or any perception code. TIERS's frozen e4v3 helpers
are imported read-only and lazily (``tiers_receipts()``), after their pins are checked
by ``measure_k4s.main``.
"""
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

MAC_DIR = Path(__file__).resolve().parent
REPO_ROOT = MAC_DIR.parents[3]
MAC_REL = "reports/explore/k4s-confirm/mac"
TIERS_PACKAGE_REL = "reports/strategy_council_20260928/live-loop/v4/mac-e4-package"
E4V3_REL = TIERS_PACKAGE_REL + "/e4v3"
MANIFEST_NAME = "K4S-MAC-MANIFEST.json"

# Frozen identities (r3 §2.1-§2.2; TIERS tier_backend constants, cross-checked at runtime).
NATIVE_PROVENANCE_SHA = "44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2"
SD1_CHECKPOINT_SHA = "37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85"
SD1_CALIBRATION_SHA = "e300353346983e888d896b20412d4075496a6f14ef3625cefc7eeadacec5e414"
SD1_THRESHOLD = 0.5005528330802917
SD1_SCHEMA = "clasher.k4s.sd1-manifest.v1"
SD1_ARTIFACT_ID = "clasher-sd1-k4s-default-20261011"
SD1_CHECKPOINT_JOB_PATH = "inputs/R3a.pt"
SD1_CALIBRATION_JOB_PATH = "inputs/R3a-calibration.json"
# Repo-relative SD1 inference path (k4s-confirm/sd1_manifest.py SOURCES; cross-checked by a test).
SD1_SOURCES = (
    "reports/explore/k4s-confirm/cached_policy.py",
    "reports/explore/k4s-confirm/sd1_policy.py",
    "reports/explore/k4s-confirm/proposals.py",
    "reports/explore/e1/policy.py",
    "imitation/evaluation/d1.py",
    "imitation/evaluation/standalone.py",
    "imitation/model/inference.py",
    "student-source/exit_r3/network.py",
)
SD1_INFERENCE_MODE = dict(device="cpu", dtype="float32", torch_threads=1, cuda_visible_devices="",
                          grad="torch.inference_mode", temperatures=[1.0, 1.0, 1.0], forwards_per_poll=1)
TIERS_SCORER_REL = "reports/explore/s1/anchor.py"
TIERS_SCORER_BASE_REL = "reports/explore/e1/planner.py"
T1_INVENTORY_COMMIT = "81f2483e"
T1_K4_CORPUS_SHA = "a97b1fbf6cbc33a7b65aa5fc91eb0acdd07c922aaf0737620a849163aaadbfe8"

# Cells (r3 §1.1). Keys are canonical strings so no float ever names a cell.
FULL_CELL = "1.0"
K4S_CELLS = ("0.9", "0.8", "0.7", "0.6")
BUDGET_MS = {"1.0": 200, "0.9": 180, "0.8": 160, "0.7": 140, "0.6": 120}
# Canonical deadline-cell naming, shared by the END producer (end_pool.py), the procedure (§3)
# and the Mac reader/gate inputs: rates are the bare key, integer counts are key + "_count".
DEADLINE_RATE_KEYS = ("cutoff", "no_complete_play", "fallback")
FLEET_REFERENCE_SCHEMA = "clasher.k4s.mac-fleet-reference.v1"
END_RECHECK_SCHEMA = "clasher.k4s.end-recheck.v1"
END_POOL_REL = "reports/explore/k4s-confirm/end_pool.py"
POLL_P99_LIMIT = Fraction(20, 1000)          # gate 3, seconds, inclusive
DEADLINE_MARGIN = Fraction(2, 100)           # gate 6, absolute, inclusive
FPS_MIN, PROCESSED_MIN = Fraction(18), Fraction(95, 100)   # gate 4
SD1_AGREEMENT_MIN = Fraction(995, 1000)      # gate 0 (TIERS §7.3)
MAX_TECHNICAL_REPEATS = 1                    # TIERS addendum §F: one repeat session
IN_SESSION_MAX_GAP_SECONDS = 2 * 3600        # K4S must start within 2 h of TIERS completion

MAC_LIMITS = dict(agreement=2000, unloaded=100, speed=300, warmup_seconds=300,
                  speed_seconds=300, decisions=1000, census_seconds=300, golden=125)
DRY_LIMITS = dict(agreement=32, unloaded=16, speed=32, warmup_seconds=2,
                  speed_seconds=2, decisions=32, census_seconds=0, golden=125)

TIERS_GATE_FAILURE_WORDS = ("Exactness mismatch", "Zero-budget", "Zero native budget")
TIERS_REQUIRED_COMPLETE = ("tiers-complete.json", "tiers-summary.json", "tiers-identity.json",
                           "exactness-tiers.json", "belief-exactness.json", "student-agreement.json",
                           "build-tiers.json")


class PreconditionRefusal(ValueError):
    """Raised before any measurement; a refusal is not a session and consumes no repeat."""
    cause = "precondition-refusal"


class GateInputError(ValueError):
    cause = "gate-input"


# ---------------------------------------------------------------- hashing and pins

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def is_sha256(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def verify_pinned(root, files, label):
    """Every pinned file exists inside root and has its exact SHA-256."""
    root = Path(root).resolve()
    if not files:
        raise PreconditionRefusal("Empty pin set: " + label)
    for name, expected in sorted(files.items()):
        path = (root / name).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            raise PreconditionRefusal("Pin escapes root: " + name) from None
        if not is_sha256(expected):
            raise PreconditionRefusal("Unfilled pin (" + label + "): " + name)
        if not path.is_file() or sha(path) != expected:
            raise PreconditionRefusal("Pin mismatch (" + label + "): " + name)


def load_k4s_manifest(path, expected_sha256, runtime_root, *, require_frozen):
    """Verify the K4S manifest, every K4S file and every reused read-only TIERS file."""
    path = Path(path)
    if expected_sha256 is None or sha(path) != expected_sha256:
        raise PreconditionRefusal("K4S manifest SHA mismatch")
    manifest = json.loads(path.read_text())
    if manifest.get("schema") != "clasher.k4s.mac-manifest.v1":
        raise PreconditionRefusal("Unsupported K4S manifest schema")
    verify_pinned(runtime_root, manifest["k4s_files"], "K4S Mac files")
    verify_pinned(runtime_root, manifest["end_files"], "K4S END producer/pooler files")
    verify_pinned(runtime_root, manifest["reused_readonly"], "reused read-only TIERS files")
    tiers_script = manifest["measure_tiers_unmodified"]
    if manifest["reused_readonly"].get(tiers_script["path"]) != tiers_script["sha256"]:
        raise PreconditionRefusal("measure_tiers.py statement disagrees with its read-only pin")
    if manifest["native"]["provenance_linux_sha256"] != NATIVE_PROVENANCE_SHA:
        raise PreconditionRefusal("Native provenance SHA changed")
    if require_frozen:
        if manifest.get("frozen") is not True:
            raise PreconditionRefusal("Mac session requires the frozen K4S manifest")
        sd1 = manifest["sd1_manifest"]
        if not is_sha256(sd1.get("sha256")):
            raise PreconditionRefusal("SD1 manifest SHA is not filled in the K4S manifest")
        kernel = manifest["k4s_kernel"]
        if not kernel.get("files") or any(not is_sha256(v) for v in kernel["files"].values()):
            raise PreconditionRefusal("K4S kernel pins are not filled in the K4S manifest")
        verify_pinned(runtime_root, kernel["files"], "K4S kernel")
    return manifest


def tiers_receipts(runtime_root=None):
    """Read-only import of TIERS's frozen e4v3 receipts module (no edits, no writes)."""
    directory = str((Path(runtime_root) if runtime_root else REPO_ROOT) / E4V3_REL)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    import receipts
    if Path(receipts.__file__).resolve().parent != Path(directory).resolve():
        raise PreconditionRefusal("Wrong e4v3 receipts module imported")
    return receipts


# ---------------------------------------------------------------- exact comparisons

def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise GateInputError("Non-finite or non-numeric gate input: " + label)
    return Fraction(value)


def at_least(value, threshold, label="value"):
    """Inclusive, against the IEEE double nearest the exact decimal threshold.

    Thresholds are exact rationals (e.g. 0.8 - 0.10 = 7/10, 0.9^2 = 81/100) rounded once to
    the nearest double, so a measured 0.7 meets "p10 >= 0.7" as written (TIERS's float
    semantics); no threshold is ever formed by float arithmetic.
    """
    _finite(value, label)
    return float(value) >= float(Fraction(threshold))


def at_most(value, threshold, label="value"):
    _finite(value, label)
    return float(value) <= float(Fraction(threshold))


def cell_fraction(cell):
    if cell not in BUDGET_MS:
        raise GateInputError("Unknown cell: " + repr(cell))
    return Fraction(cell)


def charge_scale_text(cell):
    """Exact 1/c as a rational string: "1", "10/9", "5/4", "10/7", "5/3"."""
    return str(Fraction(1) / cell_fraction(cell))


def deadline_cell_record(cell, n, counts):
    """One fleet END deadline cell in the canonical naming (producer side).

    ``counts`` maps each DEADLINE_RATE_KEYS name to an integer count over ``n`` rows. The
    rate is count / n (correctly rounded, equal to float(Fraction(count, n))).
    """
    if type(n) is not int or n <= 0:
        raise GateInputError("Deadline cell needs a positive integer n")
    if set(counts) != set(DEADLINE_RATE_KEYS):
        raise GateInputError("Deadline cell counts must be exactly " + ",".join(DEADLINE_RATE_KEYS))
    record = dict(budget_ms=BUDGET_MS[cell], charge_scale=charge_scale_text(cell), n=n)
    for key in DEADLINE_RATE_KEYS:
        count = counts[key]
        if type(count) is not int or not 0 <= count <= n:
            raise GateInputError("Deadline count must be an integer in [0, n]: " + key)
        record[key + "_count"] = count
        record[key] = float(Fraction(count, n))
    return record


# ---------------------------------------------------------------- statistics (r3 §1.4)

def quantiles(values):
    """Identical linear-interpolation quantiles to TIERS receipts.quantiles."""
    values = sorted(values)
    if not values or any(not math.isfinite(v) or v < 0 for v in values):
        raise GateInputError("Need finite nonnegative observations")

    def q(p):
        index = (len(values) - 1) * p
        lo, hi = math.floor(index), math.ceil(index)
        return values[lo] + (values[hi] - values[lo]) * (index - lo)
    return dict(n=len(values), p10=q(.1), p25=q(.25), p50=q(.5), p90=q(.9),
                p95=q(.95), p99=q(.99), max=values[-1])


def k4s_speed_summary(rows, corpus_ids=None):
    """TIERS §6.2 statistic for the K4S work unit.

    Per-state Mac wall = median over that state's loaded repeats. r_K4S = min(median
    per-state ratio, sum ratio, p90 ratio); p10_K4S = 10th percentile of per-state ratios.
    """
    grouped = {}
    for row in rows:
        if row["wall_seconds"] <= 0 or row["fleet_wall_seconds"] <= 0:
            raise GateInputError("Nonpositive speed timing")
        grouped.setdefault(row["id"], []).append(row)
    if corpus_ids is not None and set(grouped) != set(corpus_ids):
        raise GateInputError("Loaded K4S speed rows do not cover exactly the corpus states")
    ratios, fleet, measured = [], [], []
    for identity in sorted(grouped):
        samples = grouped[identity]
        refs = {r["fleet_wall_seconds"] for r in samples}
        if len(refs) != 1:
            raise GateInputError("Fleet reference changed within a state")
        wall = quantiles([r["wall_seconds"] for r in samples])["p50"]
        reference = refs.pop()
        ratios.append(reference / wall)
        fleet.append(reference)
        measured.append(wall)
    result = quantiles(ratios)
    result["sum_ratio"] = sum(fleet) / sum(measured)
    result["p90_wall_ratio"] = quantiles(fleet)["p90"] / quantiles(measured)["p90"]
    result["median_ratio"] = result["p50"]
    result["r"] = min(result["p50"], result["sum_ratio"], result["p90_wall_ratio"])
    result["states"] = len(ratios)
    result["per_state_ratios"] = ratios
    return result


def poll_summary(mac_rows, fleet_states, corpus_ids=None):
    """r_inf = fleet END median poll span (c) / Mac median poll span; poll-span p99.

    Both medians are the median over corpus states of each state's median span (fleet:
    pooled over hosts x repeats by END; Mac: over this session's warm loaded repeats).
    p99 is over every warm loaded Mac poll observation. Cold polls never enter.
    """
    grouped = {}
    for row in mac_rows:
        if row.get("cold"):
            continue
        if not (row["poll_seconds"] > 0):
            raise GateInputError("Nonpositive poll span")
        grouped.setdefault(row["id"], []).append(row["poll_seconds"])
    if not grouped:
        raise GateInputError("No warm poll observations")
    if corpus_ids is not None and set(grouped) != set(corpus_ids):
        raise GateInputError("Poll spans do not cover exactly the corpus states")
    missing = set(grouped) - set(fleet_states)
    if missing:
        raise GateInputError("Fleet poll reference lacks states: " + ",".join(sorted(missing)[:3]))
    mac_state = [quantiles(v)["p50"] for _, v in sorted(grouped.items())]
    fleet_state = [fleet_states[i]["sd1_poll_seconds"] for i in sorted(grouped)]
    mac_median = quantiles(mac_state)["p50"]
    fleet_median = quantiles(fleet_state)["p50"]
    everything = [x for values in grouped.values() for x in values]
    return dict(mac_median_seconds=mac_median, fleet_median_seconds=fleet_median,
                r_inf=fleet_median / mac_median, p99_seconds=quantiles(everything)["p99"],
                distribution_seconds=quantiles(everything), states=len(grouped),
                observations=len(everything))


def perception_aggregate(spans, active_seconds):
    """TIERS D5 aggregation over the loaded K4S speed blocks (§6.3 gate 2 semantics)."""
    processed = sum(s["processed"] for s in spans)
    expected = sum(s["expected"] for s in spans)
    if active_seconds <= 0 or expected <= 0:
        raise GateInputError("Empty perception window")
    fps = processed / active_seconds
    fraction = min(1., processed / expected)
    return dict(processed=processed, expected=expected, fps=fps, processed_fraction=fraction,
                active_seconds=active_seconds, passes=perception_gate(fps, fraction))


def perception_gate(fps, processed_fraction):
    return at_least(fps, FPS_MIN, "fps") and at_least(processed_fraction, PROCESSED_MIN, "processed")


def rate_fraction(rates, key):
    """Exact rate from integer counts (count / n)."""
    count = rates[key + "_count"]
    n = rates.get(key + "_n") if rates.get(key + "_n") is not None else rates.get("n")
    if type(count) is not int or type(n) is not int or n <= 0 or not 0 <= count <= n:
        raise GateInputError("Rate needs integer count and n: " + key)
    return Fraction(count, n)


def k4s_deadline_rates(rows):
    """200 ms deadline-mode cohort with integer counts (cutoff, no-complete-play, fallback)."""
    if not rows:
        raise GateInputError("Empty deadline cohort")
    n = len(rows)
    out = dict(n=n)
    for key in ("cutoff", "no_complete_play", "fallback", "student_default", "preparation_default"):
        count = sum(bool(r.get(key, False)) for r in rows)
        out[key + "_count"], out[key] = count, count / n
    out["wall_ms"] = quantiles([r["wall_seconds"] * 1000 for r in rows])
    out["over_200_ms"] = sum(bool(r["over_200_ms"]) for r in rows)
    out["cut_return_over_208_ms"] = sum(bool(r["cut_return_over_208_ms"]) for r in rows)
    return out


def deadline_gate(mac_rates, fleet_deadline, cell):
    """Gate 6: Mac 200 ms rates each <= fleet END (b) K4S rate at b(c), 1/c charge, + 2 pp.

    Exact rational comparison of integer counts: count_mac/n_mac <= count_ref/n_ref + 2/100.
    """
    reference = fleet_deadline[cell]
    checks = {key: rate_fraction(mac_rates, key) <= rate_fraction(reference, key) + DEADLINE_MARGIN
              for key in ("cutoff", "no_complete_play")}
    keep = ("n", "cutoff", "cutoff_count", "cutoff_n", "no_complete_play", "no_complete_play_count",
            "no_complete_play_n")
    return dict(cell=cell, passes=all(checks.values()), checks=checks,
                reference={k: reference[k] for k in keep if k in reference},
                measured={k: mac_rates[k] for k in keep if k in mac_rates})


def sd1_agreement_gate(comparisons):
    """TIERS §7.3: >= 99.5% joint gate+top-8 equality and every disagreement tolerated."""
    if not comparisons:
        return dict(passes=False, fraction=0., n=0, unexplained=0)
    equal = sum(bool(r["equal"]) for r in comparisons)
    unexplained = sum((not r["equal"]) and (not r["allowed"]) for r in comparisons)
    passes = Fraction(equal, len(comparisons)) >= SD1_AGREEMENT_MIN and unexplained == 0
    return dict(passes=passes, fraction=equal / len(comparisons), n=len(comparisons),
                unexplained=unexplained)


# ---------------------------------------------------------------- gates and cell mapping

def gate_table(inputs):
    """Every §1.4 gate for every K4S cell, from one complete gate-input record."""
    g0 = inputs["gate0"]["passes"] is True
    g3 = at_most(inputs["poll_p99_seconds"], POLL_P99_LIMIT, "poll p99")
    g4 = perception_gate(inputs["perception"]["fps"], inputs["perception"]["processed_fraction"])
    g5 = inputs["gc"]["passes"] is True
    table = {}
    for cell in K4S_CELLS:
        c = cell_fraction(cell)
        gates = {
            "0_exactness": g0,
            "1_speed": at_least(inputs["r_k4s"], c, "r_K4S") and at_least(inputs["p10_k4s"], c - Fraction(1, 10), "p10"),
            "2_inference": at_least(inputs["r_inf"], c * c, "r_inf"),
            "3_poll_p99": g3,
            "4_perception": g4,
            "5_gc": g5,
            "6_deadline": deadline_gate(inputs["mac_deadline"], inputs["fleet_deadline"], cell)["passes"],
        }
        gates["passes"] = all(gates.values())
        table[cell] = gates
    return table


def map_cell(inputs):
    """c_M among K4S cells: the largest c <= 0.9 passing gates 0-6.

    The provisional cell is the largest c passing gates 0-5. Gate 6 failure moves down
    one cell, where every gate is re-checked, until a cell passes or none remains.
    """
    table = gate_table(inputs)
    pre6 = [c for c in K4S_CELLS if all(v for k, v in table[c].items() if k not in ("6_deadline", "passes"))]
    provisional = pre6[0] if pre6 else None
    trail, chosen = [], None
    if provisional is not None:
        for cell in K4S_CELLS[K4S_CELLS.index(provisional):]:
            trail.append(dict(cell=cell, passes=table[cell]["passes"],
                              gate6=table[cell]["6_deadline"]))
            if table[cell]["passes"]:
                chosen = cell
                break
    largest = next((c for c in K4S_CELLS if table[c]["passes"]), None)
    if largest != chosen:
        raise AssertionError("Step-down and largest-passing definitions disagree")
    return dict(cells=table, provisional_cell=provisional, gate6_trail=trail,
                c_M_k4s=chosen, mac_infeasible=chosen is None)


def kill_flags(inputs, tiers_inputs):
    """§5.4 Mac side, mechanically."""
    gate0 = inputs["gate0"] if inputs else tiers_inputs["gate0"]
    poll = inputs.get("poll_p99_seconds") if inputs else None
    poll_ok = None if poll is None else at_most(poll, POLL_P99_LIMIT, "poll p99")
    reasons = []
    if tiers_inputs["exactness_failure_kind"] == "all-tiers":
        reasons.append("TIERS §7.2 single-thread/belief exactness failure: every tier infeasible")
    if tiers_inputs["exactness_failure_kind"] == "workers-only":
        reasons.append("TIERS §7.2 2/4-worker-only equality failure: K4S is a 4-worker search")
    for part, ok in sorted(gate0.get("parts", {}).items()):
        if ok is not True:
            reasons.append("gate 0 part failed: " + part)
    if poll_ok is False:
        reasons.append("poll-span p99 above 20 ms")
    return dict(k4s_killed_on_mac=bool(reasons), all_tiers_infeasible=tiers_inputs["exactness_failure_kind"] == "all-tiers",
                reasons=reasons)


def final_cell(tiers_inputs, mapping, c_star):
    """c_M: 1.0 iff TIERS found K4 Mac-feasible in its 1.0 cell; otherwise the K4S mapping."""
    if c_star not in ("0.9", "0.8"):
        raise GateInputError("c* must be 0.9 or 0.8")
    if tiers_inputs["exactness_failure_kind"] == "all-tiers":
        c_m, source = None, "TIERS all-tier exactness failure"
    elif tiers_inputs["k4_cell_1_0"] is True:
        c_m, source = FULL_CELL, "TIERS K4 1.0-cell feasibility (read from receipts)"
    elif mapping is None:
        c_m, source = None, "K4S gate 0 failed from TIERS receipts; no K4S measurement needed"
    else:
        c_m, source = mapping["c_M_k4s"], "K4S cell mapping (gates 0-6)"
    eligible = c_m is not None and c_m != FULL_CELL and Fraction(c_m) <= Fraction(c_star)
    return dict(c_M=c_m, source=source, c_star=c_star, k4s_eligible_c_M_le_c_star=eligible,
                mac_infeasible_for_k4s=c_m is None)


def combine_k4s_sessions(records):
    """Minimum r and worst value of every gate input across valid K4S sessions."""
    if not records:
        raise GateInputError("No valid K4S session")
    fleet = records[0]["fleet_deadline"]
    if any(canonical(r["fleet_deadline"]) != canonical(fleet) for r in records):
        raise GateInputError("Sessions used different fleet deadline references")
    parts = {}
    for record in records:
        for part, ok in record["gate0"].get("parts", {}).items():
            parts[part] = parts.get(part, True) and ok is True
    return dict(
        gate0=dict(passes=all(r["gate0"]["passes"] is True for r in records), parts=parts),
        r_k4s=min(r["r_k4s"] for r in records),
        p10_k4s=min(r["p10_k4s"] for r in records),
        r_inf=min(r["r_inf"] for r in records),
        poll_p99_seconds=max(r["poll_p99_seconds"] for r in records),
        perception=dict(fps=min(r["perception"]["fps"] for r in records),
                        processed_fraction=min(r["perception"]["processed_fraction"] for r in records)),
        gc=dict(passes=all(r["gc"]["passes"] is True for r in records)),
        mac_deadline=worst_rates([r["mac_deadline"] for r in records]),
        fleet_deadline=fleet, sessions=len(records))


def worst_rates(cohorts):
    """Per key, the cohort with the highest exact rate (each key may come from a different session)."""
    out = {}
    for key in ("cutoff", "no_complete_play"):
        worst = max(cohorts, key=lambda c: rate_fraction(c, key))
        out[key], out[key + "_count"], out[key + "_n"] = worst[key], worst[key + "_count"], worst["n"]
    # gate 6 reads count/n per key; keep each key's own denominator.
    return dict(n=None, **out)


# ---------------------------------------------------------------- TIERS receipts (read only)

def exactness_failure_kind(error_text):
    """TIERS §7.2 outcome from a TIERS failure trace: None, 'workers-only' or 'all-tiers'."""
    if not error_text or not any(w in error_text for w in TIERS_GATE_FAILURE_WORDS):
        return None
    labels = re.findall(r"Exactness mismatch: (\S+)", error_text)
    if labels and all(re.search(r"/1=[24]$", label) for label in labels):
        return "workers-only"
    return "all-tiers"


def _read_json(path):
    text = Path(path).read_text()
    return json.loads(text.splitlines()[0]) if text.count("\n") <= 1 else json.loads(text)


def git_bytes(repository, commit, name):
    result = subprocess.run(["git", "-C", str(repository), "show", commit + ":" + name], capture_output=True)
    if result.returncode != 0:
        raise PreconditionRefusal("Not in the committed tree: " + name)
    return result.stdout


def verify_committed_receipts(directory, files, *, repository, commit, repository_path):
    """r3 §1.4 / CONFORMANCE-r2 N2: reused TIERS receipts are read from a commit.

    ``commit`` must be a full SHA that is an ancestor of the repository's HEAD; the committed
    tree at ``repository_path`` must hold exactly the sealed inventory (every manifest file
    plus receipt-manifest.json and its sidecar), and every committed blob must equal the
    bytes being read.
    """
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise PreconditionRefusal("Committed TIERS receipts need a full 40-hex commit")
    rel = Path(repository_path or "")
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise PreconditionRefusal("TIERS receipt repository path must be repo-relative without traversal")
    repository = Path(repository)
    ancestry = subprocess.run(["git", "-C", str(repository), "merge-base", "--is-ancestor", commit, "HEAD"],
                              capture_output=True)
    if ancestry.returncode != 0:
        raise PreconditionRefusal("TIERS receipt commit is not an ancestor of HEAD")
    listing = subprocess.run(["git", "-C", str(repository), "ls-tree", "-r", "--name-only", commit, "--",
                              rel.as_posix() + "/"], capture_output=True, text=True)
    names = sorted(set(files) | {"receipt-manifest.json", "receipt-manifest.sha256"})
    committed = sorted(line[len(rel.as_posix()) + 1:] for line in listing.stdout.splitlines())
    if listing.returncode != 0 or committed != names:
        raise PreconditionRefusal("Committed TIERS receipt inventory differs from the sealed inventory")
    for name in names:
        if git_bytes(repository, commit, rel.as_posix() + "/" + name) != (Path(directory) / name).read_bytes():
            raise PreconditionRefusal("TIERS receipt differs from its committed blob: " + name)
    return dict(commit=commit, repository_path=rel.as_posix(), files=len(names))


def read_tiers_session(directory, manifest_sha256, *, require_mac, classify=None, committed=None):
    """Admit one TIERS session receipt directory, read only, by path + receipt-manifest SHA.

    Admissible: a sealed complete session (TIERS §7 D0-D9 done), or a sealed session that
    TIERS terminated on a §7.2 exactness gate failure (a valid gate outcome). Anything
    else, or any TIERS technical-repeat candidate, is refused. ``committed`` =
    dict(repository, commit, repository_path) proves the receipts are committed bytes.
    """
    directory = Path(directory)
    manifest_path = directory / "receipt-manifest.json"
    if not is_sha256(manifest_sha256) or not manifest_path.is_file() or sha(manifest_path) != manifest_sha256:
        raise PreconditionRefusal("TIERS session-completion receipt SHA mismatch: " + str(directory))
    sidecar = directory / "receipt-manifest.sha256"
    if not sidecar.is_file() or sidecar.read_text() != manifest_sha256 + "  receipt-manifest.json\n":
        raise PreconditionRefusal("TIERS receipt-manifest.sha256 sidecar mismatch")
    manifest = _read_json(manifest_path)
    verify_pinned(directory, manifest["files"], "TIERS session receipts")
    if committed is None:
        raise PreconditionRefusal("TIERS receipts must be read from a commit (commit + repo-relative path)")
    commitment = verify_committed_receipts(directory, manifest["files"], **committed)
    scope = manifest.get("scope", "")
    if require_mac and not scope.startswith("MAC-REPLAY"):
        raise PreconditionRefusal("TIERS receipt is not an authorized Mac session: " + scope)
    if not require_mac and not (scope.startswith("MAC-REPLAY") or scope.startswith("LINUX-DRY-RUN")):
        raise PreconditionRefusal("TIERS receipt scope not admissible: " + scope)
    files = manifest["files"]

    def load(name):
        return _read_json(directory / name) if name in files else None
    failure = load("failure.json")
    complete = load("tiers-complete.json")
    error = failure.get("error", "") if failure else ""
    kind = exactness_failure_kind(error)
    if manifest["status"] == "complete" and failure is None and complete and complete.get("completed") is True:
        missing = [n for n in TIERS_REQUIRED_COMPLETE if n not in files]
        if missing:
            raise PreconditionRefusal("TIERS complete session lacks: " + ",".join(missing))
        state = "complete"
    elif manifest["status"] == "failed" and kind is not None:
        state = "exactness-terminated"
    else:
        raise PreconditionRefusal("TIERS §7 list is not complete in this session (status "
                                  + str(manifest["status"]) + "); K4S refuses to start")
    classification = classify(directory) if classify is not None else None
    if classification is not None and classification.get("technical_repeat_candidate"):
        raise PreconditionRefusal("TIERS session is technically invalid (TIERS classifier); "
                                  "a K4S block inside it would be invalid")
    return dict(directory=str(directory), receipt_manifest_sha256=manifest_sha256, scope=scope,
                state=state, exactness_failure_kind=kind, error=error or None,
                complete=complete, identity=load("tiers-identity.json"), summary=load("tiers-summary.json"),
                exactness=load("exactness-tiers.json"), belief=load("belief-exactness.json"),
                student_agreement=load("student-agreement.json"), build=load("build-tiers.json"),
                coordinator_lock=load("coordinator-lock.json"), classification=classification,
                committed=commitment)


def read_sealed(directory, manifest_sha256, *, scopes, label, required=(), statuses=None):
    """A sealed K4S receipt directory by path + receipt-manifest SHA: seal, sidecar, scope,
    status and every listed file re-hashed. Returns the manifest; read files only through
    ``read_sealed_json`` so unlisted bytes are never consumed."""
    directory = Path(directory)
    manifest_path = directory / "receipt-manifest.json"
    if not is_sha256(manifest_sha256) or not manifest_path.is_file() or sha(manifest_path) != manifest_sha256:
        raise PreconditionRefusal(label + " receipt-manifest SHA mismatch")
    sidecar = directory / "receipt-manifest.sha256"
    if not sidecar.is_file() or sidecar.read_text() != manifest_sha256 + "  receipt-manifest.json\n":
        raise PreconditionRefusal(label + " receipt-manifest.sha256 sidecar mismatch")
    manifest = _read_json(manifest_path)
    if manifest.get("scope") not in scopes:
        raise PreconditionRefusal(label + " has an unexpected scope: " + str(manifest.get("scope")))
    if statuses is not None and manifest.get("status") not in statuses:
        raise PreconditionRefusal(label + " seal status is " + str(manifest.get("status")))
    missing = [name for name in required if name not in manifest.get("files", {})]
    if missing:
        raise PreconditionRefusal(label + " seal does not include: " + ",".join(missing))
    verify_pinned(directory, manifest["files"], label)
    return manifest


def read_sealed_json(directory, manifest, name):
    """One sealed JSON receipt, only if listed in the (already verified) manifest."""
    if name not in manifest["files"]:
        return None
    path = Path(directory) / name
    if sha(path) != manifest["files"][name]:
        raise PreconditionRefusal("Sealed receipt changed after verification: " + name)
    return _read_json(path)


def tiers_gate0(session, golden):
    """TIERS §6.3 gate 3 / §7.2 for K4S: exactness, belief/RNG, 1/2/4-worker equality."""
    if session["state"] == "exactness-terminated":
        return dict(passes=False, kind=session["exactness_failure_kind"],
                    parts=dict(tiers_exactness_and_worker_equality=False))
    exactness, belief, summary = session["exactness"], session["belief"], session["summary"]
    records = exactness.get("records", [])
    workers = (exactness.get("passes") is True and exactness.get("states") == golden == len(records)
               and all(r.get("workers_equal") is True and r.get("zero_budget_immutable") is True for r in records))
    belief_ok = (belief.get("passes") is True and belief.get("histories") == golden
                 and belief.get("posterior_weights_cumulative_ledger_samples_rng_exact") is True)
    k4_gate3 = summary["feasibility"]["K4"]["gates"].get("3_exactness") is True
    klass = summary.get("exactness_class") in ("EXACT", "ARM64-NEAR-EXACT")
    parts = dict(tiers_exactness_and_worker_equality=workers and klass,
                 tiers_belief_rng_exactness=belief_ok, tiers_k4_corpus_exactness=k4_gate3)
    return dict(passes=all(parts.values()), kind=None, parts=parts,
                exactness_class=summary.get("exactness_class"))


def tiers_k4_full_speed(session):
    if session["state"] != "complete":
        return False
    k4 = session["summary"]["feasibility"]["K4"]
    return k4.get("feasible") is True and k4.get("cell") == 1.0


def tiers_inputs(sessions, golden):
    """Reused TIERS inputs (never re-measured): gate 0's §7.2 verdict and c_M = 1.0.

    One valid TIERS session (the normal case) is read as is. With several valid TIERS
    sessions, TIERS's own worst-input rule is applied with TIERS's float semantics on the
    K4 inputs (min r and p10, max deadline rates, every gate in every session).
    """
    if not sessions:
        raise PreconditionRefusal("No TIERS session receipt")
    gates = [tiers_gate0(s, golden) for s in sessions]
    kinds = [g["kind"] for g in gates if g["kind"]]
    kind = "all-tiers" if "all-tiers" in kinds else ("workers-only" if kinds else None)
    parts = {}
    for g in gates:
        for part, ok in g["parts"].items():
            parts[part] = parts.get(part, True) and ok is True
    full = all(tiers_k4_full_speed(s) for s in sessions)
    if full and len(sessions) > 1:
        speeds = [s["summary"]["speed"]["K4"] for s in sessions]
        checks = [next(c for c in s["summary"]["deadline_equivalence"]["K4"]["checks"] if c["cell"] == 1.0)
                  for s in sessions]
        reference = checks[0]["reference"]
        if any(canonical(c["reference"]) != canonical(reference) for c in checks):
            raise PreconditionRefusal("TIERS sessions used different 200 ms fleet references")
        worst_cut = max(c["measured"]["cutoff"] for c in checks)
        worst_ncp = max(c["measured"]["no_complete_play"] for c in checks)
        full = (min(s["r"] for s in speeds) >= 1. and min(s["p10"] for s in speeds) >= .7
                and worst_cut <= reference["cutoff"] + .02 and worst_ncp <= reference["no_complete_play"] + .02)
    return dict(gate0=dict(passes=all(g["passes"] for g in gates), parts=parts),
                exactness_failure_kind=kind, k4_cell_1_0=full,
                sessions=[dict(directory=s["directory"], receipt_manifest_sha256=s["receipt_manifest_sha256"],
                               state=s["state"], scope=s["scope"],
                               committed_path=(s.get("committed") or {}).get("repository_path"))
                          for s in sessions])


# ---------------------------------------------------------------- binding (RECHECK-r3 R5)

ANCHOR_X_HEADER = ('"""X4S2 copy of reports/explore/s1/anchor.py (exploration, NEVER ADOPTABLE).\n\n'
                   'Only change: deadline_stats also records coarse_complete (every play has a coarse score\n'
                   'that finished before the cutoff, i.e. len(first) == number of plays, including scores\n'
                   'collected late after a cutoff), coarse_scored and plays. Scoring, admission and reduction\n'
                   'are unchanged.\n\nOriginal docstring: ')
ANCHOR_X_STATS = ("    core.deadline_stats = dict(hit=hit, fallback=best is None, completed=len(scores), candidates=len(work),\n"
                  "                              coarse_complete=len(first) == len(plays), coarse_scored=len(first), plays=len(plays))\n")
ANCHOR_STATS = "    core.deadline_stats = dict(hit=hit, fallback=best is None, completed=len(scores), candidates=len(work))\n"


def scorer_normal_form(data):
    """Map the declared stats-only anchor_x derivative back to anchor.py bytes.

    Exactly two declared hunks are reverted (docstring header; deadline_stats extra keys).
    Any other difference survives, so the SHA comparison then fails closed.
    """
    text = data.decode("utf-8")
    if text.startswith(ANCHOR_X_HEADER):
        text = '"""' + text[len(ANCHOR_X_HEADER):]
        if text.count(ANCHOR_X_STATS) != 1:
            return data
        text = text.replace(ANCHOR_X_STATS, ANCHOR_STATS)
    return text.encode("utf-8")


def bind_scorer_and_native(*, tiers_runtime_files, runtime_root, k4s_scorer_rel, native_sha256,
                           tiers_build, tiers_pins_sha256, dry_run):
    """Gate 0 reuse is valid only if K4S's 4-worker scorer and native are what TIERS qualified."""
    root = Path(runtime_root)
    reasons = []
    scorer_pin = tiers_runtime_files.get(TIERS_SCORER_REL)
    base_pin = tiers_runtime_files.get(TIERS_SCORER_BASE_REL)
    if not is_sha256(scorer_pin) or not is_sha256(base_pin):
        reasons.append("TIERS bundle does not pin the qualified scorer and its e1 base")
    scorer_path = root / k4s_scorer_rel
    if Path(k4s_scorer_rel).parent.parent.as_posix() != "reports/explore":
        reasons.append("K4S scorer must sit in reports/explore/<dir>/ so its e1 base is TIERS's")
    k4s_scorer_sha = sha(scorer_path) if scorer_path.is_file() else None
    normal_sha = sha_bytes(scorer_normal_form(scorer_path.read_bytes())) if scorer_path.is_file() else None
    if not reasons and normal_sha != scorer_pin:
        reasons.append("K4S scorer differs from the TIERS-qualified 4-worker scorer beyond the declared stats hunks")
    if not reasons and sha(root / TIERS_SCORER_BASE_REL) != base_pin:
        reasons.append("e1 planner base differs from TIERS's pin")
    if tiers_build is None or tiers_build.get("native_sha256") != native_sha256:
        reasons.append("Native differs from the binary TIERS qualified in this session (build-tiers.json)")
    elif tiers_build.get("source_manifest_sha256") != tiers_pins_sha256:
        reasons.append("TIERS build does not bind the TIERS bundle manifest")
    if dry_run and native_sha256 != NATIVE_PROVENANCE_SHA:
        reasons.append("Linux dry run requires the provenance native 44874fd6")
    if not dry_run and tiers_build is not None and (tiers_build.get("target") != "aarch64-apple-darwin"
                                                    or not tiers_build.get("locked")):
        reasons.append("TIERS Mac build is not a locked aarch64-apple-darwin build")
    return dict(passes=not reasons, reasons=reasons, tiers_scorer_sha256=scorer_pin,
                tiers_scorer_base_sha256=base_pin, k4s_scorer=k4s_scorer_rel,
                k4s_scorer_sha256=k4s_scorer_sha, k4s_scorer_normal_form_sha256=normal_sha,
                native_sha256=native_sha256, native_provenance_linux_sha256=NATIVE_PROVENANCE_SHA)


# ---------------------------------------------------------------- other pins

def check_sd1_manifest(path, expected_sha256, runtime_root, bundle_student_sha256, bundle_calibration_sha256):
    """SD1 identity from the real clasher.k4s.sd1-manifest.v1 schema (k4s-confirm/sd1_manifest.py).

    Binds the nested checkpoint/calibration job paths and SHA-256s, the threshold, the
    inference mode and the complete inference_sources map (every listed source re-hashed
    under runtime_root; the key set must be exactly the frozen SD1 inference path).
    """
    path = Path(path)
    if not is_sha256(expected_sha256) or not path.is_file() or sha(path) != expected_sha256:
        raise PreconditionRefusal("SD1 manifest SHA mismatch")
    sd1 = json.loads(path.read_text())
    if not isinstance(sd1, dict) or sd1.get("schema") != SD1_SCHEMA or sd1.get("artifact_id") != SD1_ARTIFACT_ID:
        raise PreconditionRefusal("SD1 manifest schema or artifact identity differs")
    if sd1.get("checkpoint") != dict(job_path=SD1_CHECKPOINT_JOB_PATH, sha256=SD1_CHECKPOINT_SHA) \
            or sd1.get("calibration") != dict(job_path=SD1_CALIBRATION_JOB_PATH, sha256=SD1_CALIBRATION_SHA):
        raise PreconditionRefusal("SD1 manifest does not bind the R3a bytes")
    if type(sd1.get("threshold")) is not float or sd1["threshold"] != SD1_THRESHOLD:
        raise PreconditionRefusal("SD1 threshold differs")
    if sd1.get("inference_mode") != SD1_INFERENCE_MODE:
        raise PreconditionRefusal("SD1 inference mode differs")
    if not isinstance(sd1.get("torch_version"), str) or not sd1["torch_version"]:
        raise PreconditionRefusal("SD1 manifest lacks its recorded Torch version")
    sources = sd1.get("inference_sources")
    if not isinstance(sources, dict) or set(sources) != set(SD1_SOURCES):
        raise PreconditionRefusal("SD1 inference_sources is not exactly the frozen SD1 inference path")
    if bundle_student_sha256 != SD1_CHECKPOINT_SHA or bundle_calibration_sha256 != SD1_CALIBRATION_SHA:
        raise PreconditionRefusal("TIERS bundle student bytes are not SD1's bytes")
    verify_pinned(runtime_root, sources, "SD1 inference sources")
    return sd1


def check_corpus(corpus_sha256_actual, corpus_sha256_arg, inventory, publication, ids):
    """Frozen T1 K4 speed corpus: file SHA = argument = T1 publication pin; ids = inventory."""
    if corpus_sha256_actual != corpus_sha256_arg:
        raise PreconditionRefusal("K4S corpus SHA differs from the argument")
    if publication is not None and publication["tier_files"]["K4"]["sha256"] != corpus_sha256_arg:
        raise PreconditionRefusal("K4S corpus SHA differs from the T1 publication pin")
    tier = inventory["tiers"]["K4"]
    pinned = [v["id"] for v in tier["state_inventory"]]
    if tier["states"] != 300 or len(pinned) != 300 or len(set(pinned)) != 300:
        raise PreconditionRefusal("T1 K4 inventory is not 300 unique states")
    if inventory.get("outcomes_read") is not False:
        raise PreconditionRefusal("T1 inventory must declare no outcome reads")
    if ids is not None and (len(ids) != len(set(ids)) or set(ids) != set(pinned)):
        raise PreconditionRefusal("K4S corpus rows differ from the T1 K4 inventory")
    return pinned


HOST_RATIO_STATISTIC = ("geometric mean over the 300 corpus states of (pooled per-state median no-deadline K4S "
                        "work-unit wall over every host x repeat) / (host per-state median over its 3 repeats); "
                        "frozen TIERS fleet_pool direction")
HOST_RATIO_WINDOW = (Fraction(95, 100), Fraction(105, 100))
REPORTING_EVIDENCE_KEYS = ("committed_completion", "all_counted_hosts", "all_original_attempts_classified",
                           "slot0_and_every_background_slot", "reporting_priority", "reporting_guard",
                           "full_occupancy_reporting_mhz")


def in_host_ratio_window(value):
    """Inclusive [0.95, 1.05] as written (r3 §4.5), against the nearest doubles.

    Deliberately NOT TIERS's frozen ``abs(r - 1) <= .05`` (fleet_pool.py), which rejects the
    exact doubles 0.95 and 1.05 because both differences round above .05. K4S r3 §4.5 says
    "inclusive", so both endpoint doubles pass here (tests pin both forms at both endpoints).
    """
    _finite(value, "host ratio")
    return float(HOST_RATIO_WINDOW[0]) <= float(value) <= float(HOST_RATIO_WINDOW[1])


# END common identity pins (equal on every counted host; the frozen ones equal the frozen K4S
# manifest's values). Host-specific bundle receipts (each host's own tiers-pins.json) are kept
# separately as ``host_pins`` and never compared across hosts.
END_MEASUREMENT_FILES = ("reports/explore/k4s-confirm/end_reference.py", "reports/explore/k4s-confirm/end_pool.py",
                         "reports/explore/k4s-confirm/end_background.py", "reports/explore/k4s-confirm/end_evidence.py",
                         MAC_REL + "/k4s_backend.py", MAC_REL + "/k4s_logic.py")
END_FROZEN_PIN_KEYS = ("kernel_sha256", "scorer_sha256", "sd1_manifest_sha256", "corpus_sha256", "native_sha256",
                       "k4s_manifest_sha256", "measurement_files")
END_SHARED_PIN_KEYS = ("bundle_runtime_files_sha256", "bundle_measurement_files_sha256", "bundle_model_files")
END_HOST_PIN_KEYS = ("bundle_manifest_sha256", "bundle_profile_host")


def end_frozen_pins(k4s_manifest, k4s_manifest_sha256, kernel_rel, scorer_rel):
    """The frozen common END pins implied by one frozen K4S manifest (producer, pooler and Mac)."""
    kernel = (k4s_manifest.get("k4s_kernel") or {}).get("files") or {}
    sd1 = (k4s_manifest.get("sd1_manifest") or {}).get("sha256")
    sources = {}
    for rel in END_MEASUREMENT_FILES:
        sources[rel] = (k4s_manifest.get("end_files") or {}).get(rel) or (k4s_manifest.get("k4s_files") or {}).get(rel)
    pins = dict(kernel_sha256=kernel.get(kernel_rel), scorer_sha256=kernel.get(scorer_rel), sd1_manifest_sha256=sd1,
                corpus_sha256=T1_K4_CORPUS_SHA, native_sha256=NATIVE_PROVENANCE_SHA,
                k4s_manifest_sha256=k4s_manifest_sha256, measurement_files=sources)
    if not all(is_sha256(v) for k, v in pins.items() if k != "measurement_files") \
            or not all(is_sha256(v) for v in sources.values()):
        raise PreconditionRefusal("Frozen K4S manifest lacks a kernel/scorer/SD1/END-source pin")
    return pins


def check_end_pins(pins, expected_frozen, label):
    """Exactly the common key set; every frozen pin equal to its frozen value; shared pins well-formed."""
    if not isinstance(pins, dict) or set(pins) != set(END_FROZEN_PIN_KEYS) | set(END_SHARED_PIN_KEYS):
        raise PreconditionRefusal(label + " common pins have an unexpected key set")
    if not isinstance(expected_frozen, dict) or set(expected_frozen) != set(END_FROZEN_PIN_KEYS):
        raise PreconditionRefusal(label + " pins cannot be compared with the complete frozen identity")
    for key in END_FROZEN_PIN_KEYS:
        if canonical(pins[key]) != canonical(expected_frozen[key]):
            raise PreconditionRefusal(label + " was measured on a different " + key)
    models = pins["bundle_model_files"]
    if not (is_sha256(pins["bundle_runtime_files_sha256"]) and is_sha256(pins["bundle_measurement_files_sha256"])
            and isinstance(models, dict) and set(models) == {"v1.pt", "R3a.pt", "R3a-calibration.json", "states.pkl"}
            and all(is_sha256(v) for v in models.values())):
        raise PreconditionRefusal(label + " shared bundle pins are malformed")
    if models["R3a.pt"] != SD1_CHECKPOINT_SHA or models["R3a-calibration.json"] != SD1_CALIBRATION_SHA:
        raise PreconditionRefusal(label + " bundle R3a bytes are not SD1's")
    return pins


def _positive(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def check_fleet_reference(ref, corpus_sha256, corpus_ids, *, dry_run, reference_sha256=None, recheck=None,
                          expected_pins=None, end_pool_sha256=None):
    """Fleet END reference cells (a)-(c) for the T1 K4 corpus (K4S-SPEC §8; r3 §4.5).

    Mac mode requires the pooled provenance written by end_pool.py (committed completion,
    every counted host, classified attempts, slot/priority/guard evidence, full-occupancy
    MHz with signed ratios) and validates the independent re-check receipt by its bound
    inputs: the reference SHA, pool descriptor, END evidence and every host receipt seal,
    and the checker bytes. ``expected_pins`` is the complete frozen common END identity the Mac uses
    (``end_frozen_pins``: kernel/scorer/SD1/corpus/native, the frozen K4S manifest SHA and every END
    measurement source); the fleet reference must have been measured and pooled on exactly those.
    """
    if ref.get("schema") != FLEET_REFERENCE_SCHEMA:
        raise PreconditionRefusal("Unsupported K4S fleet reference schema")
    if ref.get("corpus_sha256") != corpus_sha256:
        raise PreconditionRefusal("Fleet reference was built on a different corpus")
    if not dry_run:
        check_fleet_provenance(ref, reference_sha256, recheck, expected_pins, end_pool_sha256)
    states = ref.get("states", {})
    if set(states) != set(corpus_ids):
        raise PreconditionRefusal("Fleet reference states differ from the corpus")
    for identity, row in states.items():
        for key in ("k4s_wall_seconds", "sd1_poll_seconds"):
            if not _positive(row.get(key)):
                raise PreconditionRefusal("Fleet reference " + key + " invalid: " + identity)
        result = row.get("result")
        if not isinstance(result, dict) or set(result) != {"action", "candidates", "scores"}:
            raise PreconditionRefusal("Fleet reference lacks the no-deadline K4S result: " + identity)
    deadline = ref.get("deadline", {})
    if not isinstance(deadline, dict) or set(deadline) != set(BUDGET_MS):
        raise PreconditionRefusal("Fleet deadline reference must have exactly the five registered cells")
    for cell in BUDGET_MS:
        rates = deadline[cell]
        if not isinstance(rates, dict):
            raise PreconditionRefusal("Fleet deadline reference lacks cell " + cell)
        if rates.get("budget_ms") != BUDGET_MS[cell] or rates.get("charge_scale") != charge_scale_text(cell):
            raise PreconditionRefusal("Fleet deadline cell " + cell + " lacks its budget or 1/c charge")
        if not dry_run and rates.get("n") != 3 * len(corpus_ids) * len(ref["hosts"]):
            raise PreconditionRefusal("Fleet deadline cell " + cell + " is not every host x state x repeat")
        for key in DEADLINE_RATE_KEYS:
            try:
                exact = rate_fraction(rates, key)
            except (GateInputError, KeyError):
                raise PreconditionRefusal("Fleet deadline counts invalid: " + cell + "/" + key) from None
            if rates.get(key) != float(exact):
                raise PreconditionRefusal("Fleet deadline rate disagrees with its counts: " + cell + "/" + key)
    return dict(cells={c: deadline[c] for c in BUDGET_MS}, states=len(states),
                hosts=ref.get("hosts"), pins=ref.get("pins"))


def check_fleet_provenance(ref, reference_sha256, recheck, expected_pins, end_pool_sha256):
    """Mac-mode provenance of the pooled END reference and its independent re-check."""
    hosts = ref.get("hosts")
    if ref.get("repeats") != 3 or not isinstance(hosts, list) or not hosts or hosts != sorted(set(hosts)):
        raise PreconditionRefusal("Fleet reference must be 3-repeat with named, sorted, unique hosts")
    prov = ref.get("provenance")
    if not isinstance(prov, dict):
        raise PreconditionRefusal("Fleet reference lacks its pooled END provenance")
    evidence = prov.get("reporting_load_profile_evidence")
    if not isinstance(evidence, dict) or any(evidence.get(k) is not True for k in REPORTING_EVIDENCE_KEYS):
        raise PreconditionRefusal("Fleet reference lacks machine-checked reporting-load evidence")
    if ref.get("reporting_load_profile") is not True:
        raise PreconditionRefusal("Fleet reference is not a reporting-load profile")
    for key in ("pool_input_sha256", "end_evidence_sha256", "completion_sha256", "plan_sha256", "pooler_sha256"):
        if not is_sha256(prov.get(key)):
            raise PreconditionRefusal("Fleet reference provenance lacks " + key)
    receipts = prov.get("host_receipts")
    if prov.get("counted_hosts") != hosts or not isinstance(receipts, dict) or sorted(receipts) != hosts:
        raise PreconditionRefusal("Fleet reference host set differs from the committed counted-host set")
    ratios = ref.get("host_ratio_to_pool")
    if not isinstance(ratios, dict) or sorted(ratios) != hosts or ref.get("ratio_statistic") != HOST_RATIO_STATISTIC:
        raise PreconditionRefusal("Fleet reference lacks the frozen per-host ratio statistic")
    for host in hosts:
        entry = receipts[host]
        if not is_sha256(entry.get("manifest_sha256")) or entry.get("mhz_comparison_passes") is not True:
            raise PreconditionRefusal("Fleet host receipt lacks its seal or a passing MHz comparison: " + host)
        host_pins = entry.get("host_pins")
        if not isinstance(host_pins, dict) or set(host_pins) != set(END_HOST_PIN_KEYS) \
                or not is_sha256(host_pins["bundle_manifest_sha256"]) or host_pins["bundle_profile_host"] != host:
            raise PreconditionRefusal("Fleet host receipt lacks its own bundle/profile receipt: " + host)
        if not _positive(entry.get("reference_to_reporting_mean")):
            raise PreconditionRefusal("Fleet host lacks its signed reference/reporting MHz ratio: " + host)
        if not in_host_ratio_window(ratios[host]) or entry.get("ratio_to_pool") != ratios[host]:
            raise PreconditionRefusal("Fleet host ratio outside [0.95, 1.05] or unbound: " + host)
    if ref.get("pool_conforms") is not True:
        raise PreconditionRefusal("Fleet reference pool does not conform")
    # Common identity pins incl. the frozen K4S manifest SHA and every END measurement source
    # (r2 finding 15): the reference must have been produced and pooled by the frozen code.
    check_end_pins(ref.get("pins"), expected_pins, "Fleet reference")
    if not is_sha256(reference_sha256) or not isinstance(recheck, dict):
        raise PreconditionRefusal("Fleet reference needs its independent re-check receipt")
    bound = dict(schema=END_RECHECK_SCHEMA, passes=True, outcome_access=False, reference_sha256=reference_sha256,
                 pool_input_sha256=prov["pool_input_sha256"], end_evidence_sha256=prov["end_evidence_sha256"],
                 host_receipts={h: receipts[h]["manifest_sha256"] for h in hosts}, checker_sha256=end_pool_sha256)
    for key, value in bound.items():
        if recheck.get(key) != value:
            raise PreconditionRefusal("Independent END re-check does not bind " + key)
    if not is_sha256(end_pool_sha256) or not recheck.get("checked_by") or recheck.get("checked_by") == prov.get("pooled_by"):
        raise PreconditionRefusal("END re-check must be run by someone other than the pooler, with pinned checker bytes")
    return dict(passes=True)


def check_output_isolated(output, forbidden):
    """K4S writes only to a fresh K4S output directory, never into or above a TIERS path."""
    out = Path(output).resolve()
    if out.exists():
        raise PreconditionRefusal("K4S output directory already exists")
    for root in forbidden:
        if root is None:
            continue
        root = Path(root).resolve()
        if out == root or root in out.parents or out in root.parents:
            raise PreconditionRefusal("K4S output overlaps a TIERS/read-only path: " + str(root))
    return str(out)


def forbidden_roots(runtime_root, tiers_dirs=(), tiers_bundle=None, extra=()):
    root = Path(runtime_root)
    return [root / TIERS_PACKAGE_REL, root / "reports/explore/t1", tiers_bundle,
            *tiers_dirs, *extra]


# ---------------------------------------------------------------- preconditions

def check_standalone_authorization(path, expected_sha256, tiers_shas):
    path = Path(path) if path else None
    if path is None or not is_sha256(expected_sha256) or not path.is_file() or sha(path) != expected_sha256:
        raise PreconditionRefusal("Standalone mode requires the coordinator authorization file by path + SHA")
    auth = json.loads(path.read_text())
    if auth.get("schema") != "clasher.k4s.mac-standalone-authorization.v1":
        raise PreconditionRefusal("Unsupported standalone authorization schema")
    if not auth.get("coordinator") or auth.get("sam_authorized_session") is not True or not auth.get("utc"):
        raise PreconditionRefusal("Standalone authorization lacks coordinator, Sam's session authorisation or UTC")
    descriptive = auth.get("descriptive_only_without_tiers_inputs") is True
    if not descriptive and sorted(auth.get("tiers_receipt_manifest_sha256", [])) != sorted(tiers_shas):
        raise PreconditionRefusal("Standalone authorization names different TIERS receipts")
    if descriptive and tiers_shas:
        raise PreconditionRefusal("Descriptive-only authorization must not be combined with TIERS receipts")
    return dict(auth, descriptive_only=descriptive)


def same_mac(tiers_identity, current_identity):
    """Gate 0 reuse is valid only on the Mac TIERS qualified (host, machine and sysctl identity)."""
    keys = ("hw.model", "machdep.cpu.brand_string", "hw.memsize", "hw.perflevel0.physicalcpu",
            "hw.perflevel1.physicalcpu", "hw.perflevel0.logicalcpu", "hw.perflevel1.logicalcpu")

    def parse(identity):
        out = {}
        for line in (identity.get("sysctl") or {}).get("stdout", "").splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip()
        return out
    a, b = parse(tiers_identity), parse(current_identity)
    mismatches = [k for k in ("host", "machine", "platform") if tiers_identity.get(k) != current_identity.get(k)]
    mismatches += [k for k in keys if a.get(k) is None or a.get(k) != b.get(k)]
    return dict(passes=not mismatches, mismatches=mismatches)


def check_in_session(session, lock_path, now_utc, *, require_lock=True):
    """Same-session ordering: K4S starts after TIERS completed, under the same lock, within 2 h."""
    reasons = []
    completed = (session["complete"] or {}).get("utc")
    if session["state"] == "complete":
        if not isinstance(completed, (int, float)) or not completed < now_utc:
            reasons.append("TIERS completion is not before K4S start")
        elif now_utc - completed > IN_SESSION_MAX_GAP_SECONDS:
            reasons.append("More than 2 h since TIERS completion; use standalone mode with authorization")
    lock = session.get("coordinator_lock")
    if require_lock and (lock is None or lock.get("path") != str(lock_path) or lock.get("held_exclusively") is not True):
        reasons.append("TIERS session was not held under the same coordinator lock file")
    if reasons:
        raise PreconditionRefusal("; ".join(reasons))
    return dict(passes=True, tiers_completed_utc=completed, gap_seconds=None if completed is None else now_utc - completed)


def check_repeat_admission(prior_classifications, *, released, review):
    """Repeats only for pre-listed technical failures; post-release needs an independent review."""
    technical = [c for c in prior_classifications if c.get("technical_repeat_candidate") is True]
    if len(technical) != len(prior_classifications):
        raise PreconditionRefusal("A prior K4S attempt was not a pre-listed technical failure; no repeat")
    counted = [c for c in technical if c.get("counts_toward_repeat_allowance", True)]
    if len(counted) > MAX_TECHNICAL_REPEATS:
        raise PreconditionRefusal("Technical repeat allowance exhausted; coordinator amendment required")
    if released:
        if review is None:
            raise PreconditionRefusal("K4S outcomes are released: an independent classification review is required")
        confirmed = set(review.get("confirmed_classification_sha256", []))
        if review.get("schema") != "clasher.k4s.mac-classification-review.v1" or review.get("independent_of_author") is not True:
            raise PreconditionRefusal("Independent classification review receipt is malformed")
        if any(c["receipt_sha256"] not in confirmed for c in prior_classifications):
            raise PreconditionRefusal("Independent review does not confirm every prior classification")
        if not prior_classifications and review.get("confirms_session_validity_rule") is not True:
            raise PreconditionRefusal("Independent review must confirm the session-validity classification rule")
    return dict(attempt=len(prior_classifications) + 1, technical_repeats=len(technical),
                counted_repeats=len(counted), released=released)


# ---------------------------------------------------------------- load selection

def select_load(tiers_manifest, tiers_identity, *, dry_run):
    """Load-selection rule: K4S uses TIERS's own replay perception load, byte for byte.

    The profile is the ``load`` block of the TIERS bundle manifest (tiers-pins.json) whose
    SHA TIERS recorded in its tiers-identity.json for the qualifying session; nothing is
    chosen afresh. Priority and threading equal TIERS's live configuration: nice 10 with
    inherited QoS and no affinity on the Mac (nice 19 on the Linux dry-run hosts), Torch,
    BLAS and OpenCV at one thread, perception in its own spawned process.
    """
    load = tiers_manifest["load"]
    if tiers_identity.get("load_label") != load.get("label"):
        raise PreconditionRefusal("TIERS bundle load label differs from the TIERS session's")
    if load.get("kind") not in ("v3-body-hud-only", "v4"):
        raise PreconditionRefusal("Only TIERS's real V3/V4 TRAIN replay load is admissible")
    if not dry_run and load["config"].get("device") != "mps":
        raise PreconditionRefusal("Mac replay load must be TIERS's MPS perception configuration")
    if load.get("target_fps") != 20:
        raise PreconditionRefusal("Replay load must be paced at TIERS's 20 FPS")
    labels = [load["label"]] + (["PROVISIONAL-LOAD"] if load["kind"] == "v3-body-hud-only" else [])
    return dict(kind=load["kind"], label=load["label"], labels=labels, target_fps=load["target_fps"],
                device=load["config"].get("device"), matches=list(load.get("matches", [])),
                split=load.get("split"), nice=19 if dry_run else 10,
                qos="inherited" if not dry_run else "linux SCHED_OTHER", affinity=None if not dry_run else "dry-run CPUs",
                threads=dict(torch=1, blas=1, opencv=1), process="spawned perception process (TIERS load_worker)",
                rule="TIERS bundle load block, verbatim; same session priority and threading")


def check_priority_and_threads(nice, environ, *, dry_run):
    want = 19 if dry_run else 10
    if nice != want:
        raise PreconditionRefusal("K4S measurement requires nice %d" % want)
    if any(environ.get(k) != "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")):
        raise PreconditionRefusal("OMP/OPENBLAS/MKL thread environment must be pinned to one")


def provisional_status(emulator_seen_start, emulator_seen_end, formal_e4_amendment_verified):
    if formal_e4_amendment_verified and emulator_seen_start and emulator_seen_end:
        return dict(provisional=False, label="FORMAL-E4 (emulator-on)")
    if not (emulator_seen_start and emulator_seen_end):
        return dict(provisional=True, label="PROVISIONAL (emulator-off)")
    return dict(provisional=True, label="PROVISIONAL (no formal E4 amendment)")


EMULATOR_NAMES = ("qemu-system-aarch64", "emulator", "Android Emulator")


def emulator_present(process_table_stdout):
    names = [line.strip().split(None, 1)[1] for line in process_table_stdout.splitlines()
             if len(line.strip().split(None, 1)) == 2]
    return any(any(Path(n).name == e or Path(n).name.startswith(e) for e in EMULATOR_NAMES) for n in names)


# ---------------------------------------------------------------- receipt store

class K4SStore:
    """Exclusive-creation receipts in a fresh K4S directory; sealed even on failure."""

    def __init__(self, directory, scope, forbidden=()):
        check_output_isolated(directory, forbidden)
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.scope = scope
        self.streams = {}

    def write(self, name, value):
        with (self.directory / name).open("x") as stream:
            stream.write(canonical(dict(scope=self.scope, **value)) + "\n")

    def append(self, name, value):
        if name not in self.streams:
            self.streams[name] = (self.directory / name).open("x")
        self.streams[name].write(canonical(dict(scope=self.scope, **value)) + "\n")
        self.streams[name].flush()

    def seal(self, status):
        for stream in self.streams.values():
            stream.close()
        files = {str(p.relative_to(self.directory)): sha(p)
                 for p in sorted(self.directory.rglob("*")) if p.is_file()}
        self.write("receipt-manifest.json", dict(status=status, files=files))
        with (self.directory / "receipt-manifest.sha256").open("x") as stream:
            stream.write(sha(self.directory / "receipt-manifest.json") + "  receipt-manifest.json\n")


def now_utc():
    return time.time()


def getpriority():
    return os.getpriority(os.PRIO_PROCESS, 0)

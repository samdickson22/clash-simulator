"""Strict, dependency-free receipts and the E4-v3 draft reducer."""
import hashlib
import json
import math
from pathlib import Path

TIERS = ("K0c", "S", "K2", "K4")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_files(root, files):
    root = Path(root).resolve()
    if not files:
        raise ValueError("Empty SHA manifest")
    for name, expected in files.items():
        path = (root / name).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            raise ValueError("Pin mismatch: " + name) from None
        if not path.is_file() or sha(path) != expected:
            raise ValueError("Pin mismatch: " + name)


def quantiles(values):
    values = sorted(values)
    if not values or any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("Need finite nonnegative observations")
    def q(p):
        index = (len(values) - 1) * p
        lo, hi = math.floor(index), math.ceil(index)
        return values[lo] + (values[hi] - values[lo]) * (index - lo)
    return dict(n=len(values), p10=q(.1), p25=q(.25), p50=q(.5), p90=q(.9),
                p95=q(.95), p99=q(.99), max=values[-1])


class ReceiptStore:
    """Exclusive creation; also seals incomplete runs, without overwriting."""
    def __init__(self, directory, scope):
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
        files = {p.name: sha(p) for p in sorted(self.directory.iterdir()) if p.is_file()}
        self.write("receipt-manifest.json", dict(status=status, files=files))
        with (self.directory / "receipt-manifest.sha256").open("x") as stream:
            stream.write(sha(self.directory / "receipt-manifest.json") + "  receipt-manifest.json\n")


def assert_exact(actual, expected, label):
    # Reject NaN/Inf and compare the complete ordered work, not just best action.
    if canonical(actual) != canonical(expected):
        raise ValueError("Exactness mismatch: " + label)


def near_floats(actual, expected, label):
    """Frozen r3 relative tolerance; zero/support/order cannot drift."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise ValueError("Exactness mismatch: " + label)
        return max((near_floats(actual[k], v, label+"/"+str(k)) for k,v in expected.items()), default=0.)
    if isinstance(expected, list):
        if not isinstance(actual, (list,tuple)) or len(actual) != len(expected):
            raise ValueError("Exactness mismatch: " + label)
        return max((near_floats(a,b,label) for a,b in zip(actual,expected)), default=0.)
    if isinstance(expected, float):
        if not isinstance(actual, (float,int)) or not math.isfinite(actual) or not math.isfinite(expected):
            raise ValueError("Exactness mismatch: " + label)
        relative = abs(actual-expected)/max(abs(actual),abs(expected)) if actual or expected else 0.
        if (actual == 0) != (expected == 0) or relative > 1e-12:
            raise ValueError("Exactness mismatch: " + label)
        return relative
    assert_exact(actual, expected, label)
    return 0.


def score_exactness(actual, expected, label):
    assert_exact(actual["action"], expected["action"], label+"/action")
    assert_exact(actual["candidates"], expected["candidates"], label+"/candidates")
    return near_floats(actual["scores"], expected["scores"], label+"/scores")


def belief_exactness(actual, expected, label):
    maximum = 0.
    for key in ("ledger", "events", "samples", "rng"):
        assert_exact(actual[key], expected[key], label+"/"+key)
    maximum = near_floats(actual["derived"], expected["derived"], label+"/posterior")
    for key, reference in expected["arrays"].items():
        value = actual["arrays"][key]
        assert_exact(value["dtype"], reference["dtype"], label+"/dtype")
        assert_exact(value["shape"], reference["shape"], label+"/shape")
        if key == "states" or not ("values" in reference or "values_zlib_base64" in reference):
            assert_exact(value["sha256"], reference["sha256"], label+"/"+key)
        elif "values_zlib_base64" in reference:
            for discrete in ("support_sha256", "order_sha256"):
                if discrete in reference:
                    assert_exact(value[discrete],reference[discrete],label+"/"+discrete)
            if value["sha256"] != reference["sha256"]:
                import base64, struct, zlib
                def decode(item):
                    raw = zlib.decompress(base64.b64decode(item["values_zlib_base64"],validate=True))
                    return [v[0] for v in struct.iter_unpack("<d",raw)]
                maximum = max(maximum,near_floats(decode(value),decode(reference),label+"/"+key))
        else:
            maximum = max(maximum, near_floats(value["values"],reference["values"],label+"/"+key))
            # Positive hypotheses and the ordered cumulative array retain their
            # support and order even when floating arithmetic is near-exact.
            assert_exact([v != 0 for v in value["values"]], [v != 0 for v in reference["values"]], label+"/support")
            assert_exact(sorted(range(len(value["values"])),key=lambda i:value["values"][i]),
                         sorted(range(len(reference["values"])),key=lambda i:reference["values"][i]),label+"/order")
    return maximum


def census_average(rows):
    """CPU-time integral / full census duration, including absent PID samples."""
    duration = sum(r["interval_seconds"] for r in rows)
    totals = {}
    for row in rows:
        for process in row["processes"]:
            if not process["owned"] and process["cpu_cores"] is not None:
                totals[process["pid"]] = totals.get(process["pid"],0.) + process["cpu_cores"]*row["interval_seconds"]
    return {str(pid): value/duration for pid,value in totals.items()} if duration else {}


def speed_summary(rows):
    """Reduce repeated rounds per state BEFORE reducing the sealed corpus."""
    grouped = {}
    for row in rows:
        if row["wall_seconds"] <= 0 or row["fleet_wall_seconds"] <= 0:
            raise ValueError("Nonpositive speed timing")
        key = row["tier"], row["id"]
        grouped.setdefault(key, []).append(row)
    result = {}
    for tier in TIERS:
        ratios, fleet_walls, measured_walls = [], [], []
        for (name, _), samples in grouped.items():
            if name != tier:
                continue
            refs = {r["fleet_wall_seconds"] for r in samples}
            if len(refs) != 1:
                raise ValueError("Fleet reference changed within a state")
            wall = quantiles([r["wall_seconds"] for r in samples])["p50"]
            reference = next(iter(refs))
            ratios.append(reference / wall)
            fleet_walls.append(reference)
            measured_walls.append(wall)
        result[tier] = quantiles(ratios)
        result[tier]["sum_ratio"] = sum(fleet_walls) / sum(measured_walls)
        result[tier]["p90_wall_ratio"] = quantiles(fleet_walls)["p90"] / quantiles(measured_walls)["p90"]
        result[tier]["r"] = min(result[tier]["p50"], result[tier]["sum_ratio"], result[tier]["p90_wall_ratio"])
        result[tier]["per_state_ratios"] = ratios
    return result


def perception_window(rows, start, end, target_fps=20):
    if end <= start:
        raise ValueError("Invalid perception window")
    selected = [r for r in rows if start <= r["finished"] < end]
    # Expected delivery count includes backlog and missing frames. Merely dividing
    # completed frames by captured frames would hide an overloaded replay worker.
    expected = (end - start) * target_fps
    fps = len(selected) / (end - start)
    return dict(start=start, end=end, processed=len(selected), expected=expected,
                fps=fps, processed_fraction=min(1., len(selected) / expected),
                service_ms=quantiles([r["service_ms"] for r in selected]) if selected else None,
                passes=fps >= 18 and len(selected) / expected >= .95)


def agreement(reference, measured, threshold):
    """Joint gate AND ordered top-8; tie exceptions are local to changed ranks."""
    if reference["legal"] != measured["legal"]:
        raise ValueError("Student legal mask changed")
    legal = reference["legal"]
    def order(row):
        return sorted(legal, key=lambda a: (-row["ranks"][a], a))[:8]
    old, new = order(reference), order(measured)
    old_gate = bool(legal) and reference["gate"] >= threshold
    new_gate = bool(legal) and measured["gate"] >= threshold
    equal = old_gate == new_gate and old == new
    gate_ok = old_gate == new_gate or abs(reference["gate"] - threshold) <= 1e-4
    # Every inversion/replacement must be a registered near tie in the Linux
    # reference. An unrelated tie anywhere else cannot excuse a disagreement.
    rank_ok = all(abs(reference["ranks"][a] - reference["ranks"][b]) <= 1e-4
                  for a, b in zip(old, new) if a != b)
    return dict(equal=equal, allowed=gate_ok and rank_ok, reference_gate=old_gate,
                measured_gate=new_gate, reference_top8=old, measured_top8=new)


def agreement_gate(rows):
    if not rows:
        return dict(passes=False, fraction=0., n=0, unexplained=0)
    fraction = sum(r["equal"] for r in rows) / len(rows)
    unexplained = sum(not r["equal"] and not r["allowed"] for r in rows)
    return dict(passes=fraction >= .995 and unexplained == 0, fraction=fraction,
                n=len(rows), unexplained=unexplained)


def forward_exception(tier, reference, measured, threshold):
    if tier == "S":
        old, new = json.loads(canonical(reference)), json.loads(canonical(measured))
        for value in (old,new):
            value["ranks"] = {int(k): v for k,v in value["ranks"].items()}
        result = agreement(old,new,threshold)
        return not result["equal"] and result["allowed"]
    if tier == "K0c":
        # Probability logs of the Linux top-8 certify only local near ties.
        # A sampled fallback change requires a separately sealed sample margin.
        if reference["sample"] != measured["sample"] and reference.get("sample_margin", math.inf) > 1e-4:
            return False
        old, new = reference["top8"], measured["top8"]
        ranks = dict(zip(old,reference["log_probabilities"]))
        permitted = len(old) == len(new) and all(a in ranks and b in ranks and abs(ranks[a]-ranks[b]) <= 1e-4
                                                for a,b in zip(old,new) if a != b)
        return permitted and (old != new or reference["sample"] != measured["sample"])
    return False


def choose_backend(agreement_results, forwards, perception):
    cpu = agreement_results.get("cpu", {}).get("passes", False) and forwards.get("cpu", {}).get("p99", math.inf) <= 20
    mps = agreement_results.get("mps", {}).get("passes", False) and forwards.get("mps", {}).get("p99", math.inf) <= 20
    if mps and "cpu" in forwards and forwards["cpu"]["p99"] - forwards["mps"]["p99"] >= 2 and perception["mps"] - perception["cpu"] <= 2:
        return "mps"
    if cpu:
        return "cpu"
    return None


def gc_summary(events, polls):
    opportunities = [p for p in polls if p["opportunity"]]
    delayed = {p["poll_id"] for p in opportunities if p["entered"] - p["scheduled"] > .025 and any(
        e["start"] <= p["scheduled"] < e["end"] for e in events)}
    # Charge the observed poll start, including dispatch after the GC ends.
    pauses = [p["entered"] - p["scheduled"] for e in events for p in opportunities
              if e["start"] <= p["scheduled"] < e["end"]]
    maximum = max(pauses, default=0.) * 1000
    rate = len(delayed) / len(opportunities) if opportunities else None
    return dict(opportunities=len(opportunities), delayed_polls=len(delayed),
                delayed_poll_rate=rate, max_in_opportunity_poll_delay_ms=maximum,
                max_in_opportunity_pause_ms=maximum,
                passes=rate is not None and rate <= .01 and maximum <= 50)


def feasible(speed, load, exact, gc_result, student_ok=True, deadline_cell=None):
    reasons = []
    ratio = speed["r"]
    if ratio < .8 or speed["p10"] < .7:
        reasons.append("speed")
    if not load["passes"]:
        reasons.append("perception")
    if not exact:
        reasons.append("exactness")
    if not gc_result["passes"]:
        reasons.append("GC/poll")
    if not student_ok:
        reasons.append("student backend")
    if deadline_cell is None:
        reasons.append("deadline equivalence")
    gates = {"1_speed": ratio >= .8 and speed["p10"] >= .7,
             "2_perception": load["passes"], "3_exactness": exact,
             "4_gc": gc_result["passes"], "5_student": student_ok,
             "6_deadline": deadline_cell is not None}
    return dict(feasible=not reasons, reasons=reasons, gates=gates,
                cell=deadline_cell)


def decision_rates(rows):
    if not rows:
        raise ValueError("Empty deadline cohort")
    return dict(n=len(rows), cutoff=sum(r["cutoff"] for r in rows)/len(rows),
                fallback=sum(r["fallback"] for r in rows)/len(rows),
                no_complete_play=sum(r["no_complete_play"] for r in rows)/len(rows),
                wall_ms=quantiles([r["wall_seconds"]*1000 for r in rows]),
                over_200_ms=sum(r["over_200_ms"] for r in rows),
                cut_return_over_208_ms=sum(r["cut_return_over_208_ms"] for r in rows))


def deadline_equivalence(speed, measured, fleet):
    initial = 1. if speed["r"] >= 1. else .8 if speed["r"] >= .8 else None
    checks = []
    for cell in ((1., .8) if initial == 1. else (.8,) if initial == .8 else ()):
        reference = fleet[str(cell)]
        passed = all(measured[key] <= reference[key] + .02 for key in ("cutoff", "no_complete_play"))
        checks.append(dict(cell=cell, passes=passed, reference=reference, measured=measured))
        if passed:
            return dict(initial_cell=initial, cell=cell, checks=checks)
    return dict(initial_cell=initial, cell=None, checks=checks)

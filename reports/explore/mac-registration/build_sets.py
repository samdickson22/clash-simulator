#!/usr/bin/env python3
"""TIERS Amendment 4, B.1-B.5 selection: one SHA-verified pass over T1's 32 captures.

Reads only the 32 ``capture.pkl.gz`` files that T1's committed corpora.json pins
(never ``games/`` or ``local-complete.json``), keeps outcome-free row metadata,
and fails closed on any lineage, count or health difference. Writes the
registration sets and packet schedule, the B.5 fixture plan and a stage receipt.
Run at nice 19 on one core; nothing here is timed.
"""
import argparse
import collections
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import macreg_io as io
import selection


def scan(files, speed_digests, validate_row, canonical_digest, log=print):
    """Pass 1: per-row metadata, validity, per-tier counts/health, speed-row digests."""
    pool, per_capture, lineage = [], [], {}
    counts = {t: collections.Counter() for t in io.TIERS}
    health = {t: collections.Counter() for t in io.TIERS}
    for number, entry in enumerate(files, 1):
        capture = io.load_capture(entry)
        retained = 0
        for row in io.capture_rows(capture):
            tick = io.row_identity(row, entry)
            try:
                validate_row(row, entry["tier"])
                valid, error = True, None
            except ValueError as failure:
                valid, error = False, str(failure)
            pool.append(dict(id=row["id"], tier=entry["tier"], seed=entry["seed"], tick=tick, valid=valid, error=error))
            if row["id"] in speed_digests:
                lineage[row["id"]] = canonical_digest(row)
            retained += 1
        row = None  # an empty capture retains no rows
        counted = sum(capture["counts"].values())
        counts[entry["tier"]].update({str(tuple(k)): v for k, v in capture["counts"].items()})
        health[entry["tier"]].update(capture["health"])
        per_capture.append(dict(relative=entry["relative"], sha256=entry["sha256"], tier=entry["tier"],
                                seed=entry["seed"], retained=retained, counted=counted,
                                health=dict(capture["health"])))
        del capture
        log("capture %d/32 %s retained=%d counted=%d" % (number, entry["relative"], retained, counted))
    return pool, per_capture, lineage, counts, health


def check_capture_receipt(corpora, counts, health, per_capture):
    """B.1: per-tier stratum counts and capture health equal corpora.json."""
    for tier in io.TIERS:
        if dict(counts[tier]) != corpora["tiers"][tier]["counts"]:
            raise ValueError("Capture stratum counts differ from corpora.json: " + tier)
        if dict(health[tier]) != corpora["tiers"][tier]["capture_health"]:
            raise ValueError("Capture health differs from corpora.json: " + tier)
    return dict(counts_equal=True, health_equal=True,
                retained_equals_counted=all(c["retained"] == c["counted"] for c in per_capture),
                retained=sum(c["retained"] for c in per_capture), counted=sum(c["counted"] for c in per_capture))


def check_lineage(speed_digests, lineage, pool):
    """B.1: every published speed row is a capture row with the same canonical digest."""
    valid = {m["id"]: m["valid"] for m in pool}
    missing = sorted(set(speed_digests) - set(lineage))
    differ = sorted(i for i in lineage if lineage[i] != speed_digests[i])
    invalid = sorted(i for i in speed_digests if not valid.get(i, False))
    if missing or differ or invalid:
        raise ValueError("Lineage cross-check failed: missing=%r differ=%r invalid=%r" % (missing[:4], differ[:4], invalid[:4]))
    return dict(speed_rows=len(speed_digests), canonical_digest_equal=len(lineage), missing=0, differ=0)


def select(pool, speed, end, extra_sources, inventory=()):
    """B.2-B.5 on metadata; returns registration fields, fixture plan and disclosures."""
    selection.check_pool(pool)
    validity = selection.validity_summary(pool)
    if validity["stop"]:
        raise ValueError("More than 1%% of capture rows fail the public row contract: %d/%d" % (validity["invalid"], validity["rows"]))
    packets, games = selection.select_packets(pool, inventory=inventory)
    schedule = selection.build_schedule(packets)
    packet_ids = [m["id"] for m in packets]
    speed_ids = [i for t in io.TIERS for i in speed[t]]
    agreement, fill = selection.select_agreement(pool, speed_ids, packet_ids)
    public_ids, golden_ids = [e["id"] for e in end[:1200]], [e["id"] for e in end[1200:]]
    if public_ids != speed_ids:
        raise ValueError("END public order differs from corpora.json inventory order")
    fixture, extra = selection.fixture_ids(public_ids, golden_ids, agreement, packet_ids, pool)
    sets = dict(golden=golden_ids, speed={t: list(speed[t]) for t in io.TIERS}, agreement=agreement, packets=packet_ids)
    plan = dict(fixture_ids=fixture, end_rows=len(end), extra_ids=extra,
                extra_sources={i: extra_sources[i] for i in extra})
    return dict(sets=sets, packet_schedule=schedule), plan, dict(validity=validity, packet_games=games, agreement=fill)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    io.runtime_arguments(p)
    p.add_argument("--corpora", type=Path, required=True, help="T1 corpora.json (3501e2ac)")
    p.add_argument("--end-digests", type=Path, required=True, help="Amendment 3 canonical-row-digests.json")
    p.add_argument("--end-digests-sha256", required=True)
    p.add_argument("--captures", type=Path, required=True, help="local copy: corpus-<tier>-<index>/capture.pkl.gz")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    io.require_low_priority()
    a.output.mkdir(parents=True)
    pins, runtime = io.setup_runtime(a)
    corpora = io.read_pinned_json(a.corpora, io.CORPORA_SHA256)
    if corpora.get("outcomes_read") is not False:
        raise ValueError("corpora.json must declare no outcome reads")
    end = io.end_digests(a.end_digests, a.end_digests_sha256)
    speed = {t: [v["id"] for v in corpora["tiers"][t]["state_inventory"]] for t in io.TIERS}
    speed_digests = {e["id"]: e["canonical_sha256"] for e in end[:1200]}
    from convert_states import canonical_digest
    from corpus_contract import validate_row
    files = io.capture_inventory(corpora, a.captures)
    started = io.utc()
    pool, per_capture, lineage, counts, health = scan(files, speed_digests, validate_row, canonical_digest)
    receipt_check = check_capture_receipt(corpora, counts, health, per_capture)
    lineage_check = check_lineage(speed_digests, lineage, pool)
    source = {(f["tier"], f["seed"]): f["relative"] for f in files}
    registration, plan, disclosure = select(pool, speed, end, {m["id"]: source[(m["tier"], m["seed"])] for m in pool},
                                            inventory=sorted(source))
    shas = dict(pool=io.write_json(a.output / "pool.json", dict(rows=pool, captures=per_capture, outcomes_read=False)),
                sets=io.write_json(a.output / "mac-sets.json", registration),
                plan=io.write_json(a.output / "fixture-plan.json", plan))
    schedule = registration["packet_schedule"]
    stage = dict(schema="clasher.tiers-a4.selection-stage.v1", utc_start=started, utc_end=io.utc(),
                 **io.process_identity(),
                 corpora_sha256=io.CORPORA_SHA256, end_digests_sha256=a.end_digests_sha256,
                 end_fingerprint=io.END_FINGERPRINT, e4v3_pins=pins, runtime=runtime, versions=io.runtime_versions(),
                 script_sha256={n: io.file_sha(io.HERE / n) for n in ("build_sets.py", "selection.py", "macreg_io.py")},
                 captures=[dict(relative=f["relative"], sha256=f["sha256"], sha256_verified=True) for f in files],
                 capture_receipt=receipt_check, lineage=lineage_check, **disclosure,
                 counts=dict(golden=len(registration["sets"]["golden"]), speed=sum(len(v) for v in speed.values()),
                             agreement=len(registration["sets"]["agreement"]), packets=len(registration["sets"]["packets"]),
                             fixture=len(plan["fixture_ids"]), extra=len(plan["extra_ids"])),
                 schedule=dict(first_timestamp_seconds=schedule[0]["timestamp_seconds"],
                               last_offset_seconds=schedule[-1]["offset_seconds"], cadence="P1 sealed 20 Hz ticks; games joined by one 10-tick search interval"),
                 sets_sha256=io.sets_sha256(registration["sets"]), output_sha256=shas, outcomes_read=False, games_read=False, timing=False)
    io.write_json(a.output / "selection-stage.json", stage)
    print(json.dumps(dict(counts=stage["counts"], invalid=disclosure["validity"]["invalid"],
                             last_offset_seconds=stage["schedule"]["last_offset_seconds"], output_sha256=shas)), flush=True)


if __name__ == "__main__":
    main()

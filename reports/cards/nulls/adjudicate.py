#!/usr/bin/env python3
"""Three-way, per-observable adjudication. Missing/ambiguous evidence never passes.

Input: {scenario_id, script_sha256, native_version, arm, provenance, observables}.
Each observable is {value, classification, evidence, ...}; classification is
stat, mechanics, dependent, stochastic, or ordering. Only direct stat values
can receive STAT_DIFFERENCE_EXPECTED; HP-dependent outcomes cannot.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from scenarios import VERSION

ALIASES = {"Graveyard_rework_Skeleton": "Skeleton", "GoblinCurseGoblin": "Goblin"}
STAT_FIELDS = {"max_hp", "shield_capacity", "configured_damage", "configured_speed",
               "hit_speed_ms", "load_time_ms", "configured_lifetime_ms", "radius", "duration_ms"}
KINDS = {"stat", "mechanics", "dependent", "stochastic", "ordering"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def equal(a, b, tolerance=0, multiset=False):
    if multiset:
        if not isinstance(a, list) or not isinstance(b, list):
            raise ValueError("multiset observable requires lists")
        return Counter(canonical(x) for x in a) == Counter(canonical(x) for x in b)
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isfinite(a) and math.isfinite(b) and abs(a - b) <= tolerance
    return canonical(a) == canonical(b)


def adjudicate(arms):
    if set(arms) != {"native", "ours", "rsim"}:
        raise ValueError("all three distinct arms required")
    base = arms["native"]
    if base.get("native_version") != VERSION:
        raise ValueError("wrong/missing native client or content version")
    for name, arm in arms.items():
        if arm.get("arm") != name or not arm.get("provenance"):
            raise ValueError(f"{name}: missing arm identity/provenance")
        for key in ("scenario_id", "script_sha256", "replay_sha256", "native_version"):
            if not base.get(key) or arm.get(key) != base[key]:
                raise ValueError(f"{name}: mismatched/missing {key}")
    keys = set().union(*(a["observables"] for a in arms.values()))
    rows = []
    for key in sorted(keys):
        metrics = {name: a["observables"].get(key) for name, a in arms.items()}
        row = {"observable": key, "values": {name: m.get("value") if m else None for name, m in metrics.items()}}
        if any(m is None or m.get("available", True) is False or "value" not in m
               or not m.get("evidence") for m in metrics.values()):
            rows.append(dict(row, verdict="MISSING_EVIDENCE"))
            continue
        contract = lambda m: (m.get("classification"), m.get("field"), m.get("unit"),
                              m.get("tolerance", 0), m.get("multiset", False))
        if len({contract(m) for m in metrics.values()}) != 1:
            rows.append(dict(row, verdict="OBSERVABLE_CONTRACT_MISMATCH"))
            continue
        m = metrics["native"]
        kind, field, unit, tolerance, multiset = contract(m)
        if kind not in KINDS or not isinstance(tolerance, (int, float)) or tolerance < 0 or not math.isfinite(tolerance):
            raise ValueError(f"invalid observable contract: {key}")
        if kind == "stat" and field not in STAT_FIELDS:
            raise ValueError(f"{key}: {field} is not a direct stat; use dependent or mechanics")
        # Null is an observed 'did not occur' only with available=true and evidence.
        values = row["values"]
        pairs = {"native_ours": equal(values["native"], values["ours"], tolerance, multiset),
                 "native_rsim": equal(values["native"], values["rsim"], tolerance, multiset),
                 "ours_rsim": equal(values["ours"], values["rsim"], tolerance, multiset)}
        row.update(classification=kind, agreement=pairs, unit=unit,
                   evidence={name: metrics[name]["evidence"] for name in arms})
        if all(pairs.values()):
            verdict = "AGREE"
        elif kind == "stat":
            verdict = "STAT_DIFFERENCE_EXPECTED"
        elif kind == "dependent":
            verdict = "STAT_CONFOUNDED_REQUIRES_CONTROL"
        elif kind == "stochastic":
            verdict = "RNG_DISTRIBUTION_REQUIRES_REPEATS"
        elif kind == "ordering":
            verdict = "ORDERING_DIFFERENCE"  # use multiset=true for wave semantics
        elif pairs["native_ours"]:
            verdict = "MECHANICS_SUPPORTS_OURS"
        elif pairs["native_rsim"]:
            verdict = "MECHANICS_SUPPORTS_ROYALESIM"
        else:
            verdict = "MECHANICS_NEITHER_MATCHES_NATIVE"
        row["verdict"] = verdict
        rows.append(row)
    return {"schema": "cards.nulls.adjudication.v1", "native_version": VERSION,
            "scenario_id": base["scenario_id"], "script_sha256": base["script_sha256"],
            "replay_sha256": base["replay_sha256"], "observables": rows,
            "counts": dict(Counter(r["verdict"] for r in rows)),
            "scope": "exploration; native 15.535 mechanics evidence, no live-16.402 stat authority"}


def derive(trace, metadata, arm, provenance):
    """Conservative common observables; add focused rich measurements separately.

    Object IDs never match across engines. Group by side/root/body, and compare
    whole-wave records as multisets. Every causal combat outcome defaults to
    dependent; a reviewer must supply a control before promoting it to mechanics.
    """
    units, losses = {}, []
    last_tick = None
    with gzip.open(trace, "rt") as stream:
        for line in stream:
            frame = json.loads(line)
            tick = frame["tick"]
            if last_tick is not None and tick != last_tick + 1:
                raise ValueError("one-tick trace required")
            last_tick = tick
            for o in frame["objects"]:
                if o.get("hp") is None or o["hp"] <= 0:
                    continue
                group = f"{o['owner']}/{o['card_id']}/{ALIASES.get(o['body_name'], o['body_name'])}"
                uid = o["native_id"]
                if uid not in units:
                    units[uid] = {"group": group, "birth": tick, "position": [o["x"], o["y"]],
                                  "last": tick, "hp": o["hp"], "max_hp": o.get("max_hp"),
                                  "first_move_tick": None, "first_move_delta": None,
                                  "previous_position": [o["x"], o["y"]]}
                u = units[uid]
                if u["last"] != tick and o["hp"] < u["hp"]:
                    losses.append([tick, group, u["hp"] - o["hp"]])
                position = [o["x"], o["y"]]
                if u["first_move_tick"] is None and position != u["previous_position"]:
                    u["first_move_tick"] = tick
                    u["first_move_delta"] = [p - q for p, q in zip(position, u["previous_position"])]
                u.update(last=tick, hp=o["hp"], previous_position=position)
    if last_tick != metadata["scenario"]["script"]["end_tick"]:
        raise ValueError("incomplete trace")
    groups = defaultdict(list)
    for u in units.values():
        groups[u["group"]].append(u)
    obs = {}
    def add(key, value, classification, field, unit, multiset=False, available=True):
        obs[key] = {"value": value, "classification": classification, "field": field, "unit": unit,
                    "multiset": multiset, "tolerance": 0, "available": available,
                    "evidence": f"{trace.name}:ticks {metadata['scenario']['script']['start_tick']}..{last_tick}"}
    for group, rows in groups.items():
        # Birth count/timing can change after combat, and cannot automatically be
        # attributed to a mechanic when an older version kills the parent sooner.
        add(group + ".births", [u["birth"] for u in rows], "dependent", "birth_ticks", "ticks", True)
        add(group + ".max_hp", sorted({u["max_hp"] for u in rows if u["max_hp"] is not None}), "stat", "max_hp", "hp", True,
            all(u["max_hp"] is not None for u in rows))
        records = [{"birth": u["birth"], "birth_position": u["position"],
                    "death": u["last"] + 1 if u["last"] < last_tick else None,
                    "first_move_tick": u["first_move_tick"], "first_move_delta": u["first_move_delta"]}
                   for u in rows]
        add(group + ".life_multiset", records, "dependent", "life_records", "ticks/native_units", True)
    add("all.hp_losses", losses, "dependent", "capped_unattributed_hp_loss", "ticks/hp", True)
    return {"schema": "cards.nulls.measurements.v1", "arm": arm, "native_version": VERSION,
            "scenario_id": metadata["scenario"]["id"], "script_sha256": metadata["scenario"]["script_sha256"],
            "replay_sha256": metadata["replay_sha256"], "provenance": provenance, "observables": obs}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--native", type=Path, required=True)
    p.add_argument("--ours", type=Path, required=True)
    p.add_argument("--rsim", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = adjudicate({name: json.loads(getattr(a, name).read_text()) for name in ("native", "ours", "rsim")})
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(json.dumps(result["counts"], sort_keys=True))


if __name__ == "__main__":
    main()

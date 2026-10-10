#!/usr/bin/env python3
"""Prepare reviewable inputs; this script grants no freeze/adoption authority.

The historical golden125 fixture can ONLY prepare a Linux dry run. Registered
Mac sets/reference receipts are supplied by the corpus owner after review.
"""
import argparse
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import pickle
import shutil
import time
import traceback

from receipts import TIERS, canonical, quantiles, sha
from tier_backend import (CALIBRATION_SHA, NATIVE_SHA, STUDENT_SHA, THRESHOLD,
                          V1_SHA, TierBackend, setup_imports)


def write(path, value):
    with Path(path).open("x") as stream:
        stream.write(canonical(value) + "\n")


def copy_file(source, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copyfile(source, destination)


def runtime_pins(root):
    # Seal every Python source, plus every file the inherited official runtime
    # manifest declares. The latter includes combat, Rust, templates and data.
    source = root / "reports/explore/s1/receipts/runtime-pin-r2.json"
    if not source.is_file():
        source = root / "reports/explore/s1/receipts/runtime-pin.json"
    names = set(json.loads(source.read_text())["files"])
    names.update(str(p.relative_to(root)) for p in root.rglob("*.py"))
    missing = [name for name in names if not (root / name).is_file()]
    if missing:
        raise ValueError("Incomplete frozen runtime: " + repr(missing[:8]))
    result = {name: sha(root / name) for name in sorted(names)}
    qualified = json.loads((root / "reports/explore/s1/receipts/qualified-source-binding.json").read_text())
    for name, expected in qualified["qualified_source_files"].items():
        if result[name] != expected:
            raise ValueError("Not the qualified S1 tier source: " + name)
    return result


def stage_load(config_path, out):
    """Copy explicit offline replay files; no discovery, client or networking."""
    config = json.loads(Path(config_path).read_text())
    if config["kind"] not in ("v3-body-hud-only", "v4") or config["target_fps"] != 20:
        raise ValueError("Use the qualified TRAIN replay perception ABI at 20 FPS")
    if any(k in config["config"] for k in ("port", "discovery", "endpoint", "url", "grpc", "events")):
        raise ValueError("Only body/HUD offline perception or selected V4 allowed")
    for key in ("body", "hud", "geometry", "checkpoint"):
        if key in config["config"]:
            source = Path(config["config"][key])
            target = Path("load") / (key + source.suffix)
            copy_file(source, out / target)
            config["config"][key] = str(target)
    for key in ("owner_launcher", "selection", "split"):
        if key in config:
            source = Path(config[key])
            target = Path("load") / (key + source.suffix)
            copy_file(source, out / target)
            config[key] = str(target)
    matches = []
    split = json.loads((out / config["split"]).read_text())
    members = {row["seed"]: row for row in split["matches"]}
    for index, path in enumerate(config["matches"]):
        source = Path(path)
        receipt = json.loads((source / "receipt.json").read_text())
        if receipt.get("split") != "train" or members.get(receipt["seed"], {}).get("split") != "train":
            raise ValueError("Load source is not TRAIN")
        target = Path("load") / ("match-" + str(index))
        for name in ("receipt.json", "frames.jsonl", "video.mp4"):
            copy_file(source / name, out / target / name)
        matches.append(str(target))
    config["matches"] = matches
    config["label"] = "PROVISIONAL-LOAD" if config["kind"] == "v3-body-hud-only" else "QUALIFIED-V4-LOAD"
    return config


def prepare(args):
    if args.linux_dry_run:
        from measure_tiers import admit_platform
        admit_platform(True, False)
        if sha(args.native) != NATIVE_SHA:
            raise ValueError("Wrong Linux provenance native")
    out, root = args.output.resolve(), args.runtime_root.resolve()
    out.mkdir(parents=True, exist_ok=False)
    for source, name, expected in ((args.student, "R3a.pt", STUDENT_SHA),
                                  (args.v1, "v1.pt", V1_SHA),
                                  (args.calibration, "R3a-calibration.json", CALIBRATION_SHA)):
        if sha(source) != expected:
            raise ValueError("Wrong policy artifact: " + name)
        copy_file(source, out / name)
    load = stage_load(args.load_config, out)
    copy_file(args.states, out / "states.pkl")
    manifest = dict(schema="clasher.e4v3.inputs.v1", final=False, threshold=THRESHOLD,
        profile="linux-dry-run" if args.linux_dry_run else "mac-preregistered", load=load,
        runtime_files=runtime_pins(root),
        measurement_files={p.name: sha(p) for p in sorted(Path(__file__).parent.iterdir()) if p.suffix in (".py", ".sh") or p.name == "spec-pins.json"},
        specification=json.loads((Path(__file__).parent / "spec-pins.json").read_text()),
        topology=json.loads(args.topology.read_text()))
    if args.linux_dry_run:
        if not args.search_cpus or not args.background_cpus or args.load_cpu is None:
            raise ValueError("Dry reference preparation requires explicit isolated CPU groups")
        os.sched_setaffinity(0, set(args.search_cpus))
        manifest["files"] = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}
        # Temporarily write only the bootstrap identity needed by TierBackend.
        # It is renamed, never overwritten, before the final manifest is made.
        write(out / "tiers-pins.json", manifest)
        backend = TierBackend(out, root, args.native)
        backend.search_cpus = args.search_cpus
        try:
            rows = backend.rows
            if len(rows) != 125:
                raise ValueError("Dry run expects the historical golden125 corpus")
            original = [r for r in json.loads(args.golden.read_text())
                        if r["variant"] == "screen8" and r["repeat"] == 0]
            by_id = {str(r["id"]): {k: r[k] for k in ("action", "candidates", "scores")} for r in original}
            ids = [str(row["id"]) for row in rows]
            selected = [ids[index] for index in backend.np.linspace(0, len(ids)-1, 32, dtype=int)]
            manifest["sets"] = dict(golden=ids, agreement=selected, packets=selected,
                                    speed={tier: selected for tier in TIERS})
            manifest["packet_schedule"] = [dict(id=identity_, offset_seconds=index*.5, opportunity=True,
                cadence="synthetic dry-run 2Hz scheduling of fixed historical TRAIN fixtures")
                for index, identity_ in enumerate(selected)]
            write(out / "golden.json", by_id)
            belief_refs = {}
            for index, row in enumerate(rows):
                belief_refs[str(row["id"])] = backend.belief_result(row, False, frozen=True)
                if (index+1) % 25 == 0:
                    print(f"Linux belief reference: {index+1}/125", flush=True)
            write(out / "belief-reference.json", belief_refs)
            student_refs = {}
            for identity_ in selected:
                student_refs[identity_], _ = backend.infer(identity_, "cpu")
            write(out / "student-reference.json", student_refs)
            refs = {tier: {} for tier in TIERS}
            raw = []
            deadline_refs = {tier: {"1.0": [], "0.8": []} for tier in TIERS}
            from replay_load import LinuxBackground
            with LinuxBackground(out, root, args.native, out / "reference-perception.jsonl",
                                 args.load_cpu, args.background_cpus, preparing=True) as background:
                for repeat in range(3):
                    for tier in TIERS[repeat % 4:] + TIERS[:repeat % 4]:
                        for identity_ in selected:
                            background.check()
                            result, timing = backend.work(backend.by_id[identity_], tier)
                            if identity_ not in refs[tier]:
                                refs[tier][identity_] = dict(result=result, forward=timing.get("forward"), walls=[])
                            from receipts import assert_exact
                            assert_exact(result, refs[tier][identity_]["result"], "reference repeat")
                            refs[tier][identity_]["walls"].append(timing["wall_seconds"])
                            raw.append(dict(repeat=repeat, tier=tier, id=identity_, wall_seconds=timing["wall_seconds"],
                                cpu_clock_mhz=[float(line.split(":")[1]) for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("cpu MHz")]))
                    print("Loaded fleet reference repeat " + str(repeat+1) + "/3", flush=True)
                for repeat in range(3):
                    for tier in TIERS[repeat % 4:] + TIERS[:repeat % 4]:
                        for cell, budget in (("1.0", .2), ("0.8", .16)):
                            for identity_ in selected:
                                background.check()
                                backend.prepare_work(backend.by_id[identity_])
                                _, timing = backend.work(backend.by_id[identity_], tier, deadline=budget)
                                deadline_refs[tier][cell].append(dict(id=identity_, repeat=repeat, **timing))
                    print("Loaded fleet deadline repeat " + str(repeat+1) + "/3", flush=True)
            for tier in TIERS:
                for reference in refs[tier].values():
                    reference["wall_seconds"] = quantiles(reference.pop("walls"))["p50"]
            write(out / "speed-reference.json", refs)
            write(out / "reference-raw.json", dict(records=raw))
            from receipts import decision_rates
            write(out / "deadline-reference.json", {
                tier: {cell: decision_rates(rows) for cell, rows in cells.items()}
                for tier, cells in deadline_refs.items()})
            write(out / "deadline-reference-raw.json", deadline_refs)
            manifest["fleet_reference"] = dict(host=__import__("platform").node(),
                nice=os.getpriority(os.PRIO_PROCESS, 0), repeats=3,
                physical_cores=sorted(os.sched_getaffinity(0)), native_sha256=sha(args.native),
                scope="same-host Linux calibration; historical golden125; no scientific reporting states",
                reporting_load_profile=False, comparable_dry_run_load=True,
                dry_run_background_cpus=args.background_cpus, dry_run_replay_cpu=args.load_cpu,
                load_kind=load["kind"], reference_generated_separately=True, utc=time.time())
        finally:
            backend.close()
        (out / "tiers-pins.json").rename(out / "bootstrap-manifest.json")
    else:
        # Reviewed production corpus and references are prepared separately. No
        # generated/repeated historical fixture can accidentally meet Mac counts.
        if not args.reference_packet:
            raise ValueError("Mac staging requires reviewed --reference-packet")
        packet = json.loads((args.reference_packet / "registration.json").read_text())
        manifest["sets"] = packet["sets"]
        manifest["packet_schedule"] = packet["packet_schedule"]
        manifest["fleet_reference"] = packet["fleet_reference"]
        manifest["deadline_replay_semantics"] = packet["deadline_replay_semantics"]
        for name in ("golden.json", "belief-reference.json", "student-reference.json", "speed-reference.json", "deadline-reference.json", "registration.json"):
            copy_file(args.reference_packet / name, out / name)
        for source in sorted(args.reference_packet.rglob("*")):
            if source.is_file() and not (out / source.relative_to(args.reference_packet)).exists():
                copy_file(source, out / "reference-source" / source.relative_to(args.reference_packet))
    manifest["files"] = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}
    write(out / "tiers-pins.json", manifest)
    with (out / "tiers-pins.sha256").open("x") as stream:
        stream.write(sha(out / "tiers-pins.json") + "  tiers-pins.json\n")
    print(canonical(dict(manifest_sha256=sha(out / "tiers-pins.json"), final=False,
                         files=len(manifest["files"]), output=str(out))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--states", type=Path, required=True)
    parser.add_argument("--golden", type=Path)
    parser.add_argument("--student", type=Path, required=True)
    parser.add_argument("--v1", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--load-config", type=Path, required=True)
    parser.add_argument("--topology", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--linux-dry-run", action="store_true")
    parser.add_argument("--reference-packet", type=Path)
    parser.add_argument("--search-cpus", type=lambda value: [int(i) for i in value.split(",")])
    parser.add_argument("--background-cpus", type=lambda value: [int(i) for i in value.split(",")])
    parser.add_argument("--load-cpu", type=int)
    args = parser.parse_args()
    try:
        prepare(args)
    except BaseException:
        if args.output.is_dir() and not (args.output / "preparation-failure.json").exists():
            write(args.output / "preparation-failure.json", dict(error=traceback.format_exc(), final=False))
            write(args.output / "preparation-failure-manifest.json", dict(status="failed",
                files={str(p.relative_to(args.output)):sha(p) for p in args.output.rglob("*") if p.is_file()}))
            (args.output / "preparation-failure-manifest.sha256").write_text(
                sha(args.output / "preparation-failure-manifest.json")+"  preparation-failure-manifest.json\n")
        raise


if __name__ == "__main__":
    main()

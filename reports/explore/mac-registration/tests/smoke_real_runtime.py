#!/usr/bin/env python3
"""Real-runtime smoke on 05 (not part of unittest discovery): one setup_imports per interpreter.

Builds a mini Mac-profile fixture (golden125 + 6 published S rows), converts it with the
frozen write_state_rows, then, through the END-A3-verified runtime:
  * main process: io.setup_runtime(bootstrap_runtime=False) + real TierBackend + infer;
  * spawned child: memory_check.child (setup_runtime + real TierBackend + forwards).
Before Sol round-1 finding 1 this raised "cannot set number of interop threads".
Usage: smoke_real_runtime.py <work dir> <output dir>   (nice 19, one core)
"""
import json
import multiprocessing as mp
from pathlib import Path
import pickle
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import macreg_io as io
import memory_check


def build_fixture(args, out):
    io.setup_runtime(args, bootstrap_runtime=True)
    t1 = Path("/mpac/sdicks02/jobs/clasher/t1-20261010-r1")
    with (t1 / "end-bundle-preparation-r1/golden-states.pkl").open("rb") as stream:
        golden = pickle.load(stream)
    with (t1 / "corpus-publication-staging-r1/S-states.pkl").open("rb") as stream:
        speed = pickle.load(stream)[:6]
    rows = golden + speed
    (out / "fixture").mkdir()
    (out / "fixture/states.pkl").write_bytes(pickle.dumps(rows, protocol=5))
    from convert_states import write_state_rows
    states_sha = io.file_sha(out / "fixture/states.pkl")
    write_state_rows(rows, out / "fixture", states_sha, (out / "fixture/states.pkl").stat().st_size, source_verified=True)
    (out / "fixture/ids.json").write_text(json.dumps(dict(golden=[str(r["id"]) for r in golden], speed=[str(r["id"]) for r in speed])))


def main():
    work, out = Path(sys.argv[1]), Path(sys.argv[2])
    io.require_low_priority()
    out.mkdir(parents=True)
    rt = work / "runtime-a3"
    args = SimpleNamespace(runtime_root=rt, native=Path("/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1/native/clasher_core.abi3.so"),
                           end_manifest=work / "END-A3-manifest-01-f6cebbaa.json", e4v3=None,
                           extra_path=[rt / "imitation/evaluation/runtime_dependencies", rt / "reports/strategy_council_20260928/imitation"])
    builder = mp.get_context("spawn").Process(target=build_fixture, args=(args, out))  # unpickling needs a bootstrap
    builder.start()
    builder.join()
    if builder.exitcode != 0:
        raise SystemExit("fixture builder failed")
    pins, runtime = io.setup_runtime(args, bootstrap_runtime=False)
    meta = json.loads((out / "fixture/ids.json").read_text())
    golden, ids = meta["golden"], meta["speed"]
    sets = dict(golden=golden, speed={t: [] for t in io.TIERS}, agreement=ids, packets=ids)
    final = Path("/mpac/sdicks02/jobs/clasher/e4v3-bundle-05-final")
    io.work_bundle(out / "bundle", out / "fixture/states.pkl", out / "fixture", sets, final / "v1.pt", final / "R3a.pt")
    from tier_backend import TierBackend
    backend = TierBackend(out / "bundle", rt, args.native)
    try:
        io.check_e4v3_modules()
        refs = {i: backend.infer(i, "cpu")[0] for i in ids}
        threads = (backend.torch.get_num_threads(), backend.torch.get_num_interop_threads())
    finally:
        backend.close()
    worker = mp.get_context("spawn").Process(target=memory_check.child, args=(args, out / "bundle", ids, out / "child.json"))
    worker.start()
    worker.join()
    child = json.loads((out / "child.json").read_text()) if worker.exitcode == 0 else None
    result = dict(schema="clasher.tiers-a4.real-runtime-smoke.v1", utc=io.utc(), **io.process_identity(),
                  versions=io.runtime_versions(), runtime=runtime, main_infer=len(refs), torch_threads=threads,
                  child_exitcode=worker.exitcode, child=child, passes=worker.exitcode == 0 and child["forwards"] == len(ids) + 1
                  and len(refs) == len(ids), outcomes_read=False, timing=False)
    io.write_json(out / "real-runtime-smoke.json", result)
    print(json.dumps({k: result[k] for k in ("passes", "main_infer", "torch_threads", "child_exitcode")}))
    sys.exit(0 if result["passes"] else 1)


if __name__ == "__main__":
    main()

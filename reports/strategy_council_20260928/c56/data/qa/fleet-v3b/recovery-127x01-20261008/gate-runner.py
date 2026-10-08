"""Recovered-hub C56 verification; leaves original extractor/runtime unchanged."""
from __future__ import annotations
import concurrent.futures
import json
import multiprocessing
import os
from pathlib import Path
import resource
import shutil
import socket
import sys
import time
import traceback
import zipfile
import numpy as np
import fleet_v3b as f

HISTORICAL_Q = f.Q
f.Q = HISTORICAL_Q / "recovery-127x01-20261008"
Q = f.Q
EXPECTED_EXTRACTOR = "8e95786c1dede45e9fd8d02f8c85cd86331667d3dbc5c8a6713808f0520ac9c7"


def usage():
    a = resource.getrusage(resource.RUSAGE_SELF)
    b = resource.getrusage(resource.RUSAGE_CHILDREN)
    return a.ru_utime + a.ru_stime + b.ru_utime + b.ru_stime


def verify():
    result = f.verify_base()
    assert result["files"] == 1622 and result["inputs"] == 454
    assert f.cb.file_sha256(Path(f.ex.__file__)) == EXPECTED_EXTRACTOR
    base = f.read(Q / "mac-base.json")
    actual = {str(p.relative_to(f.cb.DATA)) for p in f.OUT.glob("*/shard-*")
              if p.suffix in {".npz", ".json"}}
    assert actual == set(base["files"]), "Unexpected production inventory"
    result.update(runtime=f.cb.runtime_manifest(), extractor_sha256=EXPECTED_EXTRACTOR,
                  replaces="Historical 127x02 integrity verification; independently rerun on 127x01",
                  production_inventory_exact=True)
    f.write(Q / "reverification.json", result)
    return result


def audit():
    base = f.gate()
    keys = sorted(str(Path(n).relative_to("recon/engine-v3")).removesuffix(".json")
                  for n in base["files"] if n.endswith(".json"))
    rows = perspectives = 0
    with concurrent.futures.ProcessPoolExecutor(
            8, mp_context=multiprocessing.get_context("spawn")) as pool:
        for i, result in enumerate(pool.map(f.audit_one, keys), 1):
            assert not result["errors"] and result["illegal"] == 0
            rows += result["rows"]
            perspectives += len(result["summaries"])
            if i % 100 == 0:
                print(json.dumps({"base_units_validated": i, "rows": rows}), flush=True)
    assert (len(keys), perspectives, rows) == (811, 38134, 30483676)
    return dict(units=len(keys), perspectives=perspectives, rows=rows, errors=0,
                illegal_labels=0, cache_directory=str(Q / "unit-audits"),
                replaces="Historical 127x02 base audit; fresh cache and validators on 127x01")


def roundtrip():
    target = Q / "serialization-roundtrip"
    target.mkdir(exist_ok=True)
    results = []
    for key in f.read(Q / "mac-base.json")["equivalence_units"]:
        src = f.OUT / (key + ".npz")
        dst = target / (key.replace("/", "-") + ".npz")
        assert not dst.exists(), dst
        with np.load(src, allow_pickle=False) as arrays:
            f.ex.v5.save_npz_deterministic(dst, {name: arrays[name] for name in arrays.files})
        original = f.cb.file_sha256(src)
        actual = f.cb.file_sha256(dst)
        results.append(dict(unit=key, original_sha256=original, roundtrip_sha256=actual,
                            byte_identical=original == actual))
    result = dict(units=results, all_byte_identical=all(r["byte_identical"] for r in results),
                  python=sys.version, numpy=np.__version__,
                  zlib_compile=f.zlib.ZLIB_VERSION, zlib_runtime=f.zlib.ZLIB_RUNTIME_VERSION)
    f.write(Q / "serialization-roundtrip.json", result)
    assert result["all_byte_identical"], result
    return result


def compare_one(key):
    # Prior run_unit removes old v2 NPZs. These three selected units have none.
    assert not (f.cb.DATA / "recon/engine-v2b" / (key + ".npz")).exists()
    assert not (Q / "equivalence-replay" / (key + ".json")).exists(), "Fresh replay required"
    try:
        result = f.equivalence_one(key)
    except Exception:
        result = dict(unit=key, comparison_error=traceback.format_exc())
    original = f.OUT / (key + ".npz")
    fresh = Q / "equivalence-replay" / (key + ".npz")
    result.update(unit=key, original_sha256=f.cb.file_sha256(original),
                  raw_replay_sha256=f.cb.file_sha256(fresh) if fresh.exists() else None)
    result["raw_byte_identical"] = result["original_sha256"] == result["raw_replay_sha256"]
    f.write(Q / ("strict-equivalence-" + key.replace("/", "-") + ".json"), result)
    return result


def equivalence():
    keys = f.read(Q / "mac-base.json")["equivalence_units"]
    assert keys == [f"s117/shard-011-part-{n:02d}" for n in (4, 5, 6)]
    with concurrent.futures.ProcessPoolExecutor(
            3, mp_context=multiprocessing.get_context("spawn"), initializer=f.initialize) as pool:
        results = list(pool.map(compare_one, keys))
    passed = all(r["raw_byte_identical"] and not r.get("comparison_error") for r in results)
    result = dict(complete=passed, gate="Raw NPZ archive SHA256 equality; normalization does not qualify",
                  units=results, extraction_authorized_by_gate=passed)
    f.write(Q / "strict-equivalence.json", result)
    assert passed, "Fresh Linux replay is not byte-identical; production extraction must stop"
    return result


def main():
    assert socket.gethostname() == "127x01"
    assert Path("/mpac/sdicks02/jobs/clasher/hub-ready.json").is_file()
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    assert all(os.environ.get(k) == "1" for k in
               ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"))
    assert shutil.disk_usage(f.cb.DATA).free >= 12 * 2**30
    assert f.ex.disk_bytes() < 7.375 * 2**30
    Q.mkdir(exist_ok=True)
    manifest = Q / "mac-base.json"
    if not manifest.exists():
        with manifest.open("xb") as stream:
            stream.write((HISTORICAL_Q / "mac-base.json").read_bytes())
    assert manifest.read_bytes() == (HISTORICAL_Q / "mac-base.json").read_bytes()
    for name, job in (("verify", verify), ("base-audit", audit),
                      ("roundtrip", roundtrip), ("equivalence", equivalence)):
        start = time.monotonic()
        cpu = usage()
        try:
            result = job()
            record = dict(passed=True, result=result)
        except Exception:
            record = dict(passed=False, error=traceback.format_exc())
        record.update(utc=f.ex.utc(), host=socket.gethostname(),
                      wall_seconds=time.monotonic() - start, cpu_seconds=usage() - cpu)
        f.write(Q / (name + "-receipt.json"), record)
        print(json.dumps(record), flush=True)
        assert record["passed"], record.get("error")
    f.write(Q / "gates-complete.json", dict(utc=f.ex.utc(), complete=True))


if __name__ == "__main__":
    main()


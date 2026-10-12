#!/usr/bin/env python3
"""Regenerate PREREG-SEARCH-TIERS-AMENDMENT-4-20261011.json from the note, sources and test logs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
V4 = "reports/strategy_council_20260928/live-loop/v4"
SOURCES = ("selection.py", "macreg_io.py", "build_sets.py", "assemble_states.py", "student_reference.py",
           "memory_check.py", "seal_receipt.py", "stage_nocopy.py", "fetch_captures.sh", "verify_captures.py",
           "make_amendment_record.py", "run_tests.sh", "run_phase3.sh", "build_runtime.sh",
           "tests/smoke_real_runtime.py", "tests/test_selection.py", "tests/test_pipeline.py",
           "tests/test_stage_nocopy.py", "tests/test_verify_captures.py", "tests/test_runtime_binding.py")


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def committed_sha(path, ref="origin/main"):
    """Frozen records are hashed as committed (the shared checkout may lag origin/main)."""
    return hashlib.sha256(subprocess.check_output(["git", "-C", str(ROOT), "show", ref + ":" + path])).hexdigest()


def main():
    target = ROOT / V4 / "PREREG-SEARCH-TIERS-AMENDMENT-4-20261011.json"
    previous = json.loads(target.read_text()) if target.exists() else {}
    review = json.loads(sys.argv[1]) if len(sys.argv) > 1 else previous.get("independent_review", dict(final_verdict="PENDING", rounds=[]))
    errata = json.loads((HERE / "errata.json").read_text()) if (HERE / "errata.json").exists() else []
    tests = json.loads((HERE / "receipts/unit-tests.json").read_text())
    record = dict(
        schema="clasher.tiers.amendment4-candidate.v1", study="PREREG-SEARCH-TIERS",
        title="Outcome-blind Mac registration inputs: agreement2000 + packets1000 selection, cadence and fixture",
        status="ADOPTED (COORDINATOR 16d431b4; commit 94df513d)", coordinator_thread="0523ae6f-baa3-4d4e-b233-b392671670db",
        role="Mac registration inputs builder; T1 corpus-owner delegate; T1 keeps merge and seal authority",
        prepared_host="127x05",
        note=dict(path=V4 + "/PREREG-SEARCH-TIERS-AMENDMENT-4-20261011.md", sha256=sha(V4 + "/PREREG-SEARCH-TIERS-AMENDMENT-4-20261011.md")),
        design_proposal=dict(path=V4 + "/MAC-REGISTRATION-INPUTS-PROPOSAL-20261011.md", commits=["59396fb0", "2cab69f0"],
                             sha256=committed_sha(V4 + "/MAC-REGISTRATION-INPUTS-PROPOSAL-20261011.md")),
        coordinator_rulings=["22:26Z rules B.1-B.7 adopted as written; overlapping minimal fixture approved; P1 cadence",
                             "22:31Z no-copy Mac staging added to the A4 builder's scope; scope message with constraints sent 22:30:53Z",
                             "23:04Z (COORDINATOR 684195b3, recorded 23:04:25Z) stage_nocopy.py APPROVED as an external operational staging helper inside A4 under six conditions"],
        original_freeze=dict(path=V4 + "/PREREG-SEARCH-TIERS-FREEZE-20261010.json", sha256=committed_sha(V4 + "/PREREG-SEARCH-TIERS-FREEZE-20261010.json"), unchanged=True),
        amendments_unchanged={n: committed_sha(V4 + "/" + n) for n in ("PREREG-SEARCH-TIERS-AMENDMENT-1-20261010.md",
                              "PREREG-SEARCH-TIERS-AMENDMENT-2-20261011.json", "PREREG-SEARCH-TIERS-AMENDMENT-3-20261011.json")},
        changes_none_of=["hypothesis", "arm", "seed", "tier", "gate", "threshold", "reducer", "slots", "budgets",
                         "warmup", "op6_guard", "memory_floor", "a3p_check", "outcome_handling"],
        e4v3_files_changed=False,
        e4v3_pins=dict(json.loads((HERE / "receipts/e4v3-pins.json").read_text())),
        rules=dict(
            b1=dict(pool="32 SHA-verified T1 captures, seeds 4503603407370496+[3,11), a51ea64c", corpora_sha256="3501e2acf444c2f23a5ed9f9471ebcabfc66216b412847c033759c3f4b2cde13",
                    validity="corpus_contract.validate_row(row, tier)", invalid_stop_fraction=.01,
                    lineage="1,200 speed canonical digests equal committed END digests (c09142b9); per-tier counts/health equal corpora.json",
                    speed_rows_from="published 282b0877"),
            b2=dict(game_key="(tier, seed)", game_priority="sha256('tiers-packets/{tier}/{seed}') ascending",
                    interleave="round-robin by rank in TIERS order", rows="valid rows ascending info.tick", packets=1000, truncation="last game at exactly 1000"),
            b3=dict(cadence="P1", tick_seconds=.05, join_ticks=10, timestamp="(tick + O_k) * 0.05; O_0=-f_0; O_{k+1}=O_k+l_k+10-f_{k+1}",
                    offset="timestamp - schedule[0].timestamp", opportunity=True, disclosed_session_hours=[6, 6.5]),
            b4=dict(agreement="speed1200 | packets | F; |F| = max(0, 2000 - |speed | packets|)", fill_allocation="corpus.quotas over fill-pool tier counts",
                    fill_priority="sha256('tiers-agreement/{tier}/{seed}/{tick}') ascending, ties by id", order="(TIERS index, seed, tick)",
                    uncovered_case="0 < |F| < occupied tiers: stop and escalate (no new rule)"),
            b5=dict(order="public 1200 (END) + golden125 (END) + extra by (TIERS index, seed, tick)", end_prefix_fingerprint="c09142b97ecc147efa635036a69508e16fe647347749e052d321048910040901",
                    identity="ordered canonical fingerprint", conversion="convert_states.py --states --expect-fingerprint on 05"),
            b6=dict(host="127x05", profile="mac-preregistered offline bundle", torch_threads=1,
                    gate="300 S speed ids: legal equal, receipts.agreement equal, |gate|,|logit| deltas <= 1e-4 vs pooled END S forwards",
                    fallback="recompute on 01 after its END pool"),
            b7=dict(receipt="mac-sets-selection.json", merger="T1", seal="T1-REGISTRATION")),
        mac_staging=dict(status="APPROVED by coordinator ruling issued 23:04Z 2026-10-11, recorded in COORDINATOR 684195b3 at 23:04:25Z (entry '23:04 UTC'; git commit time 23:04:29Z), answering Sol r2 finding 8",
                         ruling_conditions=["outside e4v3 and runtime root; SHA-pinned in A4; verify e4v3 measurement_files == END-A3 18 entries; import frozen prepare_bundle unchanged; override copy_file only for states.pkl/states-rows.json/states-rows.bin",
                                            "placement: clonefile -> hard link -> data copy only if >= 10 GiB free after; SHA-verify each, fail closed",
                                            "after placement chmod a-w on source and bundle copies of the three files; record in receipt",
                                            "keep the byte-identical tiers-pins.json test (real frozen prepare_bundle, with vs without helper) in A4 evidence",
                                            "immediately before the Mac session re-verify the three SHAs in the staged bundle (stage_nocopy.py --verify-bundle); session receipt records helper use, method per file and SHAs",
                                            "no re-pins only while nothing frozen changes; if anything does, stop"],
                         session_verify="stage_nocopy.py --verify-bundle <bundle>",
                         helper="reports/explore/mac-registration/stage_nocopy.py",
                         reason="prepare_bundle.py a1c59fa3 is in measurement_files (END-A3 01/08, fleet_pool binding) and refuses pre-placed files",
                         design="import the unmodified frozen prepare_bundle; substitute module copy_file for states.pkl/states-rows.json/states-rows.bin only",
                         placement=["apfs clonefile (macOS)", "hard link", "data copy only if >= 10 GiB free after"],
                         verification="SHA-256 of each placed file equals its source; fail closed",
                         evidence="synthetic 05: frozen prepare_bundle Mac mode, tiers-pins.json byte-identical plain vs helper",
                         peak_disk="about one fixture copy (~36 GiB) instead of ~72 GiB"),
        re_pins_required=[],
        re_pin_analysis={"e4v3 / measurement_files / END-A3 manifests": "unchanged", "runtime_files": "unchanged (helper outside runtime root, enforced)",
                         "TIERS freeze 47aba25e and A1-A3": "unchanged (A3 records prepare_bundle after-SHA a1c59fa3; bytes unchanged)", "K4S Mac manifest c1fb1e9a": "unchanged (prepare_bundle never K4S-pinned)",
                         "FROZEN-K4S 416f6e51": "unchanged (no fleet file changes)"},
        memory_check=dict(cap_bytes=6 * 2**30, rule="main VmHWM + two sequential D6 child VmHWM, each 2,000 retained inputs, Mac profile on 05"),
        source_files={p: sha("reports/explore/mac-registration/" + p) for p in SOURCES},
        tests=tests, independent_review=review, errata=errata,
        runtime_binding=json.loads((HERE / "receipts/runtime-a3-binding.json").read_text()),
        runtime_binding_a5=json.loads((HERE / "receipts/runtime-a5-binding.json").read_text()),
        real_runtime_smoke={k: v for k, v in json.loads((HERE / "receipts/real-runtime-smoke.json").read_text()).items()
                            if k in ("passes", "main_infer", "torch_threads", "child_exitcode", "versions", "utc")},
        outcome_blind=True, outcomes_read=False, games_read=False, timing_runs=False, mac_access=False,
        ssh_to_01_03_04_08=False)
    target.write_text(json.dumps(record, sort_keys=True, indent=1) + "\n")
    print(sha(V4 + "/PREREG-SEARCH-TIERS-AMENDMENT-4-20261011.json"))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Regenerate K4S-MAC-MANIFEST.json (SHA-256 of every K4S Mac file and every reused file).

    python3 build_manifest.py                       # draft: kernel/SD1 pins may be unfilled
    python3 build_manifest.py --kernel REL --kernel REL --freeze   # at the K4S freeze

--freeze refuses unless the SD1 manifest exists and the K4S kernel files are named; it
records their SHA-256 and sets frozen=true. The manifest's own SHA-256 is what the
operator passes to measure_k4s.py as --k4s-manifest-sha256.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import k4s_logic as L  # noqa: E402

K4S_FILES = ("measure_k4s.py", "k4s_logic.py", "k4s_backend.py", "classify_k4s_failure.py",
             "build_manifest.py", "K4S-MAC-PROCEDURE.md", "test_measure_k4s.py")
E4V3_REUSED = ("measure_tiers.py", "receipts.py", "tier_backend.py", "replay_load.py", "telemetry.py",
               "classify_failure.py", "corpus_contract.py", "spec-pins.json",
               # frozen fleet helpers reused read-only by the K4S END producer/pooler
               "fleet_end.py", "fleet_profile.py", "fleet_validity.py", "fleet_pool.py", "fleet_reference.py",
               # TIERS Amendment 3: TierBackend.__init__ imports state_rows (K4S Amendment 2)
               "state_rows.py")
END_FILES = ("reports/explore/k4s-confirm/end_reference.py", "reports/explore/k4s-confirm/end_pool.py",
             "reports/explore/k4s-confirm/end_background.py", "reports/explore/k4s-confirm/end_evidence.py")
RUNTIME_REUSED = (L.TIERS_SCORER_REL, L.TIERS_SCORER_BASE_REL, "reports/explore/s1/cached_policy.py",
                  "reports/explore/s1/gc_window.py")
REFERENCES = {
    "prereg": "reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md",
    "conformance_r2": "reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-CONFORMANCE-r2.md",
    "recheck_r3": "reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-RECHECK-r3.md",
    "tiers_prereg_r3": "reports/strategy_council_20260928/live-loop/v4/PREREG-SEARCH-TIERS-r3-DRAFT.md",
    "tiers_addendum_r3": L.TIERS_PACKAGE_REL + "/E4-V3-ADDENDUM-r3-DRAFT.md",
    "k4s_spec": "reports/explore/k4s-confirm/K4S-SPEC.md",
    "t1_corpus_inventory": "reports/explore/t1/corpora/corpus-03-a51ea64c/corpora.json",
    "t1_corpus_publication": "reports/explore/t1/corpora/corpus-03-a51ea64c/publication.json",
}
SD1_MANIFEST_REL = "reports/explore/k4s-confirm/SD1-MANIFEST.json"
KERNEL_CANDIDATES = ("reports/explore/k4s-confirm/anchor_x.py", "reports/explore/x4s2/sdefault.py")


def build(root, kernel=(), freeze=False):
    root = Path(root)

    def pin(rel):
        path = root / rel
        if not path.is_file():
            raise FileNotFoundError(rel)
        return L.sha(path)
    tiers_script = L.E4V3_REL + "/measure_tiers.py"
    sd1_path = root / SD1_MANIFEST_REL
    sd1_sha = L.sha(sd1_path) if sd1_path.is_file() else None
    if freeze and (sd1_sha is None or not kernel):
        raise SystemExit("--freeze needs the committed SD1 manifest and the reviewed K4S kernel files")
    reused = {L.E4V3_REL + "/" + n: pin(L.E4V3_REL + "/" + n) for n in E4V3_REUSED}
    reused.update({rel: pin(rel) for rel in RUNTIME_REUSED})
    return dict(
        schema="clasher.k4s.mac-manifest.v1",
        study="PREREG-K4S", checklist_item="CONFORMANCE-r2 F-8 / N2; RECHECK-r3 R3, R5",
        frozen=bool(freeze), status="FROZEN" if freeze else "DRAFT: independent review pending; not frozen",
        prereg=dict(path=REFERENCES["prereg"], sha256=pin(REFERENCES["prereg"])),
        references={k: dict(path=v, sha256=pin(v)) for k, v in REFERENCES.items()},
        k4s_files={L.MAC_REL + "/" + n: pin(L.MAC_REL + "/" + n) for n in K4S_FILES},
        end_files={rel: pin(rel) for rel in END_FILES},
        reused_readonly=reused,
        measure_tiers_unmodified=dict(
            path=tiers_script, sha256=reused[tiers_script],
            statement="measure_tiers.py, the TIERS manifest/spec-pins and every e4v3 file are reused read-only "
                      "and unmodified; K4S never edits them, never re-hashes the TIERS manifest and never "
                      "writes under any TIERS path."),
        tiers_freeze=dict(prereg_r3_sha256="ef0db97ad509753ccf63c7376f800d6db7f0b82ee07f102476eafb939e2a4c77",
                          freeze_commit="cc6410b2",
                          addendum_r3_sha256="fc54507d5f742f4ef6ecd0b656ee47fdb61d1468a14ff4cb4dd14a94a6311a9b"),
        native=dict(provenance_linux_sha256=L.NATIVE_PROVENANCE_SHA,
                    mac_binding="Mac native = the binary the TIERS session built and qualified "
                                "(TIERS build-tiers.json native_sha256, source_manifest_sha256 = TIERS "
                                "tiers-pins.json SHA); K4S never rebuilds it"),
        scorer_binding=dict(tiers_scorer=L.TIERS_SCORER_REL, tiers_scorer_base=L.TIERS_SCORER_BASE_REL,
                            rule="K4S scorer == TIERS-pinned scorer bytes, or the declared stats-only "
                                 "anchor_x derivative whose two hunks revert to them exactly"),
        k4s_kernel=dict(files={rel: pin(rel) for rel in kernel},
                        candidates={rel: pin(rel) for rel in KERNEL_CANDIDATES if (root / rel).is_file()},
                        interface="planner_class(base) with the full S-default rule (apply_default), "
                                  "K4S-SPEC §4(e)-(f)"),
        sd1_manifest=dict(path=SD1_MANIFEST_REL, sha256=sd1_sha, exists=sd1_sha is not None,
                          note="filled at the K4S freeze (CONFORMANCE-r2 F-2)"),
        corpus=dict(inventory_commit=L.T1_INVENTORY_COMMIT, k4_states_sha256=L.T1_K4_CORPUS_SHA, states=300,
                    inventory=REFERENCES["t1_corpus_inventory"], publication=REFERENCES["t1_corpus_publication"]),
        fleet_reference_schema="clasher.k4s.mac-fleet-reference.v1 (K4S-MAC-PROCEDURE.md §3)",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=L.REPO_ROOT)
    parser.add_argument("--kernel", action="append", default=[])
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--output", type=Path, default=L.MAC_DIR / L.MANIFEST_NAME)
    args = parser.parse_args(argv)
    manifest = build(args.root, args.kernel, args.freeze)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(L.sha(args.output) + "  " + args.output.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# K4S END — integration fix package for Sol (one package)

Prepared 2026-10-13T10:07:12Z by the K4S runner on 127x05. Offline only; no host step since A1/A1b. Code on main at be175723 (fix round) and later runner edits in d7a37dbb / this commit; END evidence line k4s-end-r1 (BR-1) tip 98566c032d0b6ea2ec613ed9a45b0dc2a5df33cb.

## Why this package exists

The individually approved package (Sol full r2, a770a69e) failed at the first real runs one interface at a time (S1 ssh-exit race, fixed in s1s2-r6 and coordinator-checked; E4 vs main; S4 runtime-pin shape). An offline end-to-end integration audit with real inputs and fake hosts (`end-staging/INTEGRATION-AUDIT-r1/REPORT.md` 0d709b5becc8cc99ccffed08ad9532d05979b4461ea29e530aa557ef6deab6f6) found 6 MISMATCH and 12 UNTOOLED rows. This package fixes all of them in one round, plus ruling IR-03 (COORDINATOR aebb0929). Please review it as an integrated chain, not only per component.

## Candidates (relative to reports/explore/k4s-confirm/run-r1/end-prep/)

| Dir | Fixes | SHA256SUMS sha256 | Key file |
|---|---|---|---|
| `b3-r6/` | B1: S4 runtime-pin `files` follows frozen prepare_bundle (dict keys; list accepted; per-file SHAs not checked, as frozen; 17 differ = S9's tracked_pin_sha_differs_from_git); L4 `assembler_sha256` in receipts | `1966ac8bbaa14e0fe36424adb3d6feb8cb2ca7f543b911c473802630f2dc5dfc` | assemble_fleet_reference.py 76b7b7cf4b9a7ebf9cbcaa46a6d6f1baefca36b40148f6f104d5055cafa4dd63 |
| `b3-r7/` | IR-03: 127x03 admissions = system bus only; 03 requests rewritten (`requests-ir03/`) | `1a31b47d27670cb806954449887de768eed4a65dfcb54659df5bd9cb6cd09105` | assemble_fleet_reference.py 2b8f5fb3b79b85103394e18c39330b772fbf2deb28d95fbd01d2d73273d7f016 (**adopted S4**) |
| `s3s9s10-r4/` | B2 (S10 runtime at `<base>/runtime-<P12>`), B3+B5 (S9 exports SD1-MANIFEST, t1 corpora.json, DELTA-MANIFEST as SHA-pinned support members; runtime_files unchanged), B7/U9 (S10 `--declare-roots` = S7 schema), U2 (`--tools-source`: the 6 S7-pinned tools), U3 (`--end-inputs`: native + K4 corpus), U4 (interpreter probe in the existing login), U10 (S9 `refresh-clone`), L4 (S10 pins adopted S4), U1 (new **S11** `s11_host_repository.py`: host `--repository` on k4s-end-r1, provision at P', advance to X; 1 login each), IR-03 (S3 END admission set) | `3978d2a4329ef256a6b8581767e643bffe84e7e69171e6cc81a5626738b35315` | s10 4437467182830d9594e9bd2543db982a456a56e87b459ba335e374cbe3605382; s11 914a622d057ae6204913af798887eedede9b643141c64bfaa7c695fcf8f9658e |
| `s5s6s7-r4/` | U5 (S7 `build-argv`), U6 (`prepare-preflight-receive`), U7 (PREPARE-PROOF), U8 (`k4s_a6_builder.py` END-JOB builder; proven against frozen end_job + S9 equivalence on a scratch clone), L1, L6 (S5 pins DELTA), U12 (ruling-file templates); S7 now also pins host python, evidence path/SHA, SD1, corpus inventory | `d04c6ca16af01028200c5d252da1ef29c463819815b8de434f15b43fc70bf750` | gate e346a71f58c02673356fc4bcf989db2e11f30deaad5ee78523c558e7dd9c6562; preflight c779345116c1bf6c0ab28af8751a36489642c5b9c870326f516361f54bf115f5 |

Unchanged and still pinned: safe-input-r3 (`806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00`), bootstrap-r1 (`99efd8a68a5f786c2bec9df560f2d266a9111593a0726010569baa9d31e683da`), s1s2-r6 (S1 r6 `16cbbf57f9a9b3cd505ff3ef51d207bac81d0f2c32ddc00d04a5e5f4b030deae` coordinator-checked; S2 unchanged).

Each dir has RESPONSE-r<N>.md (row -> fix file:line -> named tests), MUTATION-RESULTS, README, PROGRESS.

## Runner verification (pristine /dev/shm copies with sibling dirs; umask 022; 3.12 k4s-freeze and 3.8)

| Suite | normal 3.12 | -O 3.12 | normal 3.8 | -O 3.8 |
|---|---|---|---|---|
| b3-r6 | 519 + 24 skip + 2 desel | same | same | same |
| b3-r7 | 536 + 27 skip + 2 desel | same | same | same |
| s3s9s10-r4 | 955 | 955 | 955 | 955 |
| s5s6s7-r4 | 726 | 671 + 55 skip (verifier refuses -O) | 726 | 671 + 55 skip |

b3 skips = frozen-consumer tests without a K4S_FROZEN_ROOT export (workers ran them: 543 / 563 all pass); desel = the two real-Q6 tests. Worker mutation: b3-r6 13/13, b3-r7 9/9, s3s9s10-r4 py312 163/169 and py38 68/71 (survivors = documented equivalents), s5s6s7-r4 176/178 (51/51 new).

## Real-input evidence (offline, fake hosts)

- s3s9s10-r4 `REAL-CHAIN-r4.json`, `REAL-CHAIN-r4b.json` (with s5s6s7-r4), `REAL-CHAIN-r4c-IR03.json`: S4 -> S10 staging to a fake host -> S11 provision -> S5 to the frozen identity check (passes with real native/corpus/bundle/runtime; stopped before any model load) -> S7 build-argv + gate -> S9 refresh/equivalence -> S11 advance -> frozen end_job / producer_registry / producer_claim on the advanced repository; IR-03: frozen ReportingGuard accepts the bus-only 03 job and refuses the old shapes.
- Production artifacts rebuilt on 05 with this code (d7a37dbb): S9 runtime manifest 1fa0ebf5… (runtime_files fc3dbeb4 and measurement 42b8986d unchanged; inventory 4316 = +3 support files; verify --frozen OK); 6 bundles (b3-r7; 04 tiers-pins identical to the b3-r6 proof); 6 guard jobs (03 bus-only), build+verify OK; RC-6 `--declare-roots` OK (`end-staging/r4-rebuild/ROOTS-DECLARATION.json` 872ced5028db256e3b587f7fd5f2a9a4f6a5247f0b1a0548adb3e7accb628a40); S10 dry-runs 6/6 and S11 provision dry-runs 2/2 rc 0.

## Rulings in force / requested

- In force: BR-1 (k4s-end-r1, 7f93dbbf); IR-03 (aebb0929).
- **Requested with this package:** (a) **B6** — RC-6 declaration, preflight disclosures and any other pre-X commit go to main; k4s-end-r1 gets exactly X = P' + end/END-JOB.json. (b) **U4** — END host interpreter `/mpac/sdicks02/tools/uv-python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12` (the interpreter K4S reporting used on 03/04 per the supervisor admission receipts); S10's probe checks it read-only (numpy, torch, cv2, scipy import; no model load). (c) **D1 extension** — S9 exports three more SHA-pinned support files (SD1-MANIFEST.json b8ce7b4c…, t1 corpus-03-a51ea64c/corpora.json 3501e2ac…, DELTA-MANIFEST.json), never in runtime_files.

## Runner edits after the workers (all logged in each dir's PROGRESS/RESPONSE)

1. b3-r7: `test_s4_r7_ir03.py` looked up request metadata by absolute path (failed in copied trees); basename lookup. Test-only.
2. s3s9s10-r4: `ADOPTED_S4_SHA256` moved from b3-r6 76b7b7cf to b3-r7 2b8f5fb3 (IR-03 S4), test constant and test path updated, chain re-pinned (k4s_adopt.py), README L4 line. A first sed edit failed silently on a delimiter; corrected and disclosed in PROGRESS-r4.

## Disclosures

1. s5s6s7-r4 worker made one early full `cp -a` of repo-full including its work tree, which byte-copied 4 tracked complete.json files (the E4 files); not parsed or shown; deleted at once; later scratch clones copied `.git` only.
2. The S4/S3 worker hand-wrote an S7-shape RC-6 declaration with an unreviewed scratch script before `--declare-roots` existed; superseded by the tool output above.
3. The audit used an audit-only patched S4 copy (IA-P1) in /dev/shm to pass B1; never used for production.
4. s5s6s7-r4 has `builder-proof/END-JOB.json` (proof copy on main under run-r1/end-prep); the real END-JOB is committed only on k4s-end-r1 at A6.
5. Bundles are ~23.5 GB each; A2 run A per host transfers ~26.5 GB (runtime, tools, end-inputs, pf00 bundle, guard job; 10 logins), runs B/C ~23.5 GB each (6 logins).

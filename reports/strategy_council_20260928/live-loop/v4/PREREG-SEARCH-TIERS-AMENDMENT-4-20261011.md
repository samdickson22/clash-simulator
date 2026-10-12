# TIERS Amendment 4: Mac registration inputs (agreement2000 + packets1000), outcome-blind

Independent GPT-6.1-Sol review: **APPROVE** in round 4 of 4. Rounds 1–2 were REJECT, round 3 was APPROVE_WITH_CONDITIONS, and every finding was addressed; records are in `reports/explore/mac-registration/reviews/SOL-REVIEW-A4-r{1,2,3,4}.md`. Status: **ADOPTED** (COORDINATOR `16d431b4`; commit `94df513d`). The no-copy staging helper inside it was approved by coordinator ruling at 23:04Z on 2026-10-11 (COORDINATOR `684195b3`). Prepared 2026-10-11 from 22:25Z on 127x05 by the Mac registration inputs builder (coordinator thread 0523ae6f), acting as T1's delegate for the corpus-owner role. T1 keeps merge and seal authority. Design input: [MAC-REGISTRATION-INPUTS-PROPOSAL-20261011.md](MAC-REGISTRATION-INPUTS-PROPOSAL-20261011.md) (commits 59396fb0, 2cab69f0). The coordinator adopted rules B.1–B.7 as written and approved the overlapping minimal fixture (COORDINATOR.md, 22:26Z).

**What this amendment does not change.** It changes no hypothesis, arm, seed, tier, gate, threshold or reducer. It also leaves unchanged the slot count, budgets, warmup, OP-6 guards, the 24 GiB floor, the A3-P check and every outcome-handling rule. The frozen [TIERS freeze record](PREREG-SEARCH-TIERS-FREEZE-20261010.json) (`47aba25e…`), Amendment 1, [Amendment 2](PREREG-SEARCH-TIERS-AMENDMENT-2-20261011.json) (`46d8c4be…`) and [Amendment 3](PREREG-SEARCH-TIERS-AMENDMENT-3-20261011.json) (`3e5627cb…`) are unchanged. No e4v3 file changes: `measure_tiers.py` stays at 6066228b, and the Amendment 3 files (`tier_backend.py` 02e2139f, `state_rows.py` 3899276b, `convert_states.py` 7ce30683, `prepare_bundle.py` a1c59fa3), `corpus_contract.py` e62b6df5 and `receipts.py` 839a43be are byte-identical. No K4S re-pin follows.

## Why an amendment

The frozen text fixes the counts (125 golden, ≥2,000 agreement, ≥1,000 packets, 4×300 speed), the 20-field row contract, the packet-schedule binding and T1's merge. It does not say how agreement2000 and packets1000 are selected, from what source, at what cadence, or by whom. The E4-v3 addendum wanted both sets frozen "before any fleet reporting game", and that moment has passed. Amendment 1 A1.1 set the precedent for placing a step after reporting, outcome-blind. Here the inputs are excluded-range corpus captures whose outcomes are never read. The rules below are fixed and committed before the captures are opened: the 03 read happens only after this amendment is adopted.

## Rules (adopted as B.1–B.7)

**B.1 Pool and validity.**
- The pool is every retained row in T1's 32 capture files: seeds `4503603407370496+[3,11)`, 8 games per tier, a51ea64c lineage.
- Each file's SHA-256 must equal `source_capture_shas` in the committed `corpora.json` (`3501e2ac…`).
- Rows failing `corpus_contract.validate_row(row, tier)` are excluded before any ranking, and their ids and count are disclosed. **If more than 1 % fail, the build stops** and is escalated.
- **Lineage cross-check (fail closed):**
  - every one of the 1,200 published speed rows must be a capture row whose `convert_states.canonical_digest` equals the committed END digest (Amendment 3 `canonical-row-digests.json`, fingerprint c09142b9);
  - per-tier stratum counts and capture health must equal `corpora.json`;
  - retained versus counted rows are disclosed per capture.
- Speed rows always come from the published file (`282b0877`), never from the capture copy.

**B.2 Packets (packets1000).**
- Within each tier, games are ordered by ascending `sha256("tiers-packets/{tier}/{seed}")`.
- Games are taken round-robin by rank in `TIERS` order (K0c, S, K2, K4).
- Each game's valid rows are appended in ascending `info.tick` until the total reaches 1,000. The last game is truncated at exactly 1,000. Earlier games are whole.

**B.3 Cadence (P1, sealed ticks).**
- Tick = 0.05 s (20 Hz). Games are joined with exactly one 10-tick search interval: O_0 = −f_0 and O_{k+1} = O_k + l_k + 10 − f_{k+1}, where f_k and l_k are game k's first and last packet ticks.
- `timestamp_seconds = (tick + O_k) * 0.05`, so the first is exactly 0.0.
- `offset_seconds = timestamp_seconds − schedule[0].timestamp_seconds`.
- `opportunity = true` for every packet.
- Each entry has exactly `{id, tick, timestamp_seconds, offset_seconds, opportunity}`. `tick` equals the row's `info.tick`, and offsets strictly increase. These are the frozen `measure_tiers` checks.
- **Disclosure:**
  - The proposal estimates a mean gap of about 2.2 s, so one D7 or D8 pass takes about 30–40 minutes, against the addendum's 15 minutes.
  - The TIERS Mac sub-session therefore grows from about 100 minutes to **about 6–6.5 hours**.
  - Schedule offsets reveal the lengths of excluded games, which test no hypothesis.
  - Packets are not filtered by state size. The A3-P load-tail risk is disclosed, not engineered away.

**B.4 Agreement (agreement2000).**
- Agreement = speed1200 ∪ packets ∪ F, where |F| = max(0, 2,000 − |speed ∪ packets|).
- The fill pool is the valid rows outside speed ∪ packets. |F| is allocated across tiers by T1's `corpus.quotas`: proportional to fill-pool counts, at least one each, largest remainders. Within each tier, take the lowest `sha256("tiers-agreement/{tier}/{seed}/{tick}")`, ties by id. The salt is domain-separated from T1's `tier/seed/tick` speed priority.
- The list is ordered by (TIERS index, seed, tick). D6 uses its first 2,000 entries, which is all of them unless |speed ∪ packets| exceeds 2,000.

**B.5 Fixture order and identity.**
- `states.pkl` holds, in order:
  1. the published public 1,200 (END order);
  2. golden125 (END order);
  3. the extra rows (agreement minus speed) by (TIERS index, seed, tick).
- It is written once with `pickle.dump(rows, f, protocol=5)` after the reviewed runtime bootstrap.
- Its first 1,325 entries (id plus canonical digest) must equal the END index, entry by entry (c09142b9).
- Identity is the ordered canonical fingerprint (Amendment 3). An independent re-assembly must reproduce it. Then, on 05: `convert_states.py --states … --expect-fingerprint <reviewed>`.

**B.6 Fleet-CPU student logits.**
- `student-reference.json` = `{id: TierBackend.infer(id, "cpu")}` for every agreement id, written as the prepare_bundle dry run wrote it.
- **Host:** 127x05 (Threadripper 3990X, x86-64 Linux, the e4v3 venv, one Torch thread, nice 19, one core, no timing). The backend is constructed in the Mac-registration profile on the converted fixture.
- **Gate:** on the 300 S speed ids, every record must equal T1's pooled END fleet S forward (`speed-reference.json` [S][id].forward), with:
  - the same legal set;
  - the same discrete gate and ordered top-8 (`receipts.agreement` `equal`);
  - the gate and every legal logit within the F1 tolerance of 1e-4.
- Otherwise the reference is recomputed on 01 after its END pool.

**B.7 Receipts.**
- `mac-sets-selection.json` binds by SHA:
  - the capture verification, pool and invalid counts, game order and truncation point, and fill quotas;
  - all ids (via `mac-sets.json`), the schedule SHA, the assembly and fingerprint, the conversion receipt, the student reference and its cross-check, the memory check, and the script SHAs;
  - `outcomes_read: false`.
- T1 merges `sets`, `packet_schedule` and `student-reference.json` into its reviewed `registration.json` and seals T1-REGISTRATION. T1 does not seal before these inputs are delivered (coordinator, 22:26Z).

## Implementation clarifications (no rule change)

1. **A game is (tier, seed).** T1 reuses corpus seed indices 3–10 for every tier (for example, `K0c-200/4503603407370499/…` and `S-200/4503603407370499/…`). Every grouping, ordering and joining key is therefore the pair, never the seed alone.
2. **Uncovered case of B.4: stop, no new rule.** If 0 < |F| < (number of tiers with fill rows), "at least one each" cannot hold, and no adopted rule covers it. The build then **stops and escalates** to the coordinator. The expected |F| is about 50–150, so this case is not expected.
3. **Games come from the 32 pinned capture entries,** not from the rows found. A game with no retained or no valid rows contributes no packets and keeps its SHA-ranked round-robin slot. An empty capture file is handled. Speed or packet rows that fail the contract stop the build; they cannot be dropped silently.
4. **Identity checks.** Every capture row must have `id == "{tier}-200/{seed}/{tick}"` with the capture file's tier and seed, or the build stops.
5. **Runtime provenance (fail closed).** `build_runtime.sh` makes the builder's runtime on 05: T1's END-preparation runtime with its e4v3 package replaced by the END source commit f6cebbaa. The full runtime check runs once when `build_runtime.sh` creates the runtime. After that, every stage that loads the runtime re-runs it before doing anything else: `build_sets.py`, `assemble_states.py`, `student_reference.py compute`, and `memory_check.py` (the main process and both D6 children). The check requires that:
   - the frozen `prepare_bundle.runtime_pins` of that root equals T1's committed END-A3 manifest for 01 (`bd9804c3…`, all 3,785 `runtime_files`);
   - e4v3 is the runtime's own package, and its `measurement_files` equal END-A3's;
   - the native module SHA is `44874fd6…`.

   The other stages do not run this check:
   - The frozen converter `convert_states.py` runs on the same runtime and performs only its own checks: the SHA of the input `states.pkl`, `--expect-fingerprint`, and disk verification.
   - `student_reference.py cross-check` and `seal_receipt.py` load no runtime. They check the e4v3 pins of the package they import, and they check the artifact and receipt chain (item 6). The runtime binding recorded by the earlier stages is carried forward into the sealed receipt; it is not re-measured.

   The receipt is `receipts/runtime-a3-binding.json`. The 05 interpreter (CPython 3.12.12, torch 2.10.0+cpu, numpy 2.2.6) differs from 01's END interpreter (3.12.13, torch 2.10.0+cu128, numpy 2.3.5); this is disclosed, and B.6's cross-check is the gate. Only S speed states have pooled END student forwards, so the 300-state cross-check samples platform equivalence; it cannot certify each of the other agreement states.
6. **Receipt chain.** Each builder stage after selection re-hashes the artifacts it consumes and checks the previous stage's receipt (selection → assembly → conversion → student reference → cross-check and memory). These stages are assembly, reference computation, the memory check, the cross-check and the seal. The frozen converter checks its own input SHA and the expected fingerprint. `seal_receipt.py` re-verifies every artifact and receipt, the actual reference keys and the memory workload before sealing.
7. **One runtime bootstrap per interpreter.** Processes that construct a `TierBackend` leave `setup_imports` to the backend; a second call fails in torch (`set_num_interop_threads`). A real-runtime smoke on 05 (`receipts/real-runtime-smoke.json`) passes with a real Mac-profile backend and a spawned D6-style child.

## Procedure and roles

- **Phase 1 (05 only).** Code, synthetic tests, this record, Sol review (at most 4 rounds), commit. The coordinator then adopts Amendment 4.
- **Phase 2 (03 read).** This happens only after adoption and a declared 03 window, expected at about 08:47Z Oct 12 when K4S 03 stops at its apt timer. Proposal §C.2 is followed exactly:
  - one ssh session from 05 with `-o ControlMaster=no -o ControlPath=none`;
  - `rsync --files-from` listing only the 32 `capture.pkl.gz` paths from `corpora.json`, with `--rsync-path='nice -n 19 taskset -c 63 rsync' --bwlimit=32768`;
  - never `games/` or `local-complete.json`, and nothing written on 03;
  - every SHA verified on 05, then "released" posted to the coordinator at once.

  If the window is refused or any SHA mismatches, the builder stops and reports. The fresh-capture fallback needs a separate coordinator ruling.
- **Phase 3 (05, nice 19, one core, no timing).** Run `build_sets.py` → `assemble_states.py` → `convert_states.py --states --expect-fingerprint` → `student_reference.py compute` → `memory_check.py` → `student_reference.py cross-check` (once T1's END pool exists) → `seal_receipt.py`.
  - An independent Haiku 5.5 worker, at max effort and without reading the selection code, reproduces the ids, the schedule and the fingerprint from the same captures and this text.
  - **Blocking memory check:** in the Mac profile, every backend must retain exactly the agreement inputs (≥ 2,000 unique ids). Each D6 child runs a cold forward plus 2,000 forwards. The summed VmHWM of the main backend and both children must be at most 6 GiB. The receipt binds the sets, the bundle manifest and the student-reference receipt. Linux CPU RSS is a proxy for the Mac's CPU/MPS footprint, not an upper bound; the Mac session's own receipts remain binding.
  - Hand-off is to T1 (merge and seal) and to the coordinator.
- **Hands off:**
  - no ssh to 01, 04 or 08;
  - 03 only in the declared window;
  - no Mac contact;
  - no reads of outcomes, heldout data, `games/` or `local-complete.json`;
  - no writes in T1-owned trees.

## Mac staging without a data copy (coordinator ruling 22:31Z; scope message sent 22:30:53Z)

**Status: APPROVED by coordinator ruling issued at 23:04Z on 2026-10-11** and recorded in COORDINATOR commit `684195b3` at 23:04:25Z (the entry reads "23:04 UTC"; the git commit time is 23:04:29Z). The ruling answers Sol round 2, finding 8. The scope message allowed two designs, an edit to `prepare_bundle.py` or a pre-staging helper that runs before it, and said "if neither works, STOP and report". Neither works, for the reasons below. The builder stopped and reported. The coordinator then approved `stage_nocopy.py` as an external operational staging helper inside Amendment 4, under these conditions:
1. **Location and pinning.** It lives outside e4v3 and the runtime root, and it is SHA-pinned in this record. Before running, it verifies that e4v3's `measurement_files` equal END-A3's 18 entries. It imports the frozen `prepare_bundle` unchanged and overrides `copy_file` only for the bundle's `states.pkl`, `states-rows.json` and `states-rows.bin`; every other file goes through the frozen copy path.
2. **Placement order.** First clonefile, then a hard link, then a data copy only if at least 10 GiB stays free afterwards. Each file's SHA is checked after placement, and any mismatch fails closed.
3. **Protection.** After placement, both the source and the bundle copies of the three files are made read-only (`chmod a-w`), and the receipt records it.
4. **Equivalence evidence.** The real frozen `prepare_bundle` must give a byte-identical `tiers-pins.json` with and without the helper. That test stays in this amendment's evidence: `tests/test_stage_nocopy.py`, `FrozenPrepareBundle`.
5. **Session-time re-verification.** Immediately before the Mac session, `stage_nocopy.py --verify-bundle <bundle>` re-hashes the three files. Each must be present, read-only, and SHA-equal both to the staging receipt and to `tiers-pins.json`. The command writes a timestamped verification receipt. The session receipt records that the helper was used, the method per file, and those SHAs.
6. **No re-pins, conditionally.** This holds only while nothing frozen changes. If anything frozen changes, stop.

**Problem.** The Mac has about 65.7 GiB safely reachable and no external volume. Frozen `prepare_bundle.py` copies the fixture into the bundle (`shutil.copyfile` is a data copy on macOS), so staging peaks at about 72 GiB.

**Why the pinned file stays unchanged.** Two facts rule out the simpler designs:
- `prepare_bundle.py` (a1c59fa3) is in every bundle's `measurement_files`, which hash every e4v3 `.py`/`.sh` plus `spec-pins.json`. The END-A3 manifests for 01 and 08 pin it, and `fleet_pool` binds `measurement_files` across hosts. Editing it would break END↔Mac pin equality.
- Frozen `prepare_bundle` cannot accept pre-placed files: it creates `--output` with `exist_ok=False`, and `copy_file` raises `FileExistsError` on an existing destination. A pre-staging step before `prepare_bundle` is therefore impossible.

**Design.** `stage_nocopy.py` imports the **unmodified** frozen module from the reviewed e4v3 directory, after checking that the import resolved to that file. It replaces only the module-level `copy_file`, and only for the bundle's three fixture files (`states.pkl`, `states-rows.json`, `states-rows.bin`). It then runs `prepare_bundle.main()` with the same arguments the frozen command uses. Every other file, and the whole manifest, is produced by the frozen code.
- **Placement order, each step SHA-256 verified against the source (fail closed):**
  1. APFS `clonefile(2)`, called directly through libc on macOS (not `cp -c`, which falls back to a data copy on `EXDEV`/`ENOTSUP`). This is copy-on-write with its own inode; a clone failure raises.
  2. Hard link on the same filesystem.
  3. A data copy, **only** if at least 10 GiB stays free afterwards; otherwise staging fails.
- **Guards:**
  - Before importing, the e4v3 directory's `measurement_files` (computed with `prepare_bundle`'s own formula) must equal END-A3's 18 entries exactly, `prepare_bundle.py` a1c59fa3 included. The import must also resolve to that file.
  - The helper refuses to run from inside e4v3 or `--runtime-root`, because `runtime_files` hashes every `.py` there.
  - After placement, the source and bundle copies of the three files are made read-only (`chmod a-w`), and the resulting modes are recorded (condition 3).
  - It writes its receipt beside the bundle, never inside it. The receipt holds the method, SHA, bytes and read-only modes for each file, the helper and `prepare_bundle` SHAs, the `tiers-pins.json` SHA, and the free space.
  - `--verify-bundle` does the session-time re-verification (condition 5). It fails closed if any of the three files has changed, is missing, or is writable again.
- **Evidence (synthetic, 05):** the real frozen `prepare_bundle.py` a1c59fa3 in Mac mode gives a byte-identical `tiers-pins.json` and `tiers-pins.sha256`, and the same file set, whether run plainly or through the helper. The helper's three fixture files share the source inode.
- **Effect:** peak staging disk is about one copy of the fixture (about 36 GiB) instead of about 72 GiB.
- **Procedural change, disclosed and approved:**
  - The Mac session's staging step runs `stage_nocopy.py --e4v3 <e4v3> -- <unchanged prepare_bundle arguments>` instead of `prepare_bundle.py <arguments>`.
  - Immediately before the session, it runs `stage_nocopy.py --verify-bundle <bundle>`.
  - The helper's SHA is pinned in this record.
  - After a hard link, the source and bundle copies share an inode; making both read-only guards against modification. A clone has no such coupling, which is why it is tried first.

**Re-pins required: none.** This holds while nothing frozen changes (condition 6). Sol round 2 independently agreed.

| Pinned set | Effect |
| --- | --- |
| e4v3 files, `measurement_files`, END-A3 manifests 01/08 | None. No e4v3 byte changes, and the helper lives outside e4v3. |
| `runtime_files` | None, provided the helper sits outside the runtime root. This is enforced. |
| TIERS freeze record `47aba25e`, Amendments 1–3 | None. Amendment 3 records `prepare_bundle.py`'s after-SHA `a1c59fa3`, and those bytes are unchanged. No record pins a file that changes. |
| K4S Mac manifest `c1fb1e9a` | None. K4S never pins `prepare_bundle.py` (K4S Amendment 2), and no K4S-pinned file changes. |
| FROZEN-K4S `416f6e51` | None. No fleet file changes. |

## Code (`reports/explore/mac-registration/`)

| File | Role |
| --- | --- |
| `selection.py` | Pure B.2–B.5 rules on outcome-free metadata, including a verbatim copy of `corpus.quotas` (tested equal to T1's) |
| `macreg_io.py` | Pins, bootstrap, capture inventory and loading, identity checks, offline work bundle |
| `build_sets.py` | B.1 pass over the 32 captures, then selection; writes `mac-sets.json`, `fixture-plan.json`, `pool.json` and `selection-stage.json` |
| `assemble_states.py` | B.5 assembly, the END-prefix check and the expected fingerprint |
| `student_reference.py` | B.6 `compute` and `cross-check` |
| `memory_check.py` | Blocking Mac-profile memory check |
| `seal_receipt.py` | B.7 `mac-sets-selection.json` |
| `stage_nocopy.py` | No-copy Mac staging helper (frozen `prepare_bundle`, fixture files cloned or hard-linked) |
| `run_phase3.sh` | Phase 3 steps on 05 with the exact paths |
| `fetch_captures.sh`, `verify_captures.py` | Phase 2: the single §C.2 rsync from 03, then the 05 check that exactly the 32 pinned files are present and SHA-equal (never unpickled) |
| `build_runtime.sh` | Builds and verifies the END-A3-equal runtime on 05 |
| `tests/` | 38 synthetic tests plus `smoke_real_runtime.py` (real runtime, 05): rules, end-to-end with fake captures through the real Amendment 3 converter, fail-closed cases, hand-off glue, no-copy placement (including the real frozen `prepare_bundle` in Mac mode), copy verification. They pass on Python 3.8.10 and on 3.12.12 (torch 2.10.0+cpu, numpy 2.2.6). |

Source SHAs and test results are in the [amendment record](PREREG-SEARCH-TIERS-AMENDMENT-4-20261011.json).

## Errata (after adoption; COORDINATOR `16d431b4`)

**E1. Test-only portability fix to `tests/test_stage_nocopy.py`. No helper, rule or frozen-file change.**
- **Source:** reported by the Mac operator (commits `27faac2c` and `44040cd3`; receipts in `reports/explore/mac-e4-session/receipts/phase-b-prep-20261011/a4-nocopy-darwin/`) and relayed by the coordinator.
- **What was wrong:** `FrozenPrepareBundle.test_manifest_byte_identical_and_fixture_not_copied` assumed the Linux path. It asserted that each bundle fixture file shares the source inode, and that `--verify-bundle` reports the method `hardlink`. On macOS the helper correctly tries `clonefile` first (condition 2), and a clone has its own inode. The test therefore failed on Darwin even though the helper behaved correctly. The byte-identity assertions passed on the Mac, and so did the operator's own Darwin check: identical `tiers-pins.json`, `apfs-clone` placement, mode 0o444, and `--verify-bundle` passing, then failing closed once a file was made writable.
- **Fix:** the test now reads the placement method from the staging receipt. It expects `apfs-clone` on Darwin, with a different inode, and `hardlink` on Linux, with the same inode. The `--verify-bundle` method assertion uses the same expectation. Nothing else in the test changed.
- **Test SHA:** `f75cd3a3189e050d65bb52ae4dffb748d4b160d9ccffa79b74a031735e74202b` before, `b540df8273398be034bea7b254f34c2e5cb60fb932f977284e8f434f9cc069e9` after.
- **Unchanged:** `stage_nocopy.py` stays at `96abd8474d6410d6ba4342889e18d5caed5b455417535d44440d676041f653c7`.
- **Tests:** 38/38 pass on Python 3.8.10 and on 3.12.12 on 05.
- **Review:** a diff-only Sol check is recorded in `reports/explore/mac-registration/reviews/SOL-REVIEW-A4-E1.md`.

**E2. Staging-helper pin follows TIERS Amendment 5. One line; no rule, logic or frozen-file change by A4.**
- **Source:** TIERS Amendment 5 (adopted, COORDINATOR `46ab6923`; main `8799a0d6`) changes `e4v3/fleet_validity.py` from `94d0e7f2…` to `0775b704905324d70f9a43bc580bcbba1548cb2d2a4835c84ff61a0d8b64ae0f`. A5 ruling R5(b) requires this erratum.
- **Change:** in `stage_nocopy.py`, the `FROZEN_MEASUREMENT_FILES["fleet_validity.py"]` entry goes from `94d0e7f2…` to `0775b704…`. Nothing else in the helper changed.
- **Helper SHA:** `96abd8474d6410d6ba4342889e18d5caed5b455417535d44440d676041f653c7` before, `166a163620f7a1924ff50e120a2e9dff3e449329a02f5b5b52b13398536bc67d` after.
- **Pin check:** the 18 pins now equal the `measurement_files` of the e4v3 package at `8799a0d6`. An e4v3 holding the superseded `fleet_validity` bytes is refused before `prepare_bundle` is imported.
- **Tests:** 38/38 pass on Python 3.8.10 and on 3.12.12 against the A5 e4v3. The no-copy integration test runs the real frozen `prepare_bundle` through the helper on those bytes.
- **Re-stage before staging:** the Mac runtime must be re-staged from main `8799a0d6` or later, or overlaid and re-verified, before any Mac staging. Under A2's "same amended bytes everywhere", no TIERS Mac session runs on a runtime that holds `fleet_validity.py` `94d0e7f2`.
- **B.6:** the pooled-S-forward gate binds the A5 END pool.
- **Status:** accepted by the coordinator (COORDINATOR `8bbb0908`). The coordinator checked all 18 pins against the A5 e4v3 inventory at `8799a0d6` personally, and the Sol diff check was waived.

**E3. The builder's runtime binding follows TIERS Amendment 5, so Phase 3 builds on A5 bytes. Builder code only; no rule or frozen-file change by A4.**
- **Problem:** the builder's provenance check (`macreg_io.verify_runtime`) and its runtime (`build_runtime.sh` → `runtime-a3`) were bound to T1's END-A3 manifest `bd9804c3`. That manifest holds `fleet_validity.py` `94d0e7f2`. Under A2's "same amended bytes everywhere", Phase 3 must run on A5 bytes. T1 has committed SHAs for its END-A5 bundle manifests (01 `5df0fa00…`, 08 `93daf063…`) but not the manifest files. It has committed the inventory diff `reports/explore/t1/receipts/END-A5-runtime-manifest-inventory-diff.json` (`900bae16afeafeccd990109d23057a6f263f43a999b18e1a0e9b687b38afd69f`, commit `ffb138ab`). That diff certifies that END-A5 equals END-A3 with only `e4v3/fleet_validity.py` changed to `0775b704…`, in both `runtime_files` and `measurement_files`, with the native module unchanged.
- **Change:**
  - **`macreg_io.py`:**
    - A new function `a5_expected()` takes the committed END-A3 manifest and replaces exactly the `fleet_validity` entry, following the SHA-pinned diff.
    - It fails closed unless the diff is ADOPTED at `8799a0d6`, names exactly that one entry in `runtime_files` and in `measurement_files`, and reports the native module unchanged. The result must also equal the diff's 18-entry inventory.
    - `verify_runtime` and `runtime_arguments` take the new `--end-a5-diff` argument.
  - **`build_runtime.sh`:** builds `runtime-a5`, which is T1's END-preparation runtime plus the e4v3 package at `f6cebbaa` plus `fleet_validity.py` from `8799a0d6`, and verifies it.
  - **`run_phase3.sh`, `tests/smoke_real_runtime.py` and `tests/test_pipeline.py`:** use `runtime-a5` and pass `--end-a5-diff`.
  - **New test:** `tests/test_runtime_binding.py` checks that exactly one entry is replaced and covers six fail-closed cases.
  - **Unchanged:** selection, assembly, conversion, the student reference, the memory check, the seal and `stage_nocopy.py` (E2 bytes, `166a1636…`).
- **SHAs (before → after):**

  | File | Before | After |
  | --- | --- | --- |
  | `macreg_io.py` | `0f6042b4…` | `2d6181fd…` |
  | `build_runtime.sh` | `114d1b5d…` | `eeec07c6…` |
  | `run_phase3.sh` | `87b54c05…` | `8a60925a…` |
  | `tests/smoke_real_runtime.py` | `6854ec6a…` | `d2ec4b28…` |
  | `tests/test_pipeline.py` | `85825db4…` | `a7fca998…` |
  | `tests/test_runtime_binding.py` | none | `bad7ad1b…` |

- **Evidence:**
  - **`receipts/runtime-a5-binding.json`:** `runtime-a5` holds 3,785 `runtime_files` and 18 `measurement_files`, equal to END-A3 + `fleet_validity` `0775b704`, with native `44874fd6`.
  - **`receipts/real-runtime-smoke-a5.json`:** a real Mac-profile `TierBackend` on `runtime-a5` passes, with a single bootstrap and a spawned D6-style child.
  - **Tests:** 40/40 pass on Python 3.8.10 and 3.12.12 against the A5 e4v3.
  - **Kept as evidence:** `runtime-a3` and its receipts.

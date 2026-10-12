# T1 END: PC4 sensitivity-CLI and reducer lineage investigation r1

- **Investigator:** Claude Opus 5.5, independent. I am not the T1 worker, the production-packet reviewer or the coordinator.
- **Where and when:** 127x05, 2026-10-12, about 08:05Z–08:27Z.
- **Inputs:**
  - origin/main 8e814b78 at the start and 3debb7b8 at the end. The two new commits, 8fc25b2d and 3debb7b8, touch only R3/R5 pool-check receipts; every file cited below is unchanged.
  - `origin/worker/t1-op7-apt-20261010`, head ef4c073a.
  - the production-packet review `END-PRODUCTION-PACKET-REVIEW-r1.md`, F2, F3, R1 and R2.
- **Scope kept:**
  - Git reads only (`git show`, `git diff`, `git merge-tree` dry run), plus reading T1's local job scripts on 05: `final-durability-r3.py`, `stage-op7-reporting.sh` and the copier scripts.
  - No SSH. No edits to repository or T1 files. I opened no outcomes, no `games/` files and no `complete.json`/`interference.json`.
  - The committed sidecar 48730da5 was read for its keys and its `cpu_accounting_rule` counts only. It is a health-only file.

## 0. Answer in one paragraph

OP-7 changed the **reporting guard**, not just the analysis. It altered stop/flag classification (`host_audit.py`, `supervise.py`, a new `apt_budget.py`) and the SSH CPU meter (`ssh_budget.py`, a new `cpu_accounting.py`), and it pre-specified two extra descriptive analyses. **2,361 of the 3,072 counted blocks** (all of replacement-r2 and r3) ran under OP-7 frozen manifest **488f6c8d** (freeze ef4c073a). That manifest pins `ssh_sensitivity.py` **bb124cc4**, `reduce.py` **aebb2017** and the OP-7 version of the PC4 text.

Main still carries the OP-6 bytes because the OP-7 branch was never merged. That is a lineage gap, not a decision. No committed document ever chose e643a342 over bb124cc4 for the OP-7 phases, and no committed ruling has yet landed OP-7 for release.

The counted root is **one directory**, `…/replacement-frozen-op7-0108-r3/hub-blocks` on 127x01. It holds 3,072 entries through a chain of carry-forward symlinks. Both CLI versions and both reducers take exactly one `--root`.

**Recommendation:**
- PC4 runs bb124cc4 on that root.
- The release reducer is aebb2017.
- Land both by **copying the frozen bytes onto main at their canonical paths** in a narrow commit. Do **not** merge the branch, and leave main's `FROZEN-T1.json` at 24817e16.

## 1. What OP-7 is, and which guard each counted block ran under

### 1.1 OP-7 is a guard change, plus prespecified sensitivity analyses

The evidence is `git diff aeeb3003 04633bdb` (25 files), together with `reports/explore/t1/OP7-T1.md` at 04633bdb.

**Guard and stop rules:**
- `host_audit.py` 5717d01c → f25ef204. The census now captures cgroup and four-UID provenance, and admits source-proven Ubuntu apt processes from `/system.slice/apt-daily{,-upgrade}.service` as an apt family instead of `foreign_compute`.
- `supervise.py` d4028d92 → 36063cd8:
  - `guard_reason = ssh_budget.stop_reason(...) or apt_budget.stop_reason(...)`;
  - a per-block `apt_meter`;
  - `interference['ubuntu_apt']`, `apt_flagged`, and `interfered |= apt_flagged`.
- `apt_budget.py` is new (c1578535). Apt flags at >0.5% of a core averaged over a block. The block stops at a >10% average after 60 s, or at >150% in a single sample.
- These rules exist because 01's replacement-r1 phase **stopped** at 21:03:53Z on an `unattended-upgrade` root (COORDINATOR.md:1887, which authorized OP-7). Under OP-7 that process would be flagged, not stopped.

**Meter accounting:**
- `ssh_budget.py` 0c2759f5 → 0ef24fac and the new `cpu_accounting.py` 5ecae99d add `OP-7-observed-child-credit-v2` (credit lots, newest-first settlement, expiry after three scans).
- OP7-T1.md: "its meter uses the same correction only in the new OP-7 phase, never in the running r1 phase".

**Analysis:**
- `ssh_sensitivity.py` e643a342 → bb124cc4 adds:
  - `apt_flagged` (it re-validates the apt meter, its source and cgroup, all four UIDs and the helper evidence; `:25-56`);
  - the paired-v2-meter fail-closed check (`:29-30`);
  - `ssh_or_apt_flagged`, `*_meter_stop`, `cpu_accounting_rule` and `flag_counts` (`:69-71`, `:91-94`);
  - `analyze_apt` and `analyze_union` (`:85-97`).
- `reduce.py` fdea088c → aebb2017 is a pure 7-line addition at `:131-141`: the import plus three result keys. Everything else in the reducer is byte-identical. OP-7 r1 (`:64-69`), r2 (`:36`, `:109`) and r3 (`:159`) all confirm that the primary analysis and its RNG are untouched.
- OP7-T1.md, under "Prespecified descriptive sensitivity", **prespecifies** the apt-excluded and SSH-OR-apt-excluded analyses, using RNG 2026101040.

So OP-7 is not "only a sensitivity addition". It changed what the guard stops, flags and meters for every block launched under it.

### 1.2 Guard regime per counted phase

The sources are `reports/explore/t1/receipts/phase-source-bindings-final-op7-r3.json` (08cad0ff) on main, and the sidecar's own `cpu_accounting_rule` tally.

| Phase (01 / 08 blocks) | Frozen manifest (job `FROZEN-T1.json`) | Guard rules | `ssh_sensitivity.py` pinned | Sidecar rule tag |
| --- | --- | --- | --- | --- |
| reporting (124 / 33 = 157) | **a7ebba64** = `receipts/reporting-manifest-0108.json` | OP-1…OP-5, OP-5_08 (no OP-6) | none | legacy-self-plus-reaped |
| replacement-r1 (155 / 399 = 554) | **24817e16** = `receipts/replacement-manifest-op6-0108-r1.json` = main's `FROZEN-T1.json` | + OP-6 | e643a342 | legacy-self-plus-reaped |
| replacement-r2 (1181 / 160) and r3 (512 / 508), 2,361 in total | **488f6c8d** = `receipts/replacement-manifest-op7-0108-r2.json` = `FROZEN-T1.json` at ef4c073a | + OP-7 (`operational_delta_op7.status = FROZEN_ADMITTED_C3_PASS`) | **bb124cc4** | OP-7-observed-child-credit-v2 |

Totals: 711 legacy blocks (01 279, 08 432) and 2,361 v2 blocks (01 1693, 08 668). Both match the sidecar exactly.

**Launch evidence:**
- `replacement-launch-receipt-op7-0108-r2.json` gives `freeze_commit` ef4c073a, `reviewed_source_commit` d8cc4ff7, `confirmation_commit` 1947830b and `manifest_sha256` 488f6c8d.
- `replacement-launch-receipt-op7-0108-r3.json` gives the same freeze and manifest.
- `replacement-authorization-op7-0108-r2.json` binds 488f6c8d with `r3_explicitly_frozen = true`.
- The completion receipt records `r3_frozen_source_commit` = ef4c073a and `r3_manifest_sha256` = 488f6c8d.

**Pins inside 488f6c8d:** `ssh_sensitivity.py` bb124cc4, `reduce.py` aebb2017, `supervise.py` 36063cd8, `host_audit.py` f25ef204, `ssh_budget.py` 0ef24fac, `apt_budget.py` c1578535, `cpu_accounting.py` 5ecae99d, and `RELEASE-PRODUCTION-CHECKS-20261010.md` **9b0704e2**, which is the OP-7 text of PC4.

Observed flags in the counted data: apt-flagged 0, apt stops 0, SSH stops 0, SSH-flagged 477 (all on 08). The apt-sensitivity analysis will therefore equal the primary analysis, and the union analysis will equal the SSH analysis. The accounting change still governs SSH metering for 2,361 blocks.

## 2. What the binding documents designate

| Document | What it says | Designates |
| --- | --- | --- |
| PREREG-SEARCH-TIERS r3 draft and FREEZE 47aba25e | No sensitivity CLI or OP-n text. Operational deltas live at the T1 FROZEN level | nothing |
| Amendments 1–4 and adopted A5 | A3, A4 and A5 say "OP-6 guards unchanged". A5 §1 says "the guard freeze `FROZEN-T1.json` 24817e16 and its nine modules" are unchanged. The completion receipt's C2 says "END reference uses strict OP6" | the **E4 END reference guard** (`fleet_validity.GUARD_MODULES`, 9 modules, `GUARD_RULES = frozen-t1-op1…op6-v1`). This is not the reporting-block sensitivity CLI or the reducer |
| OP-6 confirmation 9118153b, and main's `FROZEN-T1.json` 24817e16 `operational_delta_op6` | `reviewed_commit` d60586b3, `sensitivity_source` `ssh_sensitivity.py`, `production_release_conditions` "PC1-PC4" | e643a342, **for the OP-6 phase**. It predates OP-7 |
| PC4 text on main, ff0b7afe (`RELEASE-PRODUCTION-CHECKS-20261010.md:8`) | "PC4, OP-6 sensitivity sidecar … mixed OP-5/OP-6 regimes … OP-6 confirmation: 9118153b. Release integration review: 977c4dfb; integrated branch c5b2e059" | OP-6 wording. It is stale: it was never updated on main because OP-7 was never merged |
| PC4 text in 488f6c8d, 9b0704e2 (the diff aeeb3003 → 04633bdb on that file) | "PC4, **OP-6/OP-7** sensitivity sidecar … exact apt meter/source validation and mandatory paired matching meters … apt-flagged, both-flagged and either-flagged counts … stop=True … mixed OP-5/OP-6/OP-7 meter regimes … union analysis … the reducer rechecks … including both flags, the derived union flag and flag-count/stop-proof disclosures" | **bb124cc4 behaviour.** e643a342 can't satisfy it, because it has no apt validation, no paired-meter check and no union or flag counts |
| OP-7 confirmation 1947830b (COORDINATOR.md entry at 23:08Z) | PASS on d8cc4ff7: "GO C2 (FROZEN, re-hash, bind …), then C3 …, then the reviewed Option B" | authorizes the **running phase** on OP-7 bytes. It contains no release or merge ruling |
| 488f6c8d `operational_delta_op7.release_condition` | "PC4 strict flags, both/union counts, stop=True completion proofs and mixed meter regimes before both routes" | the OP-7 PC4 applies to **both** release routes |
| `reporting-completion-op7-r3-20261011.json` 9e788d20 (bc3730c4), and its END projection 4dd191b6 | `ssh_sensitivity_sha256` 48730da5. `sensitivity_health_check` reports APT flags, APT stops, and both/either counts. `release_status`: "PC1-PC4 mandatory before both routes" | completion was checked against the **OP-7** PC4 content |
| Release review 977c4dfb and integration c5b2e059 | c5b2e059 (18:52Z, Oct 10) adds `release_reference.py`, `check_reference.py`, and the `barrier.py` +5 lines. It was merged to main at 597b0964, so it is **already in main**. 977c4dfb: "reduce.py, common.py and barrier.py are unchanged since 64608f6f" | It predates OP-7 (authorized at 21:24Z) and carries the OP-6 reducer fdea088c. It **cannot** have adopted or rejected OP-7 |
| COORDINATOR.md (grep for bb124cc4, e643a342, aebb2017, merge, PC4) | The only lineage entries are :2626-2632 (F2/F3, which commissioned this investigation) | **No committed ruling adopts OP-7 for release, and none rejects it** |

**Conclusion.** The governing PC4 for 77% of the counted blocks is the OP-7 text frozen in 488f6c8d, and it is satisfiable only by bb124cc4 and aebb2017. "Main pins e643a342" is true only of the OP-6 freeze and of E4's guard freeze. Neither was ever meant to govern OP-7 blocks.

## 3. Is OP-7 on main or in the release integration? How should it land?

### 3.1 Facts

- `git merge-base --is-ancestor` reports that 04633bdb, d8cc4ff7 and ef4c073a are **not** ancestors of origin/main. The branch is pushed (`origin/worker/t1-op7-apt-20261010` = ef4c073a), and its merge base with main is aeeb3003.
- c5b2e059 **is** an ancestor of main. It carries the OP-6 reducer.
- The OP-7 tree **lacks the release barrier.** `git diff origin/main ef4c073a` shows `release_reference.py` −294, `check_reference.py` −84, `barrier.py` −5, and the tests (`test_release_reference.py`, `test_reference_packet.py`). So neither lineage alone can run the release:
  - main lacks the OP-7 reducer and CLI;
  - ef4c073a lacks the barrier, which `reduce.py:9` imports through `outcome_release` → `release_reference.prerequisites`.
- Main already contains the bb124cc4, c1578535, 5ecae99d and 0ef24fac bytes, under `reports/explore/k4s-confirm/` (38c195b8). That is precedent for copying frozen bytes, but at a K4S path that T1 cannot import.

### 3.2 Merging the frozen branch is not recommended

- A `git merge-tree` dry run applies cleanly with 0 conflicts.
- But a merge would replace main's `reports/explore/t1/FROZEN-T1.json` 24817e16 with 488f6c8d, and `host_audit.py` and `ssh_budget.py` with their OP-7 versions.
- Those two modules are among E4's nine frozen `GUARD_MODULES` (`fleet_validity.py:10-12`, checked at `:66-70` against the bundle's freeze). They are pinned to 24817e16 by A3, A5, the END reference launch receipts and the pool check (`git grep 24817e16` gives more than 25 committed receipts).
- After a merge:
  - any E4 bundle rebuilt from main, such as a Mac TIERS session or a re-stage, would carry OP-7 guard modules;
  - OP-7 `ssh_budget.py` imports `cpu_accounting`, which is not one of the nine modules;
  - main's `FROZEN-T1.json` path would no longer be the freeze that A5 calls unchanged.

  This is an avoidable risk to the END reference and to PC2-style pins.

### 3.3 Recommended: copy the frozen bytes into a narrow landing commit on main

Copy these files at the **same canonical paths**. The reducer needs `common.ROOT = HERE.parents[2]` and `plan.json` beside it (`common.py:4-12`), so it cannot run from a subdirectory.

| Path (`reports/explore/t1/`) | From `git show ef4c073a:` | SHA-256 (= 488f6c8d `files[...]`) | E4 guard module? |
| --- | --- | --- | --- |
| `ssh_sensitivity.py` | e643a342 → **bb124cc4** | bb124cc4716d… | no |
| `reduce.py` | fdea088c → **aebb2017** | aebb2017d1ee… | no |
| `apt_budget.py` | new, **c1578535** | c15785357a95… | no |
| `cpu_accounting.py` | new, **5ecae99d** | 5ecae99d9097… | no |
| `RELEASE-PRODUCTION-CHECKS-20261010.md` | ff0b7afe → **9b0704e2** (the doc that governs the counted data) | 9b0704e2… | no |

**Leave unchanged:** `FROZEN-T1.json` (24817e16), `host_audit.py`, `ssh_budget.py`, `supervise.py`, and every e4v3 file.

**Import compatibility on main** (static check):
- bb124cc4 imports `ssh_budget.lan_connection`, which is byte-identical in 0c2759f5 and 0ef24fac.
- `apt_budget` imports `ssh_budget.generation` and `total_ticks`; both exist in main's 0c2759f5 (`:12`, `:60`).
- `cpu_accounting` needs only the standard library.
- The release-time functions (`flagged`, `apt_flagged`, `directories_valid`, `health_ledger`, `analyze*`) read only proof content. They never read the live host.

**Pin handling (PC2-style):**
- Do not edit `FROZEN-T1.json` 24817e16. E4 owns that pin, and the OP-7 phases never ran under it.
- Commit a new receipt, for example `receipts/release-lineage-op7-20261012.json`. For each landed path it binds:
  - landed sha == `488f6c8d.files[path]` == sha of `git show ef4c073a:path`;
  - the reviews r1–r3 (1f073ab8, c6cbfb1b, f7826322) and confirmation 1947830b;
  - the statement that main's `FROZEN-T1.json` remains the r1/E4 freeze and is now stale for these 2 code files and 1 doc (disclosed, and not checked at release; only `run.py`/`supervise.py` launch gates check it).
- Have the coordinator tag ef4c073a, for example `t1-op7-freeze-ef4c073a`, so it stays reachable if branches are cleaned up.
- Commit through the temp-index procedure, then run the secret scan.

**Tests:**
- On the landing tree, nice 19 and one core: `test_reduce`, `test_op6`, `test_barrier`, `test_release_reference` and `test_reference_packet`, plus the e4v3 suite (expect 70/70, unchanged).
- `test_op7.py` imports OP-7 `host_audit` (`test_op7.py:8`), so the full suite is valid only on an exact `git archive ef4c073a` export, where 1947830b already recorded 213/213. Either rerun it there, or add only the `ssh_sensitivity`/`reduce` subset of test_op7 under `-k`. Don't commit a test file that fails on main.

**Reviews needed:**
1. A **coordinator ruling** (R1), committed, naming the CLI, the reducer, the landing method and the PC4 root below.
2. A **narrow Sol diff review** of the landing commit. Model routing is "Sol reviews Claude code". The review covers byte identity with ef4c073a for the 5 paths; that nothing else changed (in particular the E4 guard modules and `FROZEN-T1.json`); import compatibility with main's `ssh_budget`; the test results; and that `reduce.py` still calls `outcome_release` before `load_blocks` (`:120`, `:123`).
3. A short **977c4dfb addendum**, which Sol r1 can cover. 977c4dfb's "reduce.py unchanged since 64608f6f" stops being true, so it should confirm that barrier, release_reference and check_reference are untouched and the only reducer delta is aebb2017.

No new science review is needed. aebb2017 and bb124cc4 already passed OP-7 r1–r3 and 1947830b, and the analysis plan is unchanged from 488f6c8d.

## 4. The PC4 counted root and how 48730da5 was produced

### 4.1 One root, not eight

The counted inventory `counted-inventory-final-op7-r3.json` 50f24dd6 lists `durable_path` under 8 parents:
- the 01-local `<job>/<phase>`;
- the 08 copies `<job>/hub-blocks`;
- for each of the 4 jobs: `reporting-frozen-0108-r1`, `replacement-frozen-op6-0108-r1`, `replacement-frozen-op7-0108-r2` and `replacement-frozen-op7-0108-r3`, all under `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/` on 127x01.

Those are **resolved** paths. The generator wrote `durable_path=str(p.parent.resolve())` (`final-durability-r3.py:42`), and the root it globbed was a single directory.

**Construction of that root:**
- `supervise.py:77` (main) / `:91` (ef4c073a) symlinks each 01-local complete block into `<job>/hub-blocks/<id>`.
- `mirror.copy_block` (`mirror.py:28-44`) copies 08 blocks into `<job>/hub-blocks/<id>` and writes `hub-ack.json` there and back on 08.
- Each new phase job **carries forward** the preserved blocks as symlinks into the previous job's `hub-blocks` (`stage-op7-reporting.sh:27-30`: `(j/"hub-blocks"/d["id"]).symlink_to(src/d["id"])`):
  - r2: 711 preserved (`blind-reinventory-option-b-op7-r2.json`, `completed_blocks_preserved = 711`, `source_job` = the op6 r1 job);
  - r3: 2,052 preserved (`blind-reinventory-option-b-op7-r3-draft.json`, `source_job` = the op7 r2 job).

  1,020 new r3 blocks + 2,052 preserved = 3,072.

**PC4 root:** `127x01:/mpac/sdicks02/jobs/clasher/t1-20261010-r1/replacement-frozen-op7-0108-r3/hub-blocks`. It has 3,072 `*/complete.json` entries, with 1,100 `hub-ack.json` (08) reached through the chain r3 → r2 → r1 `hub-blocks` → phase directories. Every directory basename is unique. It contains no lost (ledger-excluded) ID: `final-durability-r3.py:32` asserts `sid not in lost`.

### 4.2 How 48730da5 was generated

The record is `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/final-durability-r3.py` on 05 (sha 1416a7af…, mtime 12:27 PDT = 19:27Z). It is **not committed**. It ran on 127x01: it checks 01's r3 supervisor PID 1410693 and copier PID 1410572.
- `:2`, `:14-22`: `j = …/replacement-frozen-op7-0108-r3`, `sha(j/FROZEN-T1.json) == 488f6c8d`, and all 196 `j/repo` files hash-verified.
- `:30-44`: it globs `j/hub-blocks/*/complete.json` and asserts 2400/600/72, 24,576 game hashes and 1,100 ACKs.
- **`:46` (the argv):** `[sys.executable, j/repo/reports/explore/t1/ssh_sensitivity.py, '--root', j/hub-blocks, '--ledger', reporting-completion-sealed-r1/blind-ledger-final.json (866e6f7f), '--out', reporting-completion-sealed-r1/ssh-sensitivity-final.json]`. The CLI is bb124cc4 (from the 488f6c8d-verified job repo).
- `:47-48`: it asserts 3,072 blocks and no apt flag or stop.

The output utc is 19:27:23Z, equal to `raw_durability.utc` in the completion receipt.

**Gaps:**
- The argv and the interpreter (`sys.executable`) are recorded in no committed byte.
- The completion receipt records only output SHAs.
- The 05 file is a copy, so its identity with what ran on 01 is not proven.

The PC4 rerun closes all three.

### 4.3 What the CLIs and reducers accept

| Tool | `--root` | Evidence |
| --- | --- | --- |
| `ssh_sensitivity.py` e643a342 | exactly one (`type=Path, required=True`); glob `root/*/complete.json` | main `:51`, `:27` |
| `ssh_sensitivity.py` bb124cc4 | exactly one | ef4c073a `:100`, `:61` |
| `reduce.py` fdea088c and aebb2017 | exactly one; `load_blocks` globs `root/*/complete.json`, requires `hub-ack.json` for non-01 blocks, asserts 2400/600 | `:118`, `:86-104` |

No per-phase merge is needed. The same single root serves PC4 and the release reducer.

## 5. Recommended ruling

1. **PC4 CLI:** `reports/explore/t1/ssh_sensitivity.py` **bb124cc4…a0e5**, as frozen in 488f6c8d at ef4c073a and confirmed by 1947830b. Apply the OP-7 PC4 text 9b0704e2 (OP-6/OP-7, apt validation, paired v2 meters, both/either counts, stop=True counts, mixed OP-5/OP-6/OP-7 regimes).
   - e643a342 is rejected for PC4. It can't validate the 2,361 v2 proofs' apt meters or paired rules, and it can't reproduce the checked sidecar's block entries.
   - Optional descriptive cross-check: projecting both CLIs onto the e643a342 field set (`id`, `source_id`, `population`, `cell`, `host`, `ssh_flagged`, `complete_sha256`, `interference_sha256`) should give equal results, because `flagged()` is byte-identical in the two (e643a342 `:8-22` = bb124cc4 `:9-23`).
2. **Release reducer:** `reduce.py` **aebb2017**, run from main's lineage, which already contains c5b2e059's barrier, release_reference and check_reference. Its `<out>.ssh-sensitivity-ledger.json` must equal the PC4-checked sidecar in every field except `utc`: schema, sealed, `blind_ledger_sha256`, all 3,072 block entries, and `flag_counts`. Its results must include the prespecified `apt_sensitivity` and `ssh_or_apt_sensitivity`.
3. **Landing:** a narrow copy commit on main, per §3.3. Do not merge. Leave `FROZEN-T1.json` 24817e16 and the E4 guard modules alone. Add the lineage receipt, tag ef4c073a, then get the Sol review and the 977c4dfb addendum.
   - The release checkout `<R>` used by R3, R5 and R6 should be a descendant of the landing commit. The e4v3 bytes stay equal to 8799a0d6, so R3's pool-check regeneration is unaffected.
   - If R3 has already run in a checkout without the landing, check whether its `input_files` must be regenerated in the final `<R>`. They key only the descriptor and the e4v3 paths, so the T1 file changes don't alter them, but the path prefix must be the final `<R>`.
4. **PC4 run procedure:**
   - **Authority:** a read-only execution grant on hub 127x01. Copying to 05 is not recommended (see §6, risk 3).
   - **Code:** extract `git archive ef4c073a reports/explore/t1` to scratch outside every job root, for example `/mpac/sdicks02/tmp/pc4-<utc>/`, and verify `sha(ssh_sensitivity.py) == bb124cc4` and the other 488f6c8d entries. After landing, a second run from the landing commit's bytes must give an identical result except for `utc`.
   - **Interpreter:** use the r3 job's runtime Python (copier exe `/mpac/sdicks02/tools/uv-python/cpython-3.12.13-…/python3.12`, per `raw_durability.copier_identity`). Record argv, `sys.executable` and version. Use `PYTHONDONTWRITEBYTECODE=1` and `-E -s`, but not `-I`, which would drop the script directory from `sys.path`.
   - **Command:** `nice -n 19 taskset -c 62 <py> -E -s <scratch>/reports/explore/t1/ssh_sensitivity.py --root /mpac/sdicks02/jobs/clasher/t1-20261010-r1/replacement-frozen-op7-0108-r3/hub-blocks --ledger <committed blind-ledger-final-op7-r3.json, 866e6f7f> --out <scratch>/ssh-sensitivity-pc4.json`. The CLI reads only `complete.json`, `interference.json` (hashed) and `hub-ack.json` existence. It reads no `games/` files.
   - **Checks:** the output equals 48730da5 except `utc`; 3,072 entries, exactly 2400/600/72; logical IDs equal 50f24dd6 and source IDs equal 6f6f0007; every `complete_sha256` matches the inventory; v2 = 2,361 and legacy = 711; flag counts as in the completion receipt.
   - **Commit:** the sidecar, plus a reviewer check receipt binding the sidecar SHA, ledger 866e6f7f, inventory 50f24dd6 / 6f6f0007, the set of 3,072 complete-proof SHAs (or its digest), CLI bb124cc4, source commit ef4c073a or the landing commit, the interpreter and the argv.
5. **Reviews:**
   - the coordinator ruling;
   - Sol on the landing diff;
   - the 977c4dfb addendum;
   - an independent PC4 reviewer receipt;
   - production-packet review r2, which must confirm that the reducer's emitted ledger and the PC4 sidecar match in the released tree.

## 6. Risks to the release

1. **Wrong lineage at release.** If the reducer runs from current main (fdea088c / e643a342), its emitted ledger has no apt, union or flag-count fields. The PC4 match fails closed, and the prespecified OP-7 analyses would be missing, which is a deviation from 488f6c8d. Nothing in code enforces the reducer identity: `prerequisites` checks completion, END, pool and registration, not `reduce.py`. The ruling and receipt are therefore the only guard.
2. **The root is a symlink chain across 4 job directories on one host.** Moving, cleaning or re-rsyncing any of `reporting-frozen-0108-r1`, `replacement-frozen-op6-0108-r1`, `replacement-frozen-op7-0108-r2` or `replacement-frozen-op7-0108-r3` on 127x01 breaks both PC4 and the reducer. Freeze all four until release. Don't rebuild a new root by copying.
3. **Single-copy data.** The 1,972 01-local counted blocks and their games exist only on 127x01; 05 has only health metadata. A loss of 01 before release would be unrecoverable for those blocks. Consider a coordinator-authorized, byte-identical durability copy, with the root's symlink structure preserved, to a dedicated prefix. That is a game-byte transfer, so it needs explicit authority.
4. **Unproven provenance of the generator.** The argv and interpreter for 48730da5 exist only in an uncommitted 05 copy of the script. The PC4 rerun supersedes this, so the copy is not itself a blocker.
5. **Stale documents on main after landing.** `FROZEN-T1.json` 24817e16 will still list e643a342, fdea088c and ff0b7afe. That is acceptable only with the lineage receipt's disclosure. Never "fix" it in place, because E4 pins it.
6. **Test coverage on the landing tree.** The full `test_op7` can't run against main's OP-6 `host_audit.py`. Use the `ef4c073a` export for the full suite and a subset on the landing tree, as in §3.3.
7. **No outcome risk was found.** Every step above is health-only and fails closed.

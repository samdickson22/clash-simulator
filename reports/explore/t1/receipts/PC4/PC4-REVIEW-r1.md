# PC4 reviewer check r1: OP-7 sensitivity sidecar

**Verdict: PASS**

- **Reviewer:** Claude Opus 5.5 (1M context), the independent PC4 reviewer. I am not the T1 worker, the coordinator or the lineage investigator.
- **Hosts:** reviewed on 127x05; executed read-only on hub 127x01.
- **Authority:** COORDINATOR 9897216c R1 item 4; `END-PC4-LINEAGE-INVESTIGATION-r1.md` §4 and §5.4; PC4 text 9b0704e2 (the OP-7 text in 488f6c8d).
- **Written:** 2026-10-12T08:35:18Z.
- **Scope:** health-only. I opened no `games/` files and no outcome fields. On 01 I wrote only the scratch directory, which is now removed. Nothing under `/mpac/sdicks02/jobs/clasher/` on 01 was written, and the paused mirror (pgid 516161) was not touched. No hosts other than 01 and 05 were used.

## Bound artifacts

| Item | SHA-256 |
|---|---|
| PC4 sidecar `PC4/ssh-sensitivity-pc4.json` (utc 2026-10-12T08:32:20Z) | `ea3d44d337fd3b581f11ba70633744e84ccde84dd230ce9c0e6e8ecea3ae7ea4` |
| Committed sidecar `ssh-sensitivity-final-op7-r3.json` (bc3730c4) | `48730da553491f998f16e389d65d94c0d586ed5a0964d64fa58c01f294962b62` |
| Blind ledger `blind-ledger-final-op7-r3.json` (54 events) | `866e6f7f7e41af4112602a643372d8424d951abb1c6952230d25d106a840d8fa` |
| Counted inventory (health) | `50f24dd6c93daad65ce8df3558978d669486efdf00da5e33c2d0f852b6effc72` |
| Counted inventory (END projection) | `6f6f000781d5d345846a33331d8fbc864fc679971001e23b4c7355505165386f` |
| Completion receipt | `9e788d2053c10da19e339e201d4a3b4cb7d387e96bc837778b1fee2fa10e2dca` |
| Complete-proof digest (`id source_id complete_sha256` lines, sorted by id) | `ef621e517f6616e323e7028cf8952487821e9f582c476a3e3358594a5107f243` |
| Complete-proof set digest (sorted SHAs) | `d0f010695064c0b5d397ce8f24afede30a679a571a989daa4e058c1571c23fe0` |
| CLI `ssh_sensitivity.py` | `bb124cc4716d1b902de936866bf28eec9a057128e3f04392f6234650d3a3a0e5` |
| Frozen manifest `FROZEN-T1.json` at ef4c073a | `488f6c8daccc81bc13a0f388bb254fa994020806b9245b2e315c5ba237dcb12e` |
| Archive `git archive t1-op7-freeze-ef4c073a reports/explore/t1` | `b98abf77a4928a8d2de09502048f4a5150aac76c4db5f9c5c3474a9f3d55db5b` |
| Interpreter binary | `021044895e95be79dc2f110367607e684119afbc8ce75f6f0eec94844e0acec7` |

- **Source:** tag `t1-op7-freeze-ef4c073a` (tag object 11b17e43) points to commit ef4c073a4c69e85aea0b6f9af9c1118ca8888a59.
- **Manifest check:** I verified all 193 `reports/explore/t1/` entries of 488f6c8d against the extracted scratch tree on 01 with `sha256sum -c`; every entry matched.
- **Modules loaded:** per `__pycache__`, the run loaded exactly `apt_budget.cpython-312.pyc, common.cpython-312.pyc, cpu_accounting.cpython-312.pyc, idle_services.cpython-312.pyc, ssh_budget.cpython-312.pyc, ssh_transport.cpython-312.pyc`. All are manifest-pinned, and `host_audit` was not imported.

## Run (once, on 127x01)

- **cwd:** `/mpac/sdicks02/tmp/pc4-20261012T083152Z/reports/explore/t1`
- **Command:** `PYTHONDONTWRITEBYTECODE=1 nice -n 19 taskset -c 62 /mpac/sdicks02/tools/uv-python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12 -E -s ssh_sensitivity.py --root /mpac/sdicks02/jobs/clasher/t1-20261010-r1/replacement-frozen-op7-0108-r3/hub-blocks --ledger /mpac/sdicks02/tmp/pc4-20261012T083152Z/blind-ledger.json --out /mpac/sdicks02/tmp/pc4-20261012T083152Z/ssh-sensitivity-pc4.json`
- **`sys.executable`:** `/mpac/sdicks02/tools/uv-python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12`
- **Version:** `3.12.13 (main, Aug  7 2026, 02:25:39) [Clang 22.1.3 ]`
- **Flags:** `ignore_environment=1` and `no_user_site=1`.
- **Timing:** 2026-10-12T08:32:18Z to 2026-10-12T08:32:20Z.
- **Exit code:** 0.
- **stdout:** `SSH sensitivity health ledger written; outcomes SEALED`
- **stderr:** empty (0 bytes).
- **Cleanup:** scratch `/mpac/sdicks02/tmp/pc4-20261012T083152Z` was removed at 2026-10-12T08:33:56Z, after the outputs were copied to 05 and their SHAs re-verified.

## Checks (`PC4/pc4_reviewer_check.py`, run with `python3 -I` on 05)

- `inputs_committed_sha`: PASS
- `equal_except_top_level_utc`: PASS
- `no_nested_utc_in_blocks`: PASS
- `schema_sealed_ledger`: PASS
- `entries_3072_2400_600_72`: PASS
- `logical_ids_unique_sorted`: PASS
- `logical_ids_eq_inventory_50f24dd6`: PASS
- `source_ids_eq_inventory_50f24dd6`: PASS
- `source_ids_eq_END_6f6f0007`: PASS
- `logical_ids_eq_END_6f6f0007_projection`: PASS
- `row_fields_match_inventory`: PASS
- `row_fields_match_END`: PASS
- `complete_sha256_eq_inventory_all`: PASS
- `interference_sha256_eq_inventory_all`: PASS
- `complete_sha256_unique`: PASS
- `v2_2361_legacy_711`: PASS
- `v2_iff_OP7_phase`: PASS
- `flags_eq_completion_9e788d20`: PASS
- `union_flag_derived`: PASS
- `flag_counts_recomputed_eq_sidecar`: PASS
- `flag_counts_population_totals_eq_completion`: PASS
- `per_host_flags_eq_completion`: PASS
- `hosts_1972_1100`: PASS
- `offhost_blocks_have_inventory_ACK`: PASS
- `ledger_54_events`: PASS
- `no_lost_source_in_ledger`: PASS
- `replacements_bound_to_ledger`: PASS
- `identity_entries_have_no_replaces`: PASS

**What these establish:**
- **Equality:** the PC4 output equals 48730da5 in every field except the top-level `utc` (schema, sealed, blind-ledger SHA, all 3,072 block entries and `flag_counts`).
- **Counts:** 3,072 entries, exactly 2400 primary, 600 guard and 72 descriptive.
- **IDs:** the logical IDs and (id, source_id) pairs equal 50f24dd6. The source IDs equal the `descriptor.id` set of 6f6f0007, and its `replaces or id` projection equals the logical IDs.
- **Proof SHAs:** every `complete_sha256` and every `interference_sha256` (3,072 of 3,072 are non-null) equals the inventory's.
- **Meter rules:** 2,361 v2 and 711 legacy. v2 is assigned if and only if the block's phase is OP-7 (replacement-r2 or r3).
- **Flags against 9e788d20:**
  - apt-flagged 0, apt `stop=True` 0, SSH `stop=True` 0, SSH-flagged 477, both 0, either 477.
  - Per-population and per-host totals equal the receipt.
  - The union flag equals `ssh OR apt` on every entry, and `flag_counts` recomputes exactly.
- **Durability:** 1,972 blocks are from 01 and 1,100 from 08. Every 08 block has an inventory off-host ACK SHA, which equals `verified_offhost_ACKs` 1100. The CLI also asserts that `hub-ack.json` exists for every non-01 block.
- **Proof/interference SHA:** the CLI re-hashes every `interference.json` against its proof, fail-closed.
- **Legacy flag replay, apt validation and paired v2 meters:**
  - **Legacy:** recomputed from bound LAN sources.
  - **Apt validation:** cgroup, four UIDs, helper exe evidence.
  - **Paired v2:** the `new_rule == apt_rule == RULE` assertion.

  All three are enforced by bb124cc4's fail-closed assertions, and the run exited 0 with empty stderr. I did not replay them separately, because I had no authority to open `complete.json` outside the CLI.
- **Dedup:**
  - Logical IDs are unique (the CLI asserts this too).
  - No source ID is a ledger-lost ID.
  - All 54 replacement entries are bound to a ledger event with a matching `replaces`.
  - Every identity entry has `replaces = null`.

## Disclosures (PC4 text 9b0704e2)

**Flag totals:** SSH 477; apt 0; both 0; either 477. There are 0 completed proofs with SSH `stop=True` and 0 with apt `stop=True`.

**SSH-flagged by population:** primary 379 of 2400, guard 98 of 600, descriptive 0 of 72.

**SSH-flagged by host and population:**

| host/population | SSH-flagged | total |
|---|---|---|
| 127x01/descriptive | 0 | 54 |
| 127x01/guard | 0 | 386 |
| 127x01/primary | 0 | 1532 |
| 127x08/descriptive | 0 | 18 |
| 127x08/guard | 98 | 214 |
| 127x08/primary | 379 | 868 |

**Mixed OP-5/OP-6/OP-7 meter regimes, by host and phase:**

| host | phase | regime (manifest) | meter rule | blocks | SSH-flagged |
|---|---|---|---|---|---|
| 127x01 | replacement-r1 | OP-6 (24817e16) | legacy-self-plus-reaped | 155 | 0 |
| 127x01 | replacement-r2 | OP-7 (488f6c8d) | OP-7-observed-child-credit-v2 | 1181 | 0 |
| 127x01 | replacement-r3 | OP-7 (488f6c8d) | OP-7-observed-child-credit-v2 | 512 | 0 |
| 127x01 | reporting | OP-5 (a7ebba64) | legacy-self-plus-reaped | 124 | 0 |
| 127x08 | replacement-r1 | OP-6 (24817e16) | legacy-self-plus-reaped | 399 | 352 |
| 127x08 | replacement-r2 | OP-7 (488f6c8d) | OP-7-observed-child-credit-v2 | 160 | 125 |
| 127x08 | replacement-r3 | OP-7 (488f6c8d) | OP-7-observed-child-credit-v2 | 508 | 0 |
| 127x08 | reporting | OP-5 (a7ebba64) | legacy-self-plus-reaped | 33 | 0 |

- **Meter rules by host:** 01 has 1,693 v2 and 279 legacy; 08 has 668 v2 and 432 legacy.
- **SSH-flagged by rule:** legacy 352 of 711, v2 125 of 2,361.
- All 477 SSH flags are on 127x08:
  - 352 in replacement-r1 (OP-6, legacy meter);
  - 125 in replacement-r2 (OP-7, v2);
  - 0 in r3 and 0 in reporting.

  127x01 has none.

**SSH-flagged by cell, primary:**

| cell | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|
| SSH / total | 6/48 | 8/48 | 8/48 | 7/48 | 8/48 | 8/48 | 8/48 | 8/48 | 5/48 | 6/48 |

| cell | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 |
|---|---|---|---|---|---|---|---|---|---|---|
| SSH / total | 7/48 | 8/48 | 8/48 | 8/48 | 8/48 | 8/48 | 7/48 | 6/48 | 9/48 | 7/48 |

| cell | 20 | 21 | 22 | 23 | 24 | 25 | 26 | 27 | 28 | 29 |
|---|---|---|---|---|---|---|---|---|---|---|
| SSH / total | 7/48 | 8/48 | 8/48 | 8/48 | 6/48 | 8/48 | 8/48 | 7/48 | 8/48 | 8/48 |

| cell | 30 | 31 | 32 | 33 | 34 | 35 | 36 | 37 | 38 | 39 |
|---|---|---|---|---|---|---|---|---|---|---|
| SSH / total | 9/48 | 9/48 | 7/48 | 8/48 | 7/48 | 9/48 | 8/48 | 6/48 | 8/48 | 6/48 |

| cell | 40 | 41 | 42 | 43 | 44 | 45 | 46 | 47 | 48 | 49 |
|---|---|---|---|---|---|---|---|---|---|---|
| SSH / total | 6/48 | 10/48 | 8/48 | 6/48 | 9/48 | 9/48 | 8/48 | 7/48 | 7/48 | 8/48 |

**SSH-flagged by cell, guard:**

| cell | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|
| SSH / total | 6/34 | 6/34 | 6/34 | 6/34 | 6/34 | 6/34 | 4/33 | 6/33 | 6/33 | 4/33 |

| cell | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 |
|---|---|---|---|---|---|---|---|---|
| SSH / total | 5/33 | 7/33 | 5/33 | 4/33 | 5/33 | 6/33 | 5/33 | 5/33 |

**Descriptive:** 0 SSH-flagged in every cell. The apt-flagged, both-flagged and either-flagged by-cell counts are in `ssh-sensitivity-pc4.json` → `flag_counts`. Apt and both are 0 everywhere, and either equals SSH.

## Findings

1. **PASS.** Every condition in R1 item 4 and in the PC4 text 9b0704e2 is met. No finding blocks either release route.
2. **Procedure note (not blocking).** `-E` makes CPython ignore `PYTHONDONTWRITEBYTECODE`; the probe shows `dont_write_bytecode=0`.
   - The run therefore wrote `__pycache__` inside the scratch tree only, and it was removed with the scratch directory.
   - No file under the interpreter tree is newer than the run start, and nothing was written under any job root.
   - For the post-landing rerun (§5.4), add `-B` if no bytecode at all is wanted.
3. **Consistency note.** 08's reporting phase stopped on `ssh_family_average_budget`, yet none of its 33 counted proofs has SSH `stop=True` or an SSH flag. That is consistent: the stopping block is not a completed counted proof.
4. **Still outstanding (outside this check).** §5.4 requires a second run from the landing commit's bytes, with an identical result except `utc`, once the narrow OP-7 landing is committed. The release reducer aebb2017's emitted ledger must also equal this sidecar except `utc` (R1 item 2, R7).
5. **Reviewer inputs.** The committed copies (from origin/main 9897216c and the tag), the archive and the raw copy-back are kept on 05 at `/mpac/sdicks02/tmp/pc4-review-20261012T083152Z/`, outside every job root.

## Files in `PC4/`

- `ssh-sensitivity-pc4.json` `ea3d44d337fd3b581f11ba70633744e84ccde84dd230ce9c0e6e8ecea3ae7ea4`
- `PC4-REVIEWER-CHECK-RECEIPT.json` (see its SHA in the reviewer's final message)
- `pc4_reviewer_check.py` `5c4cdada6d962ebf4bbb7e61a09547ca4f467a6078069ac90a6a4a824d393ed8`

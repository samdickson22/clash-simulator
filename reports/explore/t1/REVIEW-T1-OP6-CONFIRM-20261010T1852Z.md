# T1 OP-6 fast confirmation: CONFIRM

- Reviewer: independent T1 reviewer (Claude, on 127x05), for coordinator 0523ae6f, 2026-10-10T18:52Z
- Candidate: `d60586b33d5af83f04678d78f1525e4a74ef70cd` (unadmitted). Parent: `a2d434d5`. 13 files, 287+/22−.
- Scope: git plus local 127x05 only. No SSH to 01/03/04/08. No outcomes read. Reporting is untouched.

## Verdict: CONFIRM

OP-6 changes only the caps for rows that are already budgeted *and* whose bound family source is a LAN 129.65.221.0/24:22 connection. Which rows get budgeted is unchanged. Every other path keeps its OP-4/OP-5 rule. The reducer's primary path is unchanged in values and RNG stream. The sidecar carries only health data. Admission has two required follow-ups (F1, F2). There are three non-blocking notes (N1–N3).

## Packet integrity

- `git diff a2d434d5 d60586b3 | sha256sum` = `4f219191bd9cd5a0f22e550bb6e4a88650a48b1737d903495367b9f45550bd21`. That matches `op6.diff` and `packet.json`.
- In a clean `git archive` export of `d60586b3`, all **155/155** `FROZEN-T1.json` `files` hashes verify.
- The staged 08 overlay `op6-operations/candidate-overlay.tar` (`74a44b48…`) has 177 files, and all 177 are byte-identical to the commit. `qualification-stage.json` targets the fresh job `qualified-op6-08-r1` on 127x08 with `staged_only: true`. It preserves the old job `reporting-frozen-0108-r1`. It does not overlay 01's job.

## 1. The new thresholds apply only to the source-proven LAN ssh family

- **Who gets budgeted is unchanged.** `Families.apply` gives a row `ssh_budget` only when it is an approved idle member, or when `lan_connection(source)` holds for its authenticated UID 3822945 sshd ancestor's cached source. OP-6 does not touch `Families` or `ancestor` at all.
  - Unknown sources, conflicting sources (the cache resets to `None`) and non-LAN sources get no budget. They stay in the identity / `foreign_compute` path: an `sshd …@` with children, or python/raylet/cargo/…, is forbidden and stops.
  - Console users still return `console_user` first in `stop_reason`, which is unchanged.
- **The split.** A budgeted row is counted as `source_proven` only if `lan_connection(r['ssh_budget']['source'])` holds. Otherwise it is counted as `idle`.
  - Sample stop: `proven·2 > 3·hz·dt` **or** `idle·4 > hz·dt`.
  - Average stop (elapsed ≥ 60 s): `proven·10 > denom` **or** `idle·50 > denom`.
  - Flag: `proven·200 > denom`.
  - Fraction arithmetic gives exact 150% / 10% / 0.5% boundaries. The tests pin 150/151 ticks, 600/601 ticks and 30/31 ticks.
  - Pure idle services, with no LAN source, keep 25% / 2% exactly. That is tested at 25/26 ticks and 121 ticks over 60 s.
  - The DBus meter is untouched.
- **Heavy multi-process compute cannot hide under the caps:**
  - Metering is host-level and summed over *all* budgeted descendants, through the `increment` / `total_ticks` path, which is unchanged.
  - `total_ticks` includes `cutime+cstime`, which covers reaped children (`test_reaped_child_cpu_still_counts_at_new_caps`: 151 ticks, stop).
  - Two children at 80+71 ticks stop on the sample (`test_all_descendants_share_sample_budget`).
  - Anything above 1.5 cores in one sample stops immediately. Anything that averages above 0.1 core over a block of 60 s or more stops.
  - A process that double-forks or reparents away from the sshd loses its ancestor. It then has no budget and falls into the foreign path, which fails toward stopping.
- **Legacy meters.** A meter without the split defaults to `idle_ticks = ticks`, so it gets the old, tighter caps. `assert proven+idle == ticks` guards that.

## 2. Outcome-blindness

- **The sidecar is health-only.** `health_ledger` reads only `complete.json`, `interference.json` and `hub-ack.json`. Each entry records the logical id, source id, population, cell, host, `ssh_flagged`, `complete_sha256` and `interference_sha256`. The ledger also binds `blind_ledger_sha256`.
  - `complete.json` (`run.py:338`, `supervise.py:75`) holds the descriptor, timing and game **SHAs** only. It has no winner or loss fields.
  - The standalone CLI never opens `games/`. The test asserts that the ledger JSON contains no `games` or `loss`.
- **The primary path is unchanged.** `reduce.py` adds only `complete_sha256` to each row, and no statistic reads that field.
  - The sensitivity block runs *after* `outcome_release`, primary `population_stats`, `select` and `timing_stats`.
  - It builds its own `np.random.default_rng(seed)`, so the primary and timing generator streams are not consumed or reordered. The test asserts that the rows deep-equal the originals and that the primary `bit_generator.state` is unchanged.
  - `selection_eligible: False`. Each status is `DESCRIPTIVE_ONLY` or `NO_UNFLAGGED_BLOCKS`. The sensitivity results are never fed to `select`.
- **Nothing is read before release.** The sidecar's statistics are computed only inside the reducer, after the unchanged barrier. The pre-release CLI writes health data only.

## 3. Scope

- **What the diff touches:**
  - guard code: `ssh_budget.py`, plus one field in `supervise.py`;
  - the new `ssh_sensitivity.py`;
  - a reducer hook placed after selection;
  - `qualify.sh`, which only adds `test_op6.py`;
  - tests and the three OP-4/5 threshold expectations updated to the new caps (unchanged in kind);
  - the manifest, the receipt and the docs.
- **What it does not touch:** `run.py`, `schedule.py`, `replace.py`, `plan.json`, seeds, the barrier, the copier or the dispatch. 01's running supervisor executes its own job snapshot at fa8a1e2d. This commit does not modify that snapshot. The OP-6 overlay is staged only to the new 08 job.

## 4. The 08 rejoin plan is sound (existing reviewed rules, unchanged)

- **Completed blocks.** `replace.inventory` skips any block that has a durable hub `complete.json` with a matching seed, 8 game SHAs and, for non-01 hosts, a `hub-ack`. The 33 completed 08 blocks are therefore preserved and never reallocated. A completed block without a hub-ack fails closed through an assert.
- **Interrupted blocks.** Started but incomplete blocks become losses. They get fresh cell-, seat- and order-preserving replacement seeds via the ledger. Unstarted blocks keep their seeds.
- **Duplicates.** `load_blocks` and `health_ledger` both exclude lost ids and assert one completion per logical block.
- **Hosts.** `assert len(a.hosts)>=2`, "fewer than two named hosts; stop and amend". STOP-127x08 stays binding.

## 5. Tests

- **Clean export of `d60586b3`, on 05 with nice 19, using `venvs/t1-verifier` (numpy 2.5.3, pytest 9.1.1):**
  - the claimed nine-file set gives **114 passed**, matching the receipt;
  - the full `qualify.sh` list minus `test_anchor`, `test_coarse` and `test_belief` gives **133 passed, 1 failed** (`test_corpus::…complete_belief`).
- **Excluded or failing, environment only:** these three modules fail to collect on 05, and the one failure, `test_corpus::…complete_belief`, has the same cause. Each raises `ModuleNotFoundError` for `derived_public_state` or for the untracked `clasher.analysis.loss_review.delay_fixes`. None of these files is in the OP-6 diff. Fleet qualification runs them with the job's native runtime.

## Required before admission (not defects)

- **F1. Restore the manifest status.** `FROZEN-T1.json` status is `AWAITING_OP6_CONFIRMATION`. `barrier.reporting_release` asserts `status=='FROZEN'`, so the admission commit must restore `FROZEN` and record this review. This fails closed until then.
- **F2. Validate the sidecar before release.** Run the standalone health CLI `ssh_sensitivity.py --root <hub> --ledger <ledger>` before outcome release. In the reducer, sensitivity runs before `write(a.out)`, so any sidecar assert would abort the reducer before it writes the primary result. Those asserts are durability, interference SHA, legacy flag replay and dedup. The CLI runs the same `health_ledger` and turns any such abort into a pre-release health failure.

## Non-blocking notes

- **N1. Same seed value.** The sensitivity bootstrap uses a fresh generator with the *same* seed value as the primary (2026101040, the value given in OP6-T1.md). The streams are independent, but the resamples are correlated with the primary's. That is acceptable for a descriptive analysis.
- **N2. Idle members under a proven parent.** An approved idle member that descends from a LAN-proven sshd gets the proven caps, not the idle caps. That matches the "pure idle" wording.
- **N3. Mixed guard regimes.** 01's fa8a1e2d blocks ran under the OP-5 caps, while 08 and the new phases run under OP-6. The primary therefore pools blocks from mixed guard regimes. The sidecar's flags, which are replayed for legacy blocks, disclose this.

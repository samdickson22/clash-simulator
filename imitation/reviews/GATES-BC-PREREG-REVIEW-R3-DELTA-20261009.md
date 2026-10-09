# Independent pre-registration review, round 3 (final delta): gates (b) and (c), v1

Reviewer: Opus review sub-agent (DESIGN §7). Work ran 2026-10-08 ~23:55Z to 2026-10-09 ~00:10Z, read-only on 127x05,
with read-only `ssh` inspection of 127x02, 127x03 and 127x01 (hashing, `ls`, `ps`, `grep`). I started no games, jobs or
heavy work. I opened no gate (a) heldout output. This file is the only one written.

## Verdict: **APPROVED FOR FREEZE**

- gate (b) PREREG SHA256 `7524a4e14c70bab4304acd996ac910330bfc3f56d9bee295e4e7b237514fc347`;
- gate (c) PREREG SHA256 `8d565be1aad244a21790124f946b981e8cd6849da2ecb8d8269cd56ce1f021db`;
- final full snapshot tree `016b42fac2c40614fa55a8bb859a80893f6bea91c189a350d2f34fb3bab1b907`.

I found nothing that requires a change to either PREREG's bytes. That matters here: any non-seed text edit would change
H, and therefore every seed. The design, arms, counts, statistics, power and decision rules are the ones approved in
rounds 1 and 2. The only additions are the round-2 RC texts and the coordinator-decided namespace.

Freeze still has to carry out three steps the registration already requires (§6, F-1 to F-3). Launch has one condition
(L-1). None of them changes reviewed bytes, H or the snapshot.

## 1. Hashes I verified myself

| Object | Result |
|---|---|
| `imitation/gate-b/PREREG.md` | `7524a4e1…` ✔ = `r3-sealed/after-b.md` = `r3-seed-commitment-final/after-b.md` = `016b…/imitation/gate-b/PREREG.md` (05, 02, 03) = `confirmation-bc-v1/gate-b/evidence/PREREG.md` (03) |
| `imitation/gate-c/PREREG.md` | `8d565be1…` ✔, with the same five equalities (`gate-c/evidence` on 02) |
| `r3-sealed/index.json` | `5575fb39…` ✔ = `evidence/delta-r3-index.json` on 03 and 02 |
| Index `files` map | **393/393 files match on disk**; none missing |
| Snapshot `016b…` | manifest `35f94b5e…` on 05, 02 and 03 ✔. All 114 files re-hashed on 05 ✔. The tree hash recomputed with `snapshot.verify` semantics ✔ |
| `016b` vs `1cc0…` | Identical 114-file key set. **Only `imitation/gate-{b,c}/PREREG.md` differ.** The executable tree without the PREREG copies is `e35e83bf…` for both, equal to `source-code-tree-r3.json` and the PREREG pin ✔. The working-copy executed files equal `016b` |
| PREREG pin tables | All 53 path-backed rows per gate match on disk. The three runtime-data rows (catalog, natural and s2902 checkpoints) and `inputs-bc-v1/main02.pt` = `d77005d5…` were verified on 03 in `runtime-bc-v1`. The non-file pins (selection, release, seal, adapter freeze) are byte-identical to the round-2 text |
| Mask census pins | `BLOCKERS.md` `3e7de449…`, `blocker-census.json` `c9f23ffd…` ✔ |
| Staged freeze bundles | Every file in `confirmation-bc-v1/gate-b` (03) and `gate-c` (02) is hash-identical to its index entry: schedules, proposed seeds, merged audit, namespace, RC-3 interpretation, baseline, quiet-host, ledger r7, operations ✔ |

The PREREG-version chain from round 2 (`4ee3c55b`/`b38e4681`) to the candidate runs through r3-consolidation →
rc-text → wide-namespace-text → final-candidates → audit-archive → seed-commitment-final. The cumulative `r3-sealed`
patch covers it end to end. There is one unrecorded hop in (b), `147ec300…` → `0ff7bdb9…`: a single word, "depending
on" → "varying with", which was evidently changed to pass the registration guard's `pending` regex. It is
substantively nil (O-1).

## 2. Coordinator decisions: are they implemented correctly and honestly?

### 2.1 Fresh hash-committed namespace

- **I reproduced H independently.** I wrote my own implementation from the PREREG prose and did not import
  `seed_namespace.py`. It gives canonical bytes `8c7f0f40…`, **H = `e730c9f1…f49f50`** and **base = 1,359,319,908,352**,
  which is ≥ 2^40 and < 2^41. Both canonical documents equal the strings preserved in `namespace.json`.
- **The freeze round trip is exact.** I simulated `register.py`: it appends `\nConfirmation snapshot SHA256: <016b>\n` and
  rewrites `— DRAFT` → `— FROZEN`. `— DRAFT` occurs exactly once per document, and `— FROZEN` occurs nowhere in either
  draft. Re-canonicalizing the frozen text with the pinned `canonical()` gives the identical H. So the frozen documents
  will remain verifiable against H.
- **No circularity.**
  - Everything seed-dependent sits inside the delimited section: the formulas with base, the deck count of 42, the
    union, the audit figures and the artifact hashes.
  - The non-seed text holds no value that depends on H. The pins (`e35e83bf`, runtime inputs, receipts) all predate H.
  - The non-seed claim "zero eval_ood worlds" is structural, not seed-dependent. It holds in the old, the first wide
    and the final schedules: 320/128 eval and 0 eval_ood in all three.
  - The old deck count of "44" in the non-seed text was correctly moved into the seed section.
- **The seeds derive from H and base.** I regenerated all 4,356 integers from base and the registered formulas:
  - (b): 2 + 448 × 4 = 1,794;
  - (c): 2 + 512 × 5 = 2,562;
  - 0 cross-gate intersections;
  - minimum `1362137498353`, maximum `1362537972901`;
  - union SHA `c92f3383…` ✔.

  These equal `gate-{b,c}/proposed-seeds.json`, the merged audit's `proposed` and the staged files. Every
  `schedule.json` row seed equals base + formula, for all 448 and 192 pairs ✔.
- **No selection.**
  - The first wide namespace (`bdc74e65…`) was superseded by documentation edits (the 04 root cause), before any gate
    game. It is preserved in `prospective-wide-r3/`.
  - No game has ever run at either namespace's seeds. The wide qualification ran at ≥ 2^44.
  - With no outcomes, there was nothing to select on.
  - The disclosure (b:90–97, c:82–89) is accurate.
- **The merged audit** (`44af35a2…`) records:
  - `passed` and `complete_inventory`;
  - `errors`, `overlap` and `unresolved_errors` all empty;
  - 94 `raw_errors`, each with a resolution;
  - the 10-host set;
  - 26,434 enumerated historical values;
  - `coverage_definition` honestly scoped to "authorized scans plus bounds".

  `register.py`'s audit guard accepts it, and its `assert_complete_prereg` and `verify_namespace` both pass on both
  drafts (re-executed from the `016b` source).

  I separately checked 07's off-host bound (`127x07-offhost-candidate-r2.json`). Its largest integer is 8.6 × 10^9, so it
  has 0 hits in, and 0 values within, [min, max] of the new set.

  Ledger r7 has 48 rows, 0 unknown jobs and 0 intersections. Its jobs are mirror/training/perception jobs, exploration
  at ≥ 2^48, or administrative jobs.

### 2.2 NumPy full-width wrapper (`seed_compat.py`, `d5897eef…`)

- **Old behaviour is preserved.** For an `int`/`np.integer` value below 2^32, the original `np.random.seed` is called with
  the identical argument. Every other input passes through unchanged. Before the wrapper, seeds ≥ 2^32 raised
  `ValueError` in the legacy API, so they were never silently truncated. No previously valid call changes.
- **No aliasing.**
  - Above 2^32, `SeedSequence(int)` encodes the full integer exactly, then hashes it into 624 words. Distinct integers
    collide only with cryptographically negligible probability.
  - Array-seeded and scalar-seeded MT19937 states could coincide only by the same negligible chance.
  - All gate seeds are about 2^40.3, so every gate call takes the array path.
  - Both arms of every comparison get the same integer, and therefore the same state.
- **The scope is narrow.**
  - It is used only by `p16_adapter.py` and `legacy_audit.py`, around the unchanged P16 `eval.main`. It is a context
    manager that restores the original on exit.
  - Gate (b)'s C56 route never calls legacy `np.random.seed`.
  - `run_gate.py` changed only in the (c) P16/H2H branch, which adds `seed_offset`. (b) reads its seeds from the
    schedule, which already includes base.
- **My static consumer review** (see §5, F-2) found every gate-route consumer to be full-width:
  - C56 battle `random.Random(seed)` (`engine-rs/stage2_matches.battle`);
  - planner `np.random.default_rng(seed)` and `fair_player` `default_rng(seed+1)`;
  - standalone `torch.Generator().manual_seed`;
  - P16 `eval.py` `torch.manual_seed` / `np.random.seed` (wrapped) / `random.Random(matchup_seed+7919)` /
    `default_rng(+91117)` / `manual_seed(+271828)`;
  - the env `rng.seed`.

  The gate-route modules contain no mask, modulus, `int32`/`uint32` cast or ctypes narrowing on any seed. The empirical
  differentials agree:
  - `seed-compat-r1` and `wide-seed-search-r5` use s = 2^44 + 3,900,000,001 against 3,900,000,001, which is both
    s mod 2^44 and s mod 2^32, and against 1,752,516,353 = s mod 2^31. All differ.
  - `wide-seed-c-parity-r5` shows all six routes differing in initial decks between high and low seeds.
- **Comparability across arms is intact.** At the same wide seed and seat, P16 v1, natural and s2902 receive identical
  initial decks (checked row by row in `gates-bc-cqual-02-r5`). 02 and 03 match exactly on all 20 rows. In gate (b), the
  analysis asserts identical decks for B and A on every secondary pair, and for B's two seats on every primary pair.

### 2.3 04 overwrite incident

- **The disclosure (b:402–409, c:367–374) is accurate.**
  - The 03 archive `audit-bc-v1/127x04/inventory.json` hashes to `f65c0ade…`, matching the incident receipt and the
    merged audit's 04 source.
  - The 7 replaced shard blobs now carry 01's shard hashes. Their original hashes are in the archived 31-shard receipt
    and in no 01 receipt, so the merge used genuine 04 shards; it ended at 22:18Z.
  - `build_fresh_audit.py` (pinned `3c97a068…`) takes 04 only from `archived-merge-receipt.json` plus the incident
    receipt, and asserts 31/24/7.
- **Nothing in the audit depends on the replaced bytes.**
- **Residue (O-4).** The stale file `parallel-r4/127x04/shard-merge-receipt.json` (`4063eb31…`, in the index) is
  actually 01's merge receipt: inventory `48f051f5…`, 7 shards, under a 04 label. It is unused, but it should be
  labelled.
- **A point the text implies but does not spell out (O-5).** The mirror loop has run since Oct 7, so 04-local files under
  the mirrored trees could also have been replaced *before* 04's 22:02Z scan. That lost 04-only content is not
  enumerable. It is bounded the same way as f35: all historical seed conventions are below 2^34 or at least 2^44, and
  the hash-derived namespace sits at about 2^40.3. I accept this. The window is stated, and the root-cause receipt
  describes the mechanism.

### 2.4 07 offline

- 07 is still unreachable from 05 ("No route to host"), so the "07 returns" invalidator has not fired.
- The bound method, pinned `07-COVERAGE.md` (`dce4fee7…`) and `…-r2.json` (`59f65b8e…`), is unchanged from round 2.
- I re-checked it against the new namespace (§2.1).

### 2.5 RC-3 interpretation (no text change)

- `rc3-interpretation.json` records the baseline classes, the bounds, the marker and the sampling limitation. It is in
  both freeze bundles and is therefore pinned by the freeze manifest.
- `baseline-result.json`: 302.3 s, average 0.00853 core, peak 0.01786 core, no breaches ✔. `quiet-host-r3.json` (23:51Z):
  passed, blockers `[]` ✔.
- The marker exists on 03 (23:46:01Z) ✔. At 23:58Z, 03 had load 0.15 and no user, and no rsync was running.
- The cache service (PID 3838563) is a single-threaded v4 validation-cache fan-out at 0.1% CPU, pinned to 48–63/112–127.
  It started at 21:16:22Z, before r12 and r13, so it lies inside the qualified envelope. It is disclosed at b:276–277.
- The external monitor writes the shared `HALT.json` (`launch_with_baseline.py`, `monitor_baseline.py`). It is consistent
  with the registered interruption rules: active games finish and nothing is discarded.
- **I accept the interpretation.** RC-3's literal "any non-gate process" cannot be met on Linux: sshd and systemd have
  full affinity.
- **Gap (O-6, handled by L-1).** "Refuse launch if a competing workload overlaps 0–47 or 64–111" (b:278–279) is not
  enforced in code.
  - `run_host.py` records `admission.json` but asserts only the cache affinity.
  - The launcher checks a *pre-recorded* baseline receipt.
  - The monitor computes non-baseline overlaps only at exit, and HALTs only on a baseline-CPU breach.

  The rule is registered, so it binds the operator at launch.

### 2.6 R19 and RC-11/RC-12; allocation

- These are present as required (§3).
- Allocation:
  - (b) runs on 03 at 16, with load ceiling 20 (b:270–283);
  - (c) runs on 02 at 16, with load ceiling 64 (b:285–289 and the same in c);
  - the committed launch argv matches: 16 workers, 20 and 64, no `--include-siblings`.

## 3. Status of the round-2 required changes (RC-1 to RC-12; there is no RC-10)

Line numbers refer to the candidate bytes.

| RC | Status | Where |
|---|---|---|
| RC-1(a) title | **Resolved** | b:1, c:1: "— DRAFT" |
| RC-1(b) single final tree | **Resolved (equivalent form)** | b:362/c:316 pin the executable tree `e35e83bf`. b:389–391/c:343–345 name bundle `1cc0` plus a metadata-only successor. b:463–466/c:428–431 explain that the full tree is named by this review and appended by `register.py`, which avoids self-reference. b:185–191/c:152–158 mark the historical trees. Verified: `016b` = `1cc0` + PREREGs |
| RC-1(c) hosts | **Resolved** | b:270, b:285–289; c:224, c:239–243 |
| RC-1(d) admission numbers | **Resolved** | b:445–449, c:410–414. The r13 figures equal `final-pilot-03-r13.json` (30,352 decisions; p99 200.29657; max 202.22956; 7,965 rows; 0/0/0) |
| RC-1(e) and (f) stale lines | **Resolved** | "20 full smoke", "Re-snapshot", "REVIEW CANDIDATE", "NOT currently admitted" and "64 own processes" are all absent |
| RC-1(g) 22:38Z section | **Resolved (by removal)** | Removed rather than retained as historical. The bytes survive in `r3-sealed/before-*.md` and the r2 deltas (O-8) |
| RC-1(h) register guard | **Resolved** | `assert_complete_prereg` refuses `REVIEW CANDIDATE`, `pending` and `NOT currently admitted` outside sections headed historical. It passes on both drafts |
| RC-2(a) r13 | **Resolved** | b:281–283, b:445–453 |
| RC-2(b) gate (c) qualification | **Resolved** | c:349–358 and c:420–426. `gates-bc-cqual-{02,03,798e,2110}-r4`: 4 games × 5 routes each, all terminal, 0 rejections, 0 illegal. `cqual-r4-host-parity` and `cqual-r4-source-parity`: 0 differences. `cqual-02-topology-r5` is pinned. Wide r5 on `a8e5`: 20 per host, 0 differences. `a8e5`→`1cc0` differs only in `register.py` |
| RC-3 | **Resolved, with interpretation** | b:270–283, c:224–237, plus the RC-3 interpretation receipt (§2.5). Launch enforcement: L-1 |
| RC-4 | **Resolved** | b:234–242, c:201–209. It is implemented in `analyze_gates.py` `main()`: the replay receipt is mandatory, game-hash equality is enforced, a non-reproducing or unclassified B rejection adds `bars.integrity=False`, and (c) reports mismatches by protocol |
| RC-5 | **Resolved** | b:416–422, c:381–387. Pinned `offhost-rc5-bounds-r3.json`. The supplemental roots are among the merged-audit sources on 01/02/03/04/05/08. The f35 gap is closed by the coordinator's namespace decision |
| RC-6 | **Resolved verbatim in substance** | b:138–148 |
| RC-7 | **Resolved** | b:395–430, c:360–395, plus seed-section b:75–89. Covers the shard merges, 08 coverage, the own-input proof (`own-input-proof-r3.json`), ledgers r6 (pinned) and r7 (bundle), the 04 disclosure and the invalidators |
| RC-8 | **Substantively resolved; receipt gap** | b:427–441, c:392–406. The differentials and wide plumbing exist on all six routes. **No static consumer/type receipt exists** in `receipts/`, `operations/` or the progress log. My static review here (§2.2) fills it (F-2) |
| RC-9 | **Resolved** | `analyze_gates` `8710ab6b`, `render_reports` `63b8dc36`, `run_host` `e7ab1285`, `prepare_resume`, tests, r12, r13, the replay receipts, parity r4/r6, `07-COVERAGE`, the cqual receipts and the merged audit are all pinned. The review receipt names `016b` (this file) |
| RC-11 | **Resolved** | b:221–230, c:188–197 (pinned census, enumerated guards, engine-determinism criterion) |
| RC-12 | **Resolved** | b:254–266. Implemented in `rejection_episodes()`. Waits are excluded from the stream, because `smoke.py` `continue`s on 2304 before recording, which matches the episode definition. The exact paired-world sign-permutation test is enumerated by DP and labelled descriptive. No adjusted score is computed |

## 4. No unreviewed change to analysis, decision rules, arms, statistics or power

The cumulative diff from round 2 to the candidate is a restructuring plus the RC texts and the namespace. The text of the
arms, matching, counts, pass bars, multiplicity, interruption rules and gate (c) decisions is unchanged in substance.
The only removed rule is "all gate seeds stay below 2^32", which the coordinator's namespace decision supersedes.

The analysis code changed after round 2:

- `analyze_gates.py` `de2f9919…` → `8710ab6b…`;
- `render_reports.py`, `run_host.py` and both tests also changed.

The prior bytes are retained nowhere: I searched 05, 01, 02 and 03 (O-3). So I reviewed `8710ab6b` in full against the
registered rules.

**Gate (b):**

- The primary score is the mean over 640 games, which equals the mean of the 320 pair means.
- The CI is a whole-world bootstrap over 10,000 resamples with percentile bounds, seeded with base + 2817590002.
- PASS requires score ≥ .53 and LB > .50.
- Secondary: the mean over 128 paired worlds of B − A is compared against ≥ −.03.
- Timing:
  - the B pool is all decisions in 896 B games;
  - the A pool is 256 secondary games plus primary-opponent decisions;
  - the bar requires B over-250 = 0 and B p99 ≤ A p99 + 15;
  - integrity comes from the replay.
- Seed, deck, seat, completeness and duplicate assertions all run.

**Gate (c):**

- P16 has 384 keyed pairs with identical worlds, decks and levels asserted across the three policies. It uses the
  registered `compare.mcnemar` and `newcombe`, and PASS requires v1 win rate > natural and p < .05.
- H2H is indexed (cell // 3) × 64 + pair, with a pair-mean bootstrap seeded with base + 3217590002 and LB > .5.
- C56 is descriptive.

Everything matches.

The only executed-code changes after r13 are:

- (c)-only audit fields;
- the wrapper hookup;
- `run_gate`'s (c) offset;
- `register.py`.

I verified each step: `2110`→`df0b`→`f88e`→`a8e5`→`1cc0`. There is no `source-r16-delta` receipt for `f88e`→`a8e5`; I
diffed it myself (O-2). B's executed path (`smoke`, `search`, the stage5b player, the model) is byte-identical to r13,
so r13 admission carries over legitimately.

## 5. Threats to PASS/FAIL interpretability

None is new, and none blocks.

- The condition 2 and condition 3 operating characteristics are now stated (RC-6).
- A co-tenant burst on 03 can only push condition 3 toward FAIL, and A's >250 ms count is the registered host-noise
  control. L-1 and the marker contain the risk.
- The mask-v1 rejection asymmetry is a registered descriptive, and its cost falls on B.

## 6. Freeze and launch conditions (registered steps; no byte changes)

- **F-1 (freeze).** Ledger delta from 23:47Z to the freeze time, as the merged audit's own stated limitation requires.
  Any seeded job with an unknown range, or a range intersecting [`1362137498353`, `1362537972901`], blocks freeze.
  Coordinator decides.
- **F-2 (freeze).** Place this review file in both `confirmation-bc-v1/gate-{b,c}/evidence/`. Its §2.2 is the RC-8 static
  consumer/type review that the PREREG says is pinned before freeze. Alternatively, the worker adds an equivalent
  receipt.

  Each `approval.json` must name its own gate's PREREG SHA and `snapshot_tree_sha256 = 016b42fa…`:
  - (b): `prereg_sha256 = 7524a4e1…`;
  - (c): `prereg_sha256 = 8d565be1…`.
- **F-3 (freeze).** If 07 returns, or any pinned byte changes, before `register.py` runs, this approval lapses for the
  affected item.
- **L-1 (launch, gate b).** Immediately before launch on 03:
  - run a fresh `monitor_baseline`/quiet-host capture (≥ 300 s) with `nonbaseline_overlapping == []`;
  - require 0 console users;
  - require the marker to be present;
  - archive the capture beside `admission.json`.

  This executes b:278–279. Recommended but optional: have the monitor also HALT between games on any new
  non-baseline own process overlapping 0–47/64–111. That would be a pinned-operation change and needs a brief delta
  check.

## 7. Observations (no action required for freeze)

- **O-1.** (b) has an unrecorded intermediate, `147ec300` → `0ff7bdb9`: one word, to satisfy the `pending` guard.
- **O-2.** `source-r16-delta` is missing. I verified the content directly.
- **O-3.** The analysis-operation files changed after round 2 with no prior-byte copy kept. In future, archive before
  overwrite.
- **O-4.** The mislabelled stale 04 `shard-merge-receipt.json` should be quarantined or labelled.
- **O-5.** The pre-scan overwrite window on 04 is bounded by the namespace argument (§2.3).
- **O-6.** RC-3 launch enforcement is procedural, not in code (L-1).
- **O-7.** The "earlier qualified bound p99 200.362424 ms" traces to `runs/t6t8-final/summary.json` on 03. That file is
  not pinned. The figure is descriptive only.
- **O-8.** RC-1(g) was implemented by removal; the history is preserved in the deltas.
- **O-9.** The cache service remains a disclosed co-tenant on 48–63/112–127. It was present during r12 and r13.

---
**Verdict: APPROVED FOR FREEZE**:
- gate-b PREREG `7524a4e14c70bab4304acd996ac910330bfc3f56d9bee295e4e7b237514fc347`;
- gate-c PREREG `8d565be1aad244a21790124f946b981e8cd6849da2ecb8d8269cd56ce1f021db`;
- snapshot `016b42fac2c40614fa55a8bb859a80893f6bea91c189a350d2f34fb3bab1b907`.

Subject to registered freeze steps F-1 to F-3 and launch condition L-1.

Review file: `imitation/reviews/GATES-BC-PREREG-REVIEW-R3-DELTA-20261009.md`

## Addendum (~00:15Z 2026-10-09): secondary-world order (coordinator decision)

The coordinator decision is treated as given: the order stays **B0, B1, A0, A1**, the R20 fallback. It supersedes the
older interleaving suggestion. I checked that the candidate implements it correctly.

- **Text.** gate-b PREREG:161 reads "Secondary order B0,B1,A0,A1 in one worker; report timing per arm/host descriptively."
  - This is unchanged in substance from the round-2 bytes (`r3-sealed/before-b.md`:316).
  - b:156–163 keeps the surrounding rules:
    - timing bar 3 is evaluated over B's 896 games;
    - A's count of >250 ms decisions is the host-noise control;
    - seat 0 decides first, and the seat swaps balance controller order.
  - Gate (c) has no B/A secondary, so it correctly carries no such sentence.
- **Execution** (`016b` `run_gate.py`):
  - Each secondary world (`mode=='scripts'`) is assigned to a single worker, by `pair % workers`.
  - That worker plays it with `for arm in ('B','A'): for seat in (0,1)`, which is exactly B0, B1, A0, A1, on the same
    seeds and decks. Seat 1 reverses the scheduled decks for both arms.
  - On resume, completed receipts are skipped in that order, and nothing is re-ordered.
- **Reporting** (`analyze_gates.py` `8710ab6b`):
  - Per host, the report gives game count, nice level, thread count and max load1.
  - It also gives `timing_by_arm` for A and for B, each with p50/p99/max and the >200 ms and >250 ms counts. A's pool
    includes its primary-opponent decisions.
  - The analysis asserts that B's and A's decks are identical for each secondary seat.
  - Under the current allocation, the only host is 03.

**Confirmed: the order and the per-host timing reporting are stated and implemented correctly.** This is the order that
round 2 §4 accepted as fair on a dedicated 03, and it is the order r10–r13 qualified. The verdict above is unchanged.

Note for F-2: use this final version of the file (with this addendum) when placing it in the evidence bundles.

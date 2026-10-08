# Independent pre-registration review, round 2: gates (b) and (c), v1

Reviewer: Opus review sub-agent (DESIGN §7). Read-only on 127x05, 2026-10-08 ~22:20–22:50Z. Read-only `ssh` inspection
of run outputs on 127x03; no games, jobs or edits. No gate (a) heldout output was opened. This is the only file written.

## Reviewed content and what changed

The brief named `4590ec78…` (b) and `a163dfc2…` (c). Those hashes are verified: they equal
`gates-bc/review-r1/PREREG-gate-{b,c}.md` and `review-deltas/r2-required-changes/before-{b,c}.md`.
**The canonical files changed three times during this review.** This verdict applies to the newest bytes:

| File | SHA256 reviewed (newest, 22:42Z) |
|---|---|
| `imitation/gate-b/PREREG.md` | `4ee3c55b39fc19580f5d397c53c1de649b8f22bf52715537665cef6c5a06ca14` |
| `imitation/gate-c/PREREG.md` | `b38e4681cbf574baf7b3fb1744f1e9e04aa19a760141c637a12e0fded7481e35` |

Change sequence, each checked against `imitation/gates-bc/review-deltas/`:

1. **`4590ec78…`/`a163dfc2…` → `2549d76d…`/`a2012147…` (~22:33Z).** This version adds the "Required-review execution and integrity rules (R1–R21 delta)" section and the R3/R4/R5/R14 edits. It exists only inside snapshot tree `798e333b…`, as its internal PREREG copies; no delta file records it. It is a strict prefix of the next version.
2. **→ `e7eedf3c…`/`42bc8b41…` (22:38Z, `review-deltas/r2-required-changes/`).** Adds the GPU-bf16 waiver sentence and a "22:38Z evidence delta" covering:
   - the R16 result;
   - tree `798e333b…`;
   - r12 with 4 rejections, so 03 is *not* admitted;
   - the 02/03 stack match.
3. **→ `4ee3c55b…`/`b38e4681…` (22:42Z, `review-deltas/r2-r19-restatement/`).** Adds:
   - the binding R19 restatement and the r12 replay result;
   - the rejection-reporting rule;
   - candidate tree `211087027eeb448b…`, which supersedes `798e`;
   - a pins table;
   - r13 pending.

   It also rewords four earlier zero-rejection sentences.

Receipts I opened and verified by hash or content:
- `dev-forward-r2/{plan,result}.json`;
- `final-source-parity-r2/-r3.json`;
- `source-r12-delta.json`;
- `final-pilot-03{,-r11,-r12}.json`;
- `pilot-03-r1{0,1}-h2h-status.txt`;
- `rejection-02-r9-replay{,-with-guards}.json`;
- `rejection-03-r12-replay.json` (`09dfed64…`);
- `07-COVERAGE.md` (`dce4fee7…`);
- `inventories/127x07-offhost-candidate-r2.json` (`59f65b8e…`);
- `parallel-r4/127x0{3,4,8}/*`, including `truncated-bounds-r2.json` (`e689a8ea…`);
- `host-stack-0{2,3}-r2.json`.

On 03 I read:
- the r12 game receipts;
- the r12/r11 `load.jsonl`;
- the `798e`→`2110` snapshot-manifest diff and file diffs;
- the `gates-bc-high-seed-r1` outputs.

## Verdict: **APPROVE WITH REQUIRED CHANGES**

The design, arms, counts, statistics and decision rules remain sound, and every coordinator decision in the brief is now
written in. The R19 restatement is correctly stated and is supported by an exact replay. I am not approving freeze-pending-mechanical
because several items are **text**, not mechanics:

- the document names three different "final" trees and two contradictory admission states;
- the "dedicated 03" decision is contradicted by a co-tenancy sentence;
- gate (c)'s executed code changed after its last qualification, and no gate (c) route has been qualified on 02 at all;
- two history sources (f35, and leased hosts 09/11/16/18) are undisclosed;
- condition 2's operating characteristics are unstated, so the quoted gate power overstates the joint power.

All the fixes are cheap and none needs redesign. Nothing found warrants REJECT.

## 1. Status of round-1 items R1–R21

| Item | Status | Note |
|---|---|---|
| R1 technical interruption | **Resolved** | Text adopted. Executable HALT and console admission are in `run_gate.py` (`0c7a1be9…`), with the per-file delta in `source-r12-delta.json`. |
| R2 timing-bar scope | **Resolved** | |
| R3 eval_ood / deck concentration | **Resolved** | |
| R4 decisive pairs | **Resolved (text); pin pending** | `analyze_gates.py` changed twice during review (`09231df4…` → `de2f9919…`). The pins table has `de2f9919…`. Freeze must use that or re-pin (RC-9). |
| R5 power / MDE | **Partially** | The quoted power is for condition 1 only; joint power is lower (RC-6). |
| R6 resume / ledger | **Resolved** | |
| R7 / R17 hosts | **Partially** | 03@16 only, taskset 0–47, nice 10, ceiling 20; B-vs-A pilots done. But "≤64 own processes when sharing 03 with the v4 CPU grid" contradicts "dedicated", and SMT siblings 64–111 are not reserved (RC-3). |
| R8 pins | **Partially** | Pins table added. Stale `0ca7…` "final" tree remains; the bundle has no single authoritative pin block (RC-1). |
| R9 fair information | **Resolved** | |
| R10 gate (c) decisions | **Resolved** | |
| R11 truncation / draws | **Resolved** | |
| R12 spot replay | **Resolved** | |
| R13 seeds ≥ 2^31 | **Partially** | `gates-bc-high-seed-r1` ran all six routes at 3,900,000,001 (exit 0, tree `798e`). "Ran without error" cannot detect a silent mod-2^31 reduction. Differential check and static review are missing (RC-8). |
| R14 stale text | **Partially** | Still present: b line 107 "20 full smoke games … T5 hash"; c line 10 "requalify if model code changes during T4/T5"; both line ~172/155 "03@16 has passed … 01/04 are not yet admitted" (RC-1). |
| R15 source chain | **Resolved** | `final-source-parity-r3.json` (`71b6047a…`, tree `2110`): 20/20 model files equal manifest `2854ce1f…`, D1 deps equal the T2 hashes, with host, time and snapshot recorded. |
| R16 forward equality | **Resolved** | 4,096 dev rows: masks identical, top-8 identical with no tie exceptions, max legal Δ gate 2.4e-6 / card 3.8e-6 / tile 1.14e-5, NLL 0.34586. GPU-bf16 waiver written in. The dev population has 0 rows with >100 entities, which is disclosed (O-3). |
| R18 identical stacks | **Resolved for 02/03** | Python 3.12.13, Torch 2.10.0+cu128, numpy 2.3.5, identical config and freeze hashes. |
| R19 admission | **Resolved as restated, pending r13** | See §4. |
| R20 secondary order | **Resolved** | Allowed alternative chosen (B0,B1,A0,A1, plus per-arm timing by host). |
| R21 01 material | **Resolved** | |

Coordinator decisions in the brief:

| Decision | Written in? |
|---|---|
| Released checkpoint at T=1 with the post-T5 source; dev temperatures provenance only | Yes |
| (b) 03@16, ceiling 20; (c) 02@16; never co-hosted | Yes, but the v4-grid sharing sentence contradicts "dedicated" (RC-3) |
| R19 restated | Yes, correctly. In-gate replay consequence missing (RC-4) |
| GPU-bf16 waived | Yes |
| 07 by off-host bounds; 13 truncated archives bounded | 07 yes. Truncated archives and other raw-error resolutions are not yet mentioned in the PREREGs (RC-7) |
| Inventory "pending, mechanical" for 01/02/08 | Yes, but the exact append list and invalidators are not stated (RC-7) |

## 2. Statistics, power, decision rules, multiplicity

- **Gate (b) condition 1.** Unchanged and correct. The effective threshold is max(.53, .5+1.96·SE). Power at μ=.55 is .91/.82/.72 for q=.3/.4/.5, and the false-pass rate at .50 is ≤.025.
- **Gate (b) condition 2 has unstated operating characteristics.** The bar is a point estimate ≥ −.03 over 256 paired games, with no interval. The SD of the per-game paired difference is ≈ sqrt(.5(1−ρ)), where ρ is the correlation of B's and A's results on the same seed and deck.
  - For ρ = 0, .3 and .6, the SE is ≈ .044, .037 and .028.
  - So P(condition 2 FAIL | true Δ = 0) ≈ .25, .21 and .14.
  - By symmetry, P(PASS | true Δ = −.06) is about the same.
  - Joint power at μ = .55, Δ = 0 is therefore roughly .82 × (.75–.86) ≈ **.62–.71**, not .82, before condition 3.

  This is DESIGN's bar and I do not ask to change it. The PREREG must state it, so that a condition 2 FAIL is not read as a demonstrated regression and the quoted .82 is not read as gate power (RC-6).
- **Condition 3.** This is a zero-tolerance rule; see §4 for the detection limit.
- **Multiplicity.**
  - Gate (b)'s conditions are conjunctive (intersection–union), so there is no inflation.
  - Gate (c) has two separate decisions, each effectively one-sided at .025: McNemar with direction at p < .05 two-sided, and H2H LB > .50. They have separate consequences and no combined PASS, so the family-wise false-claim probability is ≤ .05. That is acceptable and should be stated (O-1).
  - Per-cell, family, style and rejection breakdowns are descriptive.
  - The B-minus-A rejection rate is explicitly "never a gate bar". Good.
- **Gate (c).** McNemar pairs seats separately, Newcombe is unpaired, both labelled. H2H power is .4–.55 and is stated. Truncated games are included. All correct.

## 3. 07 coverage, truncated bounds and audit completeness

**07.** The off-host bound is adequate and honestly disclosed.

- Every job window from 07's join (2026-10-07) through both outages is listed, each with an exact finite seed set or "no simulator".
- The possible delayed S1 r1 launch is conservatively included.
- The P16 identity set is kept as an exact set, not an interval (its interval spans the gate range).
- `bounds_passed: true`, `complete_inventory: false` and `exact_scan_passed: false` are all retained. Good.
- I recomputed the job seeds against all 4,356 proposed integers: 0 exact hits. Because S1 seeds exceed 2^32, I also checked aliases: 0 hits **mod 2^32 and mod 2^31**, with nearest alias distance 20.8 M.

Two dependencies must be stated:
- 07's recovery copies came from hub 01, so "copies are covered by home scans" depends on 01's scan, which is still running.
- If 07 returns before freeze, the real scan supersedes the bound.

**Truncated archives.**
- On 03, 11 of the 13 are bound by recomputed execution identities equal to the capture-plan byte hash. That is strong evidence.
- The other 2 (standalone episode-11 traces, seed 1,050,893,080) rely on the adjacent declared plan. That is weaker, but the seed is 1.77×10^9 below the gate range.
- 04's copies are byte-identical, and its 12 invalid gzip/NPZ files equal pinned synthetic-fixture bytes.
- 08 has the same 13 traces, and its reconciliation is pending.

This is adequate if disclosed in the PREREG audit section (RC-7).

**Gaps found that are not disclosed** (RC-5):

1. **f35.** `artifacts/OFFLOADED_TO_F35.md` records `artifacts/worktree-data` (archival pre-consolidation evidence) and `live-loop/l1/v3`, offloaded only to f35, which is down. Any f35-only job history (the f35 thread, 10-05/06) is also unreachable. Neither gate document nor the progress log mentions f35.
2. **Leased hosts 09/11/16/18.** These ran Clasher work: the lease P16 identity qualification (12/12) on the five original CPU hosts and on 09/15, T5 main02 on 11, T11 on 16/18, and perception on 09. They are outside the 10-host list. Their seeded content is probably bounded (the P16 identity set is the same fixed 12 worlds; training and perception have no simulator worlds), but this must be stated, like 07.
3. **Scan roots.** The 03/04/08/05 roots are `reports/`, `imitation/`, `jobs/clasher`, `clasher-eval-snapshots`, plus some `tmp/t5-*`. Repo `src/`, `scripts/`, `experiments/`, `configs/`, `tests/`, `checkpoints/` and `datasets/` are not roots, though the PREREG promises "Python and shell sources … seed formulas". My spot-check of those dirs on 05 (2,215 files) found **0 exact hits**. 01/04, which hold the bulk-offloaded `checkpoints/` and `datasets/`, were not checked by me.
4. **Overwritten evidence on 04.** `historical-docs.json` on 04 was replaced by a 127x01-labelled version from an unknown writer (PROGRESS 22:23Z). The original was used and preserved on 05. That is correct handling; it needs a disclosure line.

## 4. Timing fairness (single host 03) and admission on the final source

**Between-arm fairness.** It is structurally intact under the single-host allocation.

- **Primary.** A and B decide sequentially in one process on one 3-core set, with seat 0 first; the swap balances order. Proposals (B p99 ≈ 9 ms) are charged to B's own 200 ms.
- **Secondary.** B0, B1, A0, A1 run back to back in one worker. On a dedicated host, drift within a world is negligible.
- **Pinning and SMT.** Taskset 0–47 are 48 distinct physical cores; their SMT siblings are 64–111 (`lscpu`: CPU 64 → core 0). A co-tenant on 64–111 would slow both arms' search, and raise overrun risk, invisibly to the admission check. The pilots ran effectively dedicated (peak load1 19.59 for r11, 18.1 for r12), so "dedicated, siblings idle" is the envelope that was qualified (RC-3).
- **Rejection fallback.** In `smoke.py`, both actors share one apply loop. `apply_action` returns False, the command is dropped, nothing is retried, and the next decision comes 5 ticks later. For gate (c), the P16 env applies the same rule to both seats. The same fallback therefore holds for every arm, as the restatement says.
- **Who rejects.** All 10 observed model rejections were B: 6 in 02 r9 (seat 0) and 4 in r12 (seat 1, game 003). Each was a RoyalHogs or BombTower command repeated on consecutive decisions into a live TimedExplosive. A had 0 in ≈90k decisions. This cost falls on B, so it is conservative for B. The risk to interpretability is a post-hoc "mask-adjusted" reading of a narrow FAIL. RC-4 forbids that.

**Admission evidence on the final source.**

The candidate tree `21108702…` differs from `798e` in executed code:
- `smoke.py`, `p16_adapter.py` and `run_p16.py` gain per-card rejection tallies;
- there is a new `legacy_audit.py`, which monkeypatches `SelfPlayBattleEnv.reset` and `DiscreteTileActionSpace.apply_action` around the unchanged P16 `eval.main`.

I verified that the tallies run outside the controller timer and cannot feed a policy. The changes are audit-only.

- **Gate (b).** r12 on `798e`: 32/32 terminal, 29,744 B decisions, p99 200.270 ms, max 201.499 ms, 0 >250 ms, 0 illegal, 7,693 exact D1 rows, peak load1 18.1. Its 4 rejections reproduce exactly (`rejection-03-r12-replay.json`: 186-command stream exact, terminal 6001, TimedExplosive payload guard at `battle.py:1284`). Under restated R19 this supports admission. r13 on `2110` (started 22:41:37Z, same seed base 69175001) is the admission receipt for the final tree. Re-running the same seeds is legitimate here because the executed code changed. The PREREG also says it is not rejection selection. Good. r12 and r13 must both be reported, and neither replaces the other (RC-2).
- **Gate (c).** **Not qualified on the final source or on its host.**
  - r13 is a B-vs-A run and does not execute `p16_adapter`, `run_p16` or `legacy_audit`.
  - The only full-route real-checkpoint qualification (`gates-bc-closed-standalone-r1`) ran on **03** on an earlier tree.
  - Gate (c) executes on **02**.
  - The high-seed smoke exercised all routes, but on `798e`, on 03, at 2 games per route.
  - Gate (c) is wall-time independent, so exact action-stream equality is the right test (RC-2).

**Detection limit of condition 3.** B-vs-A pilots on 03 with timing-equivalent code (r10, r11, r12) total 90,115 B decisions with 0 >250 ms. Adding the 03 script-route final pilot gives 113,949. The maximum observed latency is 202.4 ms, so the 03 tail is tight while the host is dedicated.

That bounds the per-decision overrun rate only below ≈3.3×10^-5 (rule of three). The gate's B pool is ≈7.9×10^5 decisions (640 × ~930 + 256 × ~745). P(condition 3 passes) is:
- ≈ .92 at a true rate of 10^-7;
- ≈ .46 at 10^-6;
- ≈ .09 at 3×10^-6.

The pilots cannot distinguish these. A >250 ms event on 03 needs a ≥50 ms stall, which is a host event (co-tenant burst on siblings, reclaim, I/O), not B. That is why RC-3's isolation matters. Round 1's escalation E1 still applies and is the coordinator's call. The written rule (FAIL whatever the cause, A's count as control) is valid as registered.

## 5. Remaining threats to interpretability

1. **Unclear which tree and evidence are final.** Three trees are each called final (`0ca7`, `798e`, `2110`). The "Gate(b) allocation" paragraph still quotes r11 on `0ca7` as the admission pilot (RC-1).
2. **The audit is a snapshot in time.** Seeded jobs launched after a host's scan started are not in that scan. Examples since the scans: r12/r13 at 69.18 M, high-seed at 3.9×10^9. A post-scan launch ledger is needed (RC-7).
3. **Own-input exclusion.** 03's 4,356 raw hits are all in `inputs-bc-v1/audit-proposed-seeds.json`. Excluding it must be proven by content (seed-set hash `be64ed48…` = the union of the two pinned `proposed-seeds.json`), not by path (RC-7).
4. **`register.py` guard.** It rejects only `**TBD**` and only rewrites "— DRAFT". The current title "REVIEW CANDIDATE; INVENTORY PENDING" and the many "pending" lines would pass into `PREREG.frozen.md` unchanged (RC-1).
5. **In-gate rejection reproduction has no stated consequence** (RC-4).

## 6. Required changes

**RC-1 — both PREREGs: one authoritative final state; remove stale text.** Before freeze:

(a) Change the title to "— DRAFT" (replaced by FROZEN at registration) or "— FREEZE CANDIDATE".

(b) Replace "Final executable snapshot tree SHA256: `0ca7bf73…`" (b ≈187, c ≈170) with:
> "Final executable snapshot tree SHA256: `<freeze tree>`. It differs from `211087027eeb448bffdde4b0f9e5a99411abfe0afed84fdf828b59304af5dc37` only in the snapshot-internal PREREG copies (delta receipt `<path, SHA>`). Trees e3c6, ed42, 1fed, 506e, d992, 0f29, ab88, 0ca7 and 798e are historical. Their pilots are supporting evidence only."

(c) In "Execution is home CPU only…" (b ≈170–174, c ≈153–157), replace "Gate(b)03@16 has passed final-source B-vs-A qualification … 01/04 are not yet admitted" with:
> "Gate (b) runs only on 127x03 at 16 workers; gate (c) runs only on 127x02 at 16 workers. No other host is admitted for either gate."

(d) In "Gate(b) allocation", replace the r11 numbers with:
> "Admission evidence: r12 on `798e` (32 terminal B-vs-A games, 29,744 B decisions, p99 200.270 ms, max 201.499 ms, peak load1 18.1, 0 >250 ms, 0 illegal, 4 replay-reproduced occupancy rejections) and r13 on the final-equivalent tree `2110` (`<receipt SHA>`, `<numbers>`)."

(e) gate b line 107: replace "20 full smoke games with zero illegal actions, timing evidence; T5 hash" with:
> "per-host admission receipts as defined in the restated R19 paragraph; model source manifest `2854ce1f…`"

(f) gate c line 10: delete "Re-snapshot and requalify if model code changes during T4/T5."

(g) Keep the 22:38Z section as history, headed "(historical; superseded)".

(h) In `register.py`, also refuse freeze if the text contains `REVIEW CANDIDATE`, `pending` or `NOT currently admitted` outside a section headed "historical".

**RC-2 — admission on the final tree.**

(a) gate b, after "Requalification r13…":
> "r13 is the admission receipt for the final tree. It must meet restated R19 on its own: ≥20 terminal games, 0 >250 ms, 0 model illegal, ≥8 exact D1-skew games, exact candidate-count equality, peak load1 ≤ 20, and every rejection reproduced by exact replay. r12 and r13 are both reported; neither replaces the other. If r13 fails any criterion, 03 is not admitted and the coordinator decides. No further pilot on these seeds is run to obtain a passing result."

(b) gate c, new paragraph "Gate (c) qualification on the final tree and host":
> "Before freeze, on 127x02 with the final tree and real checkpoint (plumbing seeds disjoint from all gate namespaces, outcomes not computed): (i) ≥4 games per route: P16 v1, P16 natural, P16 s2902, H2H and C56 standalone. Zero exceptions, zero v1 illegal actions, and every rejection reproduced by exact replay and classified to a known occupancy guard. (ii) Exact action-stream equality on the same seeds between 02 and 03, and between tree `2110` and tree `798e` for every route. This proves that the audit-only changes, including the `legacy_audit` monkeypatch of `reset`/`apply_action` around unchanged `clasher.rl.eval`, leave behaviour unchanged. (iii) Record admission topology and co-tenant processes for 02. Any mismatch blocks freeze."

**RC-3 — gate b "Gate(b) allocation": a dedicated host and SMT siblings.** Replace "Maintain at least 16 free threads, and no more than 64 own processes when sharing 03 with the v4 CPU grid." with:
> "127x03 is dedicated to gate (b) from the first world to the last. No other own CPU workload runs there: no v4 grid, seed scans, builds or bulk copies. Receipt mirroring under 1 MB/s is the only exception. Gate workers use physical cores 0–47. Their SMT siblings 64–111 host no own process. Any non-gate process with affinity overlapping CPUs 0–47 or 64–111 is recorded in the launch admission receipt (`lscpu -e`, all non-gate PIDs with affinity and threads), and the gate does not start while one exists. Load1 > 20 or a console user pauses new worlds; active worlds complete."

**RC-4 — both, the R19 restatement section: in-gate reproduction and no adjusted scores.** Append:
> "After all games of a gate complete and before any outcome analysis, every model-command rejection in every protocol is replayed by exact recorded-action replay. The replay reports only reproduce/classify per rejection. A rejection that does not reproduce, or does not map to a known occupancy guard, is reported as non-deterministic. For gate (b), any such B rejection fails condition 3 (integrity), whatever its count. For gate (c), any such rejection is an exact-replay mismatch under R12 and is reported with the affected protocol's verdict. No rejection-excluded, mask-adjusted or 'what-if' score is computed or used for any decision."

**RC-5 — both, seed-audit section: disclose and bound f35 and the other leased hosts.** Append:
> "History not reachable by the 10-host scans: (i) f35, down since 2026-10-06. It holds the only copies of `artifacts/worktree-data` and `live-loop/l1/v3` (`artifacts/OFFLOADED_TO_F35.md`) and any f35-only job outputs. (ii) Leased 127x09/11/16/18, which ran the lease P16 identity qualification (the fixed 12-world identity set), T5/T11 training and perception, with no other simulator worlds. Each is bounded from off-host records (manifests, job catalogs, source formulas), as for 07: `<receipt, SHA>`. Any unboundable item goes to the coordinator before freeze. The scan roots are listed per host. Repo `src/ scripts/ experiments/ configs/ tests/ checkpoints/ datasets/` are either added as roots on every home host or covered by a recorded literal/formula sweep of those paths: `<receipt, SHA>`."

**RC-6 — gate b, "Sample-size premise": state joint operating characteristics.** Append:
> "These figures are for condition 1 alone. Condition 2 is a point bar over 256 paired games with SE ≈ .03–.045, depending on the within-seed B/A correlation. It fails with probability ≈ .14–.25 at true Δ = 0, and passes with about the same probability at true Δ = −.06. Joint power for conditions 1–2 at μ = .55, Δ = 0 is therefore ≈ .62–.71 before condition 3. A condition 2 FAIL is not evidence of a regression of that size, and a PASS is not evidence of non-inferiority. Pilots (≈ 9×10^4 B decisions on 03, 0 >250 ms) bound the overrun rate only below ≈ 3×10^-5. Over ≈ 7.9×10^5 gate decisions, condition 3 passes with probability ≈ .92 at a true rate of 10^-7 and ≈ .46 at 10^-6."

**RC-7 — both: the exact mechanical appendix required before freeze, and its invalidators.** Replace the closing "Merged 10-host … pending, mechanical" paragraph with:
> "Before freeze, append and have reviewed: (1) 127x01 and 127x02 parallel scans complete: every shard merged exactly once; inventory SHA; single-process comparison passing for every unchanged file; raw errors listed. (2) 127x08 formula review (the current file is empty) and its 13 truncated-trace bound reconciliation, plus the absent-root receipt. (3) The merged 10-host audit. It records per host the method (direct scan, or off-host bound for 07) and roots. It keeps `raw_errors` with each resolution: truncated bounds (`truncated-bounds-r2.json`, `truncated-bounds-identity.json`), synthetic fixtures (`synthetic-fixture-bounds.json`) and absent roots. `unresolved_errors` is empty. Proposed seeds include every derived offset of both schedules. Cross-gate disjointness holds, and invocation ranges are reconciled for every formula. (4) Own-input exclusion proved by content: `audit-proposed-seeds.json` seed-set SHA `be64ed48…` equals the union of the pinned proposed-seeds files. (5) The 04 `historical-docs.json` replacement, disclosed: the original on 05 (`169cc550…`) was used; writer `<identified|unknown>`. (6) A post-scan launch ledger: every seeded job launched on any audited host after that host's scan start, with its seed bounds (including pilots r12/r13 and `gates-bc-high-seed-r1`). (7) The RC-5 bounds and the RC-8 evidence. Any of the following invalidates the appendix and returns to review: an exact or formula-range intersection with any gate seed or derived seed; an unresolved unreadable file; a missing or duplicated shard; roots differing from those declared; a changed hash of a previously compared file without explanation; 07 returning before freeze (a real scan then supersedes the bound); any edit to a schedule or proposed-seeds file; any executed-code change after r13 or the RC-2(b) runs."

**RC-8 — both, R13 sentence: make the high-seed check able to detect truncation.** Append:
> "Evidence: `gates-bc-high-seed-r1` (all six routes at 3,900,000,001, tree `798e`), plus a differential check. Each route runs at s and s − 2^31 and must give different decks or initial state, and every recorded seed field, including derived seeds, must equal the intended value. A static review lists each seed consumer and its integer type. Receipt `<path, SHA>`."

**RC-9 — both, pins table.** Re-pin `analyze_gates.py`, `render_reports.py`, `test_analysis{,_c}.py` and `run_host.py` at their freeze bytes. `analyze_gates.py` changed twice during this review. Add rows for:
- the r13 receipt;
- `rejection-03-r12-replay.json`, which is already present;
- `final-source-parity-r3.json`;
- `07-COVERAGE.md` and `127x07-offhost-candidate-r2.json`;
- the RC-2(b) gate (c) receipts;
- the merged audit.

The review receipt for `register.py` must name the final freeze tree. That tree contains these PREREG bytes, so it is not `2110`.

## 7. Optional suggestions

- **O-1.** Gate (c): state that its two decisions are each at one-sided .025, so the family-wise false-claim probability is ≤ .05. Also clarify that "Report all protocols, even if another fails" refers to failing bars. An incomplete protocol makes the whole gate "not completed, no verdict", per the R6 rule and `analyze_gates`' exact-count check.
- **O-2.** Report descriptively, per arm: rejection streaks (the same command rejected on consecutive decisions, as seen in r9 and r12) and decisions lost to them. Report no outcome conditioning.
- **O-3.** The dev population has no >100-entity rows. Report, descriptively, the count of gate decisions whose entity count exceeds 100. The R16 parity does not cover that regime, although serving and scorer share code.
- **O-4.** Round-1 O1/O2/O5/O6 (searched-only p99 and overshoot distribution; deck-clustered sensitivity; engine-drift comparison against historical P16 rates; holdout-deck exposure) are still worth adding as descriptive outputs.
- **O-5.** Record the PREREG intermediate `2549d76d…`/`a2012147…` (inside tree `798e`) in a delta file, so every PREREG hash that ever entered a snapshot has a diff on record.

---
**Verdict: APPROVE WITH REQUIRED CHANGES** (RC-1 to RC-9). Freeze needs: those text changes; r13 passing; the RC-2(b) gate (c) qualification on 02; the RC-7 mechanical appendix; and a delta review of the final bytes limited to these items.
Review file: `imitation/reviews/GATES-BC-PREREG-REVIEW-R2-20261008.md`

## Addendum (~22:52Z): r13 completed

After the text above was written, `gates-bc-pilot-03-16-r13` exited 0. I read it on 03 (read-only):

- tree `211087027eeb448b…` verified;
- 32/32 terminal B-vs-A games;
- 30,352 B decisions, p99 200.297 ms, max 202.230 ms, 0 >250 ms;
- 0 rejected and 0 illegal commands for both seats;
- 7,965 exact D1-skew rows;
- candidate-count equality in all 32 games;
- peak load1 18.0.

On its face this meets RC-2(a). The worker still has to publish and pin its receipt, and RC-1(d) must quote it.

The pooled 03 B-vs-A evidence is now 120,467 B decisions with 0 overruns, a rate bound of ≈ 2.5×10^-5. That does not change §4's detection-limit conclusion.

The PREREG hashes are unchanged since the review (`4ee3c55b…` / `b38e4681…`). Nothing in RC-1 to RC-9 is resolved by r13 alone, and the verdict stands.

**Verdict: APPROVE WITH REQUIRED CHANGES** — `imitation/reviews/GATES-BC-PREREG-REVIEW-R2-20261008.md`

# Addendum B (~23:05Z): late coordinator facts, the soundness of R19, and the B-only rejection imbalance

## Versions

The canonical PREREGs are unchanged since the main review: b `4ee3c55b…`, c `b38e4681…`. They are byte-identical to the
sealed `review-deltas/r2-r19-restatement/after-{b,c}.md`, whose delta is from `e7eedf3c…`/`42bc8b41…`; I checked that
delta's predecessor `r2-required-changes/` (from `4590ec78…`/`a163dfc2…`) in the main review. No newer bytes exist.

## Fact (2): the tree change and the 0 → 4 rejections

`source-r12-delta.json` confirms that tree `798e` (r12) changed only `run_gate.py` (HALT/console guard, checked between
games) and the two PREREG copies. That change cannot select or alter an in-game action. r11's 0 versus r12's 4 is
explained by wall-time-dependent search choices on the same seeds, not by the code change. The exact replay
(`rejection-03-r12-replay.json`) reproduces all 4 rejections with no search, inference or deadline, which confirms it.

**One correction to the brief.** The final candidate tree is `2110…`, not `798e`. It also changes *executed* audit-only
code: per-card tallies in `smoke.py`/`p16_adapter.py` and the new `legacy_audit.py` wrapper. The admission receipt for
that tree is r13: 32 B-vs-A games, 0 >250 ms, 0 rejections, 0 illegal, peak load1 18.0. The gate (c) routes on 02 are
still unqualified (RC-2b).

## Is the R19 restatement sound?

**Yes.**

- In the simulator, time pauses during a decision, and the chosen command is applied at the same tick. A command
  therefore cannot become stale, and load can change only *which* action is chosen, not whether the engine accepts it.
  The right test is engine determinism given the recorded action, and exact recorded-action replay is exactly that test.
- Which action search picks under deadline pressure is part of play for both arms.
- Mask v1 is part of the frozen, qualified serving stack. Changing it now would be an unqualified post-design change,
  and mask v2 is correctly confined to future consumers.
- I verified in `smoke.py` that both actors share one apply loop. A rejection drops the command, with no retry,
  replacement, elixir loss or cycle mutation (the guard returns before `play_card`), and the next decision occurs
  normally. The P16 environment applies the same rule to both seats. The "identical fallback" claim is therefore true.

**Is it correctly written?** Yes, in both PREREGs' "Binding R19 restatement" sections, with three refinements:

1. **RC-4 still applies.** The text defines the consequence of a non-reproducing rejection only for *qualification*. It
   must also cover gate games, with the outcome-blind post-completion replay and the "no adjusted score" sentence from
   RC-4.
2. **RC-11 (new), both, R19 section.** Replace "classify as a known occupancy guard" with:
   > "classify as one of the occupancy guards enumerated in the pinned census `reports/mask-v2/BLOCKERS.md` (SHA256 `<pin>`) and `reports/mask-v2/blocker-census.json` (SHA256 `<pin>`): a `TimedExplosive` `blocks_deployment` payload (BalloonBomb, GiantSkeletonBomb, BombTowerBomb, SkeletonContainer, MightyMiner ability bomb), live-building footprint or air collision, or crown-tower command exclusion. Any other guard is unclassified and is treated as non-reproducing."
3. **Clarify in the same section:** "The criterion concerns the engine's determinism for the recorded command. The command's selection under the wall deadline is part of play."

## Does the B-only imbalance (4 vs 0) threaten fairness or interpretability?

**Evidence** (all four 03 B-vs-A pilots r10–r13, 128 games, computed from per-game receipts):

| Arm | Non-wait commands | Rejected | Games affected |
|---|---|---|---|
| B | 8,781 | 4 (4.6×10^-4) | 1 |
| A | 8,718 | 0 | 0 |

- Rejections come in **streaks**: the same blocked command is re-chosen on consecutive decisions while the payload lives
  (r9: 3+3; r12: 4). The independent unit is therefore the *episode*, and the comparison is 1 episode versus 0 in 128
  games. That is not statistically distinguishable (p = 1 at episode level; even treating commands as independent,
  Fisher p ≈ .12).
- The mask v2 audit (`reports/mask-v2/summary.json`, `eddd91a0…`, 100k recorded states) puts v1's false-positive rate
  at 1.06×10^-4 per legal placement bit. It is concentrated in states with a live payload: 4.96×10^-3 per bit versus
  ≈1×10^-5 to 1×10^-4 without one. 1.35% of states have at least one false-positive bit.
- Humans' v1-legal actions are engine-rejected at 3/4,278 = 7.0×10^-4. B's command rate (4.6×10^-4) is at or below that
  human base rate. That fits a mechanism in which B imitates human placement habits, such as re-placing on the tile
  where a Bomb Tower just died or sending Royal Hogs onto a death bomb. A's random placements rarely hit the exact
  blocked tile.

**Fairness.** Not threatened.

- Deck and seed exposure is identical by design: in the primary, each controller plays each deck once per world, and
  the secondary uses identical seeds and decks per arm.
- The engine rule and the fallback are identical for both arms.
- The remaining difference comes from which placements each arm proposes. That is a property of the arm, and under the
  frozen stack it is legitimately part of what gate (b) measures.
- The cost falls only on B: lost tempo for about 1–2 s of game time per episode, with no elixir lost. Its direction is
  **against** a PASS.

**Interpretability.** This is a real but small caveat, and it belongs in the report as a predeclared descriptive, not
as a bar or adjustment.

- **Magnitude.** At the pilot rate, the gate's ≈6×10^4 B commands imply about 28 rejections in about 5–8 episodes.
  Exposure is real: 218 of the 448 gate (b) worlds include a payload card, and 92 include both Royal Hogs and Bomb Tower.
  Even the implausible bound in which every episode decided a game moves the primary score by ≲ .01. The realistic
  effect is far smaller than the primary SE (.015–.020).
- **What it limits.** Gate (b) measures B under mask v1. A FAIL near the bar does not show that imitation proposals are
  useless with mask v2, and a PASS slightly *understates* B's benefit under v2. Neither changes any verdict.

**RC-12 (new), gate (b), the R19 section's reporting paragraph.** Append:
> "Predeclared descriptive, never a bar or adjustment. Per arm and protocol: non-wait command attempts; rejected commands and the rate; rejection episodes (maximal runs of the same rejected command by one controller in one game); games with at least one episode; per-card counts; and the guard classification from replay. Report the B-minus-A difference in rejection rate and episode count, with an exact two-sided episode-level test labelled descriptive. The report states that rejections arise from the shared mask-v1/engine occupancy gap, that the fallback is identical, that the cost falls on the arm that chose the command, and that gate (b) measures B under mask v1. No conclusion about mask v2 is drawn. No rejection-excluded, mask-v2-filtered or otherwise adjusted score is computed."

Optionally (O-6), as a descriptive count only: how many of the recorded rejected commands the pinned mask v2 would have
masked, computed by replay after completion.

## Verdict after Addendum B

Unchanged: **APPROVE WITH REQUIRED CHANGES**. The required changes are now RC-1 to RC-12. The R19 restatement is sound and
correctly drafted; RC-4 and RC-11 complete it. The 4-versus-0 imbalance is not a fairness threat. It should be a
disclosed, predeclared descriptive (RC-12) with the mask-v1 scope caveat.

**Verdict: APPROVE WITH REQUIRED CHANGES** — `imitation/reviews/GATES-BC-PREREG-REVIEW-R2-20261008.md`

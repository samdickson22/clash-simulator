# K4S run r1, round r2: receipt erratum (audit PASS_WITH_NOTES)

- **Recorded:** 2026-10-12T09:07:51Z (`date -u`), on 127x05, following the coordinator's cut-2 rulings on the round r2 audit.
- **Audit:** `audits/ROUND-r2-AUDIT.md`, retained verbatim, sha256 `4b89ddc212ca1a5e8ed748eedb52f3a38472f0e4091a6f5b5a403f88eda1f513`.
- **The r2 launch stands.** `rounds/r2/RECEIPT.json` (`95e93ac8…`) is not edited. This erratum supersedes it where they differ.

## F2: `tools/checkpoint.py`, under-described change and a running/committed divergence

- **The full diff** from the committed 7ee26396 version to the committed b5530e98 version:
  - file `reviews/CHECKPOINT-DIFF-7ee26396-b5530e98.diff`;
  - **sha256 `52cd4583d901c7a0ccd22b850252476d746a397e38770f802bd4df7e3247b941`**;
  - blobs `da2d5bd1` → `54f25dca`; file sha256 `87eec355…` → `40cca772…`, which equals the running copy on 05.
- **What the receipt omitted.** Besides the mechanical part (namespace default r2, per-host `EXPECTED` 555/554 with the `exp[h]` unwrap), the diff **replaces the alert gate**:
  - **Removed:** the 11105b3f per-phase alert, "lost blocks approaching 10% of a replacement cap" at ≥24 primary or ≥7 guard lost *in the current phase*.
  - **Added:** a ledger-cumulative gate per Option A (afe83faa):
    - cumulative lost (ledger events plus the current phase's failed blocks) ≥150 primary or ≥45 guard;
    - ledger max `replacement_k` ≥9 primary or ≥7 guard.
  - **Added:** a `cumulative_lost` record in each health JSON, and the summary text "lost this phase … cumulative …/300 … ledger max k …".
- **Divergence window:**
  - The gate rewrite was applied to the running 05 copy at **2026-10-11T22:37:02Z** (session log).
  - It first ran in the 22:41:59Z checkpoint (committed health JSON 277cfc78 carries `cumulative_lost`).
  - It was first committed at **2026-10-12T08:58:42Z** (b5530e98).
  - **For about 10 h 22 min**, the health tool that ran (new gate) differed from the committed tool (da2d5bd1, old gate). Every health JSON committed in that window was produced by the new gate.
  - The earlier namespace/EXPECTED edit (2026-10-11T22:31:30Z) was committed 17 s later in 7ee26396 (22:31:47Z), so it did not diverge.
- **Effect:** health and alerting only. The tool never stops, launches or edits a job. The new gate is the Option A escalation rule. The old rule's 24/7 thresholds had already been superseded by Option A's 150/45. No alert was missed: cumulative losses were 25/8 throughout, then 41/14, and max k ≤2.
- **Review:** a narrow Sol review of this diff is requested via the coordinator. Until then the tool is used unchanged (health only, per the ruling). The same review is asked to cover the F5 k-gate tightening below.

## F1: `tools/aptquiet_remote.sh`

- **Status:** new, unreviewed, fails open, and aborts under strict mode. It was run on 03 between 08:40Z and 08:57Z on 2026-10-12 for the step-6 reads.
- **Shelved:** the original bytes are moved to `tools/shelved/aptquiet_remote.sh`. The committed `tools/aptquiet_remote.sh` is replaced by a stub that refuses to run (exit 2).
- **Replacement:** from cut 2 on, step-6 reads use only the coordinator's inline strict-mode command (`CYCLE-CHECKLIST.md` step 6). Its full stdout and exit code are recorded.
- **r2 quiet-state evidence**, independently of the script:
  - the frozen host admission (0 foreign, 0 active);
  - the apt-lists and stamp times;
  - the 08:58:05Z health (apt flags 0).

## F4: exact times (`date -u`), replacing the rounded receipt values

| Event | Receipt said | Exact |
|---|---|---|
| "03 quiet" posted | 2026-10-12T08:47:47Z | 2026-10-12T08:47:47Z (unchanged) |
| coordinator GO to the builder | ~08:48Z | **2026-10-12T08:48:14Z** (PROGRESS) |
| builder "released" | (absent) | builder receipt fa8e700a committed 2026-10-12T08:51:48Z; "released" stated at 08:51:50Z (audit) |
| coordinator forwarded "released" | 08:52Z | **2026-10-12T08:52:16Z** (my `date -u` at receipt; the audit cites 08:52:17Z for the forward) |
| 30-min timeout | not reached | 2026-10-12T09:18:14Z |

## F3: hash gaps

The listed artifacts are not recoverable byte-for-byte for r2, because they were not persisted. From r3 on, the round receipt carries their hashes (`CYCLE-CHECKLIST.md` step 7).

## F5: k index

**Definition.** PREREG-K4S r3 §3.4 (sha 9650972d…): "the k-th lost block in cell c is replaced by seed 3000 + 50k + c (primary) or 900 + 18k + c (guard)", with caps "k ≤ 11 primary, k ≤ 9 guard".

**Frozen mechanics fix k as 0-based:**
- `schedule.replacement` sets `k = number of earlier ledger losses in the same cell`, so the first replacement has k = 0, and it asserts `k ≤ max_k`;
- `plan.json` has `max_k` 11 / 9;
- the replacement seed banks hold 600 = 50 × 12 (primary) and 180 = 18 × 10 (guard) rows, i.e. k = 0…11 and 0…9.

So `replacement_k` is a 0-based index, and the replacement count in a cell is `replacement_k + 1`.

**The two readings of the gate differ by one step:**

| Reading | Option A "within 2 of the k limit (11/9)" |
|---|---|
| Index | escalate at `replacement_k` ≥ 9 / 7 |
| Count | escalate at 9 / 7 replacements in a cell, i.e. `replacement_k` ≥ **8 / 6** |

**Applied: the stricter reading.** Escalate when the ledger max `replacement_k` is ≥8 primary or ≥6 guard (a count of 9 / 7).
- It is applied by hand at every inventory (step 3) and read from every health summary ("ledger max k").
- The health tool's automatic alert still fires at 9 / 7 until its reviewed update.
- Current values: max k primary 2, guard 1.

## Disclosure: K4S qualification during the 03 read window

**What ran:** K4S's own fresh r2 qualification on 03 (driver PGID 2102837) ran from 2026-10-12T08:39:43Z to 08:54:59Z. That covers 03's apt-daily (08:47:17Z), the "03 quiet" post (08:47:47Z) and the builder's read (08:49:03–08:51:29Z, per 4d5791da).

**What "03 quiet" certified:** that the K4S reporting phase had exited (no supervisor, no owned groups), the apt units were inactive, no apt process remained and there was no console user. **03 was not idle:** the qualification driver (nice 10) was running.

**Effect on either party:** qualification passed 28/28, including its tolerance checks, and the builder's read was bounded by SHA checks.

**For future windows:** "03 quiet" will state whether any K4S qualification or other owned process is running.

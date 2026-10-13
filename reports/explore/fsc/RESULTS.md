# FSC results: full-speed cost of always-on S-default (U3/U4; exploration, NEVER ADOPTABLE)

Reduced 2026-10-13T12:50:46Z on 127x05 by [reduce.py](reduce.py) (sha256 072a215c…, from commit 89f01fbb), exactly
as pre-declared in [READOUT.md](READOUT.md). Full output: [results.json](results.json). Mirror check:
[mirror-check.json](mirror-check.json) ([verify_mirror.py](verify_mirror.py)). Plan: [PLAN.md](PLAN.md). Log:
[PROGRESS.md](PROGRESS.md).

**Status: exploration only, NEVER ADOPTABLE.** R3a stays killed under R3 Stage 1, and nothing here admits any arm to
live play.

## Bottom line
- **Primary Δ200 = loss(K4S-200) − loss(K4-200) = −0.50 pp [−1.30, +0.30]** over 6,400 fresh paired X-deck seeds.
  The upper 95% CI is ≤ +1.0 pp, so the pre-declared outcome is **"always-on supported"**.
  - At full speed (200 ms, 1.0×), making the R3a student the cutoff default costs nothing measurable against plain K4
    on the X decks. A cost above +0.3 pp is excluded at 95%.
  - The earlier +2.2 [−0.3, +4.7] (X4S, 600 seeds) looks like noise. Pooled with those 600 seeds:
    −0.27 [−1.06, +0.49].
- **0.9× point (descriptive): Δ180 = K4S-180 − K4-180 = −1.6 pp [−3.3, +0.1]** over 1,500 fresh seeds. Pooled with
  X4S2 phase E: −1.76 [−3.29, −0.24].
- **Implication for a Mac tier (evidence only, not a decision).** Running K4S always-on would not need a
  measured-speed gate to protect full-speed play. It is neutral at 1.0× and favourable at 0.9×.

## Sample
Both hosts finished every worklist block before their STOP, so no prefix is cut.

| Host | Worklist (dispatch order) | Blocks | Games | Prefix | Dropped beyond prefix |
|---|---|---:|---:|---:|---:|
| 127x03 | `wl-03` 0–2399, then `wl-03-ext` 3900–5899 (all K4-200/K4S-200) | 2,400 + 2,000 | 8,800 | 4,400 (complete) | 0 |
| 127x04 | `wl-04` 2400–3899 (K4-180/K4S-180), then `wl-04-ext` 5900–7899 (K4-200/K4S-200) | 1,500 + 2,000 | 7,000 | 3,500 (complete) | 0 |

Every block's proof matches its game SHA-256s, and the epoch-1 files in the `-e2` mirrors are byte-identical to the
epoch-1 mirrors. Interrupted reporting blocks: 0. No yield occurred, since console users were 0 at every check.
Seeds come from the fresh bank 4503607007370496 + index, audited on a git export (`seed-audit.json`). The smoke and
STOP-test seeds are excluded.

## Contrasts (paired by seed; 5,000-rep percentile bootstrap, RNG 2026101301; 95% CI, unadjusted)
| Contrast | Seeds | Δ loss (pp) | 95% CI |
|---|---:|---:|---|
| **PRIMARY K4S-200 − K4-200 (both hosts)** | 6,400 | **−0.50** | **[−1.30, +0.30]** |
| K4S-200 − K4-200, 03 only | 4,400 | −0.39 | [−1.36, +0.59] |
| K4S-200 − K4-200, 04 only (ext) | 2,000 | −0.75 | [−2.25, +0.70] |
| K4S-200 − K4-200, 03 indices < 2400 (the plan's "2,400 fresh seeds") | 2,400 | −0.50 | [−1.79, +0.79] |
| Secondary: K4S-200 − K4-200 pooled with X4S's 600 X seeds (stratified) | 7,000 | −0.27 | [−1.06, +0.49] |
| K4S-180 − K4-180 (descriptive) | 1,500 | −1.60 | [−3.33, +0.13] |
| K4S-180 − K4-180 pooled with X4S2 phase E (stratified, descriptive) | 2,100 | −1.76 | [−3.29, −0.24] |

The two hosts agree: −0.39 on 03 and −0.75 on 04.

## Per arm (all prefix games; rates are % of search decisions)
| Arm | Seeds | Loss % | Cutoff % | Student default % | Overrun % | Fallback % | Poll ms | Wall p50 / p95 / p99 / max ms | Game CPU-h |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| K4-200 | 6,400 | 19.53 | 4.20 | 0.00 | 0.115 | 0.73 | 10.4 | 116 / 186 / 193 / 222 | 89.8 |
| K4S-200 | 6,400 | 19.03 | 3.29 | 0.85 | 0.111 | 0.74 | 10.5 | 115 / 179 / 193 / 225 | 89.4 |
| K4-180 | 1,500 | 20.53 | 9.01 | 0.00 | 0.100 | 0.87 | 10.8 | 118 / 173 / 173 / 200 | 21.3 |
| K4S-180 | 1,500 | 18.93 | 6.28 | 1.70 | 0.093 | 0.87 | 10.7 | 116 / 173 / 173 / 196 | 21.0 |

At 200 ms the student default fires on 0.85% of decisions, and the cutoff rate falls from 4.20% to 3.29%. Overrun is
unchanged at about 0.11%. At 180 ms the student is used about twice as often (1.70%).

## Run record
| Host | Epoch 1 (`rep0N`) | Epoch 2 (`rep0N-e2`) | Final STOP |
|---|---|---|---|
| 127x03 | 03:15:16Z → 07:23:12Z, 2,400 blocks, completed | 07:31:06Z → 10:57:49Z, 2,000 blocks, completed | 11:30Z (runner 1827204), `__RC=0` |
| 127x04 | 03:19:15Z → 05:57:04Z, 1,500 blocks, completed | 06:19:40Z → 09:51:47Z, 2,000 blocks, completed | 11:30Z (runner 1827204), `__RC=0` |

- **Resources:** 12 workers on 5-core slots (cores 0–59), nice 19, oom_score_adj 1000, RLIMIT_AS 8 GiB per process.
  Owned PSS peaked at 4.4 GiB and MemAvailable never fell below 118 GiB.
- **STOP proofs:**
  - The two epoch-1 STOPs (04 early at 06:10Z, 03 at 07:30Z) each had 30 recorded PIDs, none alive, no extra
    sdicks02 processes and no orphans.
  - The two 11:30Z STOPs had 44 recorded PIDs each, with the same result.
- **Idle time:** 04 idled from 05:57Z to 06:20Z (seam) and from 09:52Z to 11:30Z (worklist done). 03 idled from 07:23Z
  to 07:31Z and from 10:58Z to 11:30Z.

## Disclosures
1. **Review route.** The work used the PR-1 harness-reuse lane: the X4S2 harness at 1501be97f, with host tuples, the
   ceiling formula (start + 8 h) and the memory-guard constants changed. New host scripts went through Sol r1 and r2
   (both REQUEST_CHANGES, then fixed). After the final PR-1 round, the coordinator verified the remaining diffs directly.
   - Accepted residuals: the supervisor's own-PGID `killpg` (F8), and the 05 mirror path (F6).
2. **K4S conditions.**
   - Prefixes moved to `/mpac/sdicks02/jobs-fsc/` because `/mpac/sdicks02/jobs/clasher/` on 04 is perception
     storage. The bootstrap created the parent `/mpac/sdicks02/jobs-fsc` (disclosed residual).
   - Allowlist copies with no symlinks; memory guards; a strict STOP proof; no cron, timers or units.
3. **STOP-time changes.** `DEADLINE` moved 04:50Z → 07:30Z (coordinator, d59cce54/d4c7d646, single-constant file) →
   11:30Z (epoch 2, 9aa1cce6). The top-up segments were dropped under the 04:50Z cap and restored as the epoch-2
   extension; the READOUT amendments were declared before any affected game.
4. **First 03 launch (02:52Z) failed preflight** (`__RC=91`) on a resident sdicks02 process, the v4 validation cache
   service. Nothing was staged or started.
   - Ruling **FSC-1** (dfc637c0) exempted exactly PGID 2180934 (PIDs 2180934/2180946/2180947) on 03, given an exact
     start_ticks match and ≤ 15 ticks of growth across the two 15 s samples, read from `/proc/<pid>/stat` only.
   - It was exempt at both 03 preflights (03:12Z and 03:15Z, ticks 7603 → 7605).
   - Our slots (cores 0–59) and supervisor (core 62) overlapped its pinned cores 48–63; it was idle.
5. **Leaf move.** 03 relaunched in the fresh prefix `fsc-03-20261013b` (c7df6fac), because the failed attempt left
   `fsc-03-20261013/` holding only `bundle/`. That directory was left untouched on 03.
6. **Runner swaps.** All were done by exact PID after an identity check, each with coordinator approval:
   - 2050067 (d4c7d646) was replaced by 239670 (c7df6fac).
   - 239670 was replaced by a frozen `git archive` export runner, 1959653 (03 only, 07:30Z), because the shared
     worktree could change under a running runner.
   - The epoch-2 runner 2011028 (9aa1cce6) was replaced by 1827204 (89f01fbb).

   No STOP session ever ran from a replaced runner.
7. **Epoch-2 04 resume failed closed** at 06:10:49Z (`__RC=96`). My bug: the resume equality list included
   `reduce.py`, which 9aa1cce6 itself changed. Nothing started.
   - Fix 89f01fbb dropped `reduce.py` from the list (no host step in epoch 2 uses it) and moved to a fresh bundle dir,
     `bundle-e2r`. The unused `J/bundle-e2` stays on 04.
   - The failed log is archived in `fsc-sessions/resume-attempt1-04/`. The retry succeeded at 06:20:41Z.
8. **Seam rule (READOUT amendment e2).** Interrupted `wl` blocks are rerun in the fresh e2 instance, and their partial
   games are never read. In practice there were none: both `wl` worklists were fully proven before the seam, so
   epoch 2 ran only the extension segments.
9. **The 03 cache service exited during the run.** At 07:31:06Z the FSC-1 identity check found no PGID 2180934 on 03,
   and preflight saw no foreign process. It was present and idle at 03:12–03:15Z and absent by 07:31Z.
   - FSC never signals or touches it. Our memory stayed low (PSS ≤ 4.4 GiB, MemAvailable ≥ 118 GiB), so an OOM kill
     by us is implausible.
   - The cause is unknown and was not investigated: that would need host contact outside the plan. Reported to the
     coordinator for the K4S runner.
10. **Cross-run pairing.** The X4S pooled secondary pairs within each source only (stratified): X4S used different
    seeds and an earlier run. The 04 extension seeds are paired within 04.
11. **Labelling and code.** Game metadata still carries `study='X4S2 exploration, NEVER ADOPTABLE'`, because `run.py`
    is unchanged apart from the host tuple. The X population's G-deck entry stays in the config only for `run.py`'s
    catalogue assert; no G game was run.

## Provenance
- **Code:** prep 9f69df0b; host scripts r2 3dc9ab25; single cap d4c7d646; FSC-1 + 03b c7df6fac (launch, MANIFEST
  2f16b70d…); epoch 2 9aa1cce6 → fix 89f01fbb (resume, MANIFEST 69dc22c8…).
- **Coordinator:** GOs 19047ce7, 5f1a28be, 2ee0f32a and 877b83a0.
- **Configs:** `plan-fsc.json` 0ab43351…, `plan-fsc-04.json` 5bf33960…. Native 44874fd6…, v1 d77005d5…, R3a 37509a43….
- **Mirrors on 05:** `/mpac/sdicks02/jobs/clasher/fsc-mirror-20261013/{127x03,127x04,127x03-e2,127x04-e2}`.

# Mac registration inputs: agreement2000 + packets1000 (design proposal)

Prepared 2026-10-11 ~22:20–23:00Z on 127x05 by the design sub-agent for coordinator thread 0523ae6f. This is
read-only research plus a proposal. I made no ssh to any 127x host and no Mac contact. I read no T1 or K4S game
results, no `games/` file and no heldout data. Sources are origin/main at `76887b33`, extracted read-only, plus
metadata (`ls`/`find`) and a byte-compressibility probe of public state files on 05.

Abbreviations: `V4` = `reports/strategy_council_20260928/live-loop/v4`, `E4` = `V4/mac-e4-package/e4v3`,
`T1` = `reports/explore/t1`.

## 0. Summary

- **No frozen document says how agreement2000 or packets1000 are selected, from what source, at what cadence, or by
  whom they are built.** The frozen text fixes only their counts, their row contract, the packet-schedule binding,
  and the fact that T1 merges them into the reviewed `registration.json`.
- The addendum intended both sets to be frozen "before any fleet reporting game". That moment has passed, so building
  them now needs an **outcome-blind TIERS Amendment 4**, in the same pattern as Amendment 1's END placement.
- **Source:** T1's 32 raw captures (`capture.pkl.gz`) exist **only on 127x03**, under
  `t1-20261010-r1/corpus-reviewed-03-r1/captures/`. 05 holds only the 1,200 selected rows and golden125, and 01/08
  hold nothing. The capture SHAs are pinned in committed `corpora.json`, so a copy can be verified against git.
- **Pool:** 4,242 eligible rows were captured (K0c 1,275, S 1,156, K2 883, K4 928). That leaves 3,042 unselected rows.
- **Disk:** the minimal compliant fixture overlaps the sets: agreement = speed1200 ∪ packets ∪ fill. That adds
  only **800** rows to the END fixture. The bundle is then ≈ **38.6 GB (≈36 GiB)**, against ≈ 80 GB if the sets are
  disjoint. The frozen Mac staging command copies source to bundle, which **peaks at ≈ 72 GiB, more than the 63 GiB
  free**. A disk plan is therefore part of the critical path (§C.4).
- **Recommended owner:** a dedicated builder worker on 05 acting under T1's corpus-owner authority. T1 merges and seals
  the registration packet. Sol reviews the code, and an independent worker reproduces the result.
- **Earliest 03 read:** after K4S 03's current phase stops at the ~08:47Z Oct 12 apt timer, in a ≤20-minute gap
  before its next windowed round.

## 1. What the frozen documents say (question 1)

| # | Frozen text | Location | What it fixes |
|---|---|---|---|
| F1 | "**Student cross-platform agreement** on 2,000 frozen states: Mac CPU (1 Torch thread) and MPS each against fleet CPU" | `V4/PREREG-SEARCH-TIERS-r3-DRAFT.md:447-451` (frozen r3, record `47aba25e`) | count = 2,000, reference = fleet CPU. **No source, selection rule or owner.** |
| F2 | "**Deadline-mode tier cells:** 1,000 replay packets × {K0c, S, K2, K4} at 200 ms / 8 ms reserve under load." | `V4/PREREG-SEARCH-TIERS-r3-DRAFT.md:460` | count = 1,000, same packets for every tier. **No source.** |
| F3 | "an **opportunity** is a scheduled poll at the live search/policy cadence, computed from replay packet timestamps" | `V4/PREREG-SEARCH-TIERS-r3-DRAFT.md:370-371`; also `V4/mac-e4-package/E4-V3-ADDENDUM-r3-DRAFT.md:120-121` | Cadence = the live poll cadence, derived from packet timestamps. **No rule for building timestamps from simulator rows, or for joining games.** |
| F4 | "A tiers bundle … frozen with the PREREG (in the TIERS manifest, before any fleet reporting game): … the 2,000-state student agreement set, with fleet-CPU logits; the replay packet list for **§D7**." | `E4-V3-ADDENDUM-r3-DRAFT.md:40-52` | **When:** before reporting. That has already passed, which is why an amendment is needed. **No rule or owner.** |
| F5 | D2 "2,000 × 2"; D6 loaded forward "2,000 × 2"; D7 "1,000 replay packets … 4,000 decisions, 15 min"; D8 "up to 4 × 1,000, ≤15 min" | `E4-V3-ADDENDUM-r3-DRAFT.md:94,99-101` | Sizes and time budgets only. |
| F6 | The freeze step lists "speed corpora, fleet references, `measure_tiers.py` …" | `V4/PREREG-SEARCH-TIERS-r3-DRAFT.md:530-532` | Agreement and packets are **not** listed. |
| F7 | `MAC_LIMITS = dict(golden=125, agreement=2000, …, forwards=2000, decisions=1000)`; `validate_counts` requires `len(ids) >= count`, no duplicates, `[p["id"] for p in schedule] == sets["packets"]`, strictly increasing `offset_seconds` | `E4/measure_tiers.py:21-23,46-59` (6066228b, Amendment 2) | Counts, uniqueness and ordering. **There is no disjointness check between sets.** |
| F8 | Before timing: every `sets.packets` row passes `corpus_contract.validate_row`; every speed row passes `fleet_reference.validate_row(row, tier)`; for each packet, `row["info"].tick == packet["tick"]` and `offset_seconds == timestamp_seconds − schedule[0].timestamp_seconds` (exact float equality) | `E4/measure_tiers.py:459-471` | Row contract and schedule binding. |
| F9 | `student_agreement` iterates **all** `sets.agreement` against `student-reference.json[id]`; D6 uses `sets.agreement[:2000]`; D7/D8 use `packet_schedule[:1000]` | `E4/measure_tiers.py:221-236,340,376` | Reference file format: `TierBackend.infer(id,"cpu")` rows, as built in the dry run at `E4/prepare_bundle.py:151-154`. |
| F10 | `golden_only = set(golden) − (∪speed ∪ agreement ∪ packets)`; policy inputs are retained only for `sets.agreement` | `E4/tier_backend.py:147-152` (Amendment 3) | The code **anticipates overlapping sets**. The dry run used one 32-id list for agreement, packets and all four speed sets (`E4/prepare_bundle.py:139-143`). |
| F11 | Packet schedule "binds `{id,tick,timestamp_seconds,offset_seconds, opportunity}` separately; tick must equal the row's `info.tick`, and offsets must agree with sealed timestamps." Rows carry exactly 20 fields; top-level `replay_timestamp_seconds` is rejected. | `E4/FLEET-INPUT-SCHEMA.md:123-151` (e5b51de9) | Timestamps live in the registration, not in rows. |
| F12 | "T1 merges the `fleet_reference.json` tier-independent metadata into its reviewed `registration.json`, with … the separate student/golden/belief refs, corpus receipt and packet schedule. This does not freeze the packet or authorize reporting/Mac work." | `E4/FLEET-INPUT-SCHEMA.md:218-222` | **Merger = T1.** Builder unspecified. |
| F13 | "Registered Mac sets/reference receipts are supplied by the corpus owner after review." Mac mode copies `sets`, `packet_schedule`, `fleet_reference`, `deadline_replay_semantics` and `corpus_receipt` from `registration.json`. | `E4/prepare_bundle.py:4-5,204-219` | Supplier = **corpus owner (T1)**, after review. |
| F14 | "The owner must seal all source reference receipts and pooling evidence into the reviewed registration packet. No outcome data belongs in that packet." | `E4/README.md:62-72` | Sealing and no-outcome rule. |
| F15 | "A Mac `states.pkl` that differs from the END fixture (golden125 + agreement2000 + packets1000 + speed 4×300) is converted once on Linux with `--states`, under its own reviewed fingerprint. The Mac stages it with `prepare_bundle.py --state-rows`; the Mac never converts." | `V4/PREREG-SEARCH-TIERS-AMENDMENT-3-20261011.md:84`; coordinator 22:07Z "Mac: its own fixture is converted on Linux under its own fingerprint" (`COORDINATOR.md`) | Conversion procedure. **Not selection.** |
| F16 | Registration packet: `scope=T1-REGISTRATION`, includes `registration.json`, corpus receipt, golden/belief/student references…; fields `sets`, `packet_schedule`, … | `T1/AMENDMENT1-RELEASE-BARRIER.md:70-87`; checker `T1/release_reference.py` (checks `student-reference.json` is present and `sets.speed` = 4×300, **not** agreement/packets) | T1 owns the seal. Outcome release requires a registration, but the barrier does not check the Mac sets. |
| F17 | T1's plan defines selection only for the speed sets: "proportional occupied-stratum sampling (minimum one, largest remainders), then SHA priority of tier/seed/tick" | `T1/PLAN.md:13`; `T1/plan.json:422-` (`corpus_selection`); `T1/corpus.py:8,24-46` | The template to mirror. Says nothing about agreement or packets. |

**Not applicable:** the B6 RUNBOOK's "≥1,000 unique nonterminal packets, from at least two train recordings"
(`V4/mac-e4-package/RUNBOOK.md:14`) is the separate W-screen8 session's perception cohort. D7 packets must be 20-field
T1 contract rows (F8, F11), which train recordings cannot supply.

## 2. What is fully, partly and not specified (question 2)

| Item | Status | Missing |
|---|---|---|
| Counts (125 / ≥2000 / ≥1000 / 4×300), uniqueness, contract rows | **Fully frozen** (F7–F9, F11) | — |
| Conversion (Linux, `--states`, own reviewed fingerprint; Mac stages only) | **Fully frozen** (F15) | — |
| Merger and seal (T1 into `registration.json`, `T1-REGISTRATION`) | **Fully frozen** (F12, F13, F16) | — |
| Agreement selection | **Not specified** | Source, rule, tier mix, whether it may overlap speed or packets, ordering |
| Packet selection | **Not specified** | Source, rule, whether rows are contiguous within a game, number of games, tier mix, truncation |
| Packet timestamps and cadence | **Partly specified** (F3, F11): "live search/policy cadence", "computed from … packet timestamps", tick binding | How a simulator row gets `timestamp_seconds`; how games are joined; the `opportunity` flag rule |
| Overlap between sets | **Silent in the text; permitted by the code** (F7 has no disjointness check; F10) | An explicit statement |
| Timing ("before any fleet reporting game", F4) | **Specified but missed** | An amendment to place the build after reporting, outcome-blind |
| Builder | **Not specified** (only "corpus owner" supplies, F13) | A named builder |
| Fleet-CPU logits host | **Partly specified** ("fleet CPU", F1) | Which host and runtime |
| Mac disk headroom for staging | **Not addressed** | A plan (§C.4) |
| D7/D8 time budget under real cadence | Specified as ~15 min each (F5) | Disclosure that a sealed-timestamp schedule takes longer (§B.3) |

## 3. Source location (question 3)

- **Raw captures:** only on **127x03**, `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/corpus-reviewed-03-r1/captures/corpus-{K0c,S,K2,K4}-{0003..0010}/capture.pkl.gz`,
  32 files. Each SHA is pinned in committed `T1/corpora/corpus-03-a51ea64c/corpora.json` (`tiers.*.source_capture_shas`, e.g. line 1261).
  The capture host was 03 (`capture_host`, `T1/receipts/corpus-03-launch.json`). The capture job ran only on 03 (`T1/CORPUS-03-DISPATCH-20261010.md`).
- **05 has only the selected rows.** It holds `corpus-publication-staging-r1/` (the four tier files plus combined `states.pkl`
  11,404,739,755 B = `282b0877`, `corpora.json`) and `end-bundle-preparation-r1/golden-states.pkl` (244,819,775 B). There are
  no production `capture.pkl.gz` files on 05. The only ones are 15 KB synthetic unit-test fixtures under
  `corpus-main-admission-tests-r{1,2}/`. `corpus-publication-preserved-partial-r1/states.pkl.gz` is the "incomplete
  compression attempt" (its README).
- **The 03 durability copy is of the selected 1,200 rows only.** The durability copy (`T1/receipts/corpus-03-durability-launch.json`, `corpus-03-durable-copy-r1.json`) copied
  05 → 03 `corpus-publication-durable-r1`, `states: 1200`. `publication.json` lists the public states on 03 (`built-corpora`) and 05 only.
- **01/08:** no originals and no copies. `T1/FREEZE-T1.md:55`: "Corpus state bytes stay on05 and a … durability copy on03;
  no01/08 corpus capture or copy overlaps reporting."
- **Pool:** 4,242 eligible opportunities (`capture_health`). The reservoir cap is 300 per stratum per game
  (`T1/corpus.py:25`, `plan.json reservoir_per_stratum`). The largest per-tier stratum total over 8 games is 417, so the cap almost certainly
  never bound, and about 4,242 rows are retained. 4,242 − 1,200 = **3,042 unselected rows**. The builder must confirm
  retained = counted after the copy. (The coordinator's "~3.7k" estimate is superseded by these receipt counts.)
- The capture directories also contain `games/*.json`, which are sealed excluded-game records. **The copy must exclude them.**

## 4. Size and disk (question 4)

Measured inputs: END fixture `0addf7c0` = public 11.40 GB + golden 0.245 GB = 11.65 GB. Mean bytes per selected row:
K0c 7.74 MB, S 9.35 MB, K2 11.49 MB, K4 9.43 MB, **overall 9.50 MB**. The distribution is heavy-tailed: median 2.05 MB, max 139.7 MB
(Amendment 3 §Timing 1). `states-rows.bin` ≈ `states.pkl` ("about 2 × 11.65 GB for END", Amendment 3 item 4).

| Fixture | Rows (contract + golden) | `states.pkl` | Bundle (`pkl` + `rows.bin`) | Mac staging peak (source + bundle copy) |
|---|---|---|---|---|
| **Minimal, overlapping (recommended):** agreement ⊇ speed ∪ packets | 2,000 + 125 (800 beyond END) | ≈ 19.3 GB | **≈ 38.6 GB ≈ 36 GiB** | **≈ 77 GB ≈ 72 GiB** |
| Agreement ⊇ speed, packets disjoint from agreement | ≈ 2,700 + 125 | ≈ 26 GB | ≈ 52 GB ≈ 48 GiB | ≈ 97 GiB |
| Fully disjoint (speed, agreement and packets) | 4,200 + 125 | ≈ 40.2 GB | ≈ 80 GB ≈ 75 GiB | ≈ 150 GiB |

- **Savings from overlap** (frozen text silent, code permits): 2,200 rows ≈ 20.9 GB per file, so ≈ 42 GB less bundle and ≈ 78 GiB less
  staging peak. The fully disjoint fixture does not fit the Mac even as a bundle alone, and it would also consume
  3,000 of the 3,042 unselected rows, leaving a 42-row margin.
- The 800 extra rows are estimated at ≈ 7.6 GB. Given the heavy tail, plan for 6–10 GB.
- **The frozen staging peak does not fit.** The frozen session command runs `prepare_bundle.py` on the Mac
  (`E4/README.md:122-140`), and `copy_file` → `shutil.copyfile` makes a data copy (macOS `fcopyfile` with
  `COPYFILE_DATA`, not an APFS clone). Peak ≈ 72 GiB against 63 GiB free, before swap headroom or K4S's own ≈ 2.8 GB
  K4 corpus. See §C.4.
- **03 capture size estimate:** gzip -1 on three 256 MiB slices of `K0c-states.pkl` gave 7.1–8.4×. For ≈ 40 GB of
  pickled rows that is roughly **5–6 GB** of `capture.pkl.gz`. The builder confirms this with `stat` before copying.

## 5. Downstream reference runs (question 5)

| Input | Needed for | Status / frozen owner | Host |
|---|---|---|---|
| `student-reference.json`: `TierBackend.infer(id,"cpu")` for every agreement id, 1 Torch thread, frozen R3a + calibration threshold | D2 (F1, F9) | **New.** "with fleet-CPU logits" (F4); T1 merges it (F12). The computing host is not named. | **Recommend 05** (same Threadripper 3990X as the fleet, nice 19, one core, END-pinned runtime and venv). Cross-check against the pooled END S forwards on the 300 S speed ids. Fallback: 01 after the END pool. Not timing work. |
| `packet_schedule` | D7/D8 (no Linux reference exists for D7) | **New.** No reference run needed. | Built on 05 |
| `golden.json`, `belief-reference.json` (golden125) | D1/D1b | Exist in the END bundle (`end-bundle-preparation-r1/bundle/`, T1) | — |
| `speed-reference.json`, `deadline-reference.json`, `fleet_reference` metadata | D3/D5/D5b, r_T, gate 6 | T1 END on **127x01/127x08** (Amendment 1 A1.1; coordinator 22:07Z), then pool, then PC1–PC4 | 01/08, T1 |
| `corpus_receipt` (`corpora.json`) | speed inventory check | Exists (`T1/corpora/corpus-03-a51ea64c/corpora.json`) | — |
| Mac `states.pkl` + `states-rows.{json,bin}` | all | **New.** Linux `convert_states.py --states --expect-fingerprint` (F15) | 05 |

## A. Frozen requirements that must be followed

1. `measure_tiers.py` 6066228b and the Amendment 3 files, unchanged (Amendment 2 condition 1; Amendment 3 condition 1).
2. `sets.golden` = the 125 historical golden ids; `sets.speed` = T1's 4×300 ids exactly as in `corpora.json`; `sets.agreement` ≥2,000
   unique ids; `sets.packets` ≥1,000 unique ids, equal to the schedule's id order (F7).
3. Every agreement and packet row is a 20-field contract row (F8, F11, F10: validated and given a policy input at construction).
   Golden rows cannot serve as agreement or packet rows: they lack `d1_before`/`d1_events`.
4. Each schedule entry has exactly `{id, tick, timestamp_seconds, offset_seconds, opportunity}`, with `tick == row.info.tick`,
   `offset == timestamp − schedule[0].timestamp` (exact float) and strictly increasing offsets (F7, F8, F11).
5. The Mac fixture is converted once on Linux under its own reviewed ordered fingerprint; the Mac only stages it (F15).
6. T1 merges and seals everything into the reviewed `T1-REGISTRATION` packet, with no outcome data (F12–F14, F16).
7. Outcome blindness: reporting outcomes stay sealed, and the excluded corpus games' `games/` records are never read
   (`corpora.json outcomes_read: false`).
8. A3-P: the all-cause poll-lateness check (≤1 %, max ≤50 ms) applies to D7/D8 (Amendment 3 condition 3).

## B. Rules for the unspecified items (all outcome-blind; registered by Amendment 4)

**B.0 Amendment needed?** Yes, a single outcome-blind **TIERS Amendment 4 "Mac registration inputs"**. Reasons:
- F4 required these inputs before any reporting game, and that has passed (the precedent is Amendment 1 A1.1).
- Selection, cadence and overlap are new registered inputs.

The amendment changes no hypothesis, arm, seed, tier, gate, threshold or reducer. Its input data are excluded-range
corpus captures whose outcomes are never read, and the rules below are fixed before the captures are opened.

**B.1 Common pool and validity**
- Pool = every row in T1's 32 SHA-verified captures (seeds `4503603407370496+[3,11)`, 8 per tier, a51ea64c lineage).
- Rows failing `corpus_contract.validate_row` are excluded before any ranking, and the count is disclosed. If more than 1 % fail, stop and escalate.
- **Lineage cross-check (fail closed):** for each of the 1,200 speed ids, the capture row's canonical digest
  (`convert_states` canonical) must equal the published `282b0877` row's. Per-tier capture `counts`/`health` must equal `corpora.json`.
  Speed rows always come from the published file, never from the capture copy.

**B.2 Packets (packets1000): whole games, SHA-priority game order, tier-balanced**
- For each tier, order its 8 games by `sha256("tiers-packets/{tier}/{seed}")`, ascending.
- Take games round-robin in `TIERS` order (K0c, S, K2, K4) by rank: rank 0 of each tier, then rank 1, and so on.
- Append each game's valid rows in ascending `info.tick` until the cumulative total reaches 1,000. Truncate the last game at
  exactly 1,000 (expected ≈ 7–8 games, about 2 per tier).
- Whole games keep the live poll structure (F3). Round-robin keeps any one tier's state distribution from dominating, since
  every packet runs under all four tiers (F2). Packets naturally include some speed rows; that is allowed (F10).
- **Recommendation:** this rule. Disjointness from speed would break within-game contiguity and is not required.

**B.3 Timestamps, cadence and the opportunity flag**
- Tick = 0.05 s (20 Hz). Live search polls are every `search_decision_interval` = 10 ticks = 0.5 s (`T1/plan.json`).
- Global tick: for game k with first and last packet ticks f_k and l_k, set O_0 = −f_0 and O_{k+1} = O_k + l_k + 10 − f_{k+1}
  (games are joined with exactly one search interval).
- `timestamp_seconds = (tick + O_k) * 0.05` (Python float, so the first is exactly 0.0) and `offset_seconds = timestamp_seconds − 0.0`.
  Strictly increasing by construction; `tick` = the row's own `info.tick`.
- `opportunity = true` for every packet: every captured row is, by construction, a search poll at the live cadence with
  more than one candidate.
- **Recommended: this sealed-tick cadence ("P1").** It is the literal reading of F3/F11, and it avoids a harness artifact:
  a heavy pre-arrival state load (Amendment 3: p99 0.22 s, max 0.31 s) right after a full 208 ms decision can make a poll
  more than 50 ms late, which fails A3-P. P1 spaces most packets well beyond 0.5 s.
- **Cost (must be disclosed):** the mean gap is ≈ 2.2 s (≈ 133 eligible rows per game of ≤ 300 s), so one pass takes
  ≈ 30–40 min, against the addendum's 15 min. D7 is then ≈ 2–2.5 h and D8 up to ≈ 2–2.5 h, taking the TIERS sub-session from ≈ 100 min to
  **≈ 6–6.5 h**. The schedule offsets reveal excluded-game lengths; those games test no hypothesis.
- **Alternative ("P2"), only if the coordinator rejects the session length:** a compressed 2 Hz schedule,
  `timestamp_seconds = 0.5 * index`, with the same packets. It is shorter (D7 ≈ 33 min, D8 ≤ 33 min) but conservative,
  every poll heavy, and more exposed to the load-tail A3-P artifact. Its timestamps are synthetic rather than sealed, so it
  needs explicit amendment text overriding F11's "sealed timestamps".

**B.4 Agreement (agreement2000): speed ∪ packets ∪ tier-proportional SHA fill**
- `sets.agreement` = speed1200 ∪ packets ∪ F, with |F| = max(0, 2,000 − |speed ∪ packets|), expected ≈ 50–100.
- The fill pool is the valid rows not already in speed ∪ packets. Allocate |F| across the four tiers by `corpus.quotas`
  (proportional to fill-pool counts, at least one each, largest remainders). Within each tier take the lowest
  `sha256("tiers-agreement/{tier}/{seed}/{tick}")`, ties by id.
- The salt is domain-separated, so the ordering is independent of the speed-selection priority (`T1/corpus.py:8`).
- Order the list by (TIERS index, seed, tick).
- Rationale:
  - S alone has only 1,156 eligible rows, so the 2,000 states must cross tiers in any case.
  - Agreement is a platform-equivalence check, so it needs no independence from the speed sets.
  - Including S's own 300 timed states is directly relevant to S.
  - The overlap is what lets the fixture fit on the Mac (§4).

**B.5 Fixture order and identity**
- `states.pkl` = published public 1,200 (END order), then golden125 (END order), then the extra rows ordered by
  (TIERS index, seed, tick), written by streaming `pickle.dump(..., protocol=5)` after the reviewed runtime bootstrap.
- Its first 1,325 canonical digests must equal the END index entries (`c09142b9…` prefix check).
- Identity = the ordered canonical fingerprint (Amendment 3 §Fixture identity). An independent re-assembly reproduces it,
  then `convert_states.py --states … --expect-fingerprint <reviewed>` runs on 05.

**B.6 Fleet-CPU logits** ("fleet CPU" means x86-64 Linux 3990X with the END-pinned runtime, torch and venv, 1 thread, no timing)
- Compute `student-reference.json` on 05 with the Amendment 3 `TierBackend` in a Linux profile.
- Gate: on the 300 S speed ids, 05's S forward records must equal the pooled END fleet forward records (discrete gate and
  top-8 identical; logits within the F1 tolerances). Otherwise recompute on 01 after its END pool.
- This needs no amendment beyond naming the host in Amendment 4.

**B.7 Receipts (sealed into the registration packet, not new row fields)**
- `mac-sets-selection.json` holds: capture SHAs and the verification, pool counts, invalid-row counts, game order, packet
  truncation point, fill quotas, all ids, the schedule SHA, the fingerprint, and the script SHAs, with `outcomes_read: false`.

## C. Minimal path to a compliant Mac bundle

**C.1 Owner (recommendation)**
- **Builder:** a dedicated Opus (high) "Mac registration inputs" worker on 05, acting as T1's delegate for the corpus-owner
  role (F13). T1 is fully loaded with END (convert, A6, references, pool, PC1–PC4).
- **T1** keeps merge and seal authority: it merges `sets`/`packet_schedule`/`student-reference.json`/`mac-sets-selection.json`
  into `registration.json` and seals `T1-REGISTRATION` (F12, F16).
- **Reviews:**
  - Sol reviews the code (selection, assembler, schedule, student-reference scripts, plus the Amendment 4 text).
  - A second independent worker reproduces the ids, schedule and fingerprint from the same copied captures.
  - The coordinator adopts Amendment 4.
- The builder never writes on 03, 01 or 08, or in T1-owned trees.

**C.2 Source copy from 03 (one read, ≤20 min, in a K4S gap)**
1. **Precondition:** the K4S runner reports 03's current phase stopped. The coordinator ruling expects this at the 08:47Z Oct 12 apt
   timer. The runner also confirms the supervisor exit is sealed and the `apt-daily*` units are inactive. The coordinator declares a 03 read window,
   and the runner holds its next windowed round until the builder posts "released". **No read while any K4S reporting phase
   runs on 03**: the OP-6 SSH-family and foreign-compute guards would charge it.
2. **motd handling:** the ~00:58Z motd firing refreshes the release-upgrade stamp. Our login may still fire a stale check. Since no
   phase is running, that is harmless provided we wait. Before release, confirm no `check-new-release`/update-notifier helper is running. The runner
   then performs its own frozen pre-launch stamp reads.
3. **Copy:** one ssh session from 05 over the campus LAN with `-o ControlMaster=no -o ControlPath=none`, so no master socket
   lingers into the next round. Run `rsync --files-from` listing **only the 32 `capture.pkl.gz`** paths from `corpora.json`
   (no `games/`, no `local-complete.json`), with `--rsync-path='nice -n 19 taskset -c 63 rsync' --bwlimit=32768`.
   Write nothing on 03. About 5–6 GB at 32 MiB/s is about 3 min.
4. **Verify on 05:** each SHA-256 equals `corpora.json source_capture_shas`. Then post "released". Commit a small copy receipt.
5. **Fallback** if the window is refused or a SHA mismatches: capture fresh excluded corpus-range games (unused indices ≥11 of the audited
   `[0,64)` bank; same a51ea64c capture code via a reviewed host-adapter like `corpus-03-operational-worker.py`) on 05 at nice 19.
   Speed rows stay the published ones, and the B.1 lineage check is replaced by fresh-capture receipts. This costs about one extra review round.

**C.3 Build on 05 (nice 19, one core, no timing)**
- Select (B.1–B.4), assemble (B.5), convert with `--expect-fingerprint`, and compute student references (B.6).
- **Memory check (blocking):** offline Mac-profile `TierBackend` construction on the new fixture, with RSS and HWM receipts as in
  Amendment 3. It must show that main + 2 sequential D6 backends, each retaining 2,000 policy inputs, stay within the
  coordinator's ~6 GiB Mac cap.
- Hand the outputs to T1.

**C.4 Mac disk (blocking for staging)**
- Need ≈ 72 GiB peak + ≈ 3 GiB K4S + ≥10 GiB swap/receipts ≈ **85 GiB free**; 63 GiB is free now.
- In order of preference:
  - **(i)** The Mac operator reclaims space on the agent-owned Mac: caches and its own scratch, never Sam's code trees.
  - **(ii)** `E4_STATES`/`E4_STATE_ROWS` on an attached external volume. This needs no code change, since the paths are arbitrary.
  - **(iii)** A reviewed one-line `prepare_bundle` change to hard-link (same filesystem) instead of copying the two large files.
    This touches an Amendment 3 file and the K4S-pinned manifest, so it is last resort.
- Transfer 05 → Mac by streaming compression (`pigz -c | ssh macmini-fleet 'gunzip > …'`; ≈ 5–6 GB on the wire, no intermediate
  file), then verify SHA on the Mac.

**C.5 Timeline (UTC, estimates)**

| When | Step |
|---|---|
| Oct 11 23:00 → Oct 12 ~06:00 | Builder writes the scripts and synthetic tests and drafts Amendment 4; Sol review rounds; coordinator adoption. In parallel, the Mac operator measures reclaimable space and checks for an external volume. |
| Oct 12 ~08:47 | K4S 03 phase stops at its apt timer; the runner confirms that apt finished. |
| ~09:00–09:20 | 03 read window: copy 32 captures, verify, release 03 to K4S. |
| ~09:20–10:45 | Select, cross-check, assemble (≈ 19 GB), convert (~15–30 min), memory check, student references (~10 min). |
| ~10:45–12:00 | Independent reproduction plus review sign-off; hand off to T1. |
| After the END pool and PC1–PC4 | T1 merges and seals the registration; independent registration review; transfer to the Mac (~10–20 min compressed); Mac session (≈ 6–6.5 h under P1, plus B6 if run together). |

The Mac inputs are off the critical path if they are ready by about 12:00Z Oct 12. The END pool is expected later than that.

## D. Risks

1. **Single source.** The captures exist only on 03, which is a K4S timing host. The window depends on the K4S runner. A SHA mismatch or a missing file triggers the C.2 fallback, at about one review round of delay.
2. **K4S interference.** Any ssh or CPU on 03 during a reporting phase is charged by OP-6/OP-7. Mitigations: gap-only access, no ControlMaster, motd settle, explicit release handshake.
3. **Mac disk.** The staging peak exceeds the free space (§C.4). Swap also needs disk on a 24 GiB machine, so do not stage to within <10 GiB of full.
4. **Session length under P1** (≈ 6–6.5 h). This raises census and foreign-process risk, and thermal drift. P2 halves it but adds artifact risk and needs amendment text. It is the coordinator's call; I recommend P1.
5. **A3-P load-tail artifact.** Heavy rows at 0.5 s gaps can produce polls more than 50 ms late, failing a tier for harness reasons. Packets must **not** be filtered by size, because that biases toward early-game states. Disclose instead.
6. **Memory.** 2,000 retained policy inputs × 3 backends on the Mac are unmeasured. The C.3 check is blocking.
7. **Fleet-CPU equivalence of 05.** Same CPU model and pinned stack; the B.6 cross-check gates it.
8. **Never-validated rows.** The 3,042 unselected rows were never contract-validated. B.1 covers this with exclusion and disclosure, stopping above 1 %.
9. **Registration sequencing.** If T1 seals the registration before the Mac sets exist, a second registration is needed, because `release_reference` binds one manifest. Deliver before T1 seals.
10. **Non-reproducible pickle bytes.** Torch storage keys make bytes non-reproducible. Identity is the canonical fingerprint only (Amendment 3), never the pickle SHA.
11. **Excluded-game information.** Schedule offsets encode excluded-game lengths. No hypothesis uses those games; `games/` and `local-complete.json` are never copied or read.

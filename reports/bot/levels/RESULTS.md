# Level-aware search pilot — final results

Completed 2026-10-16 at 14:09:22 UTC / 07:09:22 PDT; final audit accepted at 14:17 UTC / 07:17 PDT.

**The registered pilot is complete and clean, but B is not promising under the fixed rule.** Across 100 paired cases, level-aware B scored 93% versus A's 96%: **B−A = −3 percentage points, 95% paired-bootstrap CI [−10, +3] pp**. The required point estimate was at least +3 pp. Confirmation, the conditional 200 ms follow-up and a LIVE bundle are therefore not advanced. The interval includes zero; this is not evidence of general harm or equivalence.

[Decision receipt](receipts/pilot-r30-decision.json), [machine report](receipts/pilot-r30-final-report.json), [execution audit](receipts/pilot-r30-owner-audit.json), [independent parent audit](receipts/pilot-r30-parent-audit.json). [Design](DESIGN.md) and [progress/audit](PROGRESS.md) contain the protocol and exact commands.

## Results

Each arm played the same 100 true-level cases, with 50 games against each fixed opponent controller and 25 cases in each controller/seat group. Scores are win=1, draw=0.5, loss=0.

| arm | W / D / L | mean score | paired Δ versus A | 95% CI |
| --- | ---: | ---: | ---: | ---: |
| A: assumes level 11 | 96 / 0 / 4 | 0.96 | — | — |
| B: corrected roots and rollouts | 93 / 0 / 7 | 0.93 | −0.03 | [−0.10, +0.03] |
| B0: legacy root-only diagnostic | 83 / 0 / 17 | 0.83 | −0.13 | [−0.21, −0.05] |

B improved four paired outcomes, worsened seven and matched 89. Its paired sample SD was 0.3319669. The interval uses the registered 20,000 case-pair bootstrap resamples with NumPy seed 0. B−A was −0.08 against R3a and +0.02 against v1, with 50 cases each; these descriptive subgroups do not alter the decision. B0 never controls the promising rule and is not a clean isolation of one implementation component.

All 100 B/A full command traces differed; the median first difference in our deployment log was tick 117. These are game-trace comparisons after trajectories diverge, not a share of individual decisions on identical public states.

| arm | match CPU seconds/game | our CPU seconds/decision | child wall seconds/game |
| --- | ---: | ---: | ---: |
| A | 34.580 | 0.1378 | 35.405 |
| B | 33.907 | 0.1398 | 34.736 |
| B0 | 34.967 | 0.1360 | 35.838 |

Match CPU includes both players and simulation; initialization is excluded. These serial measurements are not a pooled LIVE latency or default-share benchmark. The generic machine report prints mechanical power estimates for every arm; no confirmation plan is selected because the promising rule failed.

## Acceptance and provenance

All **300/300 unique games** reached native terminal results with parent, shell and every child exiting 0. There were zero errors, native FAILURES, rejected commands, missing diagnostics, controller-prior failures, placement failures, duplicate rows, unexpected rows or identity mismatches. No game was retried or excluded. Every case field and complete launch identity was checked, including 1,200 before/after controller-prior observations.

All 100 B games exercised the exact root: 12,118 roots, 130,675 body visits, 45,947 leveled visits and 75,186 tower visits; exact-root unmapped count was zero. Raw translator counters remain visible: 38,202 observations of the explicitly unsupported Goblin Hut garrison sprite `SpearGoblin_Dummy`, and eight Lightning projectile observations without a dedicated counterpart projectile (the Lightning area-effect mapping remains). These are frozen translation approximations, distinct from native failures or exact-root mapping errors; no claim of zero translator warnings is made.

The command-closure repair was exercised in 35 real games: A=9, B=10, B0=16. Acceptance closed at tick 6000, with actual native finals at ticks 6088–6139. The latest accepted command was at 5997; there were no postclosure dispatches. Twenty-three unsent reservations retained their exact submitted/due/action/card/cost evidence and balanced channel accounting. No early terminal score, invented rejection, refund or filtered failure was used.

All **1,332 frozen-input checks, 109 source hashes and seven cache hashes** matched after execution; the identity includes 1,211 runtime files. All 303 raw output files and 37 auxiliary files were copied from 01 to 05 and SHA verified; seven final audit artifacts were also mirrored back to 01. The complete raw job is `/mpac/sdicks02/jobs/clasher/bot-levels/pilot-r30/` on both hosts. [Raw inventory](receipts/pilot-r30-raw-output.sha256), [row audit](receipts/pilot-r30-row-audit.json), [execution receipt](receipts/pilot-r30-execution.md).

The actual experimental source closure governs reproduction. Five inherited files match baseline commit `f85c66d375a949e007d9aeff6983c3f028c64b50`, rather than the later distribution tree; their exact git blobs and hashes are recorded in [source provenance](receipts/terminal-r29-inherited-source-provenance.json). No newer-main files were substituted during the experiment, and no whole-main-tree test equivalence is claimed.

## Registration and fixed interpretation

Fresh R30 BASE **2444755928545600** was drawn from `os.urandom(6)<<4` at **13:41:00 UTC / 06:41:00 PDT**, after all final gates and repair publication, before bank generation or games. The bank retains the original 54-row projection pool, constants and common scope; 41 source rows were sampled across the 100 cases.

- [Registration](receipts/pilot-r30-registration.json): SHA256 `bc41e9a4274499894e05c95dde90bfd798141504cd594ac6fce1cc139992d056`.
- [Bank](receipts/pilot-r30-bank.json): SHA256 `9ef6bbade097dfc1040cf5eac6ce5eccce132c464b4bc9d429948422778844a6`; [audit](receipts/pilot-r30-bank-audit.json).
- Repair publication: `63cd3e42f8058ed6964706349a6ac3acd2a7d38e`; registration/bank publication before games: `04f5730f304ca32da517ad4314643a2065ea6ece`.
- The single reviewed launcher ran on 01 from 13:46:08 to 14:09:22 UTC / 06:46:08–07:09:22 PDT, under nice 10 and the existing CPU lease: eight game children plus one parent, with one additional report slot when needed. Four open incomplete reports were preserved at 12, 26, 53 and 78 primary pairs. No optional stopping occurred.

Truth was pinned RoyaleSim 0.1.34 / client 16.402, with planning on the owned matching `live16402b-r2` runtime. Own levels were Valkyrie 5, Archers 7, Minions 5, Cannon 6, Fireball 5, Giant 6, MiniPekka 5 and Musketeer 4; both towers were 6. This is the explicitly authorized fixed scenario plus ACCOUNT-LOG, not a fresh `collection.json` extraction (that file was absent). Opponent true levels were independent per-card population draws with the registered rarity adjustment/floors. B used the fixed fair estimate common 5 / rare 4 / epic 6 / legendary 9 / champion 11, tower 6; no per-match hidden levels, deck or order were supplied to it.

A assumed level 11 for roots, rollout configuration and native metadata. B0 used the legacy root-only scaler: own producer levels, opponent bodies at 5 without rarity adjustment, tower input 6 on the old card ladder, rollout/native metadata at 11. B used corrected roots, tower curves and qualified seat spell/payload templates. Its crown metadata affects **leaf evaluation and scripted crown-spell lethality/Lightning**, while identical-state learned-feature invariance is evidence only for that layer. Learned weights, features and static columns were frozen. Native Mirror payload level 12 and direct-cast holder-key limitations remain disclosed in DESIGN.

The common supported-card prior excluded Clone, Earthquake and Tornado before outcomes: 425/2,925 decks and 15,371/69,380 frequency weight = **22.15479965%**. It retained 2,500 decks, with all 54 original true-deck projections unchanged. Every arm and poller used the same restriction and simulator eligibility adapter. This is a conditional-population physics experiment, not literal current-LIVE-prior equivalence. Native rollout geometry and LIVE placement laws are not claimed equivalent; unsupported playable exports fail closed. No outcome-dependent scope or seed change occurred.

## Validation and preserved failed run

Fresh independent R29 review approved the exact three-file lifecycle repair and bounded commands. The final matching-byte gates passed before R30 registration:

| gate | result | evidence |
| --- | --- | --- |
| exact-binary boundary/scoring | 6/6 cases; both clients, weaker-seat swaps and delayed draws | [audit](receipts/terminal-boundary-r28-owner-audit.json) |
| cold immutable-cache failures | 9/9 | [log](receipts/pytest-preload-isolated-r28.txt) |
| actual six-file integration | 256/256; 0 skips, including 40 terminal fixtures | [audit](receipts/integration-terminal-r28-owner-audit.json) |
| native physics/transport/fairness | 254/254 | [audit](receipts/gates-terminal-r28-owner-audit.json) |
| original all-level-11 game bank | 8 clean games; 4 full command and final-state hash pairs; positive B roots | [audit](receipts/all11-terminal-r28-owner-audit.json) |
| unchanged static placement contract | 145 classifications and 1,024 exact-binary commands | [audit](receipts/placement-micro-r21-owner-audit.json) |

Native gates include 121 exports, 13 tower checks, 32 public bodies, four actual fair B decisions and 30 comparisons each through cut, snapshot and one-worker raw-fc transport. A→B→A changes then reuses the content key, with shipped cache sizes [1,2,2]. All 20 snapshot differences are only absent `spell_name` becoming empty strings; there is no numeric/type/entity/order/owner/position/key waiver. This scripted transport test is not learned-pool LIVE evidence. Exact Fireball/Poison/cache anchors remained unchanged.

**R27 remains permanently invalid and is not combined with R30.** It stopped with 55 rows: 47 terminal, including four failed winning outcomes with 16 late GAME_OVER refusals, plus eight interrupted games; 245 requested games were missing. The old wrapper confused command closure with later final game_over. The reviewed common repair preserves unsent queues and continues native HP-drain scoring, without changing policy or physics. R30 used an entirely fresh preregistered full bank; all 58 original R27 output files still match their inventory. [Preserved audit](receipts/pilot-r27-stop-audit.json), [root-cause evidence](receipts/pilot-r27-terminal-order-audit.md). Earlier failed DEV receipts also remain preserved. The twice admission-timed-out exploratory 03 probe was explicitly accepted as a nonblocking resource deferral; it was not retried.

## Separate s27 diagnostic and completion

The required [s27 offline replay](S27-M02.md) is complete: 52 fixtures passed and 23/23 paired public opportunities exercised B roots with zero errors/native failures/queue mismatches. Three action IDs and three wait durations changed; Cannon was selected zero times in either arm. Five acknowledged taps plus one explicitly UNVERIFIED internal reservation preserve the recorded queue context, not six acknowledged plays. Its conditional future, stale perception and writer-provenance limitations remain; it supplies no causal outcome or 200 ms latency conclusion.

There are no remaining pilot blockers or owned running jobs/helpers. No confirmation, latency benchmark, LIVE/model/runtime promotion, emulator/account action or GPU work was performed. Rollback remains selection of standard A/removal of experiment hooks, preserving original/restricted priors, good/bad caches, frozen models and all failed evidence. A future study requires a new reason and authorization under the fixed decision rule.

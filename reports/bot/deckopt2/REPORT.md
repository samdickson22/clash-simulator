# Reachable-level deck search — true Battle Log validation

Updated 2026-10-17T02:31:30Z. Exploration; no live deployment performed. Full-pool true-Battle-Log validation has an independently registered bank; it takes precedence for the live recommendation if deployed.

## Final recommendation

Recommend Valkyrie L5, Archers L7, Goblins L6, InfernoTower L7, Fireball L6, Giant L7, MiniPekka L5, Skeletons L7.

Registered true-deck validation: 4,500 clean games; 150 paired cases per opponent policy, deck and player. The upgraded baseline uses its own gold/wild-card allocation. These final validation rows alone support the decision.

|Player|Group|Baseline win%|Chosen deck win%|Paired Δ pp [95% CI]|
|---|---|---:|---:|---|
|base|weak pool|97.7|99.0|+1.3 [-0.7, +3.3]|
|base|strong opponent|78.0|92.7|+14.7 [+6.7, +22.7]|
|base|pooled|91.1|96.9|+5.8 [+2.7, +8.7]|
|reserve|weak pool|97.7|99.0|+1.3 [-0.7, +3.3]|
|reserve|strong opponent|85.3|94.0|+8.7 [+2.0, +15.3]|
|reserve|pooled|93.6|97.3|+3.8 [+1.1, +6.4]|

Remaining ordered upgrades cost **3625 gold**; original-budget total **5025**, including the 1,400 gold already committed to Fireball/Giant. Gold left 5296; gems spent 0. Exact steps appear below and in FULLPOOL-PLAN.json.

This selects among the four registered finalists from the 32-deck budget screen; it does not establish a global deck or upgrade optimum. The recommendation is conditional on the sampled opponent-level population and the serial no-wall full-pool twin. Pointwise paired bootstrap intervals do not include simulator, level-prior or wall200 timing uncertainty. rext-bc is n/a for true decks.

Ranking is close: giant-hut-arrows also passes, with 873/900 combined wins versus 874/900 for the registered winner, and costs 775 remaining gold. This is not evidence of head-to-head superiority; the registered mean-win-rate ranking chooses the deck above.

Final integrity audit passed 2026-10-17T02:29:10Z: all 4500 registered rows terminal and clean; all 22 recovery and 2250 interim hashes retained. Own cutoff hits 0/545864 (serial configuration).

King L6 confirmed on the live home screen (3312 HP). Both players retain deployed all-L11 planning; only simulator truth uses real levels. Each stage is registered independently.

## Full-pool true-deck variant

Real-level actual-wall200 reserve-bundle smoke passed 2026-10-16T21:16:08Z: terminal3667ticks,0ownrefusals,0unmapped rows,no native/live errors,packet checks clean. This single preflight is not validation.

Unpinned, loaded-01 wall smoke cutoff **102/156 = 65.4%**; default 64.7%. This R3a smoke used one Runtime. It is a separate setup/timing observation, not an efficacy row. The owner’s later package timing on pinned cores reports cutoff3.5% non-res (6games) and2.7% res (8games), versus C56base4.4% (5games); these are separate fleet observations (BUNDLE.md b8d41879), updated from the earlier3.1–3.2% partial snapshot. No additional wall200 rows are planned without quiet dedicated cores.

BOT LEAD cleared the gate (strong+0.150,R3a+0.054,v1+0.028) and approved serial no-wall c4 validation: set_deadline(None,1), native_threads1, pool_size0, chunks4, live deadline cleared, f1a2 explicit. Versus K4L-R-gs-rw-fc-c4-mk1a1, the fallback differs: f1a2 rather than R3a. A duplicate-case command-hash proof is required before locking the bank. Strong remains current C56 LiveBelief+it5s2, threads1, extended R3a proposer, scoped separate Runtime. Each side logs belief and fast tier at start. rext-bc is n/a for this variant.

The first serial repeat exposed a harness-only stale Recorder deadline: its cached200ms value caused wall-lateness despite inner no-wall settings. Failed preflight rows are retained; the wrapper now clears/asserts the effective deadline and the duplicate-case proof is rerun before locking validation. The projected harness already asserts all effective deadlinesNone.

Deployment package reconciled with owner BUNDLE.md (main2fa5d496, docb8d41879): f1a2 regression check passed and its pinned model/calibration files match our copies. Evaluation source1a65dcd1 differs only by the package’s added, inactive Mac runtime-pin entry; active Linux r3 code is unchanged. Full details: fullpool/release-reconciliation.json.

Serial duplicate-case proof passed 2026-10-16T21:42:45Z; identical command SHA `770040f643d1916be6ce7823d62ec8bc8bc6a107342ae6e4658956e92c670eca`.

## Projected implementation parity receipt

Requested five projected-validation cases per player, including two strong-opponent cases, completed 2026-10-16T23:08:52Z. All command/state/terminal comparisons identical: True; reserve activity confirmed in both implementations on the required res strong cases: True. Selected implementation: fc-c4 serial fast reduction. Receipt SHA `c4eb4260bbd7436c4305535b03e6df9148e2bcfccd17da5496431aba3f2da5cd`. These games are implementation checks and are excluded from validation counts; no outcomes were used for selection.

Full-pool diagnostic correction: pinned royalesim_vocab.py declares SpearGoblin_Dummy in NO_COUNTERPART (Goblin Hut garrison sprite), and royalesim_translate._lazy_unit intentionally drops it. Its raw counter is misleadingly named unmapped_unit. The full harness initially stopped on this expected counter. fullpool_clean.py exempts only that predeclared visual row; all other missing/unmapped rows and genuine failures remain flags. Every raw row and bank stays unchanged. Recovery verifies original producer exit, preserves row hashes, resumes only missing arms, and keeps partial cases on their original host. The frozen game worker, player settings and observation mapping are unchanged. Full provenance is in fullpool/resume-manifest.json once recovery is registered.

BOT LEAD protocol update: the full-pool bundle is scheduled live00:00Z, so the true-deck4500-game bank governs the decision. Projected6000-game validation is optional only after true validation finishes and CPU is idle; otherwise it is recorded not run. Its fresh bank and5/5-per-player fc-c4 parity receipt remain available. An interim read freezes225complete paired cases with actual per-policy n, paired CIs and completion-time-bias caveat; it is not a decision. No extra01/03capacity is admitted beyond4workers each.

## True Battle Log full-pool validation

4500/4500 rows; 0 flagged. Fresh bank drawn 2026-10-16T22:58:52Z; SHA `8eaf2214600b5a0fa31297cf113e482ac9b02e81cdc8db9adaabf41b2b82a8a2`.

Truth uses all original Battle Log cards, RoyaleSim16.402 with real levels; runtime live16402b-r3. Our owned C56 cards use the same frozen B upgrade vectors. Weak pool is full-pool R3a+v1; strong is the specified C56-belief/it5s2 opponent with extended R3a proposer. rext-bc n/a. Pooled weights each of the three policies equally. Both players use the approved serial no-wall configuration. Its cutoff rates are zero by construction; candidate-specific wall200 timing effects are unmeasured. The owner’s pinned wall timing is a separate bundle-level observation.

|Player|Deck|Group|Paired n|Win%|Baseline%|Δ pp [95% CI]|
|---|---|---|---:|---:|---:|---|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-goblins-skeletons|weak pool|300|99.0|97.7|+1.3 [-0.7, +3.3]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-goblins-skeletons|strong opponent|150|92.7|78.0|+14.7 [+6.7, +22.7]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-goblins-skeletons|pooled|450|96.9|91.1|+5.8 [+2.7, +8.7]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-wizard|weak pool|300|99.0|97.7|+1.3 [-0.7, +3.3]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-wizard|strong opponent|150|87.3|78.0|+9.3 [+1.3, +17.3]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-wizard|pooled|450|95.1|91.1|+4.0 [+1.1, +6.9]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-wizard-arrows|weak pool|300|97.7|97.7|+0.0 [-2.3, +2.3]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-wizard-arrows|strong opponent|150|87.3|78.0|+9.3 [+1.3, +17.3]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-wizard-arrows|pooled|450|94.2|91.1|+3.1 [+0.0, +6.2]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|giant-hut-arrows|weak pool|300|98.0|97.7|+0.3 [-2.0, +2.7]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|giant-hut-arrows|strong opponent|150|92.7|78.0|+14.7 [+6.7, +22.7]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|giant-hut-arrows|pooled|450|96.2|91.1|+5.1 [+2.0, +8.2]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-goblins-skeletons|weak pool|300|99.0|97.7|+1.3 [-0.7, +3.3]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-goblins-skeletons|strong opponent|150|94.0|85.3|+8.7 [+2.0, +15.3]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-goblins-skeletons|pooled|450|97.3|93.6|+3.8 [+1.1, +6.4]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-wizard|weak pool|300|99.0|97.7|+1.3 [-0.7, +3.3]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-wizard|strong opponent|150|95.3|85.3|+10.0 [+3.3, +16.7]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-wizard|pooled|450|97.8|93.6|+4.2 [+1.8, +6.9]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-wizard-arrows|weak pool|300|97.7|97.7|+0.0 [-2.3, +2.3]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-wizard-arrows|strong opponent|150|92.0|85.3|+6.7 [+0.0, +13.3]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-wizard-arrows|pooled|450|95.8|93.6|+2.2 [-0.7, +4.9]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|giant-hut-arrows|weak pool|300|99.0|97.7|+1.3 [-0.7, +3.3]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|giant-hut-arrows|strong opponent|150|95.3|85.3|+10.0 [+4.0, +16.7]|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|giant-hut-arrows|pooled|450|97.8|93.6|+4.2 [+1.8, +6.7]|

Public reaction/defence diagnostics (descriptive, separate from win-rate inference):

|Player|Deck|Group|Games|Enemy-play reaction p50/p90 s|Enemy Giant reaction p50/p90 s|Giant defence minus crossing p50/p90 s|Undefended Giant pushes|Median game search p50 ms|
|---|---|---|---:|---|---|---|---|---:|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|baseline|weak pool|300|2.90/7.40|3.15/7.40|-2.00/3.20|24/490 (4.9%)|125.49|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|baseline|strong opponent|150|2.15/6.65|2.15/5.20|-4.20/1.26|1/84 (1.2%)|141.94|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|baseline|pooled|450|2.65/7.15|3.15/7.15|-2.20/3.20|25/574 (4.4%)|129.45|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-goblins-skeletons|weak pool|300|2.90/7.90|2.65/6.98|-2.35/2.65|15/360 (4.2%)|179.83|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-goblins-skeletons|strong opponent|150|2.15/6.65|1.65/5.45|-4.35/1.82|0/50 (0.0%)|276.81|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-goblins-skeletons|pooled|450|2.65/7.15|2.40/6.90|-2.50/2.50|15/410 (3.7%)|207.32|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-wizard|weak pool|300|3.15/8.40|3.15/8.15|-1.80/4.20|40/412 (9.7%)|113.27|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-wizard|strong opponent|150|2.65/7.45|2.65/6.15|-2.20/2.80|2/50 (4.0%)|122.24|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-wizard|pooled|450|3.15/8.15|3.15/7.90|-1.80/3.90|42/462 (9.1%)|116.00|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-wizard-arrows|weak pool|300|3.40/8.65|3.65/8.65|-0.80/6.12|70/443 (15.8%)|132.97|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-wizard-arrows|strong opponent|150|2.65/8.15|2.65/7.05|-1.65/3.20|1/53 (1.9%)|134.09|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-wizard-arrows|pooled|450|3.15/8.15|3.40/8.65|-0.80/5.80|71/496 (14.3%)|133.78|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|giant-hut-arrows|weak pool|300|3.15/8.15|3.40/8.65|-1.00/5.94|49/506 (9.7%)|122.66|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|giant-hut-arrows|strong opponent|150|2.65/7.65|3.15/5.45|-3.20/1.16|2/50 (4.0%)|131.10|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|giant-hut-arrows|pooled|450|2.90/7.90|3.15/8.40|-1.50/5.80|51/556 (9.2%)|124.84|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|baseline|weak pool|300|3.15/8.15|2.90/6.65|-1.80/3.20|19/505 (3.8%)|263.97|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|baseline|strong opponent|150|2.65/7.15|1.90/5.15|-3.75/0.20|1/69 (1.4%)|288.31|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|baseline|pooled|450|2.90/7.90|2.90/6.65|-2.00/3.20|20/574 (3.5%)|272.76|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-goblins-skeletons|weak pool|300|2.90/7.90|2.90/6.40|-2.20/2.80|17/392 (4.3%)|282.46|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-goblins-skeletons|strong opponent|150|2.15/6.65|1.15/3.15|-4.00/0.40|1/36 (2.8%)|324.34|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-goblins-skeletons|pooled|450|2.65/7.40|2.65/6.15|-2.50/2.80|18/428 (4.2%)|293.19|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-wizard|weak pool|300|3.90/9.15|3.65/8.15|-1.00/4.62|45/419 (10.7%)|163.25|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-wizard|strong opponent|150|3.15/8.15|3.15/7.15|-4.20/2.98|0/33 (0.0%)|182.31|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-wizard|pooled|450|3.40/8.65|3.65/8.15|-1.20/4.26|45/452 (10.0%)|167.36|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-wizard-arrows|weak pool|300|3.90/9.65|3.90/8.15|-1.00/4.20|36/433 (8.3%)|270.06|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-wizard-arrows|strong opponent|150|3.15/8.65|3.15/7.15|-1.00/2.88|1/41 (2.4%)|258.35|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-wizard-arrows|pooled|450|3.65/9.15|3.90/8.15|-1.00/4.20|37/474 (7.8%)|266.37|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|giant-hut-arrows|weak pool|300|3.40/8.65|3.90/7.53|-0.80/4.50|35/485 (7.2%)|270.49|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|giant-hut-arrows|strong opponent|150|2.65/7.65|2.65/5.45|-1.35/3.20|0/55 (0.0%)|268.98|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|giant-hut-arrows|pooled|450|3.15/8.40|3.90/7.15|-1.00/4.38|35/540 (6.5%)|269.68|

Reaction is accepted enemy play to next own submitted play in simulator seconds; terminal enemy plays without a later own play are unobserved. An own play need not defend that threat. Percentiles pool observed events. Undefended share is the existing live_metrics enemy Giant lane-track proxy: no same-lane defence before contact, divided by observed Giant pushes. Defence-minus-crossing is signed time to first qualifying defence (negative means before river crossing), conditional on any defence observed. Contact-only denominators are also in metrics-summary.json. These proxies do not attribute damage causally. Search milliseconds are host-load-dependent measurements of the unbounded twin, not deployed wall200 latency.


|Player|Deck|Cutoffs/search decisions|Rate|
|---|---|---:|---:|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|baseline|0/59538|0.00%|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-goblins-skeletons|0/53600|0.00%|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-wizard|0/53541|0.00%|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|budget-inferno-wizard-arrows|0/53018|0.00%|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1|giant-hut-arrows|0/53445|0.00%|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|baseline|0/58584|0.00%|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-goblins-skeletons|0/53301|0.00%|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-wizard|0/53610|0.00%|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|budget-inferno-wizard-arrows|0/52037|0.00%|
|FP-LD-K4L-R-gs-rw-fc-c4-mk1a1-res|giant-hut-arrows|0/55190|0.00%|
## True-deck decision and ordered upgrade plan

**budget-inferno-goblins-skeletons**: Valkyrie L5, Archers L7, Goblins L6, InfernoTower L7, Fireball L6, Giant L7, MiniPekka L5, Skeletons L7.

Validation meets the registered per-player pooled/strong evidence bar. This true-deck result takes precedence if the full-pool bundle is deployed.

|Order|Card|Level|Gold|Held copies|Wild cards|
|---:|---|---|---:|---:|---|
|1|InfernoTower|3→4|50|2|0 Rare|
|2|InfernoTower|4→5|150|4|0 Rare|
|3|InfernoTower|5→6|400|10|0 Rare|
|4|InfernoTower|6→7|1000|20|0 Rare|
|5|Skeletons|5→6|400|50|0 Common|
|6|Skeletons|6→7|1000|100|0 Common|
|7|Goblins|1→2|5|2|0 Common|
|8|Goblins|2→3|20|4|0 Common|
|9|Goblins|3→4|50|10|0 Common|
|10|Goblins|4→5|150|20|0 Common|
|11|Goblins|5→6|400|50|0 Common|

Remaining spend 3625gold; original-budget total 5025, including committed Fireball400+Giant1000; gold left 5296. Gems spent0. Wilds left: {'Champion': 0, 'Common': 59, 'Epic': 0, 'Legendary': 0, 'Rare': 2}.

Interim descriptive read: fullpool/interim-50/REPORT.md. It does not authorize a deck change; final inference still uses the complete registered bank.

## C56-projected validation: not run

Recorded 2026-10-17T02:29:58Z: The true-deck decision is complete. The shared 04 host still has 60 active Python processes, three leases and load about 60; capacity was returned for competing work after the BOT LEAD's tail-lease request. A 42-slot admission probe would fit, but the host is not idle. No extra 01/03 capacity is authorized, so the optional 6,000 projected games were not launched. The independent bank and passed parity receipt are retained, but no projected validation efficacy claim is made. The completed projected screens remain reference evidence only.

## Original ten-deck screen

1280/1280 rows; 0 unclean. Bank drawn 2026-10-16T19:53:03Z; SHA `9d58111f52140e51bb8ed3cdb26f1eecb53c8e959aa3b43f76d6dcfb58ad66c0`.

Collection SHA `294eaf5bb34885517748013ca491724f8f29b5fb21add070217c00dfbd4e3d04`; King 6. True owned levels: Archers L7, Arrows L1, Bomber L1, Cannon L6, Fireball L5, Giant L6, GoblinCage L5, GoblinHut L5, Goblins L1, Knight L3, MegaMinion L3, MiniPekka L5, Minions L5, Musketeer L4, Skeletons L5, SpearGoblins L1, Tombstone L5, Valkyrie L5.

|Player|Deck|Opponent group|Paired n|Win%|Baseline%|Δ pp [95% CI]|
|---|---|---|---:|---:|---:|---|
|LD-K4L-R-gs-rw|giant-arrows|weak pool|32|96.9|96.9|+0.0 [-9.4, +9.4]|
|LD-K4L-R-gs-rw|giant-arrows|strong opponent|16|68.8|62.5|+6.2 [-18.8, +31.2]|
|LD-K4L-R-gs-rw|giant-arrows|rext-bc|16|93.8|100.0|-6.2 [-18.8, +0.0]|
|LD-K4L-R-gs-rw|giant-arrows|pooled|64|89.1|89.1|+0.0 [-7.8, +7.8]|
|LD-K4L-R-gs-rw|giant-classic|weak pool|32|87.5|96.9|-9.4 [-18.8, +0.0]|
|LD-K4L-R-gs-rw|giant-classic|strong opponent|16|43.8|62.5|-18.8 [-43.8, +6.2]|
|LD-K4L-R-gs-rw|giant-classic|rext-bc|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw|giant-classic|pooled|64|79.7|89.1|-9.4 [-17.2, -1.6]|
|LD-K4L-R-gs-rw|giant-goblins|weak pool|32|100.0|96.9|+3.1 [+0.0, +9.4]|
|LD-K4L-R-gs-rw|giant-goblins|strong opponent|16|68.8|62.5|+6.2 [-25.0, +37.5]|
|LD-K4L-R-gs-rw|giant-goblins|rext-bc|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw|giant-goblins|pooled|64|92.2|89.1|+3.1 [-6.2, +10.9]|
|LD-K4L-R-gs-rw|giant-skeleton-cycle|weak pool|32|96.9|96.9|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw|giant-skeleton-cycle|strong opponent|16|81.2|62.5|+18.8 [-12.5, +50.0]|
|LD-K4L-R-gs-rw|giant-skeleton-cycle|rext-bc|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw|giant-skeleton-cycle|pooled|64|93.8|89.1|+4.7 [-3.1, +12.5]|
|LD-K4L-R-gs-rw|giant-archers-cycle|weak pool|32|100.0|96.9|+3.1 [+0.0, +9.4]|
|LD-K4L-R-gs-rw|giant-archers-cycle|strong opponent|16|75.0|62.5|+12.5 [-12.5, +37.5]|
|LD-K4L-R-gs-rw|giant-archers-cycle|rext-bc|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw|giant-archers-cycle|pooled|64|93.8|89.1|+4.7 [-1.6, +10.9]|
|LD-K4L-R-gs-rw|giant-musket-cycle|weak pool|32|96.9|96.9|+0.0 [-9.4, +9.4]|
|LD-K4L-R-gs-rw|giant-musket-cycle|strong opponent|16|68.8|62.5|+6.2 [-18.8, +31.2]|
|LD-K4L-R-gs-rw|giant-musket-cycle|rext-bc|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw|giant-musket-cycle|pooled|64|90.6|89.1|+1.6 [-6.2, +9.4]|
|LD-K4L-R-gs-rw|giant-hut|weak pool|32|96.9|96.9|+0.0 [-9.4, +9.4]|
|LD-K4L-R-gs-rw|giant-hut|strong opponent|16|50.0|62.5|-12.5 [-43.8, +18.8]|
|LD-K4L-R-gs-rw|giant-hut|rext-bc|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw|giant-hut|pooled|64|85.9|89.1|-3.1 [-12.5, +6.2]|
|LD-K4L-R-gs-rw|giant-hut-classic|weak pool|32|87.5|96.9|-9.4 [-18.8, +0.0]|
|LD-K4L-R-gs-rw|giant-hut-classic|strong opponent|16|81.2|62.5|+18.8 [+0.0, +37.5]|
|LD-K4L-R-gs-rw|giant-hut-classic|rext-bc|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw|giant-hut-classic|pooled|64|89.1|89.1|+0.0 [-6.2, +6.2]|
|LD-K4L-R-gs-rw|giant-hut-arrows|weak pool|32|96.9|96.9|+0.0 [-9.4, +9.4]|
|LD-K4L-R-gs-rw|giant-hut-arrows|strong opponent|16|81.2|62.5|+18.8 [+0.0, +37.5]|
|LD-K4L-R-gs-rw|giant-hut-arrows|rext-bc|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw|giant-hut-arrows|pooled|64|93.8|89.1|+4.7 [-1.6, +10.9]|
|LD-K4L-R-gs-rw-res|giant-arrows|weak pool|32|100.0|96.9|+3.1 [+0.0, +9.4]|
|LD-K4L-R-gs-rw-res|giant-arrows|strong opponent|16|75.0|81.2|-6.2 [-31.2, +18.8]|
|LD-K4L-R-gs-rw-res|giant-arrows|rext-bc|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-arrows|pooled|64|93.8|93.8|+0.0 [-7.8, +7.8]|
|LD-K4L-R-gs-rw-res|giant-classic|weak pool|32|100.0|96.9|+3.1 [+0.0, +9.4]|
|LD-K4L-R-gs-rw-res|giant-classic|strong opponent|16|43.8|81.2|-37.5 [-62.5, -12.5]|
|LD-K4L-R-gs-rw-res|giant-classic|rext-bc|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-classic|pooled|64|85.9|93.8|-7.8 [-14.1, -1.6]|
|LD-K4L-R-gs-rw-res|giant-goblins|weak pool|32|96.9|96.9|+0.0 [-9.4, +9.4]|
|LD-K4L-R-gs-rw-res|giant-goblins|strong opponent|16|81.2|81.2|+0.0 [-18.8, +18.8]|
|LD-K4L-R-gs-rw-res|giant-goblins|rext-bc|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-goblins|pooled|64|93.8|93.8|+0.0 [-6.2, +6.2]|
|LD-K4L-R-gs-rw-res|giant-skeleton-cycle|weak pool|32|96.9|96.9|+0.0 [-9.4, +9.4]|
|LD-K4L-R-gs-rw-res|giant-skeleton-cycle|strong opponent|16|62.5|81.2|-18.8 [-50.0, +12.5]|
|LD-K4L-R-gs-rw-res|giant-skeleton-cycle|rext-bc|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-skeleton-cycle|pooled|64|89.1|93.8|-4.7 [-14.1, +4.7]|
|LD-K4L-R-gs-rw-res|giant-archers-cycle|weak pool|32|93.8|96.9|-3.1 [-9.4, +0.0]|
|LD-K4L-R-gs-rw-res|giant-archers-cycle|strong opponent|16|87.5|81.2|+6.2 [-12.5, +25.0]|
|LD-K4L-R-gs-rw-res|giant-archers-cycle|rext-bc|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-archers-cycle|pooled|64|93.8|93.8|+0.0 [-6.2, +6.2]|
|LD-K4L-R-gs-rw-res|giant-musket-cycle|weak pool|32|93.8|96.9|-3.1 [-12.5, +6.2]|
|LD-K4L-R-gs-rw-res|giant-musket-cycle|strong opponent|16|62.5|81.2|-18.8 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|giant-musket-cycle|rext-bc|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-musket-cycle|pooled|64|87.5|93.8|-6.2 [-14.1, +0.0]|
|LD-K4L-R-gs-rw-res|giant-hut|weak pool|32|100.0|96.9|+3.1 [+0.0, +9.4]|
|LD-K4L-R-gs-rw-res|giant-hut|strong opponent|16|87.5|81.2|+6.2 [-12.5, +25.0]|
|LD-K4L-R-gs-rw-res|giant-hut|rext-bc|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-hut|pooled|64|96.9|93.8|+3.1 [-3.1, +9.4]|
|LD-K4L-R-gs-rw-res|giant-hut-classic|weak pool|32|100.0|96.9|+3.1 [+0.0, +9.4]|
|LD-K4L-R-gs-rw-res|giant-hut-classic|strong opponent|16|81.2|81.2|+0.0 [-18.8, +18.8]|
|LD-K4L-R-gs-rw-res|giant-hut-classic|rext-bc|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-hut-classic|pooled|64|95.3|93.8|+1.6 [-3.1, +6.2]|
|LD-K4L-R-gs-rw-res|giant-hut-arrows|weak pool|32|100.0|96.9|+3.1 [+0.0, +9.4]|
|LD-K4L-R-gs-rw-res|giant-hut-arrows|strong opponent|16|93.8|81.2|+12.5 [+0.0, +31.2]|
|LD-K4L-R-gs-rw-res|giant-hut-arrows|rext-bc|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-hut-arrows|pooled|64|98.4|93.8|+4.7 [+0.0, +10.9]|

Candidate decks:

- baseline: Valkyrie L5, Archers L7, Minions L5, Cannon L6, Fireball L5, Giant L6, MiniPekka L5, Musketeer L4
- giant-arrows: Valkyrie L5, Archers L7, Minions L5, Arrows L1, Fireball L5, Giant L6, MiniPekka L5, Musketeer L4
- giant-classic: Archers L7, Arrows L1, Fireball L5, Giant L6, Knight L3, MiniPekka L5, Minions L5, Musketeer L4
- giant-goblins: Valkyrie L5, Goblins L1, Minions L5, Cannon L6, Fireball L5, Giant L6, MiniPekka L5, Musketeer L4
- giant-skeleton-cycle: Valkyrie L5, Archers L7, Minions L5, Skeletons L5, Fireball L5, Giant L6, MiniPekka L5, Musketeer L4
- giant-archers-cycle: Valkyrie L5, Archers L7, Skeletons L5, Cannon L6, Fireball L5, Giant L6, MiniPekka L5, Musketeer L4
- giant-musket-cycle: Valkyrie L5, Skeletons L5, Minions L5, Cannon L6, Fireball L5, Giant L6, MiniPekka L5, Musketeer L4
- giant-hut: Valkyrie L5, Archers L7, Minions L5, GoblinHut L5, Fireball L5, Giant L6, MiniPekka L5, Musketeer L4
- giant-hut-classic: Archers L7, GoblinHut L5, Fireball L5, Giant L6, Knight L3, MiniPekka L5, Minions L5, Musketeer L4
- giant-hut-arrows: Valkyrie L5, Archers L7, GoblinHut L5, Arrows L1, Fireball L5, Giant L6, MiniPekka L5, Musketeer L4

## Gold-budget 32-deck screen

1024/1024 rows; 0 unclean. Bank drawn 2026-10-16T21:47:11Z; SHA `1365e24caa32f7185daea69a715c80e8d8fa608ea49f12c2a938d9faf0a0e152`.

Collection SHA `81951375d9944134c8d989d8b56ad193d3626d6871dbb6eb4902a7a63b16c712`; King 6. True owned levels: Archers L7, Cannon L6, Fireball L6, Giant L7, MiniPekka L5, Minions L6, Musketeer L5, Valkyrie L5.

|Player|Deck|Opponent group|Paired n|Win%|Baseline%|Δ pp [95% CI]|
|---|---|---|---:|---:|---:|---|
|LD-K4L-R-gs-rw-res|budget-fire-spirits|weak pool|16|93.8|100.0|-6.2 [-18.8, +0.0]|
|LD-K4L-R-gs-rw-res|budget-fire-spirits|strong opponent|8|75.0|100.0|-25.0 [-62.5, +0.0]|
|LD-K4L-R-gs-rw-res|budget-fire-spirits|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-fire-spirits|pooled|32|90.6|100.0|-9.4 [-18.8, +0.0]|
|LD-K4L-R-gs-rw-res|budget-fire-spirits-minions|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-fire-spirits-minions|strong opponent|8|87.5|100.0|-12.5 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|budget-fire-spirits-minions|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-fire-spirits-minions|pooled|32|96.9|100.0|-3.1 [-9.4, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno|weak pool|16|87.5|100.0|-12.5 [-31.2, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno|strong opponent|8|87.5|100.0|-12.5 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno|pooled|32|90.6|100.0|-9.4 [-18.8, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-arrows|weak pool|16|93.8|100.0|-6.2 [-18.8, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-arrows|strong opponent|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-arrows|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-arrows|pooled|32|96.9|100.0|-3.1 [-9.4, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-goblins|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-goblins|strong opponent|8|87.5|100.0|-12.5 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-goblins|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-goblins|pooled|32|96.9|100.0|-3.1 [-9.4, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-goblins-skeletons|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-goblins-skeletons|strong opponent|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-goblins-skeletons|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-goblins-skeletons|pooled|32|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-skeletons|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-skeletons|strong opponent|8|75.0|100.0|-25.0 [-62.5, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-skeletons|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-skeletons|pooled|32|93.8|100.0|-6.2 [-15.6, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-skeletons-musket|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-skeletons-musket|strong opponent|8|87.5|100.0|-12.5 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-skeletons-musket|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-skeletons-musket|pooled|32|96.9|100.0|-3.1 [-9.4, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard|strong opponent|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard|pooled|32|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-arrows|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-arrows|strong opponent|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-arrows|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-arrows|pooled|32|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-fire|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-fire|strong opponent|8|87.5|100.0|-12.5 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-fire|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-fire|pooled|32|96.9|100.0|-3.1 [-9.4, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-skeletons|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-skeletons|strong opponent|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-skeletons|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-skeletons|pooled|32|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-skeletons-arrows|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-skeletons-arrows|strong opponent|8|87.5|100.0|-12.5 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|budget-skeletons-arrows|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-skeletons-arrows|pooled|32|96.9|100.0|-3.1 [-9.4, +0.0]|
|LD-K4L-R-gs-rw-res|budget-skeletons-fire|weak pool|16|93.8|100.0|-6.2 [-18.8, +0.0]|
|LD-K4L-R-gs-rw-res|budget-skeletons-fire|strong opponent|8|87.5|100.0|-12.5 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|budget-skeletons-fire|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-skeletons-fire|pooled|32|93.8|100.0|-6.2 [-15.6, +0.0]|
|LD-K4L-R-gs-rw-res|budget-skeletons-goblins|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-skeletons-goblins|strong opponent|8|87.5|100.0|-12.5 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|budget-skeletons-goblins|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-skeletons-goblins|pooled|32|96.9|100.0|-3.1 [-9.4, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard|strong opponent|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard|pooled|32|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-arrows|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-arrows|strong opponent|8|75.0|100.0|-25.0 [-62.5, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-arrows|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-arrows|pooled|32|93.8|100.0|-6.2 [-15.6, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-goblins|weak pool|16|93.8|100.0|-6.2 [-18.8, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-goblins|strong opponent|8|87.5|100.0|-12.5 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-goblins|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-goblins|pooled|32|93.8|100.0|-6.2 [-15.6, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-minions|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-minions|strong opponent|8|87.5|100.0|-12.5 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-minions|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-minions|pooled|32|96.9|100.0|-3.1 [-9.4, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-skeletons|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-skeletons|strong opponent|8|87.5|100.0|-12.5 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-skeletons|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-skeletons|pooled|32|96.9|100.0|-3.1 [-9.4, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-skeletons-arrows|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-skeletons-arrows|strong opponent|8|75.0|100.0|-25.0 [-62.5, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-skeletons-arrows|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-skeletons-arrows|pooled|32|93.8|100.0|-6.2 [-15.6, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-valk|weak pool|16|93.8|100.0|-6.2 [-18.8, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-valk|strong opponent|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-valk|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|budget-wizard-valk|pooled|32|96.9|100.0|-3.1 [-9.4, +0.0]|
|LD-K4L-R-gs-rw-res|giant-archers-cycle|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-archers-cycle|strong opponent|8|87.5|100.0|-12.5 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|giant-archers-cycle|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-archers-cycle|pooled|32|96.9|100.0|-3.1 [-9.4, +0.0]|
|LD-K4L-R-gs-rw-res|giant-arrows|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-arrows|strong opponent|8|87.5|100.0|-12.5 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|giant-arrows|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-arrows|pooled|32|96.9|100.0|-3.1 [-9.4, +0.0]|
|LD-K4L-R-gs-rw-res|giant-classic|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-classic|strong opponent|8|75.0|100.0|-25.0 [-62.5, +0.0]|
|LD-K4L-R-gs-rw-res|giant-classic|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-classic|pooled|32|93.8|100.0|-6.2 [-15.6, +0.0]|
|LD-K4L-R-gs-rw-res|giant-goblins|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-goblins|strong opponent|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-goblins|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-goblins|pooled|32|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-hut|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-hut|strong opponent|8|87.5|100.0|-12.5 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|giant-hut|rext-bc|8|87.5|100.0|-12.5 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|giant-hut|pooled|32|93.8|100.0|-6.2 [-15.6, +0.0]|
|LD-K4L-R-gs-rw-res|giant-hut-arrows|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-hut-arrows|strong opponent|8|87.5|100.0|-12.5 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|giant-hut-arrows|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-hut-arrows|pooled|32|96.9|100.0|-3.1 [-9.4, +0.0]|
|LD-K4L-R-gs-rw-res|giant-hut-classic|weak pool|16|93.8|100.0|-6.2 [-18.8, +0.0]|
|LD-K4L-R-gs-rw-res|giant-hut-classic|strong opponent|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-hut-classic|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-hut-classic|pooled|32|96.9|100.0|-3.1 [-9.4, +0.0]|
|LD-K4L-R-gs-rw-res|giant-musket-cycle|weak pool|16|93.8|100.0|-6.2 [-18.8, +0.0]|
|LD-K4L-R-gs-rw-res|giant-musket-cycle|strong opponent|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-musket-cycle|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-musket-cycle|pooled|32|96.9|100.0|-3.1 [-9.4, +0.0]|
|LD-K4L-R-gs-rw-res|giant-skeleton-cycle|weak pool|16|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-skeleton-cycle|strong opponent|8|87.5|100.0|-12.5 [-37.5, +0.0]|
|LD-K4L-R-gs-rw-res|giant-skeleton-cycle|rext-bc|8|100.0|100.0|+0.0 [+0.0, +0.0]|
|LD-K4L-R-gs-rw-res|giant-skeleton-cycle|pooled|32|96.9|100.0|-3.1 [-9.4, +0.0]|

Public reaction/defence diagnostics (descriptive, separate from win-rate inference):

|Player|Deck|Group|Games|Enemy-play reaction p50/p90 s|Enemy Giant reaction p50/p90 s|Giant defence minus crossing p50/p90 s|Undefended Giant pushes|Median game search p50 ms|
|---|---|---|---:|---|---|---|---|---:|
|LD-K4L-R-gs-rw-res|baseline|weak pool|16|3.40/8.90|2.90/7.25|-1.00/3.26|0/30 (0.0%)|438.43|
|LD-K4L-R-gs-rw-res|baseline|strong opponent|8|2.65/6.65|4.90/8.55|1.00/2.60|0/3 (0.0%)|444.58|
|LD-K4L-R-gs-rw-res|baseline|rext-bc|8|3.65/8.40|3.15/7.40|0.00/3.90|0/15 (0.0%)|420.31|
|LD-K4L-R-gs-rw-res|baseline|pooled|32|3.15/7.78|3.15/7.65|-0.50/3.32|0/48 (0.0%)|438.43|
|LD-K4L-R-gs-rw-res|budget-fire-spirits|weak pool|16|2.65/7.40|1.40/6.40|-3.80/2.40|2/24 (8.3%)|432.26|
|LD-K4L-R-gs-rw-res|budget-fire-spirits|strong opponent|8|2.65/6.65|0.90/1.80|-1.80/1.20|0/8 (0.0%)|412.80|
|LD-K4L-R-gs-rw-res|budget-fire-spirits|rext-bc|8|3.15/7.65|3.90/6.65|-2.00/1.10|0/19 (0.0%)|359.84|
|LD-K4L-R-gs-rw-res|budget-fire-spirits|pooled|32|2.65/7.15|2.15/6.40|-2.80/1.65|2/51 (3.9%)|409.42|
|LD-K4L-R-gs-rw-res|budget-fire-spirits-minions|weak pool|16|3.15/8.03|3.40/6.00|-2.20/5.28|2/21 (9.5%)|394.50|
|LD-K4L-R-gs-rw-res|budget-fire-spirits-minions|strong opponent|8|2.65/7.15|3.15/5.65|-1.80/0.58|0/5 (0.0%)|398.24|
|LD-K4L-R-gs-rw-res|budget-fire-spirits-minions|rext-bc|8|3.15/8.15|3.15/7.65|-0.20/3.40|0/15 (0.0%)|423.81|
|LD-K4L-R-gs-rw-res|budget-fire-spirits-minions|pooled|32|3.02/8.15|3.15/6.95|-1.80/4.16|2/41 (4.9%)|404.07|
|LD-K4L-R-gs-rw-res|budget-inferno|weak pool|16|3.65/8.63|3.40/8.45|-1.10/5.14|2/27 (7.4%)|350.91|
|LD-K4L-R-gs-rw-res|budget-inferno|strong opponent|8|3.15/8.15|2.65/4.65|0.20/0.84|0/3 (0.0%)|350.01|
|LD-K4L-R-gs-rw-res|budget-inferno|rext-bc|8|3.65/9.60|3.40/6.30|-1.00/1.86|0/18 (0.0%)|342.36|
|LD-K4L-R-gs-rw-res|budget-inferno|pooled|32|3.65/8.65|3.40/6.95|-1.00/3.48|2/48 (4.2%)|344.85|
|LD-K4L-R-gs-rw-res|budget-inferno-arrows|weak pool|16|3.65/9.65|3.40/8.40|-2.00/3.74|2/26 (7.7%)|418.98|
|LD-K4L-R-gs-rw-res|budget-inferno-arrows|strong opponent|8|2.65/8.15|1.65/6.85|-3.50/-2.14|0/3 (0.0%)|422.37|
|LD-K4L-R-gs-rw-res|budget-inferno-arrows|rext-bc|8|4.15/9.75|5.65/8.70|-1.50/2.75|0/18 (0.0%)|432.01|
|LD-K4L-R-gs-rw-res|budget-inferno-arrows|pooled|32|3.65/9.25|3.65/8.40|-2.00/3.00|2/47 (4.3%)|418.98|
|LD-K4L-R-gs-rw-res|budget-inferno-goblins|weak pool|16|3.90/8.40|3.40/6.95|-4.75/1.99|1/27 (3.7%)|343.30|
|LD-K4L-R-gs-rw-res|budget-inferno-goblins|strong opponent|8|3.15/8.65|5.90/6.50|-4.65/-4.53|0/2 (0.0%)|351.30|
|LD-K4L-R-gs-rw-res|budget-inferno-goblins|rext-bc|8|3.65/9.65|4.15/6.85|-1.75/2.08|0/15 (0.0%)|343.08|
|LD-K4L-R-gs-rw-res|budget-inferno-goblins|pooled|32|3.65/8.65|4.15/6.85|-3.60/2.20|1/44 (2.3%)|343.30|
|LD-K4L-R-gs-rw-res|budget-inferno-goblins-skeletons|weak pool|16|2.90/7.35|2.15/4.90|-4.00/3.40|1/18 (5.6%)|387.63|
|LD-K4L-R-gs-rw-res|budget-inferno-goblins-skeletons|strong opponent|8|2.65/6.65|1.15/1.55|7.00/7.00|2/2 (100.0%)|523.54|
|LD-K4L-R-gs-rw-res|budget-inferno-goblins-skeletons|rext-bc|8|3.65/9.15|2.40/4.55|-2.00/5.00|1/11 (9.1%)|410.80|
|LD-K4L-R-gs-rw-res|budget-inferno-goblins-skeletons|pooled|32|2.65/7.90|2.02/4.78|-2.50/5.80|4/31 (12.9%)|412.16|
|LD-K4L-R-gs-rw-res|budget-inferno-skeletons|weak pool|16|3.15/9.23|2.15/7.50|-1.65/3.71|2/24 (8.3%)|335.78|
|LD-K4L-R-gs-rw-res|budget-inferno-skeletons|strong opponent|8|2.65/7.65|2.65/5.15|-5.20/-4.64|0/3 (0.0%)|387.86|
|LD-K4L-R-gs-rw-res|budget-inferno-skeletons|rext-bc|8|4.15/9.15|4.40/9.25|-2.00/4.08|0/18 (0.0%)|370.20|
|LD-K4L-R-gs-rw-res|budget-inferno-skeletons|pooled|32|3.15/9.15|2.65/8.35|-2.10/3.94|2/45 (4.4%)|352.99|
|LD-K4L-R-gs-rw-res|budget-inferno-skeletons-musket|weak pool|16|3.15/8.78|2.02/4.85|-3.00/2.50|2/23 (8.7%)|343.57|
|LD-K4L-R-gs-rw-res|budget-inferno-skeletons-musket|strong opponent|8|2.65/6.65|2.90/4.70|3.50/5.50|1/2 (50.0%)|429.60|
|LD-K4L-R-gs-rw-res|budget-inferno-skeletons-musket|rext-bc|8|3.65/8.65|3.90/7.80|-0.50/4.04|1/16 (6.2%)|394.16|
|LD-K4L-R-gs-rw-res|budget-inferno-skeletons-musket|pooled|32|3.15/8.15|3.15/7.00|-1.10/3.92|4/41 (9.8%)|375.05|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard|weak pool|16|3.52/8.98|4.65/7.60|-2.00/2.00|3/31 (9.7%)|342.87|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard|strong opponent|8|3.15/8.85|3.40/4.85|-4.60/-0.20|0/4 (0.0%)|344.09|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard|rext-bc|8|4.65/9.65|4.90/8.40|-0.25/6.81|1/16 (6.2%)|349.94|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard|pooled|32|3.65/9.15|4.65/7.65|-1.20/3.38|4/51 (7.8%)|345.87|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-arrows|weak pool|16|3.90/9.90|4.15/9.03|-2.00/5.84|3/30 (10.0%)|398.18|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-arrows|strong opponent|8|3.15/8.15|3.40/7.10|-0.20/3.16|0/3 (0.0%)|417.09|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-arrows|rext-bc|8|4.15/9.60|4.15/7.65|-3.00/1.20|2/13 (15.4%)|405.16|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-arrows|pooled|32|3.65/9.15|4.15/8.12|-2.00/5.20|5/46 (10.9%)|407.57|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-fire|weak pool|16|3.15/8.63|3.15/9.15|-1.20/4.65|2/27 (7.4%)|363.07|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-fire|strong opponent|8|2.65/7.95|1.40/2.85|0.35/5.00|1/4 (25.0%)|397.14|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-fire|rext-bc|8|3.65/9.10|1.65/3.65|-1.35/2.50|0/13 (0.0%)|388.49|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-fire|pooled|32|3.15/8.65|2.65/6.30|-1.20/4.45|3/44 (6.8%)|388.73|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-skeletons|weak pool|16|3.65/8.90|4.15/8.75|-2.15/5.50|4/19 (21.1%)|363.73|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-skeletons|strong opponent|8|2.65/8.15|4.90/6.70|3.00/3.00|0/1 (0.0%)|385.70|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-skeletons|rext-bc|8|3.65/9.15|2.15/8.45|-0.80/3.20|1/15 (6.7%)|401.11|
|LD-K4L-R-gs-rw-res|budget-inferno-wizard-skeletons|pooled|32|3.15/8.65|3.78/8.80|-1.30/5.45|5/35 (14.3%)|371.64|
|LD-K4L-R-gs-rw-res|budget-skeletons-arrows|weak pool|16|3.15/7.65|2.90/6.75|-2.50/3.50|0/27 (0.0%)|428.03|
|LD-K4L-R-gs-rw-res|budget-skeletons-arrows|strong opponent|8|2.65/7.15|6.40/7.40|-2.75/-1.35|0/2 (0.0%)|471.40|
|LD-K4L-R-gs-rw-res|budget-skeletons-arrows|rext-bc|8|4.15/9.65|5.65/7.65|2.00/3.50|2/17 (11.8%)|461.02|
|LD-K4L-R-gs-rw-res|budget-skeletons-arrows|pooled|32|2.90/7.90|3.15/7.65|-0.65/3.53|2/46 (4.3%)|448.14|
|LD-K4L-R-gs-rw-res|budget-skeletons-fire|weak pool|16|2.65/7.15|2.90/5.90|-2.00/3.44|2/24 (8.3%)|477.35|
|LD-K4L-R-gs-rw-res|budget-skeletons-fire|strong opponent|8|2.15/6.65|1.65/3.55|-4.50/-2.60|0/5 (0.0%)|476.24|
|LD-K4L-R-gs-rw-res|budget-skeletons-fire|rext-bc|8|2.65/7.65|2.90/5.65|-0.50/1.37|1/15 (6.7%)|533.09|
|LD-K4L-R-gs-rw-res|budget-skeletons-fire|pooled|32|2.40/7.15|2.90/5.65|-1.75/2.57|3/44 (6.8%)|488.72|
|LD-K4L-R-gs-rw-res|budget-skeletons-goblins|weak pool|16|3.15/7.90|2.65/8.10|-2.80/4.22|1/25 (4.0%)|375.31|
|LD-K4L-R-gs-rw-res|budget-skeletons-goblins|strong opponent|8|2.65/7.60|5.15/5.15|-4.50/-4.50|0/1 (0.0%)|439.38|
|LD-K4L-R-gs-rw-res|budget-skeletons-goblins|rext-bc|8|3.15/8.15|3.15/9.35|-3.20/2.50|0/15 (0.0%)|389.57|
|LD-K4L-R-gs-rw-res|budget-skeletons-goblins|pooled|32|2.90/7.80|2.90/8.30|-3.00/4.08|1/41 (2.4%)|381.82|
|LD-K4L-R-gs-rw-res|budget-wizard|weak pool|16|3.90/8.90|3.77/7.23|-2.00/3.10|2/27 (7.4%)|387.13|
|LD-K4L-R-gs-rw-res|budget-wizard|strong opponent|8|2.65/7.65|1.15/5.95|3.00/3.00|0/1 (0.0%)|389.73|
|LD-K4L-R-gs-rw-res|budget-wizard|rext-bc|8|3.65/8.15|3.15/7.05|-3.20/-0.08|0/15 (0.0%)|372.18|
|LD-K4L-R-gs-rw-res|budget-wizard|pooled|32|3.15/8.15|3.65/7.23|-2.35/2.92|2/43 (4.7%)|387.13|
|LD-K4L-R-gs-rw-res|budget-wizard-arrows|weak pool|16|3.15/9.95|3.90/9.20|-2.80/4.80|1/23 (4.3%)|408.75|
|LD-K4L-R-gs-rw-res|budget-wizard-arrows|strong opponent|8|2.65/7.45|2.90/4.90|-3.75/8.25|1/6 (16.7%)|489.15|
|LD-K4L-R-gs-rw-res|budget-wizard-arrows|rext-bc|8|3.65/8.65|3.65/8.15|-2.60/4.86|1/20 (5.0%)|363.86|
|LD-K4L-R-gs-rw-res|budget-wizard-arrows|pooled|32|3.15/9.03|3.52/8.15|-2.80/4.92|3/49 (6.1%)|410.90|
|LD-K4L-R-gs-rw-res|budget-wizard-goblins|weak pool|16|3.65/8.90|4.40/8.18|-5.00/2.00|0/23 (0.0%)|379.13|
|LD-K4L-R-gs-rw-res|budget-wizard-goblins|strong opponent|8|2.65/7.15|1.90/3.15|-1.35/4.25|1/6 (16.7%)|336.72|
|LD-K4L-R-gs-rw-res|budget-wizard-goblins|rext-bc|8|4.15/9.65|5.65/10.15|-1.50/4.08|0/15 (0.0%)|399.38|
|LD-K4L-R-gs-rw-res|budget-wizard-goblins|pooled|32|3.15/8.90|4.03/8.90|-2.35/3.90|1/44 (2.3%)|379.13|
|LD-K4L-R-gs-rw-res|budget-wizard-minions|weak pool|16|3.65/9.15|3.02/6.88|-0.90/5.15|3/29 (10.3%)|330.47|
|LD-K4L-R-gs-rw-res|budget-wizard-minions|strong opponent|8|3.15/7.15|3.15/4.15|-2.50/1.60|0/5 (0.0%)|366.71|
|LD-K4L-R-gs-rw-res|budget-wizard-minions|rext-bc|8|4.40/10.65|3.65/8.05|0.00/5.36|1/19 (5.3%)|331.29|
|LD-K4L-R-gs-rw-res|budget-wizard-minions|pooled|32|3.65/8.87|3.65/7.20|-0.50/5.23|4/53 (7.5%)|344.40|
|LD-K4L-R-gs-rw-res|budget-wizard-skeletons|weak pool|16|3.27/8.18|2.90/7.28|-4.50/4.80|2/26 (7.7%)|380.23|
|LD-K4L-R-gs-rw-res|budget-wizard-skeletons|strong opponent|8|2.65/6.85|4.90/5.10|-2.25/0.35|0/2 (0.0%)|422.65|
|LD-K4L-R-gs-rw-res|budget-wizard-skeletons|rext-bc|8|3.65/8.15|4.15/8.15|1.20/4.00|1/16 (6.2%)|385.30|
|LD-K4L-R-gs-rw-res|budget-wizard-skeletons|pooled|32|3.15/7.65|3.40/7.95|-2.25/4.45|3/44 (6.8%)|397.57|
|LD-K4L-R-gs-rw-res|budget-wizard-skeletons-arrows|weak pool|16|3.15/8.10|5.03/8.70|-0.80/6.77|4/24 (16.7%)|483.64|
|LD-K4L-R-gs-rw-res|budget-wizard-skeletons-arrows|strong opponent|8|2.65/8.15|4.15/6.55|-0.50/2.30|0/2 (0.0%)|433.67|
|LD-K4L-R-gs-rw-res|budget-wizard-skeletons-arrows|rext-bc|8|3.15/8.65|3.15/4.95|-1.80/1.74|0/15 (0.0%)|487.25|
|LD-K4L-R-gs-rw-res|budget-wizard-skeletons-arrows|pooled|32|3.15/8.15|4.15/7.65|-1.20/5.12|4/41 (9.8%)|481.71|
|LD-K4L-R-gs-rw-res|budget-wizard-valk|weak pool|16|3.65/8.15|3.40/7.37|-2.50/3.80|2/34 (5.9%)|335.43|
|LD-K4L-R-gs-rw-res|budget-wizard-valk|strong opponent|8|2.65/7.45|7.15/8.75|-2.90/-0.42|0/2 (0.0%)|397.32|
|LD-K4L-R-gs-rw-res|budget-wizard-valk|rext-bc|8|3.65/8.30|4.15/6.25|-1.10/3.35|0/18 (0.0%)|379.13|
|LD-K4L-R-gs-rw-res|budget-wizard-valk|pooled|32|3.40/8.12|3.65/6.95|-1.20/3.94|2/54 (3.7%)|382.53|
|LD-K4L-R-gs-rw-res|giant-archers-cycle|weak pool|16|2.90/7.95|3.40/5.95|-0.50/2.92|0/25 (0.0%)|456.28|
|LD-K4L-R-gs-rw-res|giant-archers-cycle|strong opponent|8|2.65/6.15|4.15/9.15|-3.50/-0.48|0/5 (0.0%)|480.49|
|LD-K4L-R-gs-rw-res|giant-archers-cycle|rext-bc|8|3.15/7.65|3.40/9.80|-0.90/2.90|0/16 (0.0%)|375.78|
|LD-K4L-R-gs-rw-res|giant-archers-cycle|pooled|32|2.90/7.40|3.40/7.40|-0.80/2.90|0/46 (0.0%)|448.17|
|LD-K4L-R-gs-rw-res|giant-arrows|weak pool|16|3.65/8.90|3.40/6.15|-1.80/0.80|2/27 (7.4%)|406.67|
|LD-K4L-R-gs-rw-res|giant-arrows|strong opponent|8|3.15/8.15|2.15/4.85|-2.80/0.52|0/7 (0.0%)|458.32|
|LD-K4L-R-gs-rw-res|giant-arrows|rext-bc|8|4.65/9.65|3.65/7.25|0.10/7.17|3/14 (21.4%)|504.50|
|LD-K4L-R-gs-rw-res|giant-arrows|pooled|32|3.40/8.65|3.40/6.65|-1.40/1.50|5/48 (10.4%)|423.01|
|LD-K4L-R-gs-rw-res|giant-classic|weak pool|16|3.15/8.65|3.02/7.38|-1.10/3.90|2/28 (7.1%)|458.65|
|LD-K4L-R-gs-rw-res|giant-classic|strong opponent|8|2.65/6.15|0.90/2.20|-5.50/0.74|0/4 (0.0%)|431.09|
|LD-K4L-R-gs-rw-res|giant-classic|rext-bc|8|3.65/9.65|4.15/9.10|-2.50/2.38|0/17 (0.0%)|466.68|
|LD-K4L-R-gs-rw-res|giant-classic|pooled|32|2.90/8.15|3.27/8.20|-2.20/3.56|2/49 (4.1%)|455.64|
|LD-K4L-R-gs-rw-res|giant-goblins|weak pool|16|3.15/8.40|2.65/5.65|-0.50/3.23|0/30 (0.0%)|377.73|
|LD-K4L-R-gs-rw-res|giant-goblins|strong opponent|8|2.15/8.15|2.15/2.15|—/—|1/1 (100.0%)|421.63|
|LD-K4L-R-gs-rw-res|giant-goblins|rext-bc|8|3.65/8.65|2.40/4.60|-2.50/1.32|1/17 (5.9%)|391.36|
|LD-K4L-R-gs-rw-res|giant-goblins|pooled|32|3.15/8.15|2.40/5.65|-1.10/3.14|2/48 (4.2%)|391.36|
|LD-K4L-R-gs-rw-res|giant-hut|weak pool|16|3.65/8.90|3.65/7.40|-1.00/2.65|1/29 (3.4%)|354.07|
|LD-K4L-R-gs-rw-res|giant-hut|strong opponent|8|3.15/8.15|4.15/4.95|-2.50/0.30|0/2 (0.0%)|379.00|
|LD-K4L-R-gs-rw-res|giant-hut|rext-bc|8|3.65/9.65|4.15/7.65|-0.80/3.62|1/19 (5.3%)|329.05|
|LD-K4L-R-gs-rw-res|giant-hut|pooled|32|3.40/8.65|3.65/7.65|-1.00/3.32|2/50 (4.0%)|354.07|
|LD-K4L-R-gs-rw-res|giant-hut-arrows|weak pool|16|3.90/8.65|2.65/7.30|-1.20/4.48|3/27 (11.1%)|402.04|
|LD-K4L-R-gs-rw-res|giant-hut-arrows|strong opponent|8|3.15/8.65|2.65/7.05|-1.85/0.27|0/2 (0.0%)|369.56|
|LD-K4L-R-gs-rw-res|giant-hut-arrows|rext-bc|8|3.65/9.65|5.15/7.65|-0.80/3.20|1/18 (5.6%)|464.62|
|LD-K4L-R-gs-rw-res|giant-hut-arrows|pooled|32|3.65/8.90|3.65/7.65|-0.80/3.74|4/47 (8.5%)|402.04|
|LD-K4L-R-gs-rw-res|giant-hut-classic|weak pool|16|3.15/8.15|2.15/4.80|-2.10/1.16|0/33 (0.0%)|383.58|
|LD-K4L-R-gs-rw-res|giant-hut-classic|strong opponent|8|2.65/7.15|1.90/4.40|-5.20/-4.88|0/3 (0.0%)|466.46|
|LD-K4L-R-gs-rw-res|giant-hut-classic|rext-bc|8|3.65/9.40|3.90/6.30|-0.15/2.35|2/18 (11.1%)|366.63|
|LD-K4L-R-gs-rw-res|giant-hut-classic|pooled|32|2.90/7.65|2.65/6.15|-2.20/2.20|2/54 (3.7%)|388.77|
|LD-K4L-R-gs-rw-res|giant-musket-cycle|weak pool|16|3.15/7.65|3.02/7.80|-0.75/3.20|3/29 (10.3%)|405.22|
|LD-K4L-R-gs-rw-res|giant-musket-cycle|strong opponent|8|2.65/6.65|1.65/6.65|-4.80/-0.88|0/6 (0.0%)|431.83|
|LD-K4L-R-gs-rw-res|giant-musket-cycle|rext-bc|8|3.15/8.15|2.40/4.95|-1.00/2.65|0/17 (0.0%)|476.37|
|LD-K4L-R-gs-rw-res|giant-musket-cycle|pooled|32|2.65/7.15|2.77/6.75|-1.20/3.20|3/52 (5.8%)|425.94|
|LD-K4L-R-gs-rw-res|giant-skeleton-cycle|weak pool|16|2.90/8.15|2.65/7.80|-1.50/4.20|1/27 (3.7%)|360.88|
|LD-K4L-R-gs-rw-res|giant-skeleton-cycle|strong opponent|8|2.15/6.65|1.15/3.65|-2.40/0.40|1/6 (16.7%)|424.15|
|LD-K4L-R-gs-rw-res|giant-skeleton-cycle|rext-bc|8|3.65/7.70|5.15/7.65|-1.00/3.96|2/16 (12.5%)|353.34|
|LD-K4L-R-gs-rw-res|giant-skeleton-cycle|pooled|32|2.65/7.65|3.27/7.65|-1.10/3.94|4/49 (8.2%)|371.58|

Reaction is accepted enemy play to next own submitted play in simulator seconds; terminal enemy plays without a later own play are unobserved. An own play need not defend that threat. Percentiles pool observed events. Undefended share is the existing live_metrics enemy Giant lane-track proxy: no same-lane defence before contact, divided by observed Giant pushes. Defence-minus-crossing is signed time to first qualifying defence (negative means before river crossing), conditional on any defence observed. Contact-only denominators are also in metrics-summary.json. These proxies do not attribute damage causally. Search milliseconds are host-load-dependent measurements of the unbounded twin, not deployed wall200 latency.


Candidate decks:

- baseline: Valkyrie L5, Archers L7, Minions L6, Cannon L6, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- budget-fire-spirits: Valkyrie L5, Archers L7, Minions L6, FireSpirits L4, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- budget-fire-spirits-minions: Valkyrie L5, Archers L7, FireSpirits L5, Cannon L6, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- budget-inferno: Valkyrie L5, Archers L7, Minions L6, InfernoTower L7, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- budget-inferno-arrows: Valkyrie L5, Archers L7, Arrows L6, InfernoTower L7, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- budget-inferno-goblins: Valkyrie L5, Archers L7, Goblins L6, InfernoTower L7, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- budget-inferno-goblins-skeletons: Valkyrie L5, Archers L7, Goblins L6, InfernoTower L7, Fireball L6, Giant L7, MiniPekka L5, Skeletons L7
- budget-inferno-skeletons: Valkyrie L5, Archers L7, Skeletons L7, InfernoTower L7, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- budget-inferno-skeletons-musket: Valkyrie L5, Archers L7, Minions L6, InfernoTower L7, Fireball L6, Giant L7, MiniPekka L5, Skeletons L7
- budget-inferno-wizard: Valkyrie L5, Archers L7, Minions L6, InfernoTower L7, Fireball L6, Giant L7, MiniPekka L5, Wizard L7
- budget-inferno-wizard-arrows: Valkyrie L5, Archers L7, Arrows L6, InfernoTower L7, Fireball L6, Giant L7, MiniPekka L5, Wizard L7
- budget-inferno-wizard-fire: Valkyrie L5, Archers L7, FireSpirits L5, InfernoTower L7, Fireball L6, Giant L7, MiniPekka L5, Wizard L7
- budget-inferno-wizard-skeletons: Valkyrie L5, Archers L7, Skeletons L7, InfernoTower L7, Fireball L6, Giant L7, MiniPekka L5, Wizard L7
- budget-skeletons-arrows: Valkyrie L5, Archers L7, Arrows L6, Skeletons L7, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- budget-skeletons-fire: Valkyrie L5, Archers L7, FireSpirits L5, Skeletons L7, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- budget-skeletons-goblins: Valkyrie L5, Archers L7, Goblins L6, Skeletons L7, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- budget-wizard: Valkyrie L5, Archers L7, Minions L6, Cannon L6, Fireball L6, Giant L7, MiniPekka L5, Wizard L7
- budget-wizard-arrows: Valkyrie L5, Archers L7, Minions L6, Arrows L6, Fireball L6, Giant L7, MiniPekka L5, Wizard L7
- budget-wizard-goblins: Valkyrie L5, Archers L7, Minions L6, Goblins L6, Fireball L6, Giant L7, MiniPekka L5, Wizard L7
- budget-wizard-minions: Valkyrie L5, Archers L7, Wizard L7, Cannon L6, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- budget-wizard-skeletons: Valkyrie L5, Archers L7, Minions L6, Skeletons L7, Fireball L6, Giant L7, MiniPekka L5, Wizard L7
- budget-wizard-skeletons-arrows: Valkyrie L5, Archers L7, Arrows L6, Skeletons L7, Fireball L6, Giant L7, MiniPekka L5, Wizard L7
- budget-wizard-valk: Wizard L7, Archers L7, Minions L6, Cannon L6, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- giant-archers-cycle: Valkyrie L5, Archers L7, Skeletons L7, Cannon L6, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- giant-arrows: Valkyrie L5, Archers L7, Minions L6, Arrows L6, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- giant-classic: Archers L7, Arrows L6, Fireball L6, Giant L7, Knight L4, MiniPekka L5, Minions L6, Musketeer L5
- giant-goblins: Valkyrie L5, Goblins L6, Minions L6, Cannon L6, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- giant-hut: Valkyrie L5, Archers L7, Minions L6, GoblinHut L5, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- giant-hut-arrows: Valkyrie L5, Archers L7, GoblinHut L5, Arrows L6, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- giant-hut-classic: Archers L7, GoblinHut L5, Fireball L6, Giant L7, Knight L4, MiniPekka L5, Minions L6, Musketeer L5
- giant-musket-cycle: Valkyrie L5, Skeletons L7, Minions L6, Cannon L6, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- giant-skeleton-cycle: Valkyrie L5, Archers L7, Minions L6, Skeletons L7, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5

## Fresh validation

0/6000 rows; 0 unclean. Bank drawn 2026-10-16T22:58:14Z; SHA `5de59f1e494e6428a3febffd9be2aea61fa19b9b5558fc56bbc37b6753bd82c6`.

Collection SHA `81951375d9944134c8d989d8b56ad193d3626d6871dbb6eb4902a7a63b16c712`; King 6. True owned levels: Archers L7, Cannon L6, Fireball L6, Giant L7, MiniPekka L5, Minions L6, Musketeer L5, Valkyrie L5.

|Player|Deck|Opponent group|Paired n|Win%|Baseline%|Δ pp [95% CI]|
|---|---|---|---:|---:|---:|---|

Public reaction/defence diagnostics (descriptive, separate from win-rate inference):

|Player|Deck|Group|Games|Enemy-play reaction p50/p90 s|Enemy Giant reaction p50/p90 s|Giant defence minus crossing p50/p90 s|Undefended Giant pushes|Median game search p50 ms|
|---|---|---|---:|---|---|---|---|---:|

Reaction is accepted enemy play to next own submitted play in simulator seconds; terminal enemy plays without a later own play are unobserved. An own play need not defend that threat. Percentiles pool observed events. Undefended share is the existing live_metrics enemy Giant lane-track proxy: no same-lane defence before contact, divided by observed Giant pushes. Defence-minus-crossing is signed time to first qualifying defence (negative means before river crossing), conditional on any defence observed. Contact-only denominators are also in metrics-summary.json. These proxies do not attribute damage causally. Search milliseconds are host-load-dependent measurements of the unbounded twin, not deployed wall200 latency.


INCOMPLETE; partial screening deltas do not support a deck change.


Candidate decks:

- baseline: Valkyrie L5, Archers L7, Minions L6, Cannon L6, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5
- budget-inferno-goblins-skeletons: Valkyrie L5, Archers L7, Goblins L6, InfernoTower L7, Fireball L6, Giant L7, MiniPekka L5, Skeletons L7
- budget-inferno-wizard: Valkyrie L5, Archers L7, Minions L6, InfernoTower L7, Fireball L6, Giant L7, MiniPekka L5, Wizard L7
- budget-inferno-wizard-arrows: Valkyrie L5, Archers L7, Arrows L6, InfernoTower L7, Fireball L6, Giant L7, MiniPekka L5, Wizard L7
- giant-hut-arrows: Valkyrie L5, Archers L7, GoblinHut L5, Arrows L6, Fireball L6, Giant L7, MiniPekka L5, Musketeer L5

## Protocol and limits

Clean rule clarified by BOT LEAD2026-10-16: opponent policy deploy refusals are ordinary opponent behavior and retained as clean. Our own refusals, native failures, live errors and nonterminal/error games remain flagged. Raw rows, including their original diagnostic tags, are unchanged. No case is excluded for an opponent refusal.

Only validation supports the claim. Actual wins are primary, draws count as nonwins and remain in raw rows. The paired percentile bootstrap uses20,000 replicates and the same resampled case indices for candidate/baseline within each opponent policy. Pointwise intervals; no multiplicity adjustment. Degenerate all-win/all-loss bootstrap intervals do not prove true rates of0/100%.

Weak pool = R3a+v1 only. Strong LIVE-K4CW-r16 has its own row. The primary true-deck pooled result weights its three policies equally; rext-bc is n/a. In the C56-projected screens, pooled weights four policies equally and internal-only rext-bc has its own row; it never enters weak pool. All efficacy players have no wall deadline; wall200 live timing equivalence is not claimed.

Truth: RoyaleSim16.402 /0.1.34; native simulator SHA97e03055332faeb986c91a12aa64c6e22ca65948b68351803d914e0a84eb43bb. Primary true-deck planning pin live16402b-r3; projected stages use live16402b-r2. Native library SHAde11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1. Frozen roots/weights and each prescribed belief remain unchanged, with no ExactLevelRoot B. Full-pool source commit1a65dcd1a00c5e3f891228df878d3bbebe4de187; model/config/source receipts are in fullpool/. Simulator public static placement compatibility is shared by every V1Policy poller and scripted candidates.

All91 Battle Log rows uniformly sampled; nearest C56 catalog projection uses overlap, frequency, literal card tuple. Opponent levels are independent population draws from the250observed values {2:7,3:17,4:61,5:110,6:53,7:2}, with existing rare/epic offset1 and rarity floors (common1/rare3/epic6/legendary9/champion11). No sampled log row level is treated as per-match truth or passed to a planner. Projection retains all8cards for11/91rows; overlap counts are3cards:12rows,4:31,5:33,6:4,8:11. Thus80/91decks are changed by nearest-catalog mapping. Projection bias and rarity assumptions are outside the confidence intervals. Opponent towers6scenario.

rext-bc was trained on15.535.29; explicit harness opt-in evaluates it on16.402 without retraining or changing its old observation normalization. This balance/level distribution shift limits interpretation; internal eval only.

Own level risk: low-level new Wizard3/InfernoTower3/FireSpirits1, plus Knight3/Goblins1 in original candidates. Both screens disclose their exact collection snapshot; only final post-upgrade levels enter validation. Card scope C56 only; no non-C56 recommendation.

Resource receipts retain admission attempts and the03backoff: all unscored missing cases are resumed using fixed seeds, with no completed outcome discarded. Shared cpu_job admission uses per-check flock (main b8ad5e222, cpu_job md5 prefix3103e8a4093e, cpu_room0e8577911a23; supersedes the earlier wait-held lock), each partition in a distinct detached session; nice15, CPU-only, required deterministic env. Compute on01/03/04 under the later explicit04authorization;05light aggregation.

## Upgrade-budget search

Copies-only variant A locked32distinct candidate decks. Official source:127x03:/mpac/sdicks02/repos/clasher-bot-runtime/live16402c/gamedata.json, SHAa7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb. Fields items.rarities.upgradeMaterialCount/upgradeCost, indexed absolute current level minus relativeLevel minus1; common starts1,rare3,epic6,legendary9. Current needed counts agree with the collection. Fireball400/Giant1000 match committed gold spending; Musketeer4→5 matches the in-game150gold/4copies read. BOT LEAD approved this official table; later differences trigger a final-plan affordability recheck.

Held-copy maxima: Arrows1→6,625gold; Goblins1→6,625; Skeletons5→7,1400; Wizard3→7,1600; InfernoTower3→7,1600; FireSpirits1→4,75. All ownedC56 maxima total5925gold (below10321); each deck spends only on its own cards, at most4600 in the32-deck A set. This is the original copies-only reference. Variant B includes the subsequent committed Fireball/Giant upgrades and Musketeer wild-card transfer.

Variant B frozen after20:37:55Z: Fireball5→6 (400gold,9held+1rare-wild copies) and Giant6→7 (1000gold,15held+5rare-wild copies) already committed in every deck. Two further rare wilds are already applied to Musketeer: L4,4heldcopies. Remaining shared resources:8921gold,59common/2rare wildcards; gems300 excluded. All32 decks optimize only their own remaining upgrades under a registered weighted-strength heuristic, not measured upgrade value. Exact sequential replay verifies gold, held copies and shared wilds. Variant-B-full-budget.json SHA190e15df6ecea88da441ef29f2c45da56316558a5174516054997191dc5de968. All32 target vectors match pre-Musketeer-transfer B; only remaining resource accounting changed. The derived collection matches the20:37:55Z ACCOUNT-LOG entry, independently checked20:46:27Z (log snapshot SHAe66cbca5dd339b7fae73d662bf6909f65f23cc45e30c9c228a406caf48f1d78d); standalone updated collection remains pending. Baseline remaining order: Musketeer4→5,150gold/4heldcopies; Minions5→6,400gold/50common-wild copies. Remaining550gold; total1950from original10321 including1400committed. Only-res screens8cases/policy; both players validate150/policy. No account spending by this worker.

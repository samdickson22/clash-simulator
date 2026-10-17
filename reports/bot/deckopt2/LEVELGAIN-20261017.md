# First clan request target: Valkyrie

Final measured-prior result, 2026-10-17T10:42:18Z.

Request **Valkyrie first**. It has pooled paired Δ **+11.5 [+3.0, +20.0] pp**; under the request-only point-estimate heuristic it yields +2.875 pp per request cycle. 4 requests take about 21–28 hours, depending on whether the first request is available now or after seven hours. This is a collection priority, not proof of a uniquely strongest upgrade.

Following collection order: **Valkyrie → Cannon → MiniPekka → Giant → Fireball → Bats**. Nonpositive singleton point estimates are ranked afterward by shortest wait, without an inferred performance benefit. Re-evaluate after the first unlock or a shop/chest grant; these singleton effects do not establish the best combined upgrade sequence.

Actual request timing from the09:38Z account read: the current MiniPekka request has0/2 received, with next request approximately16:07Z on17October. If the recommended target is requested then and fully granted each cycle, the last required request opens approximately2026-10-18 13:07 UTC; the upgrade unlocks when its donations arrive. No unreceived copies are counted. Latest09:40:41Z read confirms unchanged levels, copies and budgets. Both known gold shop offers are already purchased; no additional offer is assumed.

Pooled Δ point order: Valkyrie → MiniPekka → Cannon → Giant → Fireball → Bats.

Δ per missing copy point order: Valkyrie → MiniPekka → Giant → Cannon → Fireball → Bats.

Fastest initial unlock order: Valkyrie → Fireball → Bats → Cannon → MiniPekka → Giant. Equal request counts are ties.

Δ per initial request-cycle point order: Valkyrie → Cannon → MiniPekka → Giant → Fireball → Bats.

First target by opponent: R3a +14.0 [+2.0, +26.0] pp; strong LIVE-K4CW-r16 +9.0 [-3.0, +21.0] pp. Strong-opponent uncertainty is shown separately.

|Singleton|Pooled Δ pp [95% CI]|Strong Δ pp [95% CI]|R3a Δ pp [95% CI]|Missing after wilds|Requests|Hours (first now / after7h)|Pooled pp/missing copy [95% CI]|
|---|---:|---:|---:|---:|---:|---:|---:|
|Valkyrie 6→7|+11.5 [+3.0, +20.0]|+9.0 [-3.0, +21.0]|+14.0 [+2.0, +26.0]|7 rare|4|21/28|+1.643 [+0.429, +2.857]|
|MiniPekka 7→8|+7.5 [-1.0, +16.0]|+11.0 [+0.0, +22.0]|+4.0 [-8.0, +16.0]|46 rare|23|154/161|+0.163 [-0.022, +0.348]|
|Cannon 7→8|+4.5 [-2.5, +11.5]|+12.0 [+3.0, +21.0]|-3.0 [-14.0, +8.0]|66 common|9|56/63|+0.068 [-0.038, +0.174]|
|Giant 7→8|+4.5 [-1.5, +10.0]|+4.0 [-4.0, +12.0]|+5.0 [-3.0, +14.0]|46 rare|23|154/161|+0.098 [-0.033, +0.218]|
|Fireball 6→7|+0.0 [-4.5, +4.5]|-1.0 [-5.0, +2.0]|+1.0 [-7.0, +9.0]|16 rare|8|49/56|+0.000 [-0.281, +0.281]|
|Bats 7→8|-1.5 [-9.5, +6.5]|+3.0 [-7.0, +14.0]|-6.0 [-17.0, +5.0]|62 common|8|49/56|-0.024 [-0.153, +0.105]|

Each initial gap/time row allocates all currently available wild cards of that rarity to that singleton. Those are alternatives. Request income assumes one request every7hours, granting2rare or8common copies. Slot-based times assume prompt grants; donation delays can extend them. Missing-copy efficiency is not gem ROI. There are no gem shop offers for deck-card copies. Daily gold offers and chests may shorten waits; no arrival rates are assumed. Valkyrie9/20 is confirmed.

|Sequential priority|Missing after remaining wild stock|Requests|Wilds actually redeemed after full grants|Gold|
|---|---:|---:|---:|---:|
|Valkyrie|7|4|3 rare|1,000|
|Cannon|66|9|18 common|2,000|
|MiniPekka|49|25|0 rare|2,000|
|Giant|49|25|0 rare|2,000|
|Fireball|19|10|0 rare|1,000|
|Bats|80|10|6 common|2,000|

Conditional first upgrade after those request grants: Valkyrie 6→7, 1,000 gold; held9 + requested8 + 3 rare wilds. Remaining gold27,518, common wilds24, rare wilds1, gems425 unchanged, before intervening income. Redeem wilds after copies arrive, so whole-request rounding does not waste them. No purchase/request/upgrade executed by this worker.

All eight deck cards+1 at fixed King7: pooled +33.5 [+25.5, +41.5] pp. Baseline 85/200 wins; all+1 152/200. This is not divided by eight or treated as the sum of singleton effects.

Complete measured audit:1600games,200paired cases (100 R3a/100strong), 229651 search decisions, zero genuine failures/cutoffs. Reserve serial full-pool twin, native1/pool0/chunks4 with f1a2 and no wall deadline; deployed all-L11 planner handling retained. Our truth levels Valkyrie6/Archers8/Bats7/Cannon7/Fireball6/Zap6/MiniPekka7/Giant7; King7. Singletons change only the named card.

Measured population:14battles, actual opponent trophies1815–2000 (mean1895.14),109 identified card slots for rarity-specific level draws; all112 displayed levels retained for pooled missing-rarity fallback. Three null identities never inferred. Independent King draws13×8/1×9. Original91 true opponent decks/seeds/seat/permutations are unchanged; this is a level-prior update, not a new arena deck-frequency sample.

CIs:20,000 paired percentile bootstrap resamples within policy, identical case indices across arms; pooled gives equal weight to the two policies. Draws count as nonwins. Intervals are pointwise, without multiplicity adjustment or prior/simulator/model uncertainty. Ranking selected point estimates is exploratory. Absolute simulated win rates are not ladder forecasts.

Measured bank SHA `223eab6005639346ce29f5fe4fd68a6805ca7545e1b8af2f7f57157a2d4f3f1e`. Source population SHA `4ddd6869de27028e403898ea008b38145edcb8dcc56c0e9d191f3a6d97a28a90`. Truth RoyaleSim0.1.34/client16.402; runtime live16402b-r3 native SHA `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1`; frozen source1a65dcd1a00c5e3f891228df878d3bbebe4de187. Full metadata and original shifted results remain in REPORT.md; raw data stay private.

# Population update:14 versus23 Battle Log rows

Compared after the frozen14-row run completed, 2026-10-17T10:40:54Z. The running bank was never modified.

|Quantity|14-row snapshot|23-row snapshot|
|---|---:|---:|
|Verified card levels|112|180|
|Unverified level slots|0|4|
|Mean identified common level|7.4884|7.5484|
|Card level7 count|52|72|
|Card level8 count|57|104|
|Card level9 count|3|4|
|King8|13/14 (92.86%)|22/23 (95.65%)|
|King9|1/14 (7.14%)|1/23 (4.35%)|

Common mean change+0.0600; absolute0.3 threshold triggered: False. King support changed: False; King mixture total-variation change2.80 percentage points. These descriptive checks do not replace case-level performance confidence intervals.

Old SHA `4ddd6869de27028e403898ea008b38145edcb8dcc56c0e9d191f3a6d97a28a90`; new SHA `0780bd555b9355facb1f85dc254e575fe7f2e314743e0357c0ce0a76dd9f47ce`. Null identities are never invented; unverified levels remain missing.

Translator corrections in corrected23 source: s70-m06 slot7 Goblins→GoblinBarrel (common→epic); s70-m03 slot1 Barbarians→GoblinCage, evo form (common→rare). Displayed levels unchanged. Original14 experiment remains frozen; form/confidence metadata retained in the source snapshot, not inferred into the unchanged historical deck bank.

Conclusion agreed by BOT LEAD: the corrected23-row population agrees with the frozen14-row level prior. Common mean+0.0600 is below0.3; King support remains8/9 with one observed King9, while its share falls7.14%→4.35%. No corrected-prior game re-run was performed, as explicitly directed. The two identity corrections change rarity strata only; displayed levels and the original14 experiment remain unchanged.

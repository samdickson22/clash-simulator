# Inherited snapshot diagnostics — partial, old native only

Read-only preparation audit, 2026-10-16 09:28:36–09:29:04 UTC. No new simulations, builds, engine changes or
comparator changes. CARD LEAD owns the bounded Astra diagnostic; this report records observations only.

08 job PID/PGID **1042473** started 08:52:08Z, acquired its lease about 09:09:20Z; active at this audit.
Workers **2041750** (plain), **2041751** (overlay), **2041753** (focused). `c1/verify/snap.done` absent.
Native `08:/mpac/sdicks02/jobs/clasher/cards/c1/out-c1/clasher_core.abi3.so` is exactly
`2ac024c79f473d8ac3e29b83f494401f1021dcca148c8c66dbe9f8ae7bae83cd`, not the approved Ronin correction `631ac18d`.
Python contains the boulder/Bandit WIP from before the Ronin correction. Do not substitute the current branch
as its source provenance. Launcher SHA256 `f2641a5aba80c2cc3a2b030e2ddb8fb56d2e4c4d8963b785966193beefef0a24`;
running comparator SHA256 `08f0cea5d111899ad2a4e19069432f42fe472da6758c44a0337e50fcb28b7766`.

Read paths on 08, under `/mpac/sdicks02/jobs/clasher/cards/c1/verify/`:
`snap-root.json`, `snap-rootstats.json`, `snap-cases.json`, their logs, and `snap-c56ctl.{json,log}`.
They are still growing; first/count/example below are from the existing partial JSON, not final receipts.
`first` is the comparator's zero-based loop index, measured after that tick's step. Each listed record has
`digest_first=null`. That does not establish continuation correctness or complete byte equivalence.

| Scenario | Entity / class | Field | First / count | Python → native example |
|---|---|---|---|---|
| AxeMan/alone | 11 / PingpongProjectile | pp_t | 112 / 3 | `0` → omitted (`None` in probe) |
| AxeMan/alone | 11 / PingpongProjectile | aim | 112 / 93 | `None` → `[3.5,25.5]` |
| AxeMan/knight | 9 / PingpongProjectile | pp_t | 29 / 4 | `0` → omitted |
| AxeMan/knight | 9 / PingpongProjectile | aim | 29 / 124 | `None` → `[3.409,16.975]` |
| AxeMan/minions | 11 / PingpongProjectile | pp_t | 29 / 3 | `0` → omitted |
| AxeMan/minions | 11 / PingpongProjectile | aim | 29 / 93 | `None` → `[3.5,16.921]` |
| AxeMan/minions | 11 / PingpongProjectile | hit_ids | 56 / 4 | `[8,9,10]` → `[9,10,8]` |
| ElectroDragon/minions | 15 / ChainLightning | chain_wait | 37 / 4 | `0` → omitted |
| ElectroDragon/minions | 15 / ChainLightning | hit_ids | 38 / 8 | `[8,9,10]` → `[8,10,9]` |
| bandit_log_stand | 9 / RollingProjectile | aim | 58 / 59 | `None` → `[3.5,17.5]` |
| bandit_log_stand | 9 / RollingProjectile | hit_ids | 75 / 42 | `[]` → `[7]` (B2-owned) |
| mk_target_dies | 11 / Projectile | projectile_origin | 80 / 447 | `[9.0,29.0]` → `[0.0,0.0]` |

The overlay records repeat the AxeMan aim/pp_t class; counts are scenario records, not unique divergences across
the two arms. The red Log case repeats missing hit ID 7; red MegaKnight case has origin `[9.0,3.0]` vs `[0,0]`.
No normalization/waiver is inferred from vector order, omitted zero, or apparent unused fields here.

Source read paths for diagnostic follow-up (in the preserved job `tree/`, and current worktree for orientation):

- `engine-cards/live_snapshot.py:188` (axe pp state and hit-ID export), `:212` (chain export).
- `engine-cards/py/src/clasher/entities.py:5945` (`PingpongProjectile`), `:6046` (`ChainLightning`).
- `engine-cards/src/projectiles.rs:23` (`pingpong_tick`, pp state and membership), `:112` (boulder stepping).
- `engine-cards/src/lib.rs` serialized `pp_t`, `chain_wait`, `aim`, `hit_ids` defaults and projectile creation;
  `engine-cards/src/c56.rs` chain release/step. Probe's field selection is in the running `ctools/probe_snapshots.py`.
- Log/Bandit remembered hits are assigned to B2. Target-selector carryovers `src/attacks.rs:22` and
  `src/c56.rs:309` remain B2-owned per focused r2 review.

04 older diagnostic job PID/PGID **4131290**, child **4132214**, remains active at 09:28:36Z, with no
`verify/snap.done`. It uses the earlier source/exporter and comparator; its Bowler/Bandit/slow/push reports
must not be pooled with 08's WIP-normalized comparison or current `631ac18d` evidence. Its finished scenario
rows and unfinished case rows remain untouched at `04:c1/verify/`. Historical `04:c1/gate/compare.json` hash
remains `0b0237acf79f51b49f36c68f789e107fbfa79229c894ef8dc2ad9b2d331315d0`.

## Bounded proof and exact proposed comparator predicates

Astra diagnostic receipt `/mpac/sdicks02/repos/clasher-cards/reports/cards/reviews/C1-snapshot-diagnostic-r1.md`,
SHA256 `2f7927333de3da04d5821f42bc715d2b3bc2972897b22adac145372b952fb9ea`, established zero/omission and
hit-ID order normalization; its Python read bound did not establish aim redundancy. The following additional
source inspection and two bounded simulations close that specific proof, not all snapshot equivalence.

On unchanged native **631ac18d**, 04 CPU1/nice15 job PID/PGID **3125961** at 09:38Z passed **2/2**; comparator
verification PID/PGID **3443725** passed **2/2** and ended 09:43:47Z. Both groups exited; no rebuild or sweep.
Exact payload from `c1/root-r2`, with `NAT=c1/out-r2 ROOT=c1/root-r2` and existing `ctools/env.sh`:
`/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 15 "$PY" -B
/mpac/sdicks02/jobs/clasher/cards/c1/ctools-r2/probe_snapshot_followup.py
/mpac/sdicks02/jobs/clasher/cards/c1/verify-r2/followup-final.json`, log `followup-final.log`.
The initial proof uses `followup.json`/`followup.log`; both are preserved. Receipt SHA256:

- `followup.json`: `b123676e3c17bce9cb7397c75b260bf2dde1b147fd6c9a109e89fb5c2bf9111b`.
- `followup-final.json`: `b10c486a7e78fdfddcce429e2d12110e52effa59333c2df13b24d1d4eb1d6daf`.
- `followup-final.log`: `febf64fb1c5880dd43480f935929d21ef77e1dd61c8528b96af8d035a90f0c62`.
- Tested comparator: `aad00c4bed5418528db06308513f6edf66b12e0af9ca4c890dd8555bc5f150a8` (local/04 agree).
- Simulation probe revision: `0dd9c48eb202119701316988ba4c19fae0c31b1b039e124aba3252accb495d92`.
  Final probe `60be8aaf65052557b333d5fe6cfd74636841d55ff7c4a3eef15835e1d66a3208` additionally keeps a compound
  child-capable predicate control, tested separately as an AST-extracted pure function without engine imports.

**Axe proof.** Exact AxeMan/knight birth t29/id9, pp_t0, period30, origin `[3499,14500]`, apex `[3227,21996]`.
Actual Python target_position `[3.227,21.996]` is omitted by the base/live export's exact-type Projectile guard;
native redundant aim `[3.409,16.975]` represents the original target. Python `PingpongProjectile.throw` installs
origin/apex; `_pp_point/update` reads them, pp_t and pp spec, not target_position (`entities.py:5945–6045`).
Native `projectiles.rs:31` uses the same state after `lib.rs` constructs it. A birth Python snapshot resumed in
native, native serialize/reload, native aim changed to `[-99,99]` and Python clone target_position changed to
`[-99,99]` preserve positions, hit history, digest and damage through turn/clear at t16, return hit at t27 and
removal age31. Native comparisons are exact except the deliberately perturbed aim; selected Python/native
fields remain checked each step. Nonzero pp_t mutation changes the trajectory and is detected.

**Pingpong predicates:** only matching class `PingpongProjectile`; missing native pp_t becomes 0; both hit-ID
lists are sorted without set conversion (IDs and multiplicity retained). Exclude aim **only if** both
authoritative origin/apex are present length-two lists and equal, integer pp_t is equal in `[0,period]`, and
period/start/reach specs agree with positive period. Origin/apex/pp_t remain in CHECK. Negative controls detect
changed nonzero phase, either endpoint, changed hit IDs and missing multiplicity; permutation alone compares
equal. Missing/mismatching authoritative state does not qualify for aim exclusion. Other classes, including
ChainLightning, do not receive these rules.

**Origin proof.** Exact mk_target_dies t80/id11 is an **Arrows** Projectile: both spell labels Arrows, both
source_character=False, piercing=False, shot_target=None; actual child_count/damage/range/speed all zero.
Python origin `[9,29]` vs native `[0,0]`. `lib.rs:3272` prevents the child call at count0; `projectiles.rs:207–214`
also returns before its sole origin reader at nonpositive child damage/range. Full native-source search for
projectile_origin finds no other reader; remaining sites are declaration/assignments. Constructor preserves
supplied origin. Python-export continuation, native roundtrip and native origin set to `[-99,99]` preserve shot
position/aim/target/hits plus digest/damage through expiry (10 updates to expiry), with no reachable child direction. Trace begins
`(8.494,28.024)` and ends `(3.94,19.24)` before removal. No child-reader comparison is bypassed to get PASS.

**Origin predicate:** only matching `Projectile`, matching spell Arrows, both non-source/non-piercing with no
shot target; Python explicitly provides child_count/damage/range all zero, native known serde-zero defaults
agree. Only then exclude projectile_origin. Keep comparison for SpawnProjectile, child-capable, non-Arrows,
changed metadata and unproven paths. Controls change each child field and remove spell identity: origin is
retained; the compound count1/damage100/range1000 control is also retained (pure-function execution).
No global field ignore, engine damage-order change, or hit-history deletion.

Review diff: `git -C /mpac/sdicks02/repos/clasher-cards-c1 diff 933178477 HEAD -- reports/cards/c1/tools/probe_snapshots.py`.
Scoped helper: `normalize_owned_fields`. Lead must read predicates/proof before coverage acceptance; neither
these two cases nor the semantic comparator establish complete snapshot byte equivalence.

## Latest inherited completion / preservation

At 09:46:12Z 08 PID/PGID **1042473** is active, no snap.done: logs have 24 C56 / 36 plain / 36 overlay /
41 focused rows. Old source/comparator/native remain unchanged. New rules were not installed into either
inherited run; their old results are not retroactively declared PASS.

04 **4131290/4132214** completed, PIDs absent at 09:45:19Z, `snap.done` **09:44:07Z**. JSON: 21 controls,
36 plain, 36 overlay, **72** focused; zero recorded errors/digest mismatches, semantic classes remain.
Completed-file SHA256 on 04 `c1/verify/`:

- `snap-c56ctl.json`: `2685d6bbaa18b43a81cc2f703ed47779706eecc0128e618186200911e61ab747`.
- `snap-root.json` and `snap-rootstats.json`: `ef45e40afc1f9791c95304e540f94c291edfbfa35565741e9d102548c81e891d`.
- `snap-cases.json`: `e0189c515405053f5108c39468b20be5c55439ca56eafd7c86b5170c8daea2a9`.
- `snap.done`: `180123e9d60f5b13e7cac13b5e151f23d4712cd2c600fe9d4dc975b5529596cd`.

Original digest-case `04:c1/verify/cases.json` also has **72** records, zero errors/mismatches, SHA256
`051a9de43c040d3cc624682d77c7961b69c13b98316fa11d1a2f363eeccb01e0`. Earlier prose's 70/35 was a count
error: actual collection is 36 scripts × two seats. Fresh gate planning uses 72; raw evidence was never changed.

# Batch C1 — progress (restart notes)

Worker: CARD LEAD engine owner for Batch C1 (Opus). Worktree `/mpac/sdicks02/repos/clasher-cards-c1`, branch
`cards/c1` (from b16716481 on `cards/lead`). Edits only `engine-cards/**` and `reports/cards/c1/**`. Spec:
`reports/cards/specs/C1-SPECS.md`. Results: `RESULTS.md`.

Current launcher repair status: **complete; independent r5 APPROVE** at tools commit
`97171f531a31f9663f74ff95093d58053125860d`. Current owner Codex Sol high. This is preparation only;
B2→C1 integration, exact-source build/affected tests, owner-authenticated inventories, duplicate audit and
fresh C56 remain required. No host execution or live-pin change. Final receipt: `reviews/REPAIR-RECEIPT.json`.
Strict silence/direct-owner questions/one automatic whole-assignment delivery remain current.

## Layout
- 127x08 `/mpac/sdicks02/jobs/clasher/cards/c1/`: `base/` (engine-cards @ b16716481), `tree/` (rsync of the
  worktree), `root|baseroot|rootstats|basestats/` (Batch A-style roots), `out-base/` (native de11f124 = base),
  `stats/gamedata.json` (scratch overlay from `fid/stats-spec.json`, 4 rows; never in git), `fid/` (fidelity harness
  copy + `final-{base,mech,stats}.jsonl`, negative control `pns-negctl.*`), `nd/` (native-diff replays, base arm),
  `ctools/` (`reports/cards/c1/tools` + `replay.sh`, `pns.sh`).
- 127x04 `/mpac/sdicks02/jobs/clasher/cards/c1/`: `tree/`, `out/` (C1 native), `root|rootstats/`, `rt/` (r1 mirror
  for the gate, src/engine-rs -> tree), `roots -> ../batchA/roots`, `gate-tools/` (Batch A copy), `tools/` (Batch A
  tools incl. `gate.sh`), `ctools/` (`env.sh`, `verify.sh`, `nd_sample.sh`, C1 tools), `verify/` (native==Python
  evidence), `nd-plan.json` (native-diff plan copy).
- Builds: `build.sh tree out` under `cpu_job.sh 8` (04; 08 is saturated by the BOT LEAD full-pool generation).

## Log (UTC)
- 2026-10-16T06:45Z start; baseline fidelity (base root): C1 12/36 PASS.
- §13–16 native-only fixes; native-diff named games 11/11 full-length match (base arm reproduces 10; 548 no longer
  diverges on base either).
- Cards in spec order. Python fidelity per card first, then the native mirror, then lockstep:
  Bowler 3/3, Assassin 3/3, BossBandit 3/3, ZapMachine 3/3, MegaKnight 3/3 (full timed-dash port after the
  4-tick-recovery-only fix left the second leap 2 ticks late), Fisherman 3/3, ElectroDragon 3/3, IceWizard 3/3,
  ElectroWizard 2/3 (C56 Knight residual), AxeMan 3/3, InfernoDragon 3/3, Ronin 3/3 with the overlay.
- Native fixes found by lockstep: ZapMachine template clock seeded at LoadTime; Electro Dragon chain template
  exported alive; the boulder and axe hit filters skip dash-travel / stealthed units without marking them hit
  (mixed game 4: Bowler boulder vs BossBandit in travel).
- 07:40Z verification on 04 (native 6741bb91): 36/36 ×2 roots, 70/70 focused cases, 21-path audit 42/42, Batch A
  review cases 4/4, native-diff 11/11; negative control live; C56 config export byte-identical (e52e8a96).
- 07:46Z mixed sample (96 games with ≥ 2 C1 cards): 81 match; 12 known causes (IceGolemite alias 10, Poison×Bandit,
  Mirror×Barrel); 72 also diverges on the base arm; 4 = the hit-filter bug above (fixed, rebuild); 173 under triage.

- Native 2ac024c7 (hit-filter fix): game 4 matches; 173 = the known C56 X-Bow clock cause (reached by the new
  trajectory; base arm never gets there); 72 also diverges on the base arm. Full rerun of `verify.sh` +
  `nd_sample.sh`: 36/36 ×2, 70/70 cases, 42/42 paths, 4/4, 11/11, sample 82 match + 14 known causes.
- Committed e0ade18d3 on `cards/c1`; C56 gate launched 2026-10-16T08:04Z on 127x04: `cpu_job.sh 8 bash c1/tools/gate.sh`,
  PID = PGID 2082511, output `c1/gate/compare.json`, log `c1/gate.log`; patched native 2ac024c7 (pinned 681b5f2c).

- 2026-10-16T08:45:42Z gate shepherd: **C56 parity PASS** vs pinned 681b5f2c, patched native 2ac024c7
  (engine e0ade18d3 / handoff bc8eba7c2): fixtures **577/577 byte-identical**, Rust-only chains **577/577**,
  roots **300/300 full + 300/300 cut identical**. PID/PGID 2082511 completed normally (08:04:25Z–08:45:16Z);
  no relaunch. Independent byte/ID/hash audit passed; evidence 04 `c1/gate/compare.json` and `c1/gate.log`,
  details RESULTS §6. No triage needed; no engine edits or sealing.

## Next
- Focused r2 correction approved; prepare final gate/launcher review and bounded comparator follow-up.
- Wait for accepted/integrated B2 before C1 integration/full final gate. Historical PASS is only §6's native.

## Sol-high resume audit (UTC)
- 2026-10-16T09:04Z resumed in place on `cards/c1` at `2e8005054`; preserved WIP
  `live_snapshot.py`, `cards/bandit.py`, `RESULTS.md`, and the three new snapshot probes.
  Commands: `git status --short`, `git log -6 --oneline`, read review thread `cards-c1-review-r1`.
- 09:04–09:06Z liveness: `ssh 127x08 'ls -l .../c1/verify/snap*; ps -u sdicks02 -o pid,ppid,etime,args'`.
  Correction: no `verify/` directory and an empty `snap.log` did **not** mean the job stopped. Exact surviving
  launcher **PID/PGID 1042473**, `bash /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 4 bash ctools/snap_08.sh`,
  waits in `cpu_room.sh` (launched 08:52Z). Preserved; **no duplicate**. B2 launcher **561530** likewise preserved.
  04's older snapshot launcher **4131290** still has child **4132214** (`probe_snapshots.py .../snap-cases.json`).
  No gate restart: run1 PASS remains scoped to engine `e0ade18d3`, native `2ac024c7`, receipt commit `2e8005054`.
- 09:06Z read `src/attacks.rs`, `src/lib.rs`, `cards/ronin.py`, `ordinary_combat_clock.py`, `attack_clock.py`,
  `battle.py`, `differential.py`, `live_snapshot.py`, and local RoyaleSim `state.rs:parry_pass/fire_scheduled`.
  Review r1 REJECT: fixed boulder endpoint export is existing WIP; Ronin progress reset must preserve finish/load/
  target; pending reflects must survive defender removal. B2 owns target selectors; C1 boulder/axe filters retained.
  Lead notified with exact launcher correction. No merge/rebase/pin/runtime/model promotion. No host 05 compute.
- 09:09Z isolated verification source via `rsync -a --exclude target --exclude __pycache__ engine-cards/
  127x04:/mpac/sdicks02/jobs/clasher/cards/c1/tree-r2/` and `rsync -a reports/cards/c1/tools/
  127x04:/mpac/sdicks02/jobs/clasher/cards/c1/ctools-r2/`; made `root-r2/{engine-rs,src,gamedata.json,reports}`
  symlinks to `../tree-r2`, `../tree-r2/py/src`, `../tree-r2/py/gamedata.json`, and the read-only r1 reports.
  No changes to old `tree/out/verify/gate` or 08's queued source.
- 09:09Z–09:10:31Z build PID/PGID **1546638**, wrapper PID 1546636; exact payload from C1 directory:
  `setsid nohup /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 8 bash build.sh tree-r2 out-r2`.
  Existing unchanged build script uses nice 15 / cargo -j8. Interim native `2a3283bc` superseded before testing
  by the whole-class correction for a defender killed before combat eligibility.
- 09:10:46Z–09:11:52Z final refresh: same payload, PID/PGID **1639762**, log `04:c1/build-r2-final.log`;
  native **631ac18d27cb15d4eba7011113a9f69a4b85740ef68a27a87cabb0d68320ad86**.
  `out-r2/build-start.txt`, `build-end.txt`, `sha256.txt` are completion receipts; PID exited normally.
  Source default-omits the new orphan queue. Living Ronin retains combat-slot reflect ordering; dead-at-boundary
  work runs before combat, death during the phase still delivers in its eligible slot, later work transfers at
  cleanup. Idle fast-forward is blocked while orphan work exists. No generalized scheduler/phase promotion.
- 09:12Z focused probe PID/PGID **1728710** completed with test-setup failure after idle/clone and two finish
  cases passed: artificially redeploying an already-moving Ronin retained native `moving=True`. Corrected the
  fixture to clear its movement telemetry when installing the synthetic deploy hold; no engine change.
  Failed evidence retained as `04:c1/verify-r2/review.{log,json}`; reruns use separate attempt outputs.
- 09:13–09:15Z focused verification on final native `631ac18d`: PID/PGID **1752845** completed **19/19 PASS**
  (`review2.json`, final PASS at 09:14:40Z); extras PID/PGID **1812370** completed **3/3 PASS** at 09:15:07Z
  (`extras.json`: both seats' defender-killed-in-combat, plus empty-queue serialization/idle/clone control).
  Together **21 distinct cases**. Negative-control PID/PGID **1812416** completed with the intended assertion
  at tick 22 on old native `2ac024c7`: target/windup/finish/load differ exactly as review r1 reported.
  All PIDs were checked absent after output completion; no retries of successful cases or build changes.

  Exact focused commands, run through SSH on 127x04, from `/mpac/sdicks02/jobs/clasher/cards/c1/root-r2`:
  `export NAT=/mpac/sdicks02/jobs/clasher/cards/c1/out-r2 ROOT=/mpac/sdicks02/jobs/clasher/cards/c1/root-r2`;
  `source /mpac/sdicks02/jobs/clasher/cards/c1/ctools/env.sh`; then the unchanged CPU wrapper with payload:
  `setsid nohup /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 15 "$PY" -B
  /mpac/sdicks02/jobs/clasher/cards/c1/ctools-r2/probe_review_r2.py
  /mpac/sdicks02/jobs/clasher/cards/c1/verify-r2/review2.json` (stdout/stderr `review2.log`, stdin `/dev/null`).
  Extras use `extras.json --extras` and `extras.log`. Old-native negative uses the same command with
  `NAT=/mpac/sdicks02/jobs/clasher/cards/c1/out`, output `negative-old-native.json --finish-only`, log
  `negative-old-native.log`. No new host-touching launcher script; pure probe is independently reviewable.

  SHA256: `review2.json` = `0a4a3396db2ad9b258f00b65e27c17cd4cadfebbfa71e9b3b822538c79d262f7`;
  `extras.json` = `9a280f910bafe66bce06219feee87baf451508616ead81a557b9269bf31cfe76`;
  `negative-old-native.log` = `9a3689508f80be5aae769be47177ee7dd107b5b66cebbaae3d05c0753b353850`.
- 09:16Z inherited 08 PID/PGID **1042473** still active, no `verify/snap.done`; progress: 9 C56 controls,
  10 C1 plain scenarios, 8 overlay scenarios, 9 focused cases; no compared-state differences in completed
  plain C1 rows. Preserved source/native and launcher. 04 old PID/PGID **4131290**, child **4132214**, also
  still active (pre-fix diagnostics). These are handed back with their exact identities, not relaunched.
- Decisions: no rollbacks; first build superseded by final refresh before testing. New queue remains a routine
  candidate pending fresh independent r2 review. Historical C56 PASS is not attributed to native `631ac18d`.
  B2 acceptance/integration must precede C1 integration; no merge/rebase or pin/runtime/model promotion;
  no new full gate. Existing broader parry selection/buff-phase residuals stay deferred for Opus.
- 09:18Z updated Sam direction **supersedes the earlier blanket Opus/design/promotion hold**, retained above
  as history. Confident reversible work may proceed within ownership when review, parity and coverage gates
  pass, with exact receipts and rollback. This C1 candidate is awaiting independent r2 review and subsequent
  B2→C1 integration coverage; those unmet prerequisites (not its design label) block acceptance. LIVE LEAD
  retains active-pin authority. No active helpers to propagate to. No Claude retries.
  Broader parry selection/buff-phase work is outside this focused r1 correction; it is not blocked merely
  waiting for Opus. Any consequential unresolved scheduling/ordering change needs evidence and appropriate
  diagnostic/review rather than a blanket model hold.
- 09:18Z final Python-only API correction: internal orphan queue uses `init=False`, preserving BattleState's
  constructor signature. Repeated only affected extras under CPU lease 1, PID/PGID **1925277**:
  same focused command with `extras-final.json --extras` / `extras-final.log`, **3/3 PASS**; PID exited.
  Native remains `631ac18d` (no Rust change). Final `battle.py` local/04 SHA256 agrees:
  `1a39bed5c9e2f718d19feb467c0f5ac503bb983da88e805156af7e28a112468d`.
  All other seven touched engine file hashes agree with 04's tested tree. `git diff --check` and AST parse
  of all eight edited Python engine/probe files passed. Original `peek.py` / `snapcmp_probe.py` diagnostic
  helpers remain preserved as untracked WIP; only focused implementation, comparator, regression probe and
  scoped reports are staged. Rollback for this candidate: revert its focused commit, keep gated artifacts
  `2e8005054` / native `2ac024c7`; no live pin or runtime was changed.
- 09:19:02Z candidate committed **f68e5f80f1b23f5d5245e3c6c856e5ec6fceac4e**:
  `git add` explicitly listed eight engine files, `PROGRESS.md`, `RESULTS.md`, `probe_review_r2.py`, and
  `probe_snapshots.py`; `git diff --cached --check` and
  `/mpac/sdicks02/cc/tools/bin/clasher-secret-scan` passed before
  `git commit -m 'Cards C1: preserve boulder snapshots and Ronin counter continuation'`.
  Ready for fresh independent C1 review r2 against `2e8005054`, carrying all review r1 findings.
  Native **631ac18d27cb15d4eba7011113a9f69a4b85740ef68a27a87cabb0d68320ad86**; focused tests and
  continuation/negative receipts above. Concrete rollback: `git revert f68e5f80f1b23f5d5245e3c6c856e5ec6fceac4e`;
  no runtime or live-pin rollback required. Separate documentation receipt commit follows; same staged scan rule.
- 09:20Z coordination rule recorded for this owner and all future delegation briefs: send routine questions,
  missing information or constraints directly via `t3_thread_send(mode='auto')` to parent
  `thread:delegated-task:command%3Amcp%3A7f0bf0df-35b9-48b9-bbf9-8f9cdcc3f584%3Adelegate-task%3Aclasher-card-lead-20261016-r1`
  or the existing relevant owner, including question, paths/evidence, recommendation and whether dependent
  work waits; continue independent work and make obvious authorized decisions. Do not use user-input tools.
  Permission controls still apply. No existing active descendants or pending input requests to propagate/resolve.
  No duplicate jobs/messages. Candidate `f68e5f80f` and receipt `0bd6fc5a3` pushed to `origin/cards/c1`;
  lead directly notified with native hash, commands, test/PID receipts and rollback for fresh r2 review.

## Approved r2 preparation / bounded follow-up (UTC)
- 2026-10-16T09:28Z read full independent r2 APPROVE at
  `/mpac/sdicks02/repos/clasher-cards/reports/cards/reviews/C1-r2.md` (SHA256
  `5e609d02ec033f86959af8278c470f053eaaf4a7b69fd96834f6fc9891d39a2a`). Approval is focused
  `f68e5f80f` / native `631ac18d`, not broad byte equivalence or combined-source gate acceptance.
  B2-owned `attacks.rs:22`/`c56.rs:309` selectors and Log remembered hits stay with B2.
- 09:28:36Z read-only liveness commands: `ssh 127x08 'date -u; ps -p 1042473 -o pid,ppid,pgid,lstart,etime,args;
  ls -l /mpac/sdicks02/jobs/clasher/cards/c1/verify/snap*; cat /mpac/sdicks02/jobs/clasher/cards/c1/verify/snap.done'`
  and 04 equivalent `ps -p 4131290,4132214`. All active; both completion receipts absent. Read growing JSON/logs
  without modifying them. 04 historical `gate/compare.json` SHA256 still `0b0237acf79f51b49f36c68f789e107fbfa79229c894ef8dc2ad9b2d331315d0`.
  Detailed partial field examples/provenance in `SNAPSHOT-DIAGNOSTICS.md`; lead notified of material gaps,
  assigned bounded Astra diagnostic. No duplicate simulation, sweep/build or watcher was started.
- 09:34Z checked inherited gate helper hashes and pinned-native path read-only on 04. Prepared
  `FINAL-GATE-PLAN.md` and **unexecuted** `tools/final_gate.sh`; script requires exact integrated SHA/native,
  explicit B2/integration/launcher-review receipts, frozen input hashes, fresh run directory and CPU lease 8.
  Reuses unchanged reviewed gate/helper tools; adds strict completeness/byte/ID/header checks to the receipt.
  Static `bash -n` and AST parse of two embedded Python blocks pass; no script execution or final gate launch.
- 09:35Z lead requested small follow-up after bounded Astra report
  `/mpac/sdicks02/repos/clasher-cards/reports/cards/reviews/C1-snapshot-diagnostic-r1.md`, SHA256
  `2f7927333de3da04d5821f42bc715d2b3bc2972897b22adac145372b952fb9ea`.
  Read only: `entities.py:PingpongProjectile.throw/_pp_point/update`, `live_snapshot.py`, `differential.py`,
  native `projectiles.rs:pingpong_tick/projectile_children` and `lib.rs` birth/import/impact sites.
  No engine/native edits. Existing 08/04 runs still active at 09:35Z, artifacts preserved.
- 09:38:21Z single CPU1 / nice15 pure `probe_snapshot_followup.py` launched PID/PGID **3125961**, completed
  **2/2 PASS** on existing `631ac18d`; evidence 04 `c1/verify-r2/followup.{json,log}`. One exact AxeMan/knight
  birth t29/id9 through return/expiry (period30, expiry age31), Python/native snapshot continuations and
  aim/target-position perturbations; nonzero phase mutation detected. Exact `mk_target_dies` t80/id11 has
  child_count/damage/range/speed all zero, so its sole native origin-reader is unreachable; exported-origin
  continuation and arbitrary native-origin perturbation preserve positions/digest/damage through expiry (10 updates to expiry).
  Native never rebuilt. Lead notified with receipt and narrower follow-up recommendation.
- 09:41Z user authorized narrow comparator predicates only; implemented in `probe_snapshots.py`, with
  explicit phase/endpoints/hit-multiplicity and child-capability negative controls in the bounded probe.
  Follow-up final run uses a fresh output pair under the same CPU1 wrapper; no broad sweep or engine change.
- Coordination update: routine message spam is prohibited. Parent/owner messages only for needed action/input,
  a blocker/failure changing next steps, or a material result/deployment/account action; default ≤3 short lines /
  80 words, current result + needed action + one receipt path. Detailed commands/hashes stay in scoped files.
  No acknowledgments/healthy polls/unchanged queue or logged/pushed messages. Clarifications still use direct
  `t3_thread_send(mode='auto')`, never input tools. No active descendants/pending legacy input requests.
  Persist this rule and parent ID in every future/resumed delegation brief; do not rebroadcast to existing children.
- 09:43:24Z final bounded follow-up PID/PGID **3443725**, unchanged native631ac, **2/2 PASS**, completed
  09:43:47Z. Exact payload: `cpu_job.sh 1 nice -n 15 "$PY" -B .../c1/ctools-r2/probe_snapshot_followup.py
  .../c1/verify-r2/followup-final.json`, after the same explicit root/NAT/env setup documented above.
  Full paths, read-site/predicate proof, tested source hashes, controls and receipt SHA256 are in
  `SNAPSHOT-DIAGNOSTICS.md`; `followup-final.json` hash
  `b10c486a7e78fdfddcce429e2d12110e52effa59333c2df13b24d1d4eb1d6daf`, log hash
  `febf64fb1c5880dd43480f935929d21ef77e1dd61c8528b96af8d035a90f0c62`.
  Comparator hash `aad00c4bed5418528db06308513f6edf66b12e0af9ca4c890dd8555bc5f150a8` matches tested04 copy.
  Added/tested a compound child-capable pure predicate control using AST extraction (no engine import/step),
  keeping it in the final probe. No simulation repeated for that additional pure assertion.
- 09:45–09:47Z completion audit: 04 old PIDs4131290/4132214 absent; `snap.done` reads **09:44:07Z**.
  Parsed raw JSON counts 21 controls / 36 plain / 36 overlay / **72** focused, zero errors/digest mismatches.
  Original `verify/cases.json` also 72/72, zero errors/mismatches; corrected RESULTS and final plan's stale
  35/70 arithmetic to36/72. Old PROGRESS entries retained as history; raw receipts untouched. 08 PID1042473
  active at09:46:12Z, no snap.done (24/36/36/41 log rows). No restart/watcher or retrospective broad PASS.
- Final preparation validation: `bash -n reports/cards/c1/tools/final_gate.sh`; AST parse of its two embedded
  Python blocks and both edited/new probe files; `git diff --check`. New host-touching launcher has **never
  executed**, remains pending independent review, and fails closed without accepted/integrated B2 readiness,
  exact reviewed launcher/source/native/input bindings and an eight-CPU parent lease. Required gate counts
  remain577 fixtures +300full/+300cut roots. No merge/rebase/build/fullgate/pin/runtime change this turn.
  Concrete rollback for this preparation is reverting its reports/tools-only commit; engine/native remain
  reviewedf68e5f80f/631ac. Focused engine rollback remains revertf68e5f80f with preserved2ac024c7 artifacts.
- Sam **strict silence / whole-assignment** rule supersedes prior reporting cadence: no routine status,
  results, queue/receipt/commit updates, acknowledgments or manual completion DMs, even if called material.
  Message only when blocked needing parent action, urgent live failure, explicit request, or essential owner
  dependency handoff (max two sentences +one receipt path). Automatic final-result delivery counts as the
  single whole-assignment report; do not duplicate it manually. Owning parent resolves routine questions
  directly; never use input tools or bypass to coordinator. Persist in future/resumed-child briefs; no tiny
  per-test delegation or rebroadcast to existing children. No active descendants/pending legacy input requests.
- 09:51Z final unexecuted launcher submission SHA256
  `57c3bd179aac3f9b50b930606b22c5f139ef7b37713202647cd7ebd589faa282`; exact unchanged gate/helper hashes
  are enforced in preflight, inherited Python optimization/overlay/root variables cleared, and raw fixture/root
  cardinality/byte/ID/header checks are mandatory before PASS. `FINAL-GATE-PLAN.md` indexes all review inputs.
  Stage only seven scoped report/tool files explicitly, run staged diff checks and
  `/mpac/sdicks02/cc/tools/bin/clasher-secret-scan` before commit/push. No engine/native delta from933178477;
  original untracked peek.py/snapcmp_probe.py remain preserved. Final automatic delivery is the sole completion
  report; no duplicate manual parent message. Pending prerequisites are lead's independent launcher/comparator
  review and accepted/integrated B2 before final integrated coverage, not unfinished preparation code.

## Current authority / launcher repair (2026-10-16 UTC)

- Current owner is Codex gpt-6.1-sol high. Earlier blanket Opus/promotion HOLD wording is retired by Sam's
  updated direction; historical text above is retained. Confident reversible repairs proceed within ownership,
  but unmet independent review, B2 acceptance/integration, exact-source coverage and required gates still block
  admission. LIVE LEAD owns active live pins. No live switch, merge/rebase or final gate in this repair.
- Strict silence remains current: no routine DMs/status/test/review/queue/commit/ack spam, one automatic final
  delivery when this whole repair assignment is done. Missing information requiring action goes directly to
  the owning CARD LEAD via t3_thread_send(mode='auto'), max two sentences plus one receipt path; no input tools.
  Future/resumed descendant briefs must include this; do not rebroadcast to already active children. No
  pending legacy input request. Independent review of the complete repair is the only delegated work planned.
- 10:29–10:36Z local source inspection/editing only on05, no engine/native import, host command, simulation,
  build, queue, launcher/gate execution or duplicate watcher. Read full CARD LEAD review
  `reports/cards/reviews/C1-final-tools-r1.md`: launcher REJECT at476a747f, comparator APPROVE unchanged.
  Original review/scratch failures remain untouched. The rejected schema1 recipe is explicitly retired;
  `FINAL-GATE-PLAN.md` now describes frozen private copies and typed schema2 admission, not input symlinks.
- F1–F6 repair: replace inherited bare-wait launcher with individually waited2 fixture parents /8 root workers /
  comparator, phase/all-child exit receipts; complete lstat inventory with no links/extra files; authenticated
  integrated engine and full bot Git archives, checked B2 ancestry; typed owner evidence bound to raw artifacts,
  source/native/review/case identities; private exclusive outputs and atomic no-clobber PASS; persistent claim
  before validation and checks of original bytes/inventory before every phase/completion; env-i, bash-p,
  isolated Python bootstrap/sys.path and explicit r1 per-arm roots; expected577 IDs, exact deterministic300
  sample/shards/full-cut pairs and full chain/check/header validation. Reviewed helper copies add path relocation
  and action/header metadata only; historical budgets/pools/shards/comparison semantics preserved.
- F7 correction: previous09:38 statement "expiry+10" was an overclaim. The origin loop compared through removal
  after10 updates (trace81..90), then broke. Corrected PROGRESS and SNAPSHOT-DIAGNOSTICS to **through expiry
  (10 updates to expiry)**; no new post-expiry simulation claimed or run. Final followup raw receipt authenticity
  remains limited as r1 review states; owning lead must inspect/hash actual final files before coverage admission.
- Local command: `/mpac/sdicks02/repos/clasher-bot/.venv/bin/python -I -S -B
  reports/cards/c1/tools/test_final_gate_contract.py`. Pure synthetic validators plus AST-extracted filesystem /
  fake-child wait functions only. First run:11 groups,3 test-harness NameError errors (missing stat in extracted
  namespace); preserved `reviews/repair-local-first-failure.json`, tool output in thread. Fixed harness import;
  passing runs and exact hashes/exit/status in `reviews/repair-local-receipt-r2.json` and tests log. No actual
  Popen, native/engine import, host driver main or remote command exercised. `bash -n`, AST parse all7 new
  Python tools, `git diff --check` passed. Comparator hash remains aad00c4b; `git diff f68e5f80f -- engine-cards`
  empty. No inherited process/artifact was touched or restarted; historical native2ac/focused631ac retained.
- Rollback: revert scoped tools/docs repair commit(s), keeping rejected launcher disabled; engine rollback
  remains f68e5f80f/native631ac and historical native2ac artifacts. No runtime/pin rollback needed. Actual
  integrated source/native, B2 acceptance and fresh C56 are intentionally not invented by these local checks.
- 10:36–10:44Z repair candidate **c45854febf93352284dd9f76b02651d989d906a7** secret-scanned/committed and
  pushed (explicit scoped add; ignored test log added explicitly with -f). Fresh independent r2 task
  `node:delegated-task:command%3Amcp%3Ae000c21a-3b07-43d9-b09f-4bc38d1126f1%3Adelegate-task%3Acards-c1-final-tools-r2-c45854f-independent`
  returned REJECT for two startup defects; full verdict and19 synthetic groups retained in reviews/FINAL-TOOLS-r2.md
  and r2-independent/receipt.json. Only two essential factual handoffs to reviewer, no parent progress DMs.
- Corrected both: full Git tree query omits empty pathspec (old readonly command exit128 preserved), outer
  env-i invocation supplies identity-derived USER before cpu_room.sh's two ps user selectors. Added exact argv
  regression for full/prefixed tree queries, identity source control; actual local readonly full-tree query exit0.
  Parent additionally found-I ignores hashseed0: flag-only local Python commands produced1 (-I -S -B) vs0
  (-P -s -S -B). Worker now uses latter flags under explicit clean env, enforces flags/seed and frozen base_prefix,
  records effective flags; isolated control interpreter remains-I (no engine work).
- Exact revised local command unchanged test_final_gate_contract.py:13 groups PASS (adds a pure stdlib flag
  subprocess, no host script/worker or engine import), AST7 and bash-n pass. Detailed command/start/end/code
  hashes/log/full-tree query count and output hash in reviews/repair-local-receipt-r3.json. r2 receipts/logs
  preserved rather than overwritten. New r3 response carries original six findings and every r2 objection.
  Need fresh independent commit-bound r3 before any host execution; accepted/integrated B2 and actual combined
  source/native coverage still required. No inherited job poll/restart, new gate/build/simulation or host script.
- 10:45–10:57Z revised **4bfae6b0844b4620d9482cc996a74bf86f1a1887** secret-scanned/committed/pushed;
  fresh independent r3 task `node:delegated-task:command%3Amcp%3Ae000c21a-3b07-43d9-b09f-4bc38d1126f1%3Adelegate-task%3Acards-c1-final-tools-r3-4bfae6b-independent`
  REJECTED one interruption-receipt defect, confirmed r2 fixes/hashseed and other classes. Full verdict and
 13+10 groups, failed first harness attempt, exact reproduction/source/receipt retained under reviews/FINAL-TOOLS-r3.md
  and r3-independent. Large raw Git .bin/.delta files remain locally intact/hash-indexed, not needed in public Git.
- R3-1 fixed: persist observed statuses by unique label before deleting live state; partial phase receipt on
  later-wait interruption; final phase/all-child union retains prior successful/failed statuses without
  duplicates/overwrites. Register phases before spawn; defer stop signals around spawn/PID registration,
  receipt writes and final cleanup; worker clears inherited mask before dispatch, pending cancellation restored
  before PASS. New synthetic tests cover fixture2/root8 after prior0/17, store/delete gap, spawn registration gap.
  Popen/killpg/mask calls are mocked, no actual process signals/masks or host script execution.
- Revised local16 groups PASS, AST7/basics bash-n PASS; exact command/start/end/log/code hashes in
  reviews/repair-local-receipt-r4.json. All old logs/rejections preserved; no engine/native/comparator/followup
  delta, host build/gate, inherited poll/restart or live pin change. Full r4 response requests fresh exact-commit
  independent review; B2→C1 integration/coverage/C56 and owning-lead evidence authority remain unchanged.
- 10:57–11:06Z **c7de06ea5a6171b4490682a7bb1be9baa825a2b4** secret-scanned/committed/pushed. Fresh r4 task
  `node:delegated-task:command%3Amcp%3Ae000c21a-3b07-43d9-b09f-4bc38d1126f1%3Adelegate-task%3Acards-c1-final-tools-r4-c7de06e-independent`
  REJECTED R4-1: a stop at cleanup entry could precede the first mask and bypass cleanup. Full verdict,16+16
  groups, failed first review harness and reproduction preserved in reviews/FINAL-TOOLS-r4.md/r4-independent.
- R4-1 fixed by retiring raising signal handlers and parent masks, rather than moving the same race. A one-way
  STOP_SIGNAL latch never raises in the handler. Explicit checks before/after PID registration, timed1-second
  waits and PASS publication raise at safe boundaries; cleanup has none, so repeated stops cannot escape its
  entry or final receipts. Stops observed before final success checkpoint remove PASS/return1; later requests
  follow completed success. Worker inherited-mask reset retained defensively; no engine mechanics affected.
- Revised local19 groups PASS: repeated cleanup-entry/unwind stops including first stop after ordinary failure,
  prior0/17 fixture2/root8, timeout responsiveness, cancellation at temp/link and during FAIL writes, plus all
  previous negatives. Only AST/extracted mock handlers and fake process/group operations; no real signals/masks,
  host scripts or native/engine import. Exact commands/start/end/code/log hashes in repair-local-receipt-r5.json.
  Need fresh independent r5 commit-bound review. B2 acceptance/integration/actual coverage/C56 still required;
  no host execution, new host PID/PGID/job, inherited poll/restart, merge/rebase, runtime or active-pin change.

## Completed launcher repair / fresh review acceptance (UTC)
- 2026-10-16T11:22:23.383600+00:00 fresh independent r5 **APPROVE** of the COMPLETE repair at
  **97171f531a31f9663f74ff95093d58053125860d**, tree a70fd27a61f02b377fb2cd79105bafc1857a895d.
  Task `node:delegated-task:command%3Amcp%3Ae000c21a-3b07-43d9-b09f-4bc38d1126f1%3Adelegate-task%3Acards-c1-final-tools-r5-97171f5-independent`.
  Full verdict reviews/FINAL-TOOLS-r5.md SHA256 **5eb6aff2dbc67df7e557247ff743a9c1425b78a95e26d4f3b85377c951dd47d2**;
  machine receipt r5-independent/receipt.json SHA256 **7033b0f507c125365c552380c518fff17fe87b1d2bda2e520dbee79b7df59ccf**.
- All original F1–F6 launcher findings and F7 prose overclaim repaired; r2 startup, r3 status-loss and r4 repeated-
  stop objections resolved. No actionable new finding.19 submitted +13 independent groups PASS; reviewer
  checked54 cleanup-boundary combinations,24 later-wait/prior-status combinations, spawn/timeout and PASS
  boundaries;80 recorded commands exit0. No host/engine/native execution. Actual command/CWD/UTC/hash detail
  is in the independent receipt, not a broad native/full-byte equivalence claim.
- Independently rehashed approval report/receipt, all indexed new review artifacts,61 preserved prior artifacts,
  seven tools against Git97171f5, and unchanged engine Git tree **64ed8e5bb66bff6cbe0e746ec59fbd0dd36b48f7**
  against f68e5f80f. Comparator aad00c4b and followup60be8aaf unchanged. Native not rebuilt/modified/rehashed
  in this assignment; existing631ac focused/2ac historical artifact bindings retained, no gate restarted.
- `reviews/launcher-review-r5.json` is a typed faithful translation for later owner-authenticated staging:
  tools_commit must remain97171f5, copy the exact report and machine receipt to its evidence/raw paths.
  `reviews/REPAIR-RECEIPT.json` indexes code/source/receipt/rollback bindings and remaining prerequisites.
  These are not B2/build/test/platform acceptance or launch authorization. No host PID/PGID/job was created;
  inherited08/04 jobs/artifacts were neither polled nor restarted during this repair. No merge/rebase/pin switch.
- Preserve all old failed artifacts. Small r5 verdict/source/log/receipt evidence is committed; raw command
  stdout/stderr copies, large Git .bin/.delta files remain locally intact and hash-indexed under r3/r4/r5-
  independent, deliberately untracked. Original peek.py/snapcmp_probe.py also preserved. No historical
  defect-expecting script was rerun against fixed code. Final recording commit changes reports/evidence only,
  leaving all reviewed tools/tests/plan and engine/comparator/followup byte-identical to approved97171f5.
- Concrete rollback binding: withhold launch; if tools source rollback is requested, revert scoped repair
  commits newest first97171f531, c7de06ea5,4bfae6b08,c45854feb, preserving these reports/artifacts and keeping
  rejected schema1 disabled. Engine fallback f68e5f80f/native631ac and historical native2ac artifacts remain.
  No runtime/live-pin rollback needed. Explicit adds, staged diff check and staged secret scan precede each
  commit; final receipt-only commit/push uses the same guarded commands. One automatic final delivery only,
  no manual parent completion DM. B2 acceptance/integration then exact-native fresh C56 still required.

## Shared Troop assignment: triage before exact captures (UTC)
- 2026-10-16T11:30–11:41Z resumed substantive C1 ownership under CARD LEAD
  `reports/cards/reviews/B2-C1-integration-contract.md`: Zap retained route,
  ElectroDragon heading, IceSpirit mode stats. `SHARED-TROOP.md` records actual
  source readers, evidence levels, missing captures, ownership and ordered gates.
  No engine/native/tool-approval change, merge/rebase/selector copying/build/gate.
- Direct essential owner handoff to B2 via t3_thread_send(auto), retry keys
  `c1-shared-troop-capture-handoff-20261016` and
  `c1-capture-three-exact-old-cases-20261016`: request immutable constructors and
  paired first-bad pre/post states for Zap bluelead1/t0, ElectroDragon bluelead6/t14,
  IceSpirit bluelead0/t23, exact source/native/tool receipts and normal acquisition.
  Second message requests the two missing non-Zap captures in the same proposal
  before independent review; no duplicate sweep or separate collection job.
  B2 supplied `evidence/B2-C1-CAPTURE-INDEX.md`: frozen collector retained summaries,
  not full roots. At11:36:39Z its existing08PID/PGID3586969 was active/lease4/24of62
  rows. B2 owns liveness and one reviewed bounded capture after terminal; C1 made
  no host contact, poll, job/watcher/queue or artifact change in B2.
- Read-only source review used `rg --files`, `rg -n`, `sed -n`, `cat`, and
  `git diff --no-index --` for B2/C1 dash.rs and dash_snapshot.py. Important actual
  schema difference: B2 dash uses timer/destination and legacy charging; C1 uses
  wait/goal/blocked and standing. Do not import an old B2 root into C1 and claim
  same-schema parity. Exact old reproductions and current-source equivalents need
  separate bindings, plus the real normal-acquisition witness.
  Two initial guessed source reads under engine-cards/src/clasher failed because
  Python resides under py/src/clasher; corrected immediately. An absent B2
  HANDOFF/glob read was harmless; no source or old evidence was changed.
- Exact local light command on05 at11:38Z:
  `PYTHONDONTWRITEBYTECODE=1 python3 -B reports/cards/c1/tools/inspect_shared_troop.py > reports/cards/c1/shared-troop/source-witness.json`.
  PASS executes selected unmodified reference AST function bodies with explicit
  minimal fixtures, reads retained failure JSON and hashes all sources. No engine
  imports/battle/native/host execution. `shared-troop/source-receipt.json` binds
  exact command/CWD/UTC/source bytes/output hash. Confirms source-level route
  numbers and one-node threshold, exact/quantized-zero heading and nonzero controls,
  kind0→2 ordinary switch and active-slow multiplier controls. This does NOT
  establish dynamic cause, reachability, native parity or acceptance.
- IceSpirit is C56. Its ordinary stat has a live end-of-frame cleanup reader even
  though spirit skips normal components. Retain comparison; no inert/export-only
  claim. ElectroDragon zero-displacement remains source candidate; Zap residual
  stun remains inferred until roots. All retained FAILs, C56 and original631ac/
  f68e5f80f/97171f5 approvals preserved. Later scoped fix needs exact witnesses,
  negative controls, independent commit-bound review, frozen B2-first integration
  and required fresh exact-native C56 in order; rollback only new scoped commits.
- Current Sam authority/strict silence/direct-owner coordination remain in force:
  no routine DMs or acknowledgments, no inputtools, one automatic final delivery
  only when whole assignment done; independently reviewed host scripts required
  before execution. No active descendants or legacy input request. Future briefs
  repeat these rules; no tiny-step delegation.
- 11:41–11:44Z expanded only the pure local inspection tool. Exact v2 command:
  `PYTHONDONTWRITEBYTECODE=1 python3 -B reports/cards/c1/tools/inspect_shared_troop.py > reports/cards/c1/shared-troop/source-witness-v2.json`.
  PASS exercises actual reference finish_movement_tick with post-transport/frozen
  state, three guard negatives and nonzero external displacement ordering; actual
  Bandit dispatch shows paused stunned standing and continued forced-stunned
  travel. No actual transport/battle/native or runtime module is imported.
  Source/command/output bindings in source-receipt-v2.json, old v1 artifacts kept.
  A first combined documentation apply_patch failed verification on an unmatched
  RESULTS header and wrote nothing; corrected patch passed. No failed test hidden.
- Small bounded source-only Astra-high diagnostic task
  `node:delegated-task:command%3Amcp%3Ae000c21a-3b07-43d9-b09f-4bc38d1126f1%3Adelegate-task%3Ac1-ice-spirit-mode-readers-astra-20261016-1144`
  examines nine named files/ranges for mode-stat readers, retained slows and
  descendant/clone/reload risks before choosing a correction. No engine execution,
  edits, host use or descendants authorized; prompt carries current strict silence
  and coordination authority. This is not implementation review or acceptance.
- 11:44Z explicit eight-path add, `git diff --cached --check`, staged
  `/mpac/sdicks02/cc/tools/bin/clasher-secret-scan`,
  `git commit -m "cards c1: bind shared Troop source witnesses and capture prerequisites"`
  and `git push origin cards/c1` succeeded at **5630d424b**. Reports/source-only
  witnesses; engine tree unchanged. No manual commit/status/result DM.
- 11:45Z bounded Astra diagnostic completed; original result retained verbatim in
  shared-troop/ICE-MODE-DIAGNOSTIC.md. On-launch two-field sync is conditional on
  exact capture: retained slow-only minimum excludes move_mode, haste and percent
  rounding; ordinary flag changes must preserve cleanup's existing-clock decision.
  Native constructor does not repair stale midflight snapshots. Actual capture,
  survival/lethal/clock-disagreement, nonstandard slows, clone/reload and descendant
  controls remain required. No engine change or implementation acceptance.
- 11:45–11:48Z prepared read-only `tools/inspect_captured_troop.py`: consumes only
  B2's separately reviewed raw capture plus expected owner SHA, checks six legacy
  cases/both seats, paired boundaries/IDs, retains FAILs and explicit absent values,
  reports boundary displacement and selected mode/config readers. It never runs
  engine/native or changes a comparator; selected observations are not parity or
  causal/reachability proof. Actual inputs still absent. Pure local command:
  `PYTHONDONTWRITEBYTECODE=1 python3 -B reports/cards/c1/tools/test_captured_troop_inspection.py`
  PASS with six synthetic shapes, seven malformed root negatives, wrong SHA,
  missing denominator/invalid collection, nonzero displacement and retained FAIL/
  absent-field controls. No fake roots are represented as actual capture evidence.
- Further read-only Clone source check: Python spells.py CloneSpell.cast and
  native clone.rs use fresh prototypes; a launched live Troop carrier remains a
  candidate in current source. Generic projectile children clone source Stats,
  while Spirit area/ElectroSpirit chain uses configured templates. After B2
  integration, rerun the real Clone/slide/hold boundary; do not pre-copy B2 code.
- 11:48–11:49Z explicit staged diffcheck/secret scan/commit/push succeeded at
  **df438b2ed**, then **b66b8f538** added unrelated duplicate-ID/missing-blue-context
  guards and negatives. Prior source/inspection receipts preserved; exact later
  command and hashes in inspection-local-receipt-v2.json. Engine tree unchanged.
- 11:49Z fresh independent Sol-high preparation review task
  `node:delegated-task:command%3Amcp%3Ae000c21a-3b07-43d9-b09f-4bc38d1126f1%3Adelegate-task%3Ac1-shared-troop-preparation-review-b66b8f538-r1`
  examined exact b66b8f538, completed11:54:05Z **REJECT**. Full verdict and exact
  independent commands/source/hash/output receipts in REVIEW-preparation-r1.md /
  review-preparation-r1-receipt.json. Source-only witnesses/limits and protected
  engine/tool identities otherwise confirmed. No actual roots/host execution.
- R1 corrected: preserve owner CAPTURE_COMPLETE vs semantic/natural FAIL labels,
  validation/collection errors and all later result/natural differences; missing
  keys remain missing versus explicitnull. Only imported template/full-root blocks
  are explicitly retained in hash-bound raw files, not printed as bulk config.
  R2 corrected: exact nonnegative integer tick/index types; first before equals
  constructor+relative, after equals before+1;45-frame bound and optional recorded
  counts. Real-schema wrapper, later FAILs, presence, correct nonzero offsets,
  detached9000 and pre-constructor99/100, bool/float/count-window negatives added.
  Same pure local test command PASS at11:56:41Z; inspection-local-receipt-r2.json
  pins exact code/review bytes. New independent commit-bound review still required.
- 11:51:52Z source-only cleanup control exact command:
  `PYTHONDONTWRITEBYTECODE=1 python3 -B reports/cards/c1/tools/inspect_spirit_cleanup.py > reports/cards/c1/shared-troop/spirit-cleanup-source-witness.json`.
  PASS actual Python callback/publish/stop/refund AST on seven explicit kind2
  states; two expose a naive ordinaryfalse cleanup predicate reversal. Does not
  prove those states occur in the old root/gameplay. Exact source/output bindings
  in spirit-cleanup-source-receipt.json; WITNESS-PLAN.md translates into focused
  continuation/negative controls and exact integration/gate order, no host script.
- Local frozen-source-bindings.json hashes16 relevant B2 current source paths
  against exact admitted identity tree-prefix:16/16match; stores distinct C1
  hashes and old B2native7738 binding. No actual native/host file touched or run.
  One overly broad local identity-map diagnostic printed too much metadata and
  was truncated; replaced with bounded suffix lookups. No evidence was altered.
  A multi-operation apply_patch was rejected for targeting one file twice; then
  corrected atomically. A documentation context typo likewise wrote nothing.
  All old rejection/output files preserved. No engine/native/approved tool delta,
  merge/rebase/build/job/host poll/selector copying or new normalization.

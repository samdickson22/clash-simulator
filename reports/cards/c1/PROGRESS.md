# Batch C1 — progress (restart notes)

Worker: CARD LEAD engine owner for Batch C1 (Opus). Worktree `/mpac/sdicks02/repos/clasher-cards-c1`, branch
`cards/c1` (from b16716481 on `cards/lead`). Edits only `engine-cards/**` and `reports/cards/c1/**`. Spec:
`reports/cards/specs/C1-SPECS.md`. Results: `RESULTS.md`.

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
- Gate shepherd complete: C56 parity PASS; see RESULTS §6.

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

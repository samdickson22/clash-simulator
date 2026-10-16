# Runtime full-pool card scope (r1-cards1): progress (resumable)

Worker for CARD LEAD. Edit only bot/players/runtime.py, bot/cards/, reports/cards/runtime/ in clasher-cards. No commits.
Scratch: 05 /mpac/sdicks02/jobs/clasher/cards/runtime/ (r1-ro = read-only copy of runtime .py/.json from 08).
Inventory research delegated (read-only) -> 05 /mpac/sdicks02/jobs/clasher/cards/runtime/INVENTORY-research.md.

## Log
- 2026-10-16T00:17:49Z start; reading runtime code.
- 2026-10-16T00:39:03Z bot/cards/scope.py (two-pass widen+merge) + runtime.py pin r1-cards1 (card_scope=full) done; smoke
  build on 08 OK (72 s; 121 cards, 350 templates; conflict meta.bodies.RamRider -> full row, FULL_WINS_BODIES).
  bot/cards/build_runtime.py done; dev root 08:/mpac/sdicks02/jobs/clasher/cards/runtime/r1-cards1-dev (src b7143dd7a
  export, native 681b5f2c, 0 overlay files differ from r1). Code sync: 05 jobs/clasher/cards/runtime/sync08.sh.
- 2026-10-16T00:54:13Z roots parity (03, gate.sh roots): live/c56/full 600/600 identical (300 roots x full/cut). 08 headline
  gate queued (cpu_job 14; 08 full). 03 noncore.sh launched (cpu_job 7) -> 03 jobs/clasher/cards/runtime/noncore/.
  Pre-existing: R.meta cards token for BarbLog/BlowdartGoblin/Ghost depends on PYTHONHASHSEED (set order in
  c56_scripted.initialize); all gate arms run PYTHONHASHSEED=0.
- 2026-10-16T01:12:28Z 08 too full (99-106 py procs): headline gate moved to 03. 03 chain (cpu_job 8, setsid):
  chain03.sh = wait noncore.log '^end' -> gate.sh headline (POLW=3 K4LW=1, RL5 = 03 jobs/.../rl5-policy-00010.pt
  sha e188e2ae) -> timing/ (save roots X1,D1,D3,D4 + time_roots.py). Logs: 03 jobs/clasher/cards/runtime/{chain03,
  gate-headline}.log, gate/hl-*, timing/. noncore so far: 0 crashes/panics/errors; D3/D4 live search ~all default
  (completed ~0.1 in 200 ms vs 2-3 on D1/D2) -> timing probe. Non-live K4L-R-gs + plain Belief crashes on a non-C56
  reveal ('no train deck'), expected; with --live-belief 2/2 M1 games clean.
  Drafts: SCOPE.md (4b/5/7 PENDING), INVENTORY.md.
- 2026-10-16T01:36:14Z **Timing probe, partial** (decision_timing.py, complete decisions LIVE-K4L-R-gs-rw-fc-w20000-t1-p2,
  X1 = C56 opponent deck, 7 decisions per arm, 03 at load ~85, medians ms c56 vs full):
  total 191 vs 288 (paired ratio median 1.05; same actions, same command sha) | R.root 20 vs 25 | fc json 12.5 vs 18.5 |
  root.snapshot 3.8 vs 6.5 | pool.begin 5.7 vs 23 | ship 11 vs 31 | worker parse 11 vs 21 | native ~same (noisy).
  Payload config bytes 0.61 MB vs 1.50 MB; full-scope cut config > 1 MiB, so LearnedPool.begin
  (lopp_fast.py:249 `len(parts[1]) < 1 << 20`) re-ships config to all workers every decision (config_resent=True).
  CAUSE: fc cut (config_need/ConfigCache/_ConfigJson) cuts only `cards`; full scope grows the other tables
  95 KB -> 795 KB (death_children 21->358 KB, bomb_children 98, soul_skeletons 84, production_children 98; ~half are
  Mirror level12: copies). Overhead ~+40-60 ms per decision at w200 = real but NOT a 10-20x native slowdown.
  The near-zero completions in noncore D3/D4/M1 also appear on the X1 C56 control in the same harness/time window
  (completed 0.14/0.33) -> mostly 03 load (rose 55 -> 85 between D2 and D3), not the new cards.
  FIX (prototype): bot/cards/fc_cut.py side-table cut (keep entries reachable by name from state + kept cards,
  fixpoint), patches ConfigCache + _ConfigJson.dumps; validation + before/after timing queued on 03 (timing.sh).
- 2026-10-16T01:36:14Z meta tokens: r1-cards1 now pins alias tokens (C56: BarbLog 20, BlowdartGoblin 77, Ghost 114 =
  seed-0 = learned-opponent npz vocab; new: own-name card_action token). r1-cards1 meta identical for
  PYTHONHASHSEED 0-3 (13726095); its C56 cards == r1-total seed 0. r1/r1-total stay seed-dependent (BOT/LIVE: run
  with PYTHONHASHSEED=0, else the learned opponent sees BarbLog/DartGoblin/Ghost as unknown under other seeds).
- 01:37Z **Timing b1 (paired, 62 complete decisions, X1 C56 opp deck, 03 load ~55-70)**, medians ms c56 -> full:
  total 212.8 -> 220.9 (paired ratio median 1.093; mean 197 -> 225), same 62 actions, same command sha 9fa08ea0.
  root 4.2 -> 6.7 | fc json 1.0 -> 1.2 | snapshot 0.9 -> 3.0 | pool.begin 1.2 -> 4.9 | ship 2.4 -> 8.5 |
  worker parse 4.7 -> 9.9 | native 143.7 -> 150.9 | learned 37 -> 40 | chunk ~35 both. Config bytes 0.37 -> 1.26 MB.
  => scope overhead ~+10-25 ms/decision (config size), native unchanged on C56 states. Not a 10-20x effect.
- 01:50Z RESUME after usage-limit stop. None of my host jobs alive (08 noncore_matches processes = live16402 worker,
  its own dir; not mine). Earlier timing b2/b3 (03, complete decisions t1-p2, full scope, medians ms): native per
  decision X1 151 | D3 145 | D4 154 | M1 130 | D1 187 -> new cards are NOT slow per native tick; root/json +10 ms on
  non-C56 decks (more distinct fc cuts). First side_cut_check crashed (fc_cut: instance built before install has no
  .side) -> fixed (falls back to the cards-only cut).
- 01:52Z addendum 4 implemented:
  * bot/search/lopp_fast.py (+33/-12): reduce_fast passes base_cut (= the player's fc flag) to LearnedPool.begin;
    fc roots ride the base config (sent once) whatever their size; every other config ships once per worker keyed by
    sha1 of its text (FIFO CONFIG_CACHE=8 mirrored in _pool_worker). base_cut=None (direct callers) keeps the size test.
    Pre-change copy: 05 jobs/clasher/cards/runtime/lopp_fast.before.py (== HEAD).
  * r1-cards1 pins: fc_side_cut=True -> Runtime installs bot/cards/fc_cut.py (before any pool forks).
  * repo-before (05/03/08 jobs/.../runtime/repo-before) = worktree with HEAD lopp_fast + r1-cards1 without side cut.
  Running: 08 gate_k4l.sh (cpu_job 16; c56/full x before/after, K4L-R-gs-rw-fc-p2, HEADLINE 0-5 x R3a,v1) -> 08
  jobs/.../runtime/gate/hl-k4l-*; 03 chain03b.sh (roots parity 3 arms -> side_cut_check -> policy HEADLINE) ->
  03 jobs/.../runtime/{gate2,timing}; 05 quiet05.sh (taskset 48-51, X1 c56/full x before/after, D3 full x2) -> 05
  jobs/.../runtime/quiet05/.
- 02:05Z **QUIET timing, 127x05 taskset 48-51 (siblings 112-115 idle), nice 10, load 15-25, window 01:58:38-02:05:08**
  (+ ~3 min of failed starts: 05 lacked the it5s2 student and lopp models -> sha-checked copies under
  jobs/.../runtime/{students,lopp-models}). LIVE-K4L-R-gs-rw-fc-w20000-t1-p2 (complete decisions), 62 decisions/run,
  PYTHONHASHSEED=0, paired by tick, all pairs same actions + same command sha (X1 9fa08ea0 x4 arms, D3 5ba8a7b5 x2).
  Medians ms (total | root | snapshot | ship | worker parse | native | config bytes):
    X1 c56  before 166.2 | 3.2 | 0.7 | 1.7 | 4.1 | 111.5 | 0.37 MB
    X1 c56  after  158.5 | 3.2 | 0.7 | 1.7 | 4.1 | 108.9 | 0.37 MB    paired vs c56-before x0.987
    X1 full before 172.8 | 5.1 | 2.0 | 6.0 | 7.1 | 116.5 | 1.26 MB    paired vs c56-before x1.065
    X1 full after  167.6 | 3.3 | 0.6 | 1.6 | 5.1 | 110.7 | 0.31 MB    paired vs c56-before x1.006
    D3 full before 181.9 | 12.1 | 2.1 | 7.0 | 6.2 | 118.0 | 1.31 MB
    D3 full after  164.3 | 3.7 | 0.7 | 1.9 | 5.8 | 105.1 | 0.39 MB    paired before->after x0.880
  => fix removes the full-scope overhead (C56 deck: x1.065 -> x1.006 of c56; non-C56 D3: -12%); lopp_fast change
  neutral on c56 (x0.987). Mac projection (fleet ~2.8x slower than Mac): X1 full-after 168 ms t1-p2 -> ~60 ms.
- 02:10Z GATES so far (final code):
  * K4L HEADLINE (08 gate_k4l.sh, K4L-R-gs-rw-fc-p2 vs R3a,v1 cases 0-5): 12/12 command shas identical across
    c56-before / c56-after / full-before / full-after, 0 errors. fp variant (content-hash path): 2/2 identical.
  * Roots parity re-run (03 gate2): live/c56/full 600/600. side_cut_check: 265/265 C56 rec roots, 80/80 non-C56.
  * Policy HEADLINE (students it5s2 + RL r5 v10 vs v1,R3a): 03 too loaded (95) -> cut to cases 0-9, both arms now
    on 08 (polgate.sh c56/full, cpu_job 7 each; c56 resumes 9 games copied from 03) -> 08 jobs/.../runtime/gate2.
  * noncore_final.sh (08, cpu_job 7): final-code LIVE K4L no-crash re-run, D1-D4/M1 vs random + D1 vs R3a.
  SCOPE.md rewritten (§1/2/4/5/5b/6/7); remaining placeholders POLICY_GATE_PENDING, FINAL_RERUN_PENDING.

## HANDOFF 2026-10-16 ~02:20Z (Claude budget; Sol takes over)
**All gates DONE; no jobs of mine are running** (08 polgate c56/full finished 02:13Z rc 0; noncore_final finished
02:17Z; 03/05 nothing). SCOPE.md has no placeholders left: POLICY_GATE_PENDING and FINAL_RERUN_PENDING were filled from
the outputs below. To re-derive them:
  - policy gate: `ssh 127x08 'cd /mpac/sdicks02/jobs/clasher/cards/runtime && python3 repo/reports/cards/runtime/tools/compare_scope.py gate2'`
    -> headline_pol 40/40 identical (it5s2 / RL r5 v10 x v1 / R3a, 10/10 each), 0 errors.
  - final no-crash: `ssh 127x08 'cd /mpac/sdicks02/jobs/clasher/cards/runtime && python3 repo/reports/cards/runtime/tools/noncore_summary.py repo/reports/cards/runtime/tools/c56_cards.json noncore-final/live.jsonl'`
    -> 6/6 clean; search_detail from noncore-final/live.jsonl.
  - K4L gate: 08 jobs/.../runtime/gate/hl-k4l-{c56,full}-{before,after}/ (12/12); fp: gate/hl-k4lfp-* (2/2).
  - roots: 03 jobs/.../runtime/gate2/roots-*.jsonl (`compare_scope.py gate2` on 03); side checks: 03 jobs/.../runtime/timing/side-check-*.json.
  - quiet timing: 05 /mpac/sdicks02/jobs/clasher/cards/runtime/quiet05/*.jsonl (`tools/timing_summary.py`).
**Files changed (uncommitted, for the lead):**
  - bot/players/runtime.py: pin set r1-cards1 (card_scope='full', fc_side_cut=True) + the extend / fc_cut.install hooks.
    (The live16402 pin, gamedata_sha256 and tournament_crown_from_gamedata lines in the same diff are another worker's.)
  - bot/search/lopp_fast.py (+33/-12, BOT LEAD approved): base_cut flag + content-hash pool config cache (CONFIG_CACHE=8).
  - bot/cards/scope.py, bot/cards/fc_cut.py, bot/cards/build_runtime.py (new; bot/cards/__init__.py is the lead's, unchanged). (Other bot/cards/*
    files are other workers': proxy_table*, balance_overlay*, build_live16402.py, PROXY-REVIEW.md.)
  - reports/cards/runtime/{SCOPE.md, INVENTORY.md, PROGRESS.md, tools/*} (new). NOTE: .gitignore:72 `/reports/**/runtime/`
    ignores this whole dir, so commit it with `git add -f reports/cards/runtime` (or rename the dir).
Scratch that can be deleted later: 05/03/08 /mpac/sdicks02/jobs/clasher/cards/runtime/ (r1-cards1-dev roots, repo and
repo-before copies, r1-ro, students/ and lopp-models/ copies on 05, rl5 checkpoint copy on 03).
Open items for other leads: SCOPE.md §7 (macOS spawn workers lack the side cut; K4L learned-opponent vocab is C56-only;
non-live Belief raises on non-C56; set PYTHONHASHSEED=0 on r1/r1-total; translator pass-through is a LIVE LEAD decision;
real r1-cards1 root not built yet).

- 2026-10-16T02:19:50.726303+00:00 gate shepherd: independently re-derived policy PASS (40/40 identical command shas, exact cases 0–9 per pair, 0 errors) and final LIVE K4L PASS (6/6 terminal, 0 crashes/panics/errors, new-card entities in every row) on 127x08 via cpu_job.sh 1. Jobs were already complete (policy rc 0; final six rc 0), no active script PIDs or recorded PID files; no restart. Existing placeholder tables verified and augmented in SCOPE.md; live16402 base r1-cards1-dev noted without rerun. Audit/source hashes: GATE-VERIFICATION.json. Reports only; no code edits, commits or sealing.

- 2026-10-16 02:20-03:10Z (after handoff; lead tasks): **R.bots widened** for r1-cards1 (scope.py: R.bots = full
  build's scripted bots, asserted equal on C56 tokens; R.base_bots keeps the old). **Review fixes** (Sol review of
  0874da215): (1) fc_cut.mirror_need keeps level12:<card> for Mirror holders' hand+cycle+last_card; (2) lopp_fast:
  with base_cut every root's own config ships once per worker by sha1 (fc = raw, no worker re-cut, never stale);
  base_cut=None = original protocol (bot/noise/mr_fast.MRPool needs it); (3) r1-cards1/r1-cards2 pin
  gamedata_sha256 = BASE_GAMEDATA 892fbfa0... Gate 4 (08 jobs/.../runtime/gate4, bots_gate.sh, all done): K4L c56 vs
  full 12/12 identical; side_cut_check 265/265 + 80/80; mirror_probe 80/80; own deck M1 vs R3a 6 games 0 errors, new
  cards played (live recipe incl. GoblinCage). Probes on 05: own_probe (GoblinCage legal 120 tiles), stale_probe
  (new protocol fresh for A and B; legacy stale on B). live16402 root now fails r1-cards1's gamedata pin (checked).
  No jobs of mine running.

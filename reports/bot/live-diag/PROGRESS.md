# live-diag PROGRESS (bot lead's live-gameplay diagnosis; exploration tier)

Owner: Opus live-diag research sub-agent of the BOT LEAD (thread clasher-bot-lead-20261014-r1). Resume from here.

## Where things are
- Code (branch bot/live-diag, worktree /mpac/sdicks02/repos/clasher-bot-livediag on 05): bot/livediag/
  - live_metrics.py: live-log metrics (tiers, plays, hand mismatch, Giant pushes, Cannon placements); analyse() also reads sim logs.
  - sim_diag.py: RoyaleSim 15.535 twin (live e16 deck vs Giant decks, live-log-shaped per-poll records).
  - root_scores.py: replays a live session through LiveSession with deterministic K4L-R-gs-rw; logs candidate cards / R3a proposals /
    work-set scores; counterfactual defence set re-scored at command delays 5/10/20/27/40 and on the level-aware root.
- RUN TREE (fleet): /mpac/sdicks02/repos/clasher-bot-livediag-run = origin/main at e883a80da^ (04f5730f3) + bot/livediag/*.
  origin/main e883a80da (R8 slot permission) breaks search players on the r1 runtime (clasher.rl.slot_permission missing,
  StandalonePlayer.last_feature_mask); the parent is what was deployed/evaluated. Synced to 03 and 01.
- Env: /mpac/sdicks02/jobs/clasher/bot-livediag/env.sh on 01/03 (r1 + r1-total pins, native-total-r1, rl5 v10 sha e188e2ae as CLASHER_LIVE_FAST).
- Job dir: /mpac/sdicks02/jobs/clasher/bot-livediag (05: runs/ = copy of runs-all, live_metrics.json, summ.py, sdicks_latency.json,
  sdicks_cannon_table.json, cannon-crops/; 01/03: sim1/, roots/).

## Status (2026-10-16T18:07:13Z)
- Part 2a (live logs) DONE and reported: search decides 100% of plays, deadline never binds, hand clog (Giant .92 / Fireball .88 in hand),
  14% of Giant pushes undefended before contact, elixir at Giant cross median 2.9.
- sim1 RUNNING: 01 live arm (LIVE-K4L-R-gs-rw-fc-w200-t4-p4, 3 workers, launcher PGID 568566); 03 rl5/k4c/r3a arms
  (launcher PGID 1919789, queued behind full-pool leases). 34 cases x R3a,v1,rext-bc each. Re-run = same command (resumable).
- root_scores: smoke on s41-m03 in progress on 03.

## Fresh bank for the timed-wait A/B (drawn 2026-10-16T18:12:47Z, before any game)
- BASE = 3568068836231360 (int.from_bytes(os.urandom(6),'big') << 4). sim_diag cases: our seat i%2, live e16 deck vs
  giant_decks()[(i//2)%5] (mirror + 4 most frequent prior Giant decks), Random(BASE+i) shuffles. Opponents R3a, v1, rext-bc.
- Arms: LD-K4L-R-gs-rw (deterministic twin of the deployed live player), -wcap10, -wcapE, -wint (bot/livediag/variants.py).
  Quoted number: paired per-case score delta vs LD-K4L-R-gs-rw, bootstrap 95% CI over cases, equal-weight opponents.

## Hosts (18:12Z): BOT LEAD moved me to 04/08 (01/03 full of full-pool). 03 keeps sim1 rl5 + r3a (leased, running).
- 04: sim1 live arm (launcher PGID 3755544), root replays 8 sessions (PGID 3776051). 08: sim1 k4c (PGID 905301), smoke3 (897599).
- Killed my own queued claims on 01 (568566) / 03 (k4c + roots, incl. 8 orphaned k4c workers by verified PID).

## A/B launches (all resumable: re-run the same launcher; sim_diag skips finished (candidate, opponent, index))
- ab1 (18:14Z): 08 `run_ab1.sh LD-K4L-R-gs-rw LD-K4L-R-gs-rw-wint` W=10 (PGID 1006405); 04 `-wcap10 -wcapE` W=7 (PGID 3887042).
- ab2 (18:17Z, BOT LEAD request): 08 `-gf -wint-gf` W=8 (PGID 1050949); 04 `-h240` W=8 (PGID 3970152). Queued on cpu_room until room frees.
- Outputs: <host>:/mpac/sdicks02/jobs/clasher/bot-livediag/ab1/<arm>/games-*.jsonl. Summarise: copy all arms to one host,
  `python3 -m bot.livediag.sim_report ab1/* --ref LD-K4L-R-gs-rw --json ab1-report.json`.
- sim1 K4C-r16 arm errors on the mirror-deck cases (opponent deck 0 = the e16 deck is not in the human prior; the frozen
  K4C belief raises 'no train deck'); LIVE/LD players use live_belief_class and are unaffected. Read K4C on decks 1-4 only.
- Winner commit must be based on main >= 5bce7c28b (slot-permission revert). bot/livediag has no dependency on the R8 change.

## Status 2026-10-16T18:31:23Z
- DONE: live metrics (part 2), sim1 (part 1), command-delay null, level null (part 3), interim A/B (RESULTS.md §5).
- -gf / -wint-gf STOPPED (08 PGID 1050949): -gf identical to base on all 29 cases (Giant/Fireball get learned values but never win).
- RUNNING: ab1 base/-wint (08 PGID 1006405), -wcap10/-wcapE (04 PGID 3887042), -h240 (04 PGID 3970152),
  ab3 -res/-h240-gf (04 PGID 519475), ab4 -ew30 (08 PGID 1836334). All write <host>:/mpac/sdicks02/jobs/clasher/bot-livediag/ab1/<arm>.
- NEXT: final A/B rows at n=204 per arm, weighted on rext-bc; pick a winner only if pooled CI > 0 and rext-bc not negative;
  winner spec + commit (based on main >= 5bce7c28b) to the BOT LEAD. Else report 'policy; training fix'.
- Readout recipe: rsync 04:ab1/ -> 08:ab1-04/; on 08 run sim_report over ab1/<arms> + ab1-04/<arms> (see ab-interim2.json).

## Process slip (2026-10-16, commit d9b795b94)
- The secret scan before the push used a hand-extracted copy of the scanner regex; the extraction failed (grep error) and
  `|| echo scan-clean` masked it, so the push preceded a valid scan. Post-push, the scanner's own regex on
  f571096fb..d9b795b94 found no hits. Fix: next commits are made in a scratch worktree detached at origin/main (so HEAD =
  parent) and `/mpac/sdicks02/cc/tools/bin/clasher-secret-scan` itself runs on the staged diff; a non-zero exit stops the push.

## Status 2026-10-16T18:56Z
- Bank-1 A/B final (RESULTS §5): no winner. Handsync check (RESULTS §6): no measurable slow-down.
- RUNNING: ab5 = -res (λ .015) vs base on BASE2 580000520902944 (drawn 18:53:30Z), 136 cases x 3 opp: 08 base (PGID 3248253),
  04 -res (PGID 2010521). DECISION RESTS ON BASE2 ALONE (bank 1 selected -res among 7 arms).
- RUNNING: ab6 λ/R grid on bank 1 (dev): 08 -res8 -res30 (PGID 3367853), 04 -res15p1 (PGID 2155688). Best grid arm then needs a NEW bank.
- TRAINING-FIX.md drafted (plan + ETAs).
TRAIN_BASE=3948945398717664 drawn 2026-10-16T18:58:41Z
- Option 2 data (BOT LEAD approved 18:5xZ): bot/livediag/dumpbank_gen.py; train bank above; db1 = 08 cases 0-499 (W10),
  04 cases 500-999 (W10); out <host>:jobs/clasher/bot-livediag/db1/roots-*.jsonl; resumable (same launcher).
  Smoke (dbsmoke on 08): replay_ok 4/4, ~220 s per base game incl. 2 reserve replays.
BASE3 (strong-opponent check)=2390764269446208 drawn 2026-10-16T19:18:55Z
BASE4 (strong-opponent replication)=1870204031157424 drawn 2026-10-16T19:31:33Z

## Status 2026-10-16T19:4xZ: deployable -res
- Strong-opponent gate PASSED (RESULTS §5b): -res vs LIVE-K4CW-r16 +0.18 [+0.07, +0.30] on BASE3. Replication ab8 on BASE4 running.
- Deployable token `res` (bot/search/reserve.py + lopp.py/lopp_fast.py hooks); res_equiv 3/3 equal hashes; wall check
  (lopp_time, 04 cores 40-49, 2x5) p50/p95 base 86/128 ms, res 96/137 ms, hit 0.008/0.009, 0 errors.
- db1 (option 2) STOPPED at 103 rows for the gate; restart with 4-opponent mix (adds LIVE-K4CW-r16) via run_db.sh (resumable).
BASE5 (B: wait/rh arms vs strong opponent)=2439740075545088 drawn 2026-10-16T19:42:25Z
TRAIN_BASE2 (db2, rh-mode option-2 data)=3777504499689488 drawn 2026-10-16T20:02:55Z
- 20:1xZ db2 rescaled (BOT LEAD: hosts idle): 08 cases 0-499 W40, 04 cases 500-1499 W40 (grown beyond 1000), fixed cpu_job.sh (flock, 5179f0f42) in run trees.
- 2026-10-16T20:20:18Z db2 re-steered: half LIVE-K4CW-r16 (i%6 map), k=4 likely-binding roots first; fit weights K4C rows x3.
- 2026-10-16T20:56:37Z option-2 milestone 2: 1181 rh-mode binding roots, mean y -0.023, CV corr -0.06 (K4C -0.21): no conditional signal on
  the game-end target. Generator now records a 100-tick series (tower HP both, crowns, elixir); fit --target h400/h600. db2 restarted
  (04 cases 500-1999 W40 PGID 635506; 08 cases 0-499 W40 PGID 2228360). Live A/B: s53 first -res (v9a); waiter for s56.
BASE6 (lc dev screen vs K4C-r16)=467516450769760 drawn 2026-10-16T21:54:26Z
BASE7 (lc10 confirmation vs K4C-r16 + rext-bc; base, -res, -rh-lc10)=1029667185899056 drawn 2026-10-16T23:23:49Z; kappa=1.0 picked on BASE6 dev

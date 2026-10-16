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

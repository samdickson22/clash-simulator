# Noise-robust decisions under perception noise (bot lead worker, exploration)

**Brief.** Coordinator ruling 91e2bb67 (lever approved): make the bot robust to perception noise.
- **Primary metric:** `PERC-emp:LIVE-K4L-R-gs-rw-fc-w200-t4-p4` vs R3a. The LIVE LEAD measured
  −0.200 [−0.263, −0.137] (0.807 → 0.607) against perfect sight (c95ef57b).
- **Secondary:** K4L vs v1 −0.070, and it5s2 −0.137 (R3a) / −0.113 (v1).
- **Noise model:** exactly `bot/live/empirical.py` + `empirical-val.json` at current main (unit threshold 0.4).
  Screens use this, the comparable reference for every number so far. Fresh-bank claims re-measure the candidate and
  the unmodified baseline against the stats deployed at that time, pre-registered.
- **Boundary:** the LIVE LEAD owns everything up to the perceived view. This work changes only decisions given that
  view. bot/live/* is never edited; proposed hooks are written out as diffs in RESULTS.md.

## What the noise looks like from the decision side

Measured offline on 60 captured game-seats (`bot/noise/tune.py`; cases 1000–1029, off the screen bank). The raw
perceived packet (PERC-emp, after the LIVE translator) against the true packet, troops and buildings only:
- **Recall 0.69**, so 1.6 true units are missing per poll. Most misses are swarm bodies: Skeleton 57% missed,
  Minion 42%. Hog, Knight, Giant and similar are missed 4–26% of polls.
- **Only 0.10 phantom units per poll.** The translator's deck-rule sanitizer and body mapping already remove most of
  the channel's ~0.19 false positives per frame per owner.
- **Wrong body among matches: 2%.**
- **Structure of the channel:**
  - misses are Markov per true unit (p(hit | hit) .92, p(hit | miss) .34, so a miss streak lasts ~2.9 polls);
  - phantoms are drawn iid per frame, mostly within 0.3 tiles of a real unit of that owner;
  - card confusion is redrawn every frame.
- Caveat: real perception errors are probably more persistent than this channel models (FP persistence was never
  measured). A filter tuned to iid phantoms may overstate its live gain. See the proposed hook in RESULTS.md.

## Levers, in the order tried

**(a) Root denoising: `bot/noise/filter.py` EntityFilter, wrapper `NR-<tag>:<player>`.**
- **Mechanism:** tracks across the bot's own polls (every 5 ticks). It rewrites the packet's entity table before any
  tier sees it. Scope `a`: it5s2 fast tier, R3a/it5s2 proposals and the search root. Scope `sr`: search root only.
  - `c<n>i<tenths>` (confirm): a new track is output only after n detections, unless no output track of that owner
    lies within i/10 tiles.
  - `m<k>[d<tenths>]` (coast): a confirmed undetected track stays k polls at its last position, plus d × velocity.
  - `v<w>` (vote): the majority body over the last w detections.
- **Fair information:** it reads only packets the bot received.
- **Persistence:** it survives PercPlayer's resync restarts within a match (several per match).

**(b) Perception-aware determinization:** several roots (with/without uncertain units) averaged. K4L already has
`K<n>`/`D` multi-sample machinery (lopp.py). Considered after (a), within the 200 ms budget.

**(c) Noise-augmented student/opponent-net training:** needs a GPU slot. Only if (a)/(b) leave a large it5s2 gap.

**(d) Confidence-gated fallback** (search ↔ it5s2 when the root looks inconsistent): after (a).

## Screening protocol

- **Twin for screening:** `LIVED-K4L-R-gs-rw-fc` (bot/noise/player.py), the deterministic twin of the live K4L.
  - It is the same LivePlayer, with it5s2 as default and proposer, and the same K4L-R-gs-rw-fc search.
  - It has no wall deadline, one thread and no pool, so every search completes.
  - **Why:** load-insensitive on the shared 04/08 hosts, reproducible (tight pairing), ~13 core-h per 600 games.
  - **Live difference:** the live arm (w200-t4-p4) falls back to it5s2 on ~2% of decisions.
  - The promoted candidate is re-measured wall-timed (quiet pinned 4-core groups on 03) before any claim.
- **Cases:** HEADLINE 0–299 vs R3a (primary) and v1, ours engine, PERC-emp.
- **Pairing:** each arm is paired per case with `PERC-emp:<same player>`.
- **Noise sizing:** a reseeded reference `PERCs1-emp:<player>` (the same PercPlayer/EmpiricalNoise with noise seed
  [seed, seat, 0x9e4c, 1]) sizes run-to-run perception noise. The HEADLINE bank carries ~0.03 selection luck.
- **Perfect sight:** each promoted filter also runs as `NR-<tag>:<player>` without PERC. It may not cost more than
  ~0.01 there.
- **Runner:** `bot/noise/run.py`. This is headline_wall's protocol, plus NR/CAP/PERCs/LIVED names and per-game
  decision stats in each row (wall p50/p95/p99, cutoff-default share, filter counters).
- **K4L diagnostic ablation:** the LIVE LEAD's `-x<part>` arms are not on main yet. They ran from an unmodified copy
  of their eval3 perc.py/empirical.py in `03:/mpac/sdicks02/repos/clasher-bot-noise-abl`, for diagnosis only.

## Promotion (fresh bank)

- A NEW bank, `BASE = int.from_bytes(os.urandom(6), 'big') << 4`.
- BASE, the decision rule and the stats file are recorded in RESULTS.md before any game.
- 600 cases each vs R3a and v1, paired, ours engine, PERC-emp with the stats deployed at that time.
- The live wall-timed K4L arm runs on quiet pinned 4-core groups.
- Timing is reported: p50/p95/p99 and default share.

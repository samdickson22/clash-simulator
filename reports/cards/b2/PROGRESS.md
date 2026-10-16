# Batch B2 (spells + spell-like) — progress (restart notes)

Worker: CARD LEAD engine sub-agent. Worktree `/mpac/sdicks02/repos/clasher-cards-b2` (05), branch `cards/b2` from
7720915a8. Edits only `engine-cards/**`, `reports/cards/b2/**`. Parallel worker on cards/b1 (troops).

## Layout (127x08: /mpac/sdicks02/jobs/clasher/cards/b2/)
- `base/` = git archive of engine-cards @7720915a8 (Batch A WIP commit); `tree/` = rsync of my engine-cards.
- `root/`, `baseroot/` = {engine-rs, src, gamedata.json -> tree|base, reports -> r1/reports} (Batch A layout).
- `fid/` = copies of `reports/cards/b2/tools/*` + fidelity pool.json, summarize.py, controlled.py.
  `run_fid.sh ROOT OUT N --cards ...` (cpu_job lease, nice 15, PYTHONHASHSEED=0); `tr.sh ROOT CARD SCEN [--names ..]`
  = per-tick both-engine trace (trace.py); `diffs.py`/`show.py`/`table.py` from Batch A.
- `base.jsonl` = baseline (adapter table) for the 10 cards; reproduces reports/cards/fidelity/results.jsonl verdicts.

## Rules
- New native Spec/Stats fields: `#[serde(default, skip_serializing_if = ...)]` (lead 01:50Z; Batch A native 1923619e).
- Pure stat values -> overlay rows in RESULTS, scratch gamedata only (apply_stats.py), never git.

## Findings so far
- Poison × dash (native-diff): native `c56.rs:area_targets` lacks `!e.dash_travel()`; dash exists only on BanditDash
  bodies (Bandit, BossBandit) -> fix is C56-inert.
- Mirror × SkeletonBalloon: `c56.rs:bomb_tick` looks up `bomb_children[stats.name]`; use `stats.key()` (falls back
  to name) -> C56 (level 11) inert.
- Spell area boundary (controlled probe: ours misses at r+0.5, RS hits up to r+1.0): RS `AOE_HIT_TEST` is a LOW-confidence
  guess; ours is the client's `LogicGameObject::intersects` (strict). Native authoritative; not changed. Shared by C56.
- Snowball cluster: knock+slow identical; 1-tick post-push step differs (ours steps back to the pre-push waypoint after a
  1.8-tile push). Fireball (C56) same scenario is identical -> push length, shared route code. Not Snowball code.
- Stats (adapter arm CLIENT16402_VALUES): Freeze AreaBuffTime 3500 (+ 16.402 life 3500); HealSpirit HP 84.
- Rage: controlled effect first tick 16/11, last 113/105 (timing mechanic, TODO).
- DarkMagic: hits 340 at [32,52,72] vs RS 696 at [33,57,81] (damage scaling + cadence, TODO).

## Log
- 2026-10-16T01:38Z start; ~01:45Z stopped on usage limit; 01:50Z resumed.
- 2026-10-16T01:56:45Z Primary arm = full 16.402 table (--table 160402; adapter arm's Void 1200 ms is the 15.535 value).
  Scratch overlay: 08 b2/fid/stats-spec.json -> b2/stats/gamedata.json (apply_stats.py, "add" rows for ABSENT fields),
  root b2/rootstats. Fixes so far (Python; native mirrored, NOT yet built): native Poison×dash + bomb_children key;
  scope_spells._register birth-tick skip (Void/Vines/Curse were 1 tick early); Vines data-driven catch clock
  (hitSpeed/hitSpeedOffset/lifeDuration), re-pick each catch, grounding window 2.1 s, grounded flier keeps air
  collision plane. With stats: Freeze 3/3, Heal 3/3, DarkMagic 3/3, Vines 3/3 PASS (r2s/r3s.jsonl).
- 2026-10-16T02:15:28Z More fixes: GoblinCurse curse slow (data speedMultiplier) + goblin deploy +1 tick; Graveyard
  birth skip, against_forward y orientation, Skeleton deploy +1 tick, acquire delay F+7 (_targetable_from_ms /
  native lock_after), creation-tick first update; Rage haste area applies on landing, cap = life left + HitSpeed,
  balance.py Rage capBuffTimeToAreaEffectTime; Clone object-phase cast, 500 ms hold, 10-tick column-edge slide after
  movement, route dropped; Freeze crownTowerDamagePerHit read (data). Native port of all; birth = tick+1 for command
  scope objects. native df5443ab: scenario lockstep native==Python on the 10 cards (root + rootstats).
- 02:15Z GATE launched on 08: b2/gate.pid 3043090 (cpu_job 8; fid/gate.sh; arms pinned r1+681b5f2c vs gtree+gout
  df5443ab; gtree file-hash 8219fb79). Result -> b2/gate/compare.json. gtree == worktree engine-cards (rsync -c).

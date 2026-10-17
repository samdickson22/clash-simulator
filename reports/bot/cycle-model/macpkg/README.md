# Soft cycle model: Mac package on the deployed RESUME tree (cycle-model owner, for the LIVE LEAD / loop owner)

**Status:** READY TO STAGE for the next Mac window. No Mac work during the Null's block.

**Rollout (the LIVE LEAD's ruling):** sequential. It goes in as a fast restart after 5 clean battles on the RESUME stage
(x1h + towers + likely -res-wint).

**Evidence:** CYC-L16-1, L16, deployed -res, vs K4CW-r16, 200 paired games.
- soft − hard +0.045 [−0.022, +0.112], which passes the pre-registered ship bar.
- clean − hard +0.090 [+0.011, +0.169]; recovery 0.50.
- Details: main reports/bot/cycle-model/RESULTS.md.

## Two variants (pick the one matching the base that ships)

| variant | base code dir (unchanged) | NEW code dir | base manifest | new manifest | launcher |
|---|---|---|---|---|---|
| `wint/` | fullpool-r1-wint (live-diag pkg-fp-resume) | fullpool-r1-wint-cyc | MANIFEST-fullpool-wint.json 7322efaa… | MANIFEST-fullpool-wint-cyc.json | run-fullpool-wint-cyc.sh |
| `plain/` | fullpool-r1 (+ e855d300 RESUME) | fullpool-r1-cyc | MANIFEST-fullpool.json e855d300… | MANIFEST-fullpool-cyc.json | run-fullpool-cyc.sh |

Each variant changes the same 6 files vs its base (FILES lists them with destinations and shas):

| file | change |
|---|---|
| bot/cyclemodel/__init__.py, belief.py, preal.py | NEW (main 3d29d82e6) |
| reports/bot/cycle-model/preal-v1.json | NEW: P(real) v1 |
| bot/fullpool/belief.py | deployed 3d1e62a2 + the 2-line `wrap` hook (with the env unset it returns today's class) |
| bot/live/translate.py | deployed c10b997b + the translator owner's drop_features + `_soft_conflict` (cycle conflicts → `card?`, belief stream only, only when enabled) |

**Launcher:** a copy of the base launcher. The only differences are the code-dir default, LL_MANIFEST, and
`BOT_CYCLE_MODEL=soft BOT_CYCLE_PREAL=$CODE/reports/bot/cycle-model/preal-v1.json`.

## Install (loop owner, on the Mac, in the Mac window)

```
B=~/clasher-live; V=<wint|plain>; NEW=<fullpool-r1-wint-cyc|fullpool-r1-cyc>; BASE=<fullpool-r1-wint|fullpool-r1>
cp -a $B/loop/code/$BASE $B/loop/code/$NEW                 # base dir untouched
# copy every FILES row: package file -> $B/<dest>  (6 code files into $NEW, the launcher + manifest into loop/)
```

## Pre-start check (see INSTALL.md step 4)

It uses live-diag's `~/clasher-live/livediag-pkg/bench/run-fpbench-mac.sh prestop` (env wrapper, 8e2489a0…) with
`LL_CODE=<new dir>`. That wrapper runs `fp_prestop_check.py` f43d5863… (the LEAD-cleared version; PRESTOP_SHA in
INSTALL, enforced). Both are reused unchanged, and the run needs the LEAD's clearance.
The new launcher stays non-executable until the check exits 0.
- **Coverage:** MANIFEST-LINES.sha256 lists every entry of the new manifest (code plus the 37 `../` data files), plus the
  installed manifest itself and the launcher (`../../`).
- **Exit 0 only if** every listed file matches, the player constructs from `--code`, and the five origin-checked modules
  (bot.live.player, bot.search.lopp_fast, bot.search.lopp, bot.search.interrupt, bot.players.runtime) import from
  `--code`. Other `bot.*` modules resolve from `$CODE` first, through the launcher's PYTHONPATH. Any other exit (1, or
  124/130 on deadline/signal) means do not start the new launcher.
- **FILES order:** code files, then the manifest, then the launcher last. So a present launcher implies the manifest was
  installed, and drive.py's session-start guard (LL_MANIFEST) then refuses to start on any missing or changed file.
- **Soft path:** the check runs with the cycle model off (it builds no translator). That soft is active is proven on
  battle 1 by the session-start line and the tr_stats tag (INSTALL.md step 6).

## Rollback

Start the next session with the base launcher (run-fullpool-wint.sh / run-fullpool.sh). The base code dir and
manifest were never touched. The cyc launchers always set BOT_CYCLE_MODEL=soft, so the base launcher is the rollback.

## Latency

- No per-decision cost: decisions without a cycle conflict take the frozen code path.
- Once per battle, the first conflict costs up to ~120 ms on loaded fleet hosts while ~100k prior rows remain. In the
  Mac-env shadow, max_ms was ≤ 5.3–7 ms. Later conflicts take ~1 ms.

## Default-off parity on these trees (fleet, 08)

Results: see PARITY.md.

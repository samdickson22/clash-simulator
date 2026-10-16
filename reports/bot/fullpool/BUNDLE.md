# Full-pool live bundle (package for the 00:00Z ladder resume)

Owner: full-pool track (exploration). Code: **main 2fa5d496e59ad80e587563aae059e49887c50c10** (every bot/ file below is at this commit).
Players: base `LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1`, treatment `LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res`.

## Gate (LIVE-AB1, PASS; reports/bot/fullpool/PROGRESS.md 21:08Z)

Bank LIVE-AB1 was drawn fresh at 19:12Z, before any game. e16 played the 91 Battle Log decks on live16402b-r3, 3800 games
with 0 errors, paired by (opponent, case). A = current live: C56 K4L, which sees off-vocab cards as their live alias and
uses the C56 catalog belief. B = `K4L-R-gs-mk1a1`: true ids and the open-world belief. Both are deterministic (no wall)
twins.

| opponent | n | A | B | B − A [95% CI] |
|---|---|---|---|---|
| R3a | 800 | 0.848 | 0.901 | +0.054 [+0.024, +0.085] |
| v1 | 800 | 0.939 | 0.966 | +0.028 [+0.008, +0.048] |
| LIVE-K4CW-r16 (strong) | 300 | 0.383 | 0.533 | +0.150 [+0.073, +0.227] |
| pooled | 1900 | 0.813 | 0.871 | **+0.058 [+0.038, +0.078]** |
| pooled, C56-only opponent decks | 255 | 0.820 | 0.851 | +0.031 [−0.024, +0.086] |
| pooled, off-vocab opponent decks | 1645 | 0.812 | 0.874 | +0.062 [+0.041, +0.083] |

Not in the gate: rext-bc (RoyaleSim-only; C56 RoyaleSim vocab), and reaction time and undefended pushes (these rows have
no play logs).

## Runtime pin

live16402b-r3: `/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3`, read-only on 03/04/08.
- native de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1;
- gamedata a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb;
- file manifest excluding the per-host RECEIPT.json: 1aa243756bd984943a9fa871486157a27879ce0915b7002e2595e866a8164be1.

The Mac native (8072e577…) and the Mac parity build belong to the CARD LEAD.

## bot/ files that differ from the Mac snapshot (manifest-simple-r2/bot-snapshot-20261016.sha256)

This is the bundle player's measured import closure: a real game of `…-mk1a1-res` under the bundle env on 08, 35
modules, plus reserve.py, fullpool/decks.py, cards/proxy_table.py and every package `__init__.py`. Files in the closure
that already match the snapshot are listed as unchanged. Copy the files from main 2fa5d496e59a
(`git show 2fa5d496e59a:<path>`).

**Changed vs the snapshot (11)**

| path | sha256 at main | snapshot sha256 |
|---|---|---|
| bot/live/levels.py | a3289daf71ef7f1e4270e2b4f56542a31f07c00a86b645ab94c7fbadd3d032bf | 822cee2a73d9de27… |
| bot/live/player.py | 02252a3d84a4754b9e39aeac45db83b92152a2efdffafea8032d03fe28d83db4 | 3b4f27d7d62042b5… |
| bot/live/translate.py | 43c9a5c70c1a7f40ad707e8b8389fa84d8589e8819049fd2953d16c2d66e8488 | 5361deb0dbe166fd… |
| bot/players/ours.py | 3bac79d3bb0b590984f20d533beedf1672e33d91c69929a01cafc8fc7baec363 | 6d923289692467b7… |
| bot/players/royalesim_translate.py | 381138734b2fcdd45434685b3b764f30c70583c51f8cc9fc4052d9b55df29fa6 | 96229925be51b54a… |
| bot/players/runtime.py | 2f653f39450b2030bc00b0b36c20890fdb2cbf48ab76e9800dc3f1edbcdeccf4 | 891a54d6fe641fdb… |
| bot/players/search.py | e130eb2eade973f969766c31cb9b1ae16953f2a3eb89e9719a2e24ac6b90a8f1 | ce2ea36cedfb4ddb… |
| bot/search/lopp.py | e7df171147a906b6cdb0fd656306171545c03fa19d99413593b392c4ed1a6b55 | c04bef9322dc0e4f… |
| bot/search/lopp_fast.py | b0c74d4763657e5891c1d25be440d43a43f55af9793f03d332aff2f2aa1e1f9a | 716e5848fe7a4d4e… |
| bot/search/lopp_feat.py | 123c5281fb445a45a6c9712f5558927d0c37a92c695cfea917c115d316640204 | 482743a845b817de… |
| bot/search/players.py | a58a47875588691677a165f07678f48af103970f980b1f3b0baef8731fdeb1cd | e35dfba09c36d105… |

**Ownership of the three changed bot/live files**
- `bot/live/player.py`: the ONLY change vs the snapshot is the full-pool belief switch (64c720ea + 844d5655). The R8
  change e883a80da and its revert 5bce7c28b cancel out. Default behaviour is unchanged (C56 catalog completion unless
  BOT_BELIEF_PRIOR selects a full-pool prior). The two hunks:
  ```
  WallCandidatePlayer.start:   p = PublicPlanner(R, rt.PRIOR, seed); p.belief.__class__ = Belief
                       ->      prior, belief_cls = planner_belief(rt, Belief); p = PublicPlanner(R, prior, seed); p.belief.__class__ = belief_cls
  LivePlayer.start:            belief.__class__ = live_belief_class(); belief.human_prior = self.rt.PRIOR
                       ->      the same, but only if belief_spec(self.rt) == 'c56' (otherwise keep the search tier's FullPoolBelief)
  ```
  **Without these hunks the live bundle silently runs the C56 belief.**
- `bot/live/translate.py` (ae3f6b0c5 vocab completion from runtime templates, e327eca93 observed-body projection) and
  `bot/live/levels.py` (b2676684f attachment graphs) are the LIVE LEAD's own changes, not required by the full-pool bot.
  Deploy whatever version the LIVE LEAD's translator plan calls for.

**Added, not in the snapshot (17)**

| path | sha256 |
|---|---|
| bot/__init__.py | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| bot/cards/__init__.py | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| bot/cards/fc_cut.py | 9ab2bc406db4a7b09a9858703e32518bbbb9fd057298e6b23f84ce6554c916fd |
| bot/cards/proxy_table.py | 72c3a4a964b5454a5ceacef9eb1a0785538c54b28d9c8dce02b15dfe7c1e52f3 |
| bot/cards/scope.py | f116b76ab4079a1cbe208e7220587cf001c2966156ec939517780c2bb53dde98 |
| bot/eval/__init__.py | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| bot/eval/headline.py | d264eaf3e68b65e5a32567ac67c49e08c85c52852c7a6df8daacb05ebd38598e |
| bot/exit/__init__.py | 0f7e111ff03a1874ba65e3655c4e0f488c9323a4fdaba4879259f826e5e49013 |
| bot/exit/student.py | e4c16637ce35d5b8fd2dd64050c9c9af24abf4b2e21c363f9b2eca1948926da0 |
| bot/fullpool/__init__.py | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| bot/fullpool/banks.py | 032b91b422b1872a07206a32608c6d0adc8097edb8acd8da0f47301dc1294ac1 |
| bot/fullpool/belief.py | 3d1e62a2d87aa8bfc41d33e848aff3fdd88d2be9e072b86b0fc3a33358348e6b |
| bot/fullpool/cards.py | 8d62b355fed6072db5c3dd996372bd92ccbbe342eca669bbf7f2827a8cf342cc |
| bot/fullpool/decks.py | 35dc25b15792e04b1a39357e0669ccdaeeeb2cb9c5d017bec6de5a11791459e8 |
| bot/fullpool/extend.py | 96d5870e61f40591bf21f3fd3f800ed1f96584ccde3807cdc425a5aa92a26c36 |
| bot/fullpool/models.py | a624bffdf58d2d844c26e0debb5c8a3dc1123aef1a874058372b8433bb3d56d4 |
| bot/search/reserve.py | 4c29fabbe316b35c2bbeebc069e3a6b7c1e3c6462f293f2e88b0c2bf37246687 |

**Unchanged closure files (8):** bot/live/__init__.py, bot/players/__init__.py, bot/players/base.py, bot/players/policy.py, bot/players/variants.py, bot/search/__init__.py, bot/search/candidates.py, bot/search/oppmodel.py.

**Snapshot files that differ at main but are outside the bundle closure (6):**
bot/live/births.py, bot/players/royalesim_match.py, bot/players/royalesim_vocab.py, bot/search/lopp_record.py, bot/search/lopp_time.py, bot/search/lopp_train.py. They are not needed by the bundle player; their upgrade is
the LIVE LEAD's call.

**Data files the player reads (sha-pinned by the code)**

| path | sha256 |
|---|---|
| reports/bot/fullpool/ab/opponent-decks-20261016.jsonl | 3a7c4e78afe1ade71a156acc377a779809366bdf8fe6fda87d09a801e2dffcd3 |
| reports/bot/fullpool/freq/arena-card-freq-b53b02a1fde4.json | b53b02a1fde471a86bafdf0d63ed4b7fcd76623b7456a2cbf0e45e7aa489b674 |
| reports/live/loop/ARENA-CARDS.md | 75a8a0ab6696fe3a5cdc27139d830adb4d0bbae53184b073153242eb64f4a0c6 |
| reports/live/loop/arena-card-freq.json | b53b02a1fde471a86bafdf0d63ed4b7fcd76623b7456a2cbf0e45e7aa489b674 |

`reports/bot/fullpool/ab/opponent-decks-20261016.jsonl` is only read by sim cases (bank e16bl), never by live play.
The other three feed the open-world belief's deck prior.

## Model files and sidecars

Masters are on the fleet under `/mpac/sdicks02/jobs/clasher/bot-fullpool/` (01/03/04/08).

| file | size (bytes) | sha256 |
|---|---|---|
| lopp-fp/k1a1.npz | 2367390 | 477590389c0d6906c5b3b80c131f910dabd286bfde21c990d50b460c54c5a8d3 |
| lopp-fp/k1a1.json | 3265 | 927ac48fe133168e0f05b12ce9694e4f981a353e4af57da881658e741a211c75 |
| fits/f1a2/step-001200.pt | 39661201 | 0c03f79ffe5aa19e2310f9a959c96c98eb98678fe4c1f10352f9eb9566b58736 |
| fits/f1a2/step-001200.pt.calibration.json | 296 | e805d498ae693c7d66ecbf5ae0d4749fc817e7abd7a1cb92effec6dcca6a4145 |
| ext/R3a-fp.pt | 36134283 | ce7b0ea49e67671dc82f3584c3eb68c9891a47899a8d8f83a0519a960df8cbc2 |
| ext/R3a-fp.pt.fullpool.json | 16544 | e9293b8e414fa4cab039182efcc5f12558b46c17290a5417b5c3306adaa830ad |
| ext/main02-fp.pt | 36464206 | 69313468f7439f9e7d0356ff92f4f2d9463e4bb5c10c32e360a0c1a1695cf0b9 |
| ext/main02-fp.pt.fullpool.json | 16550 | 99445ceb99cfe9acf0cf4c010ebb949f3464b4b414bcc7085269eeeaa5b0a213 |
| ext/rl5-v10-fp.pt | 19826547 | a6565cabe728e8842405cb7a9e040970893566596b11980ad7ddf867df3dddcc |
| ext/rl5-v10-fp.pt.calibration.json | 141 | 4a07033d9ee54b733170b974e07dd1da7ca395c609713a6df6f5af717e93f5e3 |
| ext/rl5-v10-fp.pt.fullpool.json | 16557 | 54fb366ebfff3cade90bf1c0c34a8e1a835458610368a2af38b089a32bed6e97 |

Each `*.fullpool.json` receipt must sit next to its checkpoint. BOT_FULLPOOL_POLICIES refuses a checkpoint whose receipt
does not name the pinned source (R3a 37509a43…, v1 d77005d5…).

## Environment (both players; the -res treatment differs only in the name suffix)

```
CLASHER_BOT_RUNTIME=<live16402b-r3 root>   CLASHER_DELAY_NATIVE_DIR=<root>/native   CLASHER_BOT_RUNTIME_PINS=live16402b-r3
PYTHONHASHSEED=0    NUMPY_MADVISE_HUGEPAGE=0
CLASHER_LOPP_MODELS=<dir containing k1a1.npz>              # model token -mk1a1
BOT_FULLPOOL_POLICIES=v1=<dir>/main02-fp.pt,R3a=<dir>/R3a-fp.pt
BOT_BELIEF_PRIOR=fullpool:11433651:freq=b53b02a1fde4
CLASHER_LIVE_FAST=student:<dir>/step-001200.pt             # f1a2; threshold 0.6444 read from step-001200.pt.calibration.json
```

- **PYTHONHASHSEED=0 is mandatory.** The rollout net's C56 alias tokens depend on it.
- **reserve.py and the `res` token are included.** bot/search/reserve.py is in the added list. lopp.py and lopp_fast.py
  carry the `res` hook, active only with `-res`.
- **Proof** (LIVE-AB1, 10 cases): without the token, command hashes are identical to the pre-res code, 10/10, for
  K4L-R-gs-mk1a1 and the fast path K4L-R-gs-rw-fc-t2-mk1a1. With `-res`, the reserve fires in 10/10 games (penalty > 0
  on 4600 of 12560 scored keys).

## Fast tier f1a2: C56 regression check DONE (pass)

HEADLINE x4s C56 decks, 300 paired cases each vs R3a and v1, live16402b-r3, 1800 games, 0 errors:
- f1a2 vs the extended RL r5 v10 (rl5-v10-fp@0.5375): pooled **+0.001 [−0.037, +0.037]** (R3a −0.005, v1 +0.007).
  There is no loss beyond 0.02, so f1a2 ships as the fast tier.
- Its full-pool gain, +0.039 [−0.003, +0.082] on FP-DEV, is on the dev bank, not a fresh one.
- The gate's sim twins do not use a fast tier, so the live A/B is f1a2's first live-config test.
- Fallback: `student:<dir>/rl5-v10-fp.pt@0.5375`.

## Timing (fleet reference; the Mac gate is cutoff ≤ 10% and p95 ≤ 60 ms, measured on the Mac)

lopp_time on 03, 5 pinned physical cores per arm, LIVE-AB1 cases vs R3a, live16402b-r3:

| arm | games / decisions | wall p50/p95/p99 ms | cutoff hit | default |
|---|---|---|---|---|
| base C56 live `…w200-t4-p4` | 5 / 678 | 83/190/194 | 4.4% | 1.9% |
| `…-mk1a1` | 6 / 807 | 78/184/193 | 3.5% | 2.1% |
| `…-mk1a1-res` | 8 / 845 | 85/173/200 | 2.7% | 1.7% |

The full-pool path is not slower. Its belief costs 2.3 ms per decision against 3.8 ms for the C56 LiveBelief. The 65%
smoke result was an unpinned run on a loaded host.

## Equivalence on a copy of the Mac tree

The copy is the snapshot's 69 git-reproducible files (commit f0eabd1d), plus exactly the changed and added files above
and the data files. Deterministic twins were run against R3a on LIVE-AB1 cases 0–9, on the copy and on main
2fa5d496e59a: see the section below (filled in when the runs finish).


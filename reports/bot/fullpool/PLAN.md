# Full-pool generation and retrain plan (BOT LEAD full-pool track, exploration)

Written 2026-10-16 ~02:40Z. Training runtime: **live16402 on r1-cards2** (card scope, new-card mechanics, 16.402
stats), per the BOT LEAD's decision, so the retrained nets match live balance. CPU first: the 04/08 GPUs are with
the LIVE LEAD for ~12–24 h, so GPU fits are queued. Results are reported as they come; nothing is sealed.
Numbers marked "est." are my estimates; the rest are measured or cited (EP = reports/bot/exit/PROGRESS.md,
LP = reports/bot/learned-opponent/PROGRESS.md).

## 0. Facts this plan rests on

- **ExIt plateaued on C56.** it5s2 (1.69 M labels, 4,498 games) was a local optimum: it7–it9 all null (EP:618-622,
  805-819, 1046-1056). Labels that score the student's own proposals were the big gain (EP:133). Soft targets are
  softmax(scores/0.003) (EP:845-859). The teacher choice between K4C-r16 and K4S labels made no difference (EP:686).
- **RL broke the plateau.** r5 v10: +0.059 [+0.031, +0.087] vs it5s2 on F9 (EP:1097). Later snapshots random-walk:
  v30 −0.004 on F10 (EP:1403-1408). RL claims hold only on fresh banks. The learner ran on the 01 GPU, 160 games
  per update, about 6–7 min per update.
- **Full-pool cold start.** In the extended nets, 90 policy rows and 65 K4L rows are proxy copies. Nothing has
  been trained on non-C56 states. Under live16402, 13/56 C56 cards and 22/66 new cards also changed stats, and
  live16402 v1 K4L was −0.025 [−0.063, +0.013] vs the current pin.
- **Costs.**
  - Policy game: 50–55 CPU s (rl/DESIGN.md:61).
  - K4C-r16 game: ≈2× a policy game.
  - K4L-R-gs game: 39 CPU s uncontended, 90 CPU s under load (LP:188, EP:864).
  - ExIt labels: ≈375 per game with a K4S/K4C teacher (EP:237) and 233 per game with K4L (EP:864).
  - K4L CPU fit: 2.4 M rows in 22 min (LP:234-250).
  - Student GPU fit: ≈4 h per 6000 steps for the 6-layer model (EP:983).
- **Compute now.** At most 16 live python processes per host for me on 03/04/08 (LIVE LEAD allocation). 03 has no
  working GPU. When the LIVE LEAD releases CPU, the fleet cap is ~60–80 per host.

## 1. Student: ExIt first, then RL

**Why ExIt first.** The new cards need dense supervision. A search teacher labels every searched root in a game
holding new cards (≈375 labels per game), whereas RL gets one outcome per game spread over ~65 new tokens. ExIt
on C56 plateaued, but the plateau was about squeezing more out of the same 56 cards. Here the gap is cards the
student has never been trained on. RL then picks up where ExIt stops, as it did on C56.

**G1, ExIt round 1 labels.**

```
BOT_FULLPOOL_POLICIES='v1=<ext>/main02-fp.pt,R3a=<ext>/R3a-fp.pt' CLASHER_BOT_RUNTIME_PINS=live16402 ...
python -m bot.exit.generate --out G1 --student student:<ext>/rl5-v10-fp.pt@0.5375 --teacher K4C-r16 \
    --pool R3a,v1,self --games 4000 --workers <=16/host --base 2613058991490864 \
    --decks fullpool:11433651:freq=b53b02a1fde4      # add ,own=c56 if R.bots is still C56
```

- **Teacher: K4C-r16** for G1. Its rollout opponents are the native scripted styles, which play the real new cards
  under the widened meta. K4L's learned opponent is still a proxy copy and was −0.025 under live16402. **K4L-R-gs**
  becomes the G2 teacher once the K4L net is retrained (section 2). The K4C proposer is rt.STUDENT = R3a-fp, via
  BOT_FULLPOOL_POLICIES.
- **Volume:** 4,000 games, about 1.5 M labels est. This matches it5full, the corpus that produced it5s2. Shard by
  host with `--start`: 03 at 0, 04 at 1,000,000, 08 at 2,000,000.
- **Cost:** a measured 1-game dry run (08, 02:35Z) took 267 CPU s for a full 6,001-tick game and gave 457 labels.
  An average game is about 200 CPU s est., so 4,000 games ≈ 220 CPU-h. At 48 processes (3 × 16) that is ~4.6 h; at
  3 × 60, ~1.2 h.

**F1, ExIt round 1 fit.**

```
python -m bot.exit.train --init <ext>/rl5-v10-fp.pt --new G1pack --old <C56 K4C corpus, e.g. kc7a> --new-ratio 1.0 \
    --temperature 0.003 --lr 3e-5 --steps 1500 --batch 4096 --device cpu|cuda
```

- Initialised from rl5-v10-fp. The C56 corpus is mixed 1:1 as anti-forgetting, since C56 states dominate live.
- Device: CPU if the timing probe allows (Sol slice S3: steps/min with 32 threads on 08). If it can't do 1500 steps
  in about 3 h, queue on the first free GPU.
- Lower lr than the from-scratch fits (1e-4), because this fine-tunes an RL-tuned net.
- Variants, cheap to run as soon as F1 works: new-ratio 2.0, and an arm without the C56 corpus.

**R11, RL round on the full pool.** Needs a GPU learner; actors run on CPU.
- Init: the F1 winner, or rl5-v10-fp if F1 fails its gate.
- Actors: `BOT_RL_DECKS=fullpool:11433651:freq=b53b02a1fde4` with the r5 league (v1 .15 / R3a .35 / it5s2 .30 / self
  .15 / K4C-r16 .05), opponents extended. League games vs K4C-r16 get a C56 opponent deck automatically until
  R.bots is widened.
- Critic: re-pretrain (`bot.rl.critic_pretrain`) on G1 outcomes plus the first actor block before the learner
  starts. r5's critic only saw C56 states.
- r5 hyperparameters (lr 3e-5, KL 0.01, κ 0.1, T 0.1). Snapshots every 10 updates.
- Selection on FP-DEV; the claim on a fresh bank drawn for it (FP-FRESH2), because RL snapshot selection inflates
  the bank it is selected on.

**Gates.** Paired cases, 300 per opponent.
- F1 must be at least rl5-v10-fp on FP-DEV, both decks full-pool, vs R3a-fp / v1-fp / it5s2.
- F1 must not lose more than 0.02 on C56-REG (HEADLINE x4s, r1-total) vs rl5 v10.
- If F1 fails both, R11 starts from rl5-v10-fp. Claims go on FP-FRESH1 (both decks full) and FPO-FRESH1 (live-like),
  each reported when it lands.

## 2. K4L rollout opponent: record, refit, screen

**K1, recording.**

```
python -m bot.search.lopp_record --out K1 --candidate K4C-r16 --opponents R3a,v1,student:<ext>/rl5-v10-fp.pt@0.5375 \
    --games 800 --decks fullpool:11433651:freq=b53b02a1fde4[,own=c56] --base <FP-TRAIN1 + 50,000,000> --workers <=16/host
```

- 800 cases × 3 opponents = 2,400 games, about 1.4 M rows est. (the original: 1,200 games, 695 k rows). Run under
  live16402 with extended opponents (BOT_FULLPOOL_POLICIES). The recorded seat always holds a full-pool deck.
- Cost: a measured 1-game dry run took 146 CPU s for 6,001 ticks and gave 859 rows. Average ≈110 CPU s est., so
  2,400 games ≈ 75 CPU-h, about 1.6 h at 48 processes. It runs in parallel with G1, sharing the per-host cap.
- After F1, record ~800 more games with the F1 student as opponent (on-policy rows, the pool2 recipe).

**KF1, refit (CPU, ~30 min).**
- (a) `lopp_train --init poolfp.npz` fine-tune on K1 ∪ the old pool corpus (keeps the vocab order).
- (b) A fresh 122-vocab fit on the same data.
- Keep 256×2: pool2L (512×3) was no better and ~3× the forward cost (LP:276).

**Screen.**
- K4L-R-gs-m<new> vs K4L-R-gs-mpoolfp on FPO-DEV (our deck C56) and FP-DEV (once R.bots is widened), 300 cases
  vs R3a-fp and v1-fp.
- Claim on FPO-FRESH1. The winner becomes the G2 teacher and the live K4L candidate (handed to the LIVE LEAD).

## 3. Opponent model and belief

- **Belief:** the full-pool sampler prior (bot/fullpool/belief.py) is selected automatically with full-pool decks.
  No training is needed. Check it in G1: count FullPoolBelief rebuilds per game (small logging patch with G1).
- **Opponent model:** oppmodel style weights (K4O) were tuned on C56 opponents. Re-screen the 3-style weights on
  FP-DEV only if K4L stays below K4C on the full pool. Low priority.

## 4. Compute per host, CPU first

| phase | 03 (no GPU) | 04 | 08 | wall at 16 / host | wall at ~60 / host |
|---|---|---|---|---|---|
| G1 labels, 4,000 games | 16 | 16 | 16 | ~4.6 h | ~1.2 h |
| K1 recording, 2,400 games | shares the cap with G1 | shares | shares | +1.6 h | +30 min |
| baseline + screen evals (policy, ~1,800 games) | 8 | 8 | 8 | ~35 min per screen | ~10 min |
| K4L screens (~1,200 K4L games) | 8 | 8 | 8 | ~40 min | ~12 min |
| F1 student fit | – | – | CPU 32 threads, or GPU when free | probe first (S3) | – |
| KF1 K4L fit | CPU, 16 threads | – | – | ~30 min | – |
| R11 RL | actors 16 | actors 16 | learner GPU + actors | GPU-gated | – |

GPU queue, in order: F1 (if CPU is too slow), then critic pretrain, then the R11 learner. Nothing goes on 01.

## 5. Order of work and Sol slices

Opus keeps the design and code; Sol sub-workers run the slices.

1. **S1 (running):** smoke rerun on r1-cards1 when it lands on main, including k4lf/genf (search seats on
   full-pool decks: the R.bots widening check).
2. **S3 (now, light):** CPU-fit timing probe on 08. Pack smoke1/gen shards, then `bot.exit.train --device cpu
   --steps 30 --batch 512` with 32 threads; report steps/min.
3. **On live16402:**
   - **S2:** dump meta tokens under live16402. If they differ from r1-cards1-meta.json, I re-extend the K4L nets.
     Then run `PINS=live16402 smoke.sh`.
   - **S4:** FP-DEV and FPO-DEV baselines: rl5-v10-fp, it5s2, R3a-fp, K4L-R-gs-mpoolfp, K4C-r16.
4. **S5:** launch and babysit G1 and K1 (shards and caps as above; resume on failure).
5. **Opus:** F1 and KF1 fits plus the G1 belief logging patch. **S6:** screens and claims.
6. **When GPUs return, Opus:** critic pretrain, then R11. **S7:** snapshot screening.

**Code still needed (Opus, before G1):**
- The belief-rebuild counter in generate rows.
- `--opponents` for extended policies in lopp_record already works via BOT_FULLPOOL_POLICIES; I'll check that
  extended `student:` opponents record correctly.
- If live16402 changes meta tokens: re-extend the K4L nets.

## 6. GO runbook (on the CARD LEAD's ping; all scripts in bot/fullpool/run/, committed)

Dry run, 2026-10-16 02:35–02:45Z, on 08 with the r1-cards1 dev root, OWN=c56: preflight **PASS**. Meta tokens were
identical to the dump, the three receipts verified, the G1 game had 0 errors (457 labels, belief_rebuilds 1), and
the K1 game had 0 errors (859 rows).

1. **05:** rebase on origin/main once the pin is merged, then `bot/fullpool/run/stage.sh 03 04 08`. This prints
   the tree path T=$J/repo-<sha12>.
2. **Each host, in T:**

   ```
   ROOT=<live16402 root> bot/exit/cpu_job.sh 2 bot/fullpool/run/preflight.sh $J/preflight-<sha12>
   ```

   - Use OWN=full, since R.bots is widened in this release; OWN=c56 is the fallback.
   - It must print PREFLIGHT PASS. If the meta tokens differ, re-extend the K4L nets before K1/K4L work. G1 does not
     depend on them.
3. **G1:** one shard per host, SHARD 0/1/2 = 03/04/08, GAMES = 1334/1333/1333.

   ```
   ROOT=… W=11 bot/detach.sh $J/g1-x<h>.log $J/g1-x<h>.receipt.json bot/exit/cpu_job.sh 12 bot/fullpool/run/g1.sh <SHARD> <GAMES>
   ```

4. **K1** on the same hosts, within the remaining cap of 16: SHARD 0/1/2 with CASES 267.

   ```
   ROOT=… W=3 bot/detach.sh $J/k1-x<h>.log $J/k1-x<h>.receipt.json bot/exit/cpu_job.sh 4 bot/fullpool/run/k1.sh <SHARD> 267
   ```

   When the LIVE LEAD frees CPU, relaunch the same commands with larger W. They are resumable; finished games are
   skipped.

   **Sizing at launch (BOT LEAD, 10-16):**
   - Count the host's live python first: `ps -u sdicks02 -o stat=,args= | grep -v '^Z' | grep -c '[p]ython'`.
   - On 04/08, if it is under 60, use up to 40 workers for G1+K1: G1 W=30 (cpu_job 31) and K1 W=9 (cpu_job 10).
     Otherwise use the 16 split above.
   - Keep 03 at 16 or fewer (G1 W=11 + K1 W=3).
   - Always go through cpu_job.sh, so the 105 cap holds and new work waits when the LIVE LEAD ramps up.
   - Report each launch with the host, workers, PGID (from the detach receipt) and the time from `date -u`.
   - With uneven workers, shard the games in proportion: 03 gets SHARD 0 with about 1/5 of the games, 04 and 08
     about 2/5 each, e.g. GAMES 800/1600/1600 and K1 CASES 160/320/320. Shards are disjoint by --start, so a later
     top-up on any host only needs a new SHARD index (3, 4, …).
5. **Monitoring:** the games-*.jsonl rows (errors, belief_rebuilds, labelled) and `$J/G1/STOP` to stop. That's a
   Sol slice.
6. **Fits:**
   - K4L: once K1 reaches about 1,500 games, rsync the rec-*.jsonl.gz files to 03 and run fit_kf1.sh for ARM=a and
     ARM=b (CPU).
   - Student: once G1 is done (or about 2,500 games for an early F1), run pack_g1.sh on each host, rsync the packs
     to the fit host, then fit_f1.sh on CPU if the S3 probe allows, otherwise DEVICE=cuda when a GPU is handed back.

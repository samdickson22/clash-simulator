# NS2 no-search confirmation — pre-registration

Registered before any NS2 game. Fresh BASE **1587927595246112**, drawn at **Sat Oct 17 22:27:40 UTC 2026** using `python3 -c "import os;print(int.from_bytes(os.urandom(6),'big')<<4)"`; time from `date -u`. Source snapshot current origin/main **add0b9844da8efa98f6f7f4aa7afd077d391e425**. NS1 and NS2 banks are disjoint; no NS1 games enter NS2 estimates. Work directory on08: `/mpac/sdicks02/jobs/clasher/bot-ns2-20261017/`.

## Fixed design and primary outcome

Daily `python -m bot.eval.headline`, RoyaleSim **0.1.34 /16.402**, `--engine rsim16402 --levels max --decks x4s`: every card and tower L16 on both sides; C56 x4s deck/seat scheduling; 27-tick command lag, abilities off. Cases **0–299**, identical BASE/index/seat/decks across four arms and three opponents: **3,600 scored games**. Opponents **R3a, v1, K4C-r16**. Literal strong K4C-r16 stays separate and is never included in a pooled result. Separate smoke indices300–301: two games per arm/opponent,24 games, zero errors required before scored games; smoke never enters estimates.

**ACCOUNT row skipped:** this HEADLINE revision exposes only `--levels none|max`, with symmetric all-16 vectors; it does not accept per-side account card/tower vectors. Underlying simulator support and other deck-search drivers do not establish support in HEADLINE. No substitute harness or level implementation is introduced.

| arm | fixed player specification | decoding |
|---|---|---|
|a|`K4L-R-gs-mk1a1-res-wint`|exact NS1 live-search serial twin; same rl5 rollout pin|
|c|`student:/mpac/sdicks02/jobs/clasher/bot-nosearch-20261017/strong/policy-00010.pt@0.5375`|rl5-v10 alone, threshold0.5375; greedy legal action, 5-tick cadence|
|e|`student:/mpac/sdicks02/jobs/clasher/bot-fullpool/fits/f1a2/step-001200.pt@0.5375`|f1a2 alone, threshold0.5375; greedy legal action, 5-tick cadence|
|f|`v1`|stock natural sampling **temperature1.0**, sampled gate/card/tile; seed `BASE+index+271828+seat`|

f1a2 path is `FAST` in `reports/bot/deckopt2/harness/fullpool_eval.py`; SHA256 on both04/08 **0c03f79ffe5aa19e2310f9a959c96c98eb98678fe4c1f10352f9eb9566b58736** (commands checked at22:27:19/20UTC). rl5-v10 SHA256 **e188e2aeb9a6828ffbef237aa327e495eb39ca5f8322ae18aa70c63cb81bba19**, retained verified NS1/HEADLINE bytes. f1a2 will be copied unchanged into the NS2 job and hashed before use, preventing an in-place training update. The actual e spec will therefore use `$JOB/models/f1a2-step-001200.pt@0.5375`, with identical bytes. Arm(a) remains the exact NS1 rl5-pinned search for the confirmation; changing its fast tier to f1a2 would change the primary comparison. K4C-r16 is the literal R3a-default CandidateSearchPlayer, as in NS1, not the different LIVE-K4CW-r16 alias.

**Single primary:** mean paired score difference **(a)−(c)>0 against K4C-r16**; win1, draw0.5, loss0. Primary evidence criterion: lower endpoint of its two-sided bootstrap95%CI exceeds0. Fixed n300, no early stopping, no adaptive arm/case selection. Failure to clear0 is inconclusive, not equivalence or proof that search has no value.

Secondary: per-arm/opponent score with95%CI; paired a−c, a−e and a−f per opponent. Also report equal-weight **R3a+v1-only pooled** contrasts a−e/a−f (and a−c for context). Strong row never pooled. Resample matched case indices jointly across arms; pooled estimates resample whole index clusters across both weak opponents, preserving shared bank dependence.4000 bootstrap draws, Python Random(seed0), sorted[100]/sorted[3899], as HEADLINE. Secondary intervals descriptive, no multiplicity-adjusted superiority claims.

Precision caveat registered in advance: tripling NS1 n narrows typical intervals by roughly sqrt(3), but a three-point effect is not guaranteed to resolve. Based on NS1 strong paired interval, anticipated half-width is about7pp at n300; approximate80%-power detectable advantage is about10pp. This is a fixed300-case confirmation requested by BOT LEAD, not an80%-power design for3pp.

## Diagnostics, runtime and scheduling

Report reaction p50/p90 and undefended share per arm/opponent, CPU-ms/decision for every arm. Preserve official HEADLINE reaction fields: accepted enemy play to next decision with truthy stats, including WAIT; pure policies have no such events, hence n/a. Add a clearly labelled **enemy accepted play → next own accepted play** reaction diagnostic for **all four arms**, using the existing accepted play log (l16_report.reaction definition). It is a cadence statistic, not causal defence latency. Store per-game quantiles and event counts, report medians of game quantiles and coverage. Never substitute that number for the official search-decision reaction. Undefended share = total no_def_before_contact / qualifying Giant pushes; denominator0 reported n/a. CPU-ms/decision =1000×sum(candidate timing.cpu)/sum(candidate timing.decisions), includes packet/reservation preparation and WAIT, excludes simulation advance and passive observer. Output-only job-source additions retain candidate timing and the supplemental reaction summaries; no player decisions or weights changed.

Same full-pool runtime/env as NS1 / HEADLINE-MAX-20261017b: ROOT `/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3`, PINS `live16402b-r3`, `source bot/fullpool/run/env.sh`, extended v1/R3a and full-pool rollout models; `BOT_BELIEF_PRIOR=fullpool:11433651:freq=b53b02a1fde4`; `CLASHER_LIVE_FAST=student:/mpac/sdicks02/jobs/clasher/bot-nosearch-20261017/strong/policy-00010.pt@0.5375`. `PYTHONHASHSEED=0`, `NUMPY_MADVISE_HUGEPAGE=0`, OMP/MKL/OpenBLAS/Numexpr/Torch/Rayon threads1. Writable NUMBA_CACHE_DIR under NS2 job. Source archived from the registered main commit, never the shared dirty checkout; record runtime/source/model hashes before games.

Hosts **04/08 only**, maximum24 NS2 gameworkers total, detached setsid blocks exclusively through `/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh N nice -n 15 ...`. Initial deployment08 only (04 lab-user cap70;08 cap110). Strict queue below active deck-search/deckopt3, WINT-ACC1 (`bot-livediag/wa1`) and LV2; no game admission while those higher-priority CPU jobs are active, and pause only our verified PGIDs if they resume. NS2 admission precedes lower-priority PT1/HZ1/K1 work insofar as our own scheduling is controllable; do not signal or renice foreign jobs. Admission additionally leaves load headroom, and our own load guard pauses blocks below the ceiling. No foreign jobs/claims touched.04, if later used, requires lab-user load<=70. Never contact other fleet hosts. Checkpoint parsing/preflight is not a game.

ETA: approximately **6–10 hours of admitted wall time** at16–24 workers, subject to priority release and load caps; queue wait is additional and cannot yet be bounded.24-game smoke first, then scored results reported as they land without sealing. This registration precedes every NS2 game; game count at registration **0**. No data/checkpoints/game bytes committed.

## Handoff notes — standing communication rule

Sam’s standing rule, effective immediately (BOT LEAD instruction received Sat Oct 17 22:49:59 UTC 2026): **Always steer, never queue** when messaging any thread or agent. Every `t3_thread_send` must use `mode: "steer"`; if it returns `thread_not_sendable` because the target is idle, resend the same text with `mode: "auto"`. Never use `mode: "queue"`.

Sam’s communication rule (BOT LEAD instruction received Sat Oct 17 23:16:59 UTC 2026): **Say less.** No acknowledgments or “started / queued” messages. Report only results, failures and decisions; put routine status in `reports/bot/NOSEARCH-20261017.md`. The steer/auto rule above remains in force; never use queue.

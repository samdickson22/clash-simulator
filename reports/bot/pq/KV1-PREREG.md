# KV1: v2-distilled rollout opponent (kv2) on top of RF. Pre-registration (play-quality owner, exploration)

Registered before any KV1 game. BASE **2155110047579728**, drawn on 127x04 at 2026-10-18T07:49:36Z with
`int.from_bytes(os.urandom(6),'big')<<4` (check_bank: disjoint).

## Change
Token `mkv2` (live K4L name; overrides the live `mk1a1`): the learned rollout opponent inside K4L's scorer is kv2 instead
of k1a1. kv2 = k1a1 fine-tuned on 979,776 decisions of the HP1 v2 human policy @ τ* as the opponent in 1,500 full-pool
games (Sol worker; bank 1244050996608576, tree 4511f3b45, report /mpac/sdicks02/jobs/clasher/bot-pq/kv2/REPORT.json;
recorded at L11, the recorder has no level option). On 150 held-out games of v2 decisions: gate AUC 0.869 vs k1a1 0.770,
card top-1 0.742 vs 0.549, tile within-2 0.759 vs 0.501, card and tile 0.552 vs 0.264. sha256: kv2.npz 0bb03533…,
k1a1.npz 477590389… (the copy in /mpac/sdicks02/jobs/clasher/bot-pq/models/lopp is byte-identical to lopp-fp's).
Same architecture and cost as k1a1. Why: Sam's open complaint is elixir banking (the bot meets an enemy Hog at 3.2 elixir,
humans at ~6). A rollout opponent that punishes like a human is the remaining fair search input; leaf elixir weights and
learned leaves are settled nulls.

## Design
As RF1/LP2: live Hog deck, pool v3.2 53 King-9 rows, vocab-full, rows L16 and account (same account levels), 200 paired
cases per opponent. Opponents: LIVE-K4CW-r16-fp (primary), R3a, and **HPv2** (the v2 human policy @ τ* alone,
l16_cadence opponent `HPv2`; a human-like row, since live opponents are humans). Arms `res-lb-RF-wintp` (shipped
baseline) and `res-lb-RF-mkv2-wintp`; both arms read CLASHER_LOPP_MODELS=/mpac/sdicks02/jobs/clasher/bot-pq/models/lopp
(BOT_PQ_LOPP_MODELS). 2400 games, 04/08.

## Prediction and ship rule
Prediction: kv2 − k1a1 > 0 vs HPv2 and ≥ 0 vs K4CW-fp. Ship: vs K4CW-fp pooled over both rows lower 95% bound ≥ 0 AND vs
HPv2 pooled point > 0; neither K4CW row below −0.02; Hog-crossing elixir and barrel answers not worse beyond ~2 SE. Readout
as RF1 (same scorer), per opponent, plus CPU-ms per decision.

# Gate (c): standalone imitation policy — DRAFT

Source: reports/strategy_council_20260928/imitation/DESIGN.md §5.3.
Checkpoint SHA256: **TBD** (T5 dev-selected v1-main).
Freeze this document, checkpoint and comparator hashes, adapter/model/engine/
gamedata/deck inputs, schedules and seed-audit receipts before any gate game.
Random/synthetic checkpoints are plumbing only; no strength or outcome claims.

## Policies and timing

v1-main samples gate -> card -> tile stochastically at T=1 once every five
50-ms ticks (250 ms), using the gate hazard as trained. Do not multiply the
hazard, fit an evaluation temperature, threshold probabilities or use argmax.
The auxiliary 13-bin intent hazard is not the action gate and does not schedule
plays. D1 is shared with search and built only from public events/own knowledge.
Comparators are v7r4h s2902 policy_decisions_001000000.pt and
human-bc-natural-seed2903.pt, with their native stochastic policies.

## Fixed game counts and protocols

1. P16 scripts: exactly human-prior-p16/scripts/run_eval.py's six cells
   (balanced/pressure/defense × holdout/hog26), nominal levels, training opponent
   decks, decision interval 5, max ticks 6001. Two fresh blocks × six cells ×
   32 games = 384 games PER policy, all three policies on identical world seeds,
   deck draws and candidate seats. Total 1,152 games. Alternate candidate seat;
   each 32-game cell contains 16 world pairs, with the candidate's role deck
   following it across seats, as in the P16 script protocol.
2. Head-to-head: 128 P16 seeded worlds × two seat/controller swaps = 256 games
   against s2902 1M, on the P16 Python engine. Physical world decks remain fixed
   across swaps, so both controllers use each deck once. First 64 worlds use
   development holdout vs training decks, next 64 hog26 vs training.
   **Known asymmetry:** v1 uses the v5 public mask with the game's 3×3 tower
   footprint; s2902 uses its own v4 mask. Preserve and record both per game.
   Do not silently upgrade s2902 to v5 or downgrade v1 to v4.
3. C56 scripts: 384 games = three styles ×128, eval-role C56 own decks,
   training-role C56 opponent decks, 64 world/seat pairs per style. Descriptive
   only: future anchored PPO baseline and fallback-adequacy number. No bar.

Grand total: 1,792 games. Report all protocols, even if another fails.

## Seed plan and audit

Proposed P16 block bases: 2,917,600,001 and 3,017,600,001. Per run_eval.py,
cell base = block base + 1,000,003*(role_index*6 + style_index +12);
world = cell base +1009*pair_index (0..15). Existing P16 deck RNG is
world+7919; legacy policy torch seed world+271828, opponent RNG world+91117.
The imitation CPU generator uses world+271828+physical seat and resets each game.
Head-to-head worlds = 3,117,600,001+1009*i (0..127), deck RNG world+7919.
C56 worlds = 3,217,600,001+1009*i (0..191); each style owns 64 worlds.
Schedule RNG = 3,217,590,001; bootstrap RNG = 3,217,590,002.

Audit all these expanded seeds against every prior receipt, including partial
and failed experiments, on authorized hosts 127x01/03/04/05/08 and available
historical inventories. Include JSON/JSONL/gzip, NPZ seeds/metadata, schedules,
logs and source seed formulas/ranges. Hash the scanned inventory; preserve every
match, parsing error and missing inventory. Exclude only this prospective gate's
own draft/registration and mirrors. Fail closed on overlap or incomplete audit.
Also compare to gate (b). On overlap move the complete namespace by 100,000,000
and repeat before playing; freeze exact schedules plus audit content hashes.
Proposed numbers are not a completed freshness audit. Local-only scans cannot
certify the fleet history. Synthetic smoke namespaces are excluded from gates.

## Analysis, bars and decisions

P16 scripts: binary win indicators (draws count as non-wins) paired by block,
role, style, world and seat. Report W/D/L, win rates and score (W+.5D)/N.
Exact two-sided McNemar p= min(1, 2*BinomialCDF(min(b,c); b+c,.5)), with p=1
when no discordant pairs. Bar: v1 win rate > human-bc-natural AND p<0.05,
pooled across all 384 games. No multiple variant selection or per-cell bar.
Report v1–s2902 win-rate difference and a two-sided 95% Newcombe Wilson-score
interval using the established human-prior-p16/scripts/compare.py implementation;
no bar for this comparison. McNemar uses paired discordances; report per-cell
descriptive results too.

Head-to-head: score W+.5D averaged over each controller-swap pair, then over
128 worlds; two-sided 95% paired-world percentile bootstrap, 10,000 resamples.
LB >0.50 -> v1 replaces s2902 as P16 reference policy. Otherwise s2902 stays.
Do not apply the search gate's .53 point bar here.
C56: W/D/L and score overall/per style, descriptive paired-world bootstrap;
no acceptance bar and no tuning based on these games.

No optional stopping or outcome-based reruns. Technical interruptions replay
exact seeds/configuration from the beginning without inspecting the outcome;
retain partial artifacts and reason. Slow decisions, invalid actions and losses
are results, not technical exclusions. Report every failed gate. Adapter smoke
requires four complete games per route with a synthetic checkpoint; those games
never enter this registration or its analysis.

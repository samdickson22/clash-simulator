# Pilot regression diagnosis

The hard-label fit made the student play earlier and spend on cheap cards while learning little of the teacher's placement rule. The top-1 wait metric hid this change because the single wait action could remain the largest individual logit even after most probability mass moved to hundreds of play actions. Both evaluation and collection sample the distribution.

## Label provenance

Across 9,565 labels: 4,229 no-op labels, 1,722 script-choice/top-4 play labels, and 3,614 random-candidate play labels. Of 5,336 play labels, 32.27% came from the script and 67.73% from the random sample; no-op contributes 0% of play labels. Random provenance refers to the exact selected slot/tile action, including tiles independently sampled for different slots. Script membership includes the script's own choice and top four. Classification follows the planner's script-first deduplication. Reconstructed public packets were passed to the original script ranker for every labelled row. All chosen IDs occurred in stored root candidates.

## Student probabilities and placement

Held-out teacher-play rows, n=1,126. All metrics replay complete executed histories, including unsupervised context.

| Metric | Initial -> fitted |
|---|---|
| Teacher action probability | 0.000424874 -> 0.00527048 |
| Wait probability | 0.9681 -> 0.378496 |
| Teacher card/slot marginal probability | 0.028399 -> 0.574191 |
| Full joint argmax card/slot agreement | 0 -> 0.0035524 |
| Card/slot agreement conditional on play | 0.922735 -> 0.937833 |
| Best legal play tile distance, Euclidean tiles | 7.99821 -> 7.5795 |
| Best tile within teacher slot distance, Euclidean tiles | 7.99313 -> 7.47647 |

The literal joint argmax is almost always wait, so its tile distance is undefined. The table reports the best legal play and the teacher-slot conditional tile distances instead. Hand slots hold distinct cards here, so slot and card agreement coincide. Median teacher-action probability rises from 0.00003129 to 0.00334842.

## Traced behavior

Fresh canonical 24-game traced evaluation per checkpoint, four games in each of the six existing cells, seed base 770031. Counts are sampled submitted plays. Location entropy is empirical entropy of sampled canonical tiles, conditional on playing; it is not the policy distribution's entropy.

| Metric | Initial | Fitted |
|---|---:|---:|
| win_count | 11 | 4 |
| plays_per_game | 44.7917 | 54.375 |
| wait_rate_when_playable | 0.940667 | 0.639303 |
| location_entropy_nats | 4.87799 | 5.1891 |
| elixir_at_play_mean | 5.63477 | 2.52683 |
| elixir_at_play_median | 5.5015 | 2.355 |

| Card | Initial plays | Fitted plays | Initial share | Fitted share |
|---|---:|---:|---:|---:|
| Archers | 77 | 95 | 7.16% | 7.28% |
| Cannon | 103 | 189 | 9.58% | 14.48% |
| DarkPrince | 18 | 31 | 1.67% | 2.38% |
| Fireball | 16 | 4 | 1.49% | 0.31% |
| Giant | 11 | 0 | 1.02% | 0.00% |
| Goblins | 20 | 39 | 1.86% | 2.99% |
| HogRider | 93 | 19 | 8.65% | 1.46% |
| IceGolem | 101 | 174 | 9.40% | 13.33% |
| IceSpirit | 103 | 154 | 9.58% | 11.80% |
| Knight | 58 | 69 | 5.40% | 5.29% |
| Log | 103 | 219 | 9.58% | 16.78% |
| Musketeer | 167 | 54 | 15.53% | 4.14% |
| Prince | 19 | 0 | 1.77% | 0.00% |
| Skeletons | 123 | 202 | 11.44% | 15.48% |
| Tesla | 27 | 2 | 2.51% | 0.15% |
| Zap | 36 | 54 | 3.35% | 4.14% |

Cheap-card spending crowded out win conditions and support. Hog Rider fell from 8.65% to 1.46% of plays and Musketeer from 15.53% to 4.14%; the fitted student never played Giant or Prince in these 24 games. Teacher-play labels themselves were at mean 2.451 elixir, median 2.250, so imitating their timing encourages spending well below the initial student's 5.635-elixir play average. The original fit's label-weighted batch KL rose from 0.254 in epoch 1 to 1.675 nats in epoch 3. At coefficient 0.1, this contributed only 0.168 to the final-epoch average objective, versus CE 3.430.

## Alignment and cause

All 40 games: global progress equals submitted tick / 6000; previous actions match executed actions; all play labels round-trip for both seats.
Eight teacher play labels were rerun live across both seats. Stored ticks, hands, public global features, teacher action IDs and decoded world tiles matched exactly. Saved labels round-trip through the environment's decode/encode. The same action IDs enter the native rollout and policy target. The previous full-game Python/native receipt also matched every label and action, with maximum leaf-score discrepancy 1.61e-5. No indexing, seat rotation, observation-tick or recurrent-history pipeline bug was found.

Full-action hard CE treats each sampled winning random tile as the only correct action. It rewards increasing total play probability even when precise placement remains uncertain. Wait probability on teacher-play states fell by 59 percentage points and teacher card probability rose roughly twenty-fold, while tile distance improved by less than half a tile. The weak 0.1 anchor allowed this large behavioral change. The mixed teacher/student collection visits low-elixir states unlike the student's preferred timing; matching privileged greedy rollout decisions at those states changes spending behavior. Random-candidate label noise and unavailable privileged information limit the deterministic public mapping. The measurements support these mechanisms but do not individually isolate them causally.

Evidence: it2/diagnostics.json, it2/behavior.json and it2/evaluation/diagnostic-{initial,it1}/. Original pilot fresh evaluation regressed 88/192 to 16/192, paired exact sign-flip p=1.38e-14. Iteration 2 tests candidate-conditioned soft targets with a full-distribution anchor and an advantage filter; it does not establish which intervention matters alone.

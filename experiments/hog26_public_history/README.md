The existing 809 public features already include global-resource differences at lags1,5 and20. This extension adds history of24 existing masked entity summaries: counts of troops, buildings, projectiles and effects; observed troop position means; and troop HP, direct-DPS and crown-proximity proxies with their confidence summaries, for both sides.

The97 additional features are three lag differences per summary, mean absolute observed change over the latest20 transitions, and the available-transition fraction. Changes can reflect movement, births, deaths or visibility; they are not treated as inferred private actions. All arithmetic follows a fixed order so online and batch features match exactly.

The builder receives only public feature values. It checks the public clock and the existing lag-availability flags to reject an unprimed state or a crossed game boundary. No actual endpoint, game outcome, family label or opponent-policy label is supplied. Prefix, future-perturbation, reset, clone and wide-magnitude streaming tests pass.

A full-corpus extraction/audit in `hog26_history_cache` must complete before any fitting use. The additional features yield911 inputs when appended to the existing814-column health-augmented value representation. They have not yet been used in an outcome fit.

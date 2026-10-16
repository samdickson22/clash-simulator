**CHANGES REQUESTED — do not execute the new validation harness yet.**

Reviewed clean HEAD `d1954fa93f0e92c5618688402e085bc97b6f2c69`.

1. **[P1] The deployment policy starves Three Musketeers.** [real_games.py:153](/mpac/sdicks02/repos/clasher-cards-public-graphs-20261016/reports/cards/b1/public-graphs/tools/real_games.py:153) filters out unaffordable cards before choosing its next target. The opening spends on Goblin Giant; subsequent affordable cards consume income before the nine elixir needed for 3M accumulates. Lower play counts cannot prioritize an excluded card. This threatens the mandatory deployment assertion at line 180 and prevents the intended formation/shot coverage. Choose a target before affordability filtering and wait for its natural elixir requirement, preserving legal placement and command delays.

2. **[P2] The multiple-parent witness does not exercise multiple parents within one owner.** [real_games.py:93](/mpac/sdicks02/repos/clasher-cards-public-graphs-20261016/reports/cards/b1/public-graphs/tools/real_games.py:93) counts Goblin Giants across both owners. One ordinary GG per seat satisfies the final assertion at line 184 without exercising the changed per-owner multi-parent assignment. Require and retain a real whole-board witness with at least two same-owner parents and their complete observed rider population; validate each consumer on that witness.

3. **[P2] HEADLINE model receipts precede a supported model replacement.** [validate.py:32](/mpac/sdicks02/repos/clasher-cards-public-graphs-20261016/reports/cards/b1/public-graphs/tools/validate.py:32) records checkpoint hashes during Runtime construction. The frozen headline worker subsequently calls `install_from_env(rt)`, which can replace both models through `BOT_FULLPOOL_POLICIES` ([models.py:56](/mpac/sdicks02/jobs/clasher/cards/r1-cards3-phase1/repo-eval/bot/fullpool/models.py:56)). [validation_job.sh:18](/mpac/sdicks02/repos/clasher-cards-public-graphs-20261016/reports/cards/b1/public-graphs/tools/validation_job.sh:18) leaves that override inherited, so the comparator can accept receipts describing earlier models. Unset/reject that override for this fixed-checkpoint gate, or verify the actual final models after installation.

The production helper’s complete-population fallback follows the documented public-only policy; I found no additional source blocker there. RamRider coverage remains **primary Ram body only**: the source requires `spawnAttach` for attached riders, and Ram lacks it. Preserve that rider/bola coverage gap explicitly; do not claim full RamRider mechanics closure.

Exact reviewed SHA256s:

```text
public_root.py       1cae9504afd3e7297805a50647b8e7818ace50a70f2844c1f80bcf10ff8b7744
real_games.py        c99b3238a5c16139c03c3ab39526cab3caf293a093e7b7ab11b7e4e480b04efb
validate.py          1a04bb88a69e6e6da93a72e9259567f9941e4f328b4f2f2e03f72a732b19f9ba
validation_job.sh    96d2d57c56e3bfedf370841ab32826501793967f9a528dfc1c1bb2608e56cfc9
compare_headline.py  e18683b4ff63880b27aa062a10185a74e8a3885320a32382df780708472cfb2b
```

Python AST and shell syntax checks passed; locally available manifest targets match. No edits, engine imports, project tests, SSH, jobs or descendants were performed.

Revised bytes require fresh preflight. Any later execution approval remains conditional on actual host hashes, exact reviewed-HEAD receipt, fresh output paths, prior-job quiescence, CPU admission and wrapper-only cancellation. Final independent review of genuine gate receipts remains mandatory.

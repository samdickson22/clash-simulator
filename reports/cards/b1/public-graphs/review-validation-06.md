**CHANGES REQUESTED — do not launch fresh03 from HEAD `e742c227d098e7c6ba30e9a72e25122b9129bc9e`.**

1. **[P1] Released-barrel coverage compares incompatible mechanical names.** [real_games.py:76](/mpac/sdicks02/repos/clasher-cards-public-graphs-20261016/reports/cards/b1/public-graphs/tools/real_games.py:76) collects exported child names such as `Skeleton`; line126 compares those directly with reconstructed root names. The exact captured fixture contains seven `Troop` rows named `SkeletonArmy`. Frozen template registration preserves existing templates for shared public tokens, so the public token label does not establish the selected template’s mechanical name. [object_templates_probe.py:176](/mpac/sdicks02/repos/clasher-cards-public-graphs-20261016/reports/cards/runtime/tools/object_templates_probe.py:176) reports `token_names`, confirming the inventory cannot justify this comparison.

   Resolve each exported child’s ordered `public_identity` through the frozen builder and `(token, kind)` template mapping. Match actual observed public rows by that identity, validate their selected payload stats—including LIVE10 scaling—and retain token, exported name, selected name and consumer witnesses. Keep both container and released-child positive assertions. Earlier scheduling alone cannot correct this predicate; adding a name exception would leave payload correctness unchecked.

2. **[P2] Deployment failures still precede diagnostic persistence.** [real_games.py:221](/mpac/sdicks02/repos/clasher-cards-public-graphs-20261016/reports/cards/b1/public-graphs-20261016/reports/cards/b1/public-graphs/tools/real_games.py:221) checks accepted deployments before writing progress. Persist completed-game results and accumulated metrics before that assertion as well, so a missing deployment retains the promised diagnostics.

The failed02 log proves the combined barrel assertion failed; it does **not** identify which counter failed. No production-helper defect is demonstrated by this evidence.

Reviewed SHA256s:

```text
public_root.py
1cae9504afd3e7297805a50647b8e7818ace50a70f2844c1f80bcf10ff8b7744
real_games.py
14dc9d2240b01a1541f1ebb41fa7dfe751130f53a630623f6c96ae67de815ffb
validate.py
4c8835f64cf751eca2c0b28a82eca23118c3ba949a76beb71eae4ccbcad7deb3
validation_job.sh
7b6eeee0bebac0b4ad7497a9fb7b9a59b2dfb998ed403fcd7721405fa61eac72
compare_headline.py
e18683b4ff63880b27aa062a10185a74e8a3885320a32382df780708472cfb2b
validation-inputs.sha256
d734983ecef043b341453854bc4b7c8d1db5fcf6955b16af2c026dbe9a662db3
```

AST, `bash -n`, whitespace checks, 14 locally available manifest targets and all507 accepted-source comparisons passed. Capture67/1 and exact fixture identity verified. No additional source or wrapper-safety blocker found; Ram remains primary-body-only.

Corrected bytes require fresh preflight, followed by actual-host hash/HEAD binding, old-job quiescence, exclusive03 creation, CPU admission and wrapper-only cancellation. All five fresh phases and final independent evidence review remain required. No edits, engine imports, project tests, SSH, jobs or descendants performed.

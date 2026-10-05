# M0 scalar level plumbing

Implemented player-owned card levels and Crown Tower levels. Default games retain level 11. These are source-table and synthetic contract checks, not native acceptance or playing-strength evidence.

`PlayerState.card_levels` stores canonical card names. `card_level(name)` accepts aliases and defaults to 11. `set_card_levels(mapping)` validates integer serialized levels and rejects conflicting aliases. Deck installation accepts `card_levels=` and clears the prior mapping when omitted. `PlayerState.tower_level` must be configured before constructing `BattleState`.

Battle resolution copies card stats when the player's level differs, leaving shared loader stats intact. Spell construction uses the existing level-aware factory and captures the selected level before the queued cast. Existing child and Mirror inheritance remains active. Unsupported non-tournament spell payloads fail before payment. Crown Towers support levels 10 through 12, with independent player HP and projectile damage. Towers retain internal scaling placeholder 1 and expose the actual level as `publicLevel`. Ordinary bodies expose `card_stats.level`.

The Crown curves use retained native table data: King base HP 2400 and projectile damage 50, Princess base HP 1400 and damage 50. Integer percentage growth is 7% for King HP and 8% for other Crown stats through level 9, then 10%. The Princess curve agrees with the serialized `supportPowerLevel` table. Level 11 still takes its values from the existing tournament balance layer. `source-receipt.json` records source hashes, extracted configuration and resulting values. The runtime does not depend on local native cache files.

Validation:

- `tests.log`: 60 passing tests across the new player-level suite, stat scaling, Mirror, public Mirror history, public entity levels and deck sampling.
- `spell-tests.log`: existing level-aware spell coverage, including spawned children.
- `git diff --check` passed for the changed tracked files.
- An adjacent match-rule run had two pre-existing King activation failures. `head-baseline-failures.log` reproduces both using a complete isolated HEAD `src` snapshot, unchanged tests and gamedata, and a pytest import override. The log prints the loaded snapshot module paths. Its temporary source copy was removed after the run. `baseline-failures.log` also records an earlier, narrower constructor-only in-memory comparison.

The two baseline failures are `test_short_stun_during_king_activation_does_not_change_first_shot_time` and `test_freeze_does_not_add_a_new_windup_after_king_activation`. No physics changes were made for those failures. This work did not run training, native gameplay, cloud compute or commits.

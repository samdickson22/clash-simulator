# TV Royale card-cost authority fix — 2026-08-17

## Finding

The upstream filename `cr_detection/cards/cannon-1.png` is not harmless display
metadata. `TVRoyaleUIExtractor` parsed the suffix into `CardTemplate.cost`, then
used that value in two production paths:

- gray/unaffordable hand recognition synthesized the radial readiness overlay
  from `card.cost` in `cards_in_hand_with_confidence`;
- full-replay deck discovery synthesized the same overlay for persistent gray
  card crops.

For Cannon, the stale suffix therefore generated a one-elixir readiness mask
instead of the current three-elixir mask. It could lower or redirect the template
match for a gray Cannon, which in turn could create an incomplete hand, miss or
misidentify a play transition, or reject an otherwise valid supervision row.

It did **not** determine the final public action mask's affordability. That path
already resolves the recognized hand token through the packaged `CardDataLoader`
and reads `stats.mana_cost` in
`src/clasher/rl/public_action_mask.py:159-177`. The defect was upstream of the
mask, in visual identity/event extraction.

## Fix

`TVRoyaleUIExtractor` now requires a `card_cost_resolver`. Asset suffixes remain
parseable naming metadata only and are never converted into a card cost. The
production raw-cascade extractor passes
`TVRoyalePlacementConverter.source_card_cost`, which resolves the source name
and reads `mana_cost` from the same packaged authoritative card snapshot used by
the public observation/action-mask stack.

Unknown real cards fail closed instead of falling back to their filename.
The `empty` UI sentinel remains available with no card cost and therefore gets
no synthetic affordability overlay. Extraction manifests now pin the exact
packaged gamedata path and SHA-256 under `card_cost_authority` in addition to the
template revision/hash.

This preserves the deployment contract: public static costs can be used during
offline extraction and training, while the exported policy must ultimately
encode/memorize them inside its own artifact rather than perform a runtime file
lookup.

## Validation

A focused test creates an intentionally stale `cannon-1.png` and valid
`knight-3.png`, initializes the extractor with the real packaged resolver, and
proves both resolve to cost 3. It also proves the evolution alias
`evo_cannon` resolves to the same authoritative cost.

Bounded gate:

- Ruff: clean.
- Mypy: clean on the three changed source files.
- `tests/test_rl_tv_royale_ui.py` plus
  `tests/test_rl_tv_royale_replay.py`: 23 passed.

No replay extraction, detector inference, model training, or sustained compute
ran.

# Current-client stable vocabulary for the YouTube lineage

Date: 2026-08-17  
Schema: `clasher.current_client.youtube_stable_vocabulary.v1`

## Decision

The fresh YouTube lineage must not reuse the retained checkpoint's flat,
alphabetically rebuilt 155-token vocabulary. That vocabulary represents only
66 configured deck labels and maps a current, ordinary card such as Royal Giant
to `<unknown>`. The replacement artifact uses typed stable keys such as
`card_action:RoyalGiant`, `troop_body:RoyalGiant`, and
`projectile:RoyalGiantProjectile`. Its stable SHA-256 identity includes the
namespace, so card actions, visible bodies, projectiles, areas, buffs, and
abilities with the same bare name cannot collide.

The frozen machine-readable artifact is
`reports/current_client_youtube_stable_vocabulary_v1.json` (SHA-256
`960c1c1d68dea56786b0e196c5fc772b298fa16db168a81ca6c6d36c60c54704`).
It is a data contract, not a claim that every represented mechanic is simulated
exactly.

## Authority

- Client authority: decoded client `15.546.41`.
- Packaged `gamedata.json`: 3,120,175 bytes, SHA-256
  `3d99987c19cb94a0c8a6795e943829771078e564859e34c1411e221e5d57486a`,
  embedded fingerprint `ef863332281e7c47d628d23a80881ed300d47ede`.
- Loader/data-boundary source paths: `src/clasher/data.py`,
  `src/clasher/card_aliases.py`, `src/clasher/gamedata_normalization.py`, and
  `src/clasher/rl/structured_obs.py`.
- `decks.json`: 33 decks, 66 unique deck-facing labels, SHA-256
  `39fd5d5fe36cc7cfa69cf049de3ea2e7e00bc143ec71b14f33ead300fb4b2944`.
- Retained checkpoint: 155 tokens, SHA-256
  `3353615954fdcfdb24f2ba570f1888cd6130242238391a9bcf98dcedbcfc5b88`.

## Inventory

The current loader sees 148 raw spell rows, retains 144 canonical roots, and
adds 27 surface aliases for 171 loader keys. The full base/evolution/hero graph
contains 568 unique bare names including the two simulator tower identities.
After typed-name disambiguation, the manifest contains 697 graph entries:

| Namespace | Entries | Standalone actor identity policy |
|---|---:|---|
| card action | 199 | eligible when visible |
| troop body | 141 | eligible when visible |
| projectile | 87 | eligible when visible |
| area effect | 58 | eligible when visible |
| building body | 27 | eligible when visible |
| tower | 2 | eligible |
| buff | 42 | graph-only; represented by state/status features |
| ability | 10 | graph-only; not a standalone card/entity |
| action helper | 131 | graph-only; not a standalone card/entity |

There are 492 eligible typed entries plus `<pad>` and `<unknown>`, giving 494
initial actor-token IDs. Initial numeric IDs are deterministic for this frozen
v1. Future additions must append; re-sorting is forbidden without an explicit
migration manifest. Aliases and official English labels are contextual
recognition labels, never primary IDs.

## Variants and forms

The graph explicitly retains all 41 embedded evolution roots and all 14
`heroData` roots. It also retains nested visible forms and payloads, including
Phoenix egg/respawn bodies, Elixir Golem stages, transformed cannon/demolisher
bodies, Goblin Drill/Goblinstein bodies, and the distinct Merge Maiden records.
Each occurrence carries its owner root card, graph path, variant classification,
data source, and raw subtree hash.

This matters because 125 bare labels occur in structurally different roles in
the client graph. Examples include `Freeze` as a card action, area effect, and
buff, and `SkeletonKing` as a card action, troop body, and ability. The existing
alias table also collides with real spawned-body names (`Skeleton`, `Bat`, and
`SpearGoblin`). The new contract therefore resolves a label only with an
expected namespace/context.

## Retained-checkpoint comparison

The old 155-token list exactly matches a fresh current
`StructuredObservationBuilder` over the 33 configured decks, but 77 of the 144
current canonical loader roots are absent. This is not a safe vocabulary for a
current-client vision lineage.

Royal Giant demonstrates the failure concretely:

- old `RoyalGiant`, `Royal Giant`, `royal-giant`, and `royal_giant`: token 1,
  `<unknown>`;
- new base card action: token 224;
- new base troop body: token 457;
- new base projectile: token 333;
- new evolution card action: token 225;
- new evolution projectile: token 334;
- new evolution push area: token 21.

All six are typed, non-unknown identities. `Royal Giant` normalizes to the
card-action label `royalgiant` without making that normalized label a globally
unique key.

## Unsupported and unproven mechanics

Representation and simulator fidelity are separate gates. The artifact never
drops an identity merely because its behavior is unsupported:

- all 144 canonical roots are loadable definitions, but exact current-client
  mechanics parity is not inferred from successful construction;
- 41 evolution card actions and 14 hero card actions are represented, while
  explicitly marked as not exposed as standalone definitions by the current
  `CardDataLoader`;
- 10 ability, 131 action-helper, and 42 buff nodes remain in the graph but are
  not standalone actor tokens;
- reachable bodies, projectiles, buildings, and areas are represented with an
  explicit `exact_mechanics_not_proven` state rather than being silently
  omitted.

This is deliberately conservative. A downstream simulator-support audit can
promote individual entries without changing their stable identity.

## YouTube identity gate

The current 10-replay/120-frame YouTube canary has 120 neutral frames eligible
for offline extraction, but it has decoded **zero** neutral structured
snapshots and therefore published **zero** trustworthy card identities. The
manifest records the gate as
`blocked_no_structured_identities_decoded`; it does not claim vacuous 0/0
coverage. Metadata titles were explicitly not used for deck/card claims.

Once the extractor publishes typed identity observations, the required gate is:

1. recognize the visual label into one or more contextual candidates;
2. resolve it by expected role (`card_action`, `troop_body`, `projectile`, etc.);
3. require a non-unknown stable key in this manifest;
4. quarantine unresolved or ambiguous labels rather than substituting token 1;
5. publish the decoded identity list and re-freeze this canary comparison.

Until then, Royal Giant and exhaustive current-client graph coverage are proven,
but the requested per-canary identity proof remains honestly blocked on semantic
extraction.

## Validation

`tests/test_current_client_youtube_stable_vocabulary_v1.py` reconstructs the
manifest from the frozen authorities and checks exact equality, authority
digests/counts, stable-key and stable-ID uniqueness, contiguous actor IDs, typed
collision examples, Royal Giant migration, helper exclusion, explicit
evolution/hero inventories, and the fail-closed canary state.

Verified command:

```bash
PYTHONPATH=src:. uv run pytest -q tests/test_current_client_youtube_stable_vocabulary_v1.py
```

Result: `5 passed`.


# Prospective readiness root-bank declarations

`root-bank.draft.json` declares 32 separate complete episodes, balanced across seats. Each of the 16 supported cards has two focal requests across four public tactical contexts. No captured roots, branch outcomes or acceptance families were manufactured.

The generator independently draws each episode's seed, deck pair, deck permutations and public prefix styles. It uses four recognizable pilot decks: Hog cycle, Giant double Prince, Hog pressure/control, and Giant control. A request uses one root from one full episode. It does not reuse a battle's other seat or count geometry variants as independent families. The two requests for a focal card are separate episodes with separate draws. Their shared card and context strata do not supply additional independent observations.

Unique request IDs and seeds are declarations, not proof that eventual captures are independent. Actual configuration hashes, capture paths, source episode ownership and the exposure ledger still need binding. All related roots or variants of a captured episode must remain in that episode's one family. The new bank is prospective and remains a draft until those inputs and the readiness protocol's other requirements exist.

## Root eligibility

The selector inspects canonical public packets every five native ticks from 90 through 1290, inclusive. It chooses the first packet meeting its declared context and candidate requirements. Contexts are an enemy troop in the owner's half, an enemy troop within three tiles of the bridge line, two enemy troops within three tiles of one another, or both friendly and enemy troops on the board. These predicates use observed positions, ownership and troop kind with full confidence.

The balanced public controller generates the four agreed roles: its highest-ranked immediate play, wait, its best play with another card, and a placement of the first card at least two tiles away. The focal card must occur in those actual candidates. Hand or deck membership alone does not qualify. Because wait has no card and the displaced play shares the immediate card, each selected root branches on two distinct card identities. Completing all 32 requests therefore provides two planned focal-card exposures per pilot card, plus any incidental alternate-card exposure. This requirement is fixed before branch outcomes.

A missing intermediate packet, early terminal, or exhausted eligibility window remains a recorded failure. There is no replacement draw or later outcome-based root selection. Selection stops before reading future packets once a root qualifies. This eligibility narrows the eventual admission scope; it does not promise that all 32 requests will succeed.

## Existing evidence and remaining work

An offline check of the already-opened `mix0-reversed` development capture projected its public packets through the runner's strict adapter. Its frames are at native ticks 90, 120, and 150. The selector correctly reports `missing_packets`, expecting tick 95 after the first frame. See `opened-cadence-probe.json`. This is a cadence compatibility check only. It is not a scalar continuation study or fresh reference acceptance, and the existing thirty-tick archive cannot certify the earliest-five-tick rule.

The runner owner provides capture projection and preparation through `scripts/run_readiness_v2.py`. Once genuine captures exist, the selected request maps to its `{capture_path, family_id, independence_id, root_tick, root_owner}` input, with `independence_id` equal to `source_episode_id`. The actual public packet and root hashes must come from that capture binding. The generator supplies no guessed hashes.

Concrete native configurations are now prepared in `native-configs/`, with a manifest binding all 32 requests. See that directory's README for validation and limits. Still required: five-tick public histories from 32 independently owned episodes, immutable exposure registration, scalar coverage under the four continuation pairs, and identical-execution noise studies in both engines. No native process was launched and no new gameplay outcomes or fitting were performed.

## Validation

`tests.log` records the root-bank and readiness accounting tests. The new tests cover reproducibility, duplicate episode rejection, seat and card scope, both-seat causal selection, missing frames, terminal handling, window exhaustion, and refusal to count a focal card that is in hand but absent from the candidate set. Source hashes and draft counts are in `summary.json`.

# Native configuration materialization

All 32 prospective requests now have concrete native synthetic-match configurations. `manifest.json` reports 32 configured episodes and zero unsupported declarations. They remain uncaptured and unregistered.

The converter uses the configuration already exercised by the opened `deck-mix-development/mix0-reversed` capture. Historical native comparison code uses the same ordered-deck substitution: each `battle.deck{seat}.sp` entry contains only its native card ID. The converter validates the template's initial native deck slots, default base-card entries, Princess support payload, empty command/event lists, default Ladder mode, and level-11 card/player/tower settings. Only `rndSeed` and the two ordered `sp` lists change. All other native fields remain exactly as exercised; no new native settings were guessed.

Each manifest entry binds the family and source-episode identity, root request hash, seat, exact seed, ordered decks, prefix controller styles, level and declared base forms. It also records the config's relative path, file hash, canonical config hash and native card IDs. Source and template evidence hashes are pinned. The existing historical source ruleset and current `gamedata.json` have different hashes, so both are recorded. Native card identities must agree between them before a request can produce a config.

The preserved deck order is the input order supplied to the native deck serializer. The native engine may shuffle its opening hand using the declared seed. This receipt does not claim that the first four declared cards become the opening hand.

Prefix controller styles and the five-tick root-selection rule remain capture-adapter settings. They are not encoded into undocumented native config fields. A future capture claim must bind those settings and this manifest before configuration, then verify actual base forms, levels, observations, commands and exposure ownership. These config files do not establish gameplay validity, fresh independence, acceptance or readiness to train.

Validation: 18 converter and root-bank tests passed. The converter suite checks all 32 seeds and both ordered decks against real native card IDs, proves all other config fields unchanged, validates exact manifest hashes, retains all requests that encounter an unsupported card, rejects modified caps/form fields/events/native deck observations, and rejects source-pin drift before creating output. Targeted mypy and Ruff passed. Tests use the retained opened capture as their native configuration fixture.

No emulator, native socket, capture, registry write, branch continuation or fitting was run.

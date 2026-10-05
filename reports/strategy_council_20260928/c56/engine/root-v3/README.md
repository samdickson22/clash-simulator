# Root generator v3

Four prospective 32-family banks are in `B1.json` through `B4.json`, with master seed 20261003. They contain 128 distinct episode seeds and designs, 16 requests per seat per bundle, and two to four focal requests for each bundle card. These are declarations, not captured roots or admission evidence.

`human_deck_catalog.json` contains 2,925 deck sets from 69,380 training-role perspectives. Its index and frozen role-file hashes are recorded in the catalog. The builder reads deck identities and roles only; it does not select on recorded winners, simulated outcomes or held-out roles. Engine aliases such as IceGolemite normalize to the declared IceGolem roster entry. Within each eligible archetype, the generator samples from the four most frequent decks, weighted by frequency. Archetypes rotate across a focal card's requests.

The card-scope parameter filters the human own-deck pool and the bundle's focal set. Each request uses a separate episode, independent deck permutations and a bundle-specific random stream. A missing human deck or a seed collision fails declaration instead of creating a synthetic replacement. Missing packets, terminal episodes and exhausted capture windows retain the existing failed-selection statuses.

Contexts include air threat, building pull, spell value and enemy-side deployment, plus the existing backline and own-half contexts. Non-air strata use human P16 opponent decks. Air-threat strata need human C56 air decks because the P16 roster has no air troops. The declared champion-ability rule stays masked for scripted candidates.

Generate another prospective bank without starting capture:

```sh
nice -n 10 env OMP_NUM_THREADS=1 .venv/bin/python scripts/declare_readiness_root_bank.py \
  --version 3 --master-seed 20261003 --bundle B1 \
  --human-decks reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json \
  --output /tmp/c56-new-B1.json
```

An optional `--card-scope` takes roster names. At least eight focal cards must remain in a bundle to meet the fixed 32-family, two-to-four quota. Existing output files are never overwritten.

Consumers load `RootBankV3` and use `select_root_v3` with the explicit C56 controller and contract-v5 builder. That selector reuses v2's contiguous-packet, first-eligible selection loop with the new public context predicate. The existing `config_for_request` consumer validated all 128 declarations in memory against current and native-template card IDs. No native config package, episode, ledger row or receipt was registered.

Legacy capture/admission CLIs still parse v1/v2 banks and reject v3. Their contract-v5 capture/provenance wiring and native bundle admission remain subsequent work. The old generator and default CLI behavior remain P16. `summary.json` records quota, seat, archetype, context and native-ID checks.

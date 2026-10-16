# Deck search with real simulator levels

This harness changes the decks and simulator truth, preserving the deployed deterministic `LD-K4L-R-gs-rw` and `-res` players and their live belief. It never installs the experimental exact-level planning root. Opponents are R3a, v1, LIVE-K4CW-r16, and internal-only rext-bc.

`prepare` freezes an owned collection, ten C56 candidates from the preceding deck search, all 91 Battle Log rows with their nearest C56 catalog projections, population level counts, source hashes and simulator pins. It draws a screening bank using `os.urandom` and records `date -u` before playing. Each candidate receives the same seed, seat, opponent deck/order/levels and own opening permutation under both players. Opponent levels are independent population draws with the existing rarity assumption, never the selected log row's hidden levels.

`run` partitions the case-major jobs by stable index, forks isolated games, and records atomic result rows and diagnostic errors. Existing rows are resumed only with matching bank hashes and source/runtime identities; errors require investigation. The existing public static placement adapter covers simulator differences for every actual V1Policy poller. rext-bc explicitly opts into evaluation on 16.402 while retaining its original weights and observation normalization; report this balance transfer separately.

`select` requires every screening game to be clean and complete. It selects the two highest mean pooled win deltas across players and a third if within one paired standard error of second. It records selection before drawing a fresh, disjoint validation bank of 150 cases per opponent policy. Use `--validation-collection PATH --tower-level N` to register account corrections for validation. Every stage records its own true levels.

`report` can run during the experiment. Actual wins are primary, draws remain visible, and 20,000 percentile bootstrap replicates resample case pairs within opponent policy. Weak pool contains only R3a and v1; strong search and rext-bc are reported separately. No screen rows enter validation. Do not recommend from an incomplete bank or a positive pooled point estimate alone; assess the pooled CI and strong-opponent safety for both players.

Example (inside the job's pinned environment and an admitted CPU lease):

```bash
python -m bot.deckopt2.run prepare --root JOB
python -m bot.deckopt2.run run --root JOB --stage screen --shard 0 --shards 4 --workers 8
python -m bot.deckopt2.run report --root JOB
python -m bot.deckopt2.run select --root JOB --validation-collection COLLECTION --tower-level 6
python -m bot.deckopt2.run run --root JOB --stage validation --shard 0 --shards 4 --workers 8
```

All large inputs, results and model bytes stay outside Git. Current `--card-scope c56` rejects other scopes; the next full-pool experiment needs an explicit scope extension, the matching live16402b-r3 runtime and a new bank. Frozen runtimes are read only. Use `bot/exit/cpu_job.sh` leases, at most 40 workers, nice priority, required deterministic environment and `bot/detach.sh`; the wrapper must restrict compute to the authorized hosts.

# pretrain-v1 progress log

New single-model Clash Royale policy. Input: the live memory record plus causal history. Output: gate / slot /
tile / value, with the gate sampled. There is no decision-time search. Design:
`/mpac/sdicks02/scratch/new-pretrain-20261020/{DESIGN,PREREG-DRAFT,INVENTORY,FIDELITY}.md`. Engineering choices:
[DECISIONS.md](DECISIONS.md). Code: `bot/pretrain_v1/`. Data: `/mpac/sdicks02/datasets/pretrain-v1/` on 127x05
(copied to 127x08).

Constraints in force:
- Only 08's GPU is used.
- RL training on 04/08 keeps running.
- Hosts keep MemAvailable above 28 GiB and load at or below 90.
- No Mac or live changes, and no deployment.
- Code lands on main through fresh worktrees after GPT-6.1 Sol (high) review.

## 2026-10-21

- **12:00 PDT: inputs pinned.**
  - Deployed memory package, read-only from the Mac MEM-MANIFEST: `state.py` 9085e337, `rfextras.py` 513088f2,
    cards-122 289d240f. Local byte-identical copies are vendored.
  - Live runs use `spell_events=False`, so record `events` is always empty live.
  - Re-drive corpus at the time: 15.5k / 252k matches, 34 acked batches. Jobs with source coordinates are at
    `scratch/native-redrive-full-20261021/jobs/`.
- **Label-timing measurement** (300 matches, 19,394 executed plays). At E−27 the card is in hand 99.0% of the
  time and affordable 88.3%. Under DESIGN's strict mask, 12.6% of plays therefore cannot be lag-aligned (see
  DECISIONS item 12).
- **Piece 1, featurizer**, and **piece 2, dataset builder**, written.
  - 13 unit tests pass.
  - Smoke parity audit (6 matches): 9,638 polls where the serving path (`policy.Session`) equals builder bytes,
    and 0 violations in 9,638 private-mutation and 4,369 future-suffix cases.
  - Builder speed: 0.4 s per match per core, about 106k stored rows per 500-match batch.
  - Commit e001cf230 on branch `pretrain-v1/featurizer`; Sol review R1 requested.
- **Model**: 2,102,213 parameters. Untrained, single thread on 05 over a real live game: featurize + network +
  decode p50 4.9 ms, p95 6.1 ms.

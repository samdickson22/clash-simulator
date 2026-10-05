# Two-L40S replay-disjoint expansion — 2026-08-24

## Outcome

Seven untouched public TV Royale videos were acquired and semantically
extracted on Prime Intellect pod `b3f37d95069b4596b73eb350ddc061eb` using
2×L40S 48 GB, 24 vCPU, and 144 GB RAM. Six extractors ran concurrently (three
per GPU); the seventh ran immediately afterward. Both GPUs sustained 84–100%
utilization. The pod was terminated after hash-verified copy-off.

- Cloud cost: **$0.40**.
- Wallet after termination: **$7.14**.
- First six semantic matches: 126.506 s outer wall, **170.74 games/hour**.
- All seven sequential batch legs: 167.687 s, **150.28 games/hour**.
- Sources retained locally: 575,242,821 bytes.
- Semantic artifacts retained locally: 21,334,367 bytes.

## Structured output

The seven matches contain 16,792 10-Hz neutral snapshots, 156,576 filtered
public entity observations, 135,275 typed entity identities, and 77,988 HP
measurements. All copied source, frame-index, neutral-sequence, event, and
manifest hashes match their internal manifests.

The original marker-driven event head emitted only 70 complete plays from 851
marker candidates. The new marker-independent hand/Next detector found 406
elixir-confirmed visual cycle transitions. Three-frame identity consensus
labels 363 of those, with 306 also carrying an independent in-grid placement.
These are diagnostic until each replay receives reviewed eight-card deck
closure and exact evolution/hero-state labeling.

Four native-886 galleries were then deck-closed manually:
`nXNp3GRdFks` (Royal Hogs/Earthquake versus X-Bow), `iW_07-RIjJk`
(Hog/Freeze swarm versus Mortar/Skeleton King), `aVnmZEXSgiI`
(Goblin Cage/Flying Machine versus Goblin Drill), and `i1AyFVBDsPE`
(Golem/Battle Healer versus Giant/Minion Horde). The review used official
current-client variant art to identify `MiniPekka_hero`; disabled/enabled and
base/evolution clusters remained one root-card family. A second fail-closed gate
requires the unanimous card's authoritative public cost to agree with the
observed elixir drop within 1.5. Across the four deck-closed matches, 44 retained
stratified labels were manually reviewed and 44/44 matched the visible card art.
The gate also rejected all four previously selected slot/card swaps (including
two Tesla-as-Zap errors) before audit eligibility. The four matches contribute
188 precision-gated identities, 162 with placements:

- `nXNp3GRdFks`: 73 identities / 61 complete, SHA-256
  `66e150bd3733db5ef8d3b34461372dfbc01556db650f168f0adaf7dea54ceefb`;
- `iW_07-RIjJk`: 59 identities / 56 complete, SHA-256
  `458c9cac2083b5d7221b3dff9df5d76c93317d940cfa375391efda576439e794`;
- `aVnmZEXSgiI`: 39 identities / 31 complete, SHA-256
  `eada559865a3cf7d860100181e03cf45ae6138f02ebfcfc4150c32cdc4ea6f42`;
- `i1AyFVBDsPE`: 17 identities / 14 complete, SHA-256
  `ccec8db57edf154766204d8cc7383f06234feeb0b0827b2188326ce95e5b31a7`.

`yS3akCAdr6A` remains quarantined: player 1's eight-card deck is exact, but only
seven player-0 root cards ever appear in the reviewed hand/Next clusters. Its
eighth card was not guessed. The two native-888 replays remain quarantined by
the unsupported clock layout, so none of these three enters training.

## Causal actor packaging

The four exact deck-closed streams were converted into compact actor overlays,
label-independent public-mask-v2 inputs, a shared neutral public sequence, and
separate inference-ineligible action-target sidecars. HUD-cycle-v3 events become
targets only when play, identity, placement, public-cost, and offline-only gates
all pass; rejected events are never repaired or forced legal. The native-886
portable clock was then applied and all artifacts were republished atomically.

Two matches (`iW_07-RIjJk`, `nXNp3GRdFks`) pass the full existing live-state
contract. The other two retain valid component labels but fail the full-state
contract because both players never have a complete decoded HUD on the same
neutral snapshot; `i1AyFVBDsPE` also lacks nontrivial masks on its few fully
complete rows. They are not misrepresented as fully deployable trajectories.

Across all four replay groups:

- 141 action targets align to causal actor rows;
- 111 targets are independently legal under the public mask;
- 132 have a valid public clock;
- 105 have both a valid clock and legal public mask;
- 32 additionally have complete hand, Next, and elixir observations.

This is a proven conversion path, not enough data for a fresh policy. The
deterministic corpus audit requires at least 20 replay groups, 1,000 legal+
clocked action targets, 250 fully complete actor targets, and three fully
verified replays. Current decision: `collect_more`. Audit SHA-256:
`53c3b663ac92cc110946f358eee025f48470601d895bb92d1788595de5df8fb9`.

## Native clock expansion

Five native 886×1920 videos produced 2,161/2,161 exact portable-clock matches
against macOS Vision, 88.53% teacher-conditioned coverage, zero false accepts,
and a two-sided 95% lower accuracy bound of 99.829%. This layout is accepted.

Two native 888×1920 videos produced zero portable accepts against 824 confident
Vision anchors. They failed closed and remain explicitly unsupported. Evidence:
`portable_clock_native_expansion_20260824.json` (SHA-256
`75fd13eb7e3bda0364a7ff55e24ca40f0226c3171b39f00a5cc0d393377a43a7`).

## Exact manifest hashes

| Video | Source manifest | Semantic manifest |
|---|---|---|
| `0aBzIYe-FaA` | `0778245572d53970da5c75eb04da24b1c0ecdab80c9432e3d2a5442acb67ce6a` | `20e6a89fa4127010d54c711a9985ef087011eaf0587c2a91fbcff987847a9d7e` |
| `Xf8Y9GdxlLo` | `245e7f98fadf10ca0822a7e12ff0a2d3c8fc261a9f090be2b77554f5d8f019be` | `f42c9d8cad27f3f0a8855aa7576080e13e14f5b17370784351f6351a1604b78e` |
| `aVnmZEXSgiI` | `8f1e8ed6a038fc54877c679ad40386a40a57a5346d01ebbd28c82dc1ce7e908f` | `13571ceeecb61b72179321966c80a4b26904d812e952c913dc78de68d7c68678` |
| `i1AyFVBDsPE` | `0855fc28ad0492b360b67437a3b2504361519d24e95152d2c98dcc1d53ffe53b` | `7741c0b038e7126afa0e86e2a1623f90a8391df105be8fe213c25cb6d34a4bc1` |
| `iW_07-RIjJk` | `8b6d7718ce83e271227511d2af22fa7679890bb91e01e89b195816faef275050` | `2da00c6f13b7ba8150882334419130115f0717d31ec437719b0a7e1c93d0d014` |
| `nXNp3GRdFks` | `7380c9ffb961e9d41ee19544ab1cad15d04e5c5c2eb5f67e808c8bb566fffe9b` | `a0566fb9f3dc3a130e14ab97b53efcee596834e1e0b95fa1d16665f7438b3d24` |
| `yS3akCAdr6A` | `de6db50dcd87afde19b721c09d39a8cb408b0f842821ff4af082795bc762a8ce` | `d3ad65390d7f9b7b1e85def7fb9ff0c9c7e78530969d5de1841d2ef44430539e` |

## Next gate

1. Add a typed launcher skip for unsupported 888×1920 before enabling bulk mode.
2. Convert only the four exact deck-closed event streams into fresh causal
   imitation trajectories; keep target labels in a separate offline sidecar.
3. Preserve base-card family, evolution-ready state, and hero variant labels as
   separate fields during conversion.
4. Hold out entire replay/deck groups and run a fresh one-epoch causal BC screen
   before any long H100/H200 run.

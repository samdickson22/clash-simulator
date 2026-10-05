# Development prefix reserve study

Seed **260928902** selected **27 of 32 roots** in 41.9 seconds. Five requests remained ineligible and were retained; no requests were replaced and no execution errors occurred.

The declared change applies only to the root owner's prefix controller: its ordinary action becomes wait while publicly observed own elixir is below 8. The other player's controller, root selector, four candidate roles and future continuation controllers are unchanged. The rule is recorded in `study-design.json` and each result; every prefix log contains both ordinary and actual actions.

| Requested context | Selected | Ineligible |
|---|---:|---:|
| Bridge contact | 7 | 1 |
| Contested board | 7 | 1 |
| Enemy cluster | 8 | 0 |
| Own-half threat | 5 | 3 |

The reserve design explores a narrower, resource-preserving prefix distribution. It does **not** require selected roots to hold 8 elixir: selection occurs before the next prefix action and remains unchanged. Actual selected-root elixir ranged from 3.146 to 8.020; only one root had at least 8. Claiming a strict eight-elixir root scope would misdescribe this experiment.

All 1,471 context-matching packets admitted a complete four-role candidate set. Thus the missing two-affordable-card alternative was not the remaining bottleneck at those contexts. Across all 2,784 scanned packets:

| Check | Count |
|---|---:|
| Requested context absent | 1,313 |
| Focal card absent from current hand | 1,610 |
| Fewer than two distinct public-legal cards | 41 |
| Context, focal presence and two legal cards all present | 474 |
| Focal card included in actual four-role candidates | 27 |

The first three counts overlap. In first-failed-condition order, 1,313 failed context, 997 then lacked the focal card, zero then lacked two affordable cards, and 474 reached the ranking check. Of those 474, 447 omitted the focal card from the actual candidate set and 27 selected a root.

The five unsuccessful requests were both Fireball requests (contested and bridge), Giant/own-half, HogRider/own-half and Log/own-half. Fireball was publicly playable on 169 and 123 scanned packets respectively, but neither request ever ranked it into the candidate set at a qualifying context. Giant had 55 and Log 17 packets satisfying context, focal presence and two legal cards, but the focal card was omitted from the candidates. HogRider had no context-matching packet with the focal card in hand. Selected roots cover 15 of 16 focal cards; Fireball has no selected root.

A post-run audit checked all 2,752 executed prefix boundaries: the other player was unchanged, and the root owner waited exactly when the reserve rule applied. The reserve was active at 2,638 boundaries and replaced an ordinary play with wait 2,408 times. All episode IDs, seeds and episode-design hashes are disjoint from the first development bank and reserved prospective bank; all 32 generated config hashes are also disjoint from the first development configs. These checks are saved in `seed-260928902/postrun-verification.json`.

The first bank selected 19/32 and this bank selected 27/32, but both the seed and prefix design changed. This is descriptive feasibility evidence, not an isolated causal estimate of reserve effectiveness. No candidate continuation outcomes, non-wait separation, native coverage, admission or training labels were produced.

The study uses the exact opened native game-data file, SHA256 `daa58b28cf4e45d753e83ca69a76794285b63704e62363ee58e617af3a30ecc3`. Initial scalar hands still use the first four cards of each declared deck; native shuffle equivalence remains unproven. Only an unrelated ownership-ledger source file changed during execution; battle, public controller, projection and root-selector sources remained stable. Production generator and collector code were not changed.

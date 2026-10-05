# Revised causal root generator: development selection

The revised generator selected **32/32 roots** with development seed **260928903** in 29.17 seconds. All 16 focal cards appear twice, seats remain balanced 16/16, and there were no missing roots, execution errors, replacements or source changes during selection.

The new `readiness-v2-root-bank-v2` declaration sets `prefix_owner_min_elixir=8` and `stop_tick=3600`. Giant, HogRider, Fireball, Log and Zap receive the `enemy_backline` context: at least one visible enemy troop, with every visible enemy troop at canonical y>=17 tiles. This matches the public scorer's incoming-region boundary and avoids requesting offensive focal choices in a defensive context. The other focal assignments retain their existing contexts.

The four candidate roles, focal-card exposure requirement, first-eligible selection rule, continuation conditions and decision thresholds are unchanged. `apply_prefix_owner_reserve` centralizes the prefix rule for scalar and native callers. Legacy requests missing the new field retain reserve 0 and the prior default window; their old episode-design hashes are preserved. New nonzero reserve values enter the episode-design identity.

| Context | Selected / requested |
|---|---:|
| Enemy backline | 10/10 |
| Bridge contact | 6/6 |
| Contested board | 6/6 |
| Enemy cluster | 5/5 |
| Own-half threat | 5/5 |

All 813 context-matching observations had complete four-role candidate sets. Of 98 observations also containing the focal card and at least two public-legal cards, 32 exposed the focal card in the actual candidate set and selected a root. Earlier in each prefix, missing context and absent focal cards remained visible in the diagnostics; nothing was redrawn after a failure or outcome.

Roots were selected between ticks 95 and 1635. Only the Goblins/seat 0 root needed the extended window beyond 1290, selecting at 1635. Root elixir ranged from 3.109 to 8.010. The declared reserve changes prefix exploration; it is not a strict minimum-elixir requirement on selected roots.

The post-run rule audit checked all 2,143 executed prefix boundaries. The reserve was active at 2,036 boundaries and replaced 1,840 ordinary owner plays with wait; other-player actions were unchanged. This log-based suppression count is authoritative; the copied helper's inline counter inspected the action after applying the shared rule and therefore omitted that diagnostic field. Actual executed actions and original-action logs were preserved correctly. Episode IDs, seeds and design hashes are disjoint from both prior development banks and the reserved prospective bank.

The test suite for the revised generator and native config materialization passed 23 cases, including both-perspective backline geometry, exclusion of incoming enemies, the shared owner-only reserve, threshold behavior, preserved legacy semantics and immutable focal/candidate requirements.

This is scalar development feasibility using the pinned native capture game data and a scalar-only first-four-card initial hand realization. Native shuffle equivalence and native root yield remain unproven. These observations do not isolate causal effects because the seed, contexts and window changed between development banks. Selection produced no continuation outcomes or training labels. The separately authorized 512-branch scalar continuation study follows this fixed bank without replacing any root.

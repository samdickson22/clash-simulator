# Gate (b): imitation proposals in C56 fair search — DRAFT

Source: reports/strategy_council_20260928/imitation/DESIGN.md §5.2, §2.4.3 and Stage 5b.
Checkpoint SHA256: **TBD** (T5 dev selection; no synthetic outcome is evidence).
This draft is not frozen. Before any gate game, freeze checkpoint, this document,
code/runtime/gamedata/native/prior/roles/index hashes, complete schedule and seed-audit receipt
in an immutable evaluation manifest. Freeze after T5 selects its checkpoint. No interim strength analysis.

## Arms and matching

A is the Stage 5b deadline fair player: script choice, no-op, script top four,
ability and 16 sampled public-legal placements; 200 ms absolute wall deadline,
two Rust workers. B is identical except its sampled slots use imitation top eight
joint p(card) p(tile|card), deduplicated against scripts, then random fill.
Gate probabilities never enter search proposals; no-op remains explicit.
D1 is deck-free and uses timestamped accepted public events and known own order.
Sensor conversion, event updates, D1, feature building, inference, candidates,
root construction, native workers and worker joins all count inside the deadline.
Only initialization and warmup before games are excluded.

Count convention (needed to preserve the existing A implementation): A draws 16
placements BEFORE deduplicating scripts. Its actual unique addition may be less
than 16. B exactly matches that root's A post-dedup count, never adding extra
candidates. A's random draw determines the count and supplies B's random fill;
B substitutes up to eight distinct legal imitation proposals at the front of
those slots. When legal support is small, both arms exhaust the same count.
This preserves A byte-for-byte; candidate-count equality is asserted per B root.

## Schedule and fresh seeds

Primary: 320 seeded worlds × two controller swaps = 640 games. Physical decks
and seeded world remain fixed across each pair; only A/B controller seats swap.
Use Stage 5b role-held-out eval/eval_ood planning, its seven family strata and
train opponent catalog. Both deck identities must be supported by the Stage 5
train-only prior. This is role holdout, not deck-identity holdout. Family pair
counts are 46,46,46,46,46,45,45 in Stage 5b's family order.
Secondary: each of A and B plays 256 games against balanced/pressure/defense C56
scripts on identical seeds/decks/seats: 128 pairs per arm, both seats per pair.
Family pair counts 19,19,18,18,18,18,18; styles cycle in fixed order. For these
script pairs the held-out planning deck follows the candidate across seats,
matching Stage 5b continuity. Total 1,152 games.

Proposed namespace: world seed 2,817,600,001 + 1009*i, i=0..447;
primary i=0..319, secondary i=320..447. Planner seed = world + 100000 +
physical seat; belief seed = planner + 1. Deck-schedule RNG = 2,817,590,001.
Bootstrap RNG = 2,817,590,002. Synthetic plumbing uses a disjoint namespace.
These are proposals until the audit passes, not a claim of freshness.

Before freeze, inventory every prior receipt on authorized hosts 127x01/03/04/05/08
(and available historical exports), including interrupted/abandoned runs. Search
JSON/JSONL (also gzip), nested seed values, NPZ seed arrays and metadata, schedules,
logs, Markdown, Python and shell sources for exact candidate seed integers.
Include all world, policy, deck-selection and bootstrap seeds; expand generated
seed formulas/ranges. Record each scanned file's SHA256 and host, parse errors,
proposed integers, matches and missing inventories. Exclude only this gate's
prospective draft/schedule/audit and their mirrors. Fail closed on overlap,
unreadable receipts or an incomplete inventory. On collision, advance the whole
namespace by 100,000,000 and repeat BEFORE any outcome. Freeze audit and exact
schedule; do not select seeds based on outcomes. Cross-gate namespaces must also
be disjoint. A local scan alone does not satisfy the fleet audit.

## Analysis and pass bars

Win=1, draw=0.5, loss=0. Primary score is the mean of the 320 two-game B pair
means. Two-sided 95% percentile paired-matchup bootstrap, 10,000 resamples of
whole worlds with both controller swaps retained. Report score, interval,
W/D/L, pair discordance, per-family and eval/eval_ood descriptions.

All three conditions are required:
1. Primary point score >=0.53 AND bootstrap lower bound >0.50.
2. Secondary B minus A point score >=-0.03, using all 256 paired games per arm.
   Report paired interval descriptively; no extra significance bar.
3. Zero B decisions >250 ms and B p99 <= A p99 +15 ms. Pool all candidate
   decisions (searched and forced waits), in milliseconds; report p50/p99/max,
   overshoots, truncations/fallbacks, worker count/nice/host load. A comparison
   uses the same gate schedule, not the historical Stage 5b p99.

Sample-size premise: 30–50% discordant pairs, pair-mean SD .27–.35, SE
.015–.020 at 320 pairs; true score .55 has approximately 70–90% power to clear
LB .50. The 640-game primary is fixed; no optional stopping.

Pass: B becomes default C56 fair player and live-loop v4 P3 uses it.
Fail: A stays; imitation remains fallback and a base for later work. No tuning
on these games. The sole predeclared retry is v2, with fresh seeds.
Report every result including failures. Technical interruptions replay the exact
seed/config from the beginning without inspecting the outcome; retain partial
receipts and rerun reason. Never rerun to remove a loss, slow decision, rejected
command or illegal action. No synthetic checkpoint outcome claims.

Launch prerequisite: exact D1 train/serve tensor equality on eight recorded C56
games, 20 full smoke games with zero illegal actions, timing evidence; T5 hash;
registration and independent review. Draft preparation alone does not satisfy it.

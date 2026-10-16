# r1-cards3 / live16402c — released receipts

**RELEASED, READ-ONLY on 03/04/08. All six Runtime(verify=True) checks PASS.** The full corrected v3 class gate passed before publication. CARD LEAD accepted the original orphan-rider fixture failures as harness artifacts and the one handled mixed-game GoblinGiant fallback as nonblocking. No default or active LIVE pin was changed.

| Root (same path on 03/04/08) | gamedata SHA256 | Complete read-only content/mode/symlink manifest SHA256 (excluding RECEIPT.json) |
|---|---|---|
| `/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards3` | `892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65` | `30425d27563d87f2d76052bcfd929f64ce476e42d99abaf8bada325084cd6652` |
| `/mpac/sdicks02/repos/clasher-bot-runtime/live16402c` | `a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb` | `7de3ed3cfb9516f626a6db11b7aabe2bde1f96adf5a09205a19b6abe42ed52b8` |

Native SHA256 in every root on every host: `326ce6f93c4db6a7bd15b667960a2d3ed40a0d48eab3badc9ddd181521996732`.

| Root | Host | RECEIPT.json SHA256 | Runtime(verify=True) UTC |
|---|---|---|---|
| r1-cards3 | 127x03 | `e90489148b1e08930f32f9dc84724e9ba7f44aa9df3e0adb65f202b43942ff61` | 2026-10-16T19:38:22Z PASS — [receipt](../release/r1-cards3/CREATE-03.json), [verify](../release/r1-cards3/VERIFY-03.json) |
| r1-cards3 | 127x04 | `0e0de113e68b73895259a8ec760b146847ba43fc87c86454008ab06847e543c7` | 2026-10-16T19:35:12Z PASS — [receipt](../release/r1-cards3/CREATE-04.json), [verify](../release/r1-cards3/VERIFY-04.json) |
| r1-cards3 | 127x08 | `86a62b245ac7c1be7f40d52730a7bfca727cdcb0f9ce669898700663efda8221` | 2026-10-16T19:35:12Z PASS — [receipt](../release/r1-cards3/CREATE-08.json), [verify](../release/r1-cards3/VERIFY-08.json) |
| live16402c | 127x03 | `0b8701c289ebfc81269847979c6219957b1a6ba6eb0a62eaafefd80005096619` | 2026-10-16T19:42:24Z PASS — [receipt](../release/live16402c/CREATE-03.json), [verify](../release/live16402c/VERIFY-03.json) |
| live16402c | 127x04 | `4617b19092b7fdc7a2114704b7468c6a514522dfdbe93ffed92ce9a7a5b160be` | 2026-10-16T19:36:43Z PASS — [receipt](../release/live16402c/CREATE-04.json), [verify](../release/live16402c/VERIFY-04.json) |
| live16402c | 127x08 | `2e0891da57f5952fcd292182af0b22838df14a4ff30d50ee7bbdbef5072270ac` | 2026-10-16T19:36:40Z PASS — [receipt](../release/live16402c/CREATE-08.json), [verify](../release/live16402c/VERIFY-08.json) |

Each verification checks all 476 overlays, native/data/checkpoint pins, full content/modes/symlinks before/after Runtime, read-only permissions and unchanged pre-existing r3 roots. All roots have 121 metadata cards, 142 bodies and 359 templates; config entries are 237/238. Complete read-only content manifests agree per root across hosts. Per-host receipts include host/time and actual parent inventories; canonical portable RECEIPT.json files are the 04 copies. [Aggregate release verification](receipts/RELEASE.json).

## Final gates

| Gate | Outcome |
|---|---|
| Runtime dev smokes | 2/2 PASS |
| K4L HEADLINE vs r1-total, cases 0–5 × R3a/v1 | 12/12 command SHA256s identical; 24 successful arm rows |
| live16402c totality, root/runtime × plain/scrub | 26,828 probes; 0 panics / 0 unexpected errors |
| Full-pool None-stat, both data roots | 38,842 checks each; 77,684 total; 0 exceptions |
| Full corrected v3 template class | 122 definitions / 366 scenarios / 96,792 checks / 0 exceptions |
| Class coverage | 191 observed/materialized objects; 144/144 config identities; 359 templates |
| Mixed LIVE K4L + fast | 6/6 runs, 0 crashes/panics/native/search failures; one handled graph fallback |
| Filesystem release controls | 5/5 PASS: no-replace, external symlink protection, inventory drift, output refusal, parent/source invariance |

[Current GATES.json](receipts/GATES.json), SHA256 `4b11a473294d6419274fe5403851f99e341502fdac5664541c2321c151028f72`; [full class aggregate](receipts/CLASS-V3.json). Class runs cover both seats, Python/native, combat/death/lifetime with the original 450/450/1500 tick limits. The full class run uses live16402c-dev; both data roots have verified matching identity inventories. Totality executes 6,707 probes per variant. Plain variants retain 244/243 deliberate unsupported-card rejections over 68/67 cuts; scrub variants have zero failures. The optional old-script rank comparison was not rerun; HEADLINE supplies the requested C56 command-stream parity. Lead’s separate B1+B2 gate passed 577 fixtures, 577 chains, 300+300 roots, stun 192/192 and merge review.

## Source and assembly

Exact engine source `8eaa7d1ecac2f46a2c7d8d512a46ba4f03f7cb63` (main+B1+B2), with accepted r3 fixes from ancestor a6a5401c127b. Native copied from 08 `jobs/clasher/cards/b1b2/out/clasher_core.abi3.so`, built 2026-10-16T17:12:53Z–17:13:23Z. All 507 tracked engine build-tree files match; source export has 508 files including fair_player.py. [Source audit](receipts/SOURCE-AUDIT.json).

Dev roots on 08 remain `/mpac/sdicks02/jobs/clasher/cards/runtime/r1-cards3-dev` and `live16402c-dev`. Build_runtime.py overlays the exact engine/native onto a private ordinary copy of immutable r1-cards2-r3. Build_live16402.py regenerates the same 79-slot overlay from all four hash-checked live16402b inputs, reproducing the exact a7de3e93 gamedata. [Assembly receipt](receipts/ASSEMBLY.json). Native/data/checkpoint pins, full scope/fc_side_cut, Fireball/Poison settings match the new PIN_SETS.

Read-only snapshots are copied without hardlinks, verified against source manifest `ccb6a89141cfcbd9344aa4e61978b8b1167c6f029e97083a0863b2c9892f6563`, then staged/frozen and atomically published with NOREPLACE. Existing targets always stop. Receipts preserve assembler/parent receipt hashes and source inventories. Original dev roots and all old releases stay unchanged. Release tool hash `0b2afd9cf99a40b59e749bf15b819dc62d9d11290f701b0248b7bf37d19a23e8`; committed/verifier runtime.py hash `24e98fd761767f3ed1a2f3add4321ab7996ccd2b533039a5cb126e0632579787`. [Release tools](tools/release.py), [controls](tools/test_release.py), [publication wrapper](tools/release_host.sh).

## Harness corrections and retained history

B1 gives Three Musketeers real HP and three mechanical names sharing an explicit public identity. The final None-stat probe removes HP only from private scripted-body metadata copies, verifies HP=None and the 100-HP fallback, runs all original mask/rank/candidate checks, then restores metadata. Public packets, real battles and native configs stay unchanged. The class probe validates explicitly declared public aliases with exact tokens. Four stdlib alias controls passed. The isolated attached-rider positive fixture now includes the nearest actually observed same-team parent, preserving positions/identity and keeping all root/translator/native checks. No production policy or native was changed.

Original None-stat assertions, 18 obsolete raw-name class assertions, and four correctly rejected orphan-rider roots remain preserved. Focused corrected v3 passed 6/6 before the independent full-v3 rerun. The earlier stop instruction was obeyed; publication resumed only after the lead’s explicit adjudication and full PASS. [Historical stopped PHASE1 receipt](receipts/PHASE1.json), [stop audit](receipts/STOP-AFTER-FAILED-TEMPLATE-GATE.json), [alias controls](receipts/HARNESS-CONTROLS.json). Partial/failed runs are not counted as PASS.

## Known issue and caller contract

**GoblinGiant rider-graph fallback — nonblocking, routed by CARD LEAD to B1 owner.** One original LIVE B1B2B game recorded one PublicGraphError (`parents=1,riders=2,matched=1,unsupported=[13]`), one root error and fast fallback. It completed without a crash/panic/native/search failure. Other mixed runs have zero errors. These are no-crash tests, not proof that every GoblinGiant public board reconstructs or that every non-C56 mechanic matches live.

Mixed tests use two decks in both seats, LIVE K4L-w200-t2-p2 and pure fast-it5s2, max 2,401 ticks. Four runs use the random legal-mask opponent; two additional runs prioritize a legal ThreeMusketeers play then resume random behavior. Both extra runs deploy 3M with zero errors. Decks include Royal Giant, Three Musketeers, Rune Giant (GiantBuffer), Battle Healer, Freeze, Rage, Clone, Graveyard, Goblin Giant, Royal Recruits, Lumberjack, Skeleton Barrel, Goblin Cage, Tombstone, Fisherman and Electro Wizard. A run may terminate naturally or at the stated bound.

HEADLINE uses K4L-R-gs-rw-fc-p2, R3a/v1, cases 0–5, one worker plus two rollout workers. Baseline is unchanged r1/r1-total/native-total-r1; candidate is r1-cards3-dev. Evaluator base e5c11345d plus new pins; four callers are frozen at accepted r3 source a6a5401c127b for final HEADLINE/mixed measurements: bot/live/player.py, bot/search/candidates.py, bot/search/lopp_fast.py, bot/search/players.py. Current e883a80da callers import slot_permission outside the engine-cards/r3 package; the initial 12 import-error rows are retained and not counted. These results qualify the r3 caller contract; current slot-permission callers require their owner’s matching package. Runtime/probe/release verification uses the matching pinned resource package. [Exact evaluator hashes](receipts/EVALUATOR.json).

All compute used03/04/08 only (Phase1 on04/08), normal CPU leases ≤4 (release 1), nice 15, fixed hash seed and single-thread libraries. No sealing, emulators, crontab, tailscale, model/account/default/live-selection changes. Raw snapshots/stat inventories/overlay details remain outside git, under `jobs/clasher/cards/r1-cards3-phase1`. The task’s edits were moved from b2 to cards/lead after merging requested main a156cf5b1; unrelated lead edits including the Mac pin remain preserved.

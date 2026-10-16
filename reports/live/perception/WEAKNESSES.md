# LIVE perception weakness audits (newest first)

Standing duty of `live-perc-r3` (PROGRESS-R3.md HANDOFF, duty 2): every live session or ≥ every ~3 h while the ladder runs, review the
busiest live frames (live model and current best YOLO) plus held-out replays through the best YOLO candidate; list misses, merges,
wrong owners, wrong classes and phantoms with counts; give each item a DATA fix and, if it recurs, an eval slice that joins the gates.
No hand-coded rules. Overlays and frames stay on 05 scratch (`/mpac/sdicks02/scratch/live-perc-r3/audit-<date>/`); nothing here is an image.

Tools: `live/perception/yolo/{audit_dense.py (scan + sheets), error_list.py (held-out errors), damage_recall.py, gate_table.py}`.
Thresholds: score .5, ≤ 1 tile. "damaged" = level badge or HP bar visible in that frame.

## 2026-10-16 07:11Z: audit 1 (s20–s22 live on r5e3; held-out replays; Sam's s22 report)

Inputs: EVAL-SPLIT held-out (227 frames, 833 truth units, damaged flags on every unit) through r5e3 (live) and YOLO `v4lo1024-e16`
(candidate sent 07:09Z); 41 dense live frames from s20–s22 (40 random from the busiest 15% by YOLO unit count + overlaps, seed 20261016,
plus s22-m04 n=973) under Sol review (`aud1`, pending; results appended below when it lands).

### Sam's frame (s22-m04 n=973, tick 2022, "it only sees 1 archer")
Truth: 2 enemy Archers stacked at the left bridge (one partly behind the other) + 2 own Minions below the enemy right princess tower (a
third already dead), all undamaged except the Archers' red badges.
- **r5e3: 1 Archer + 1 Minion.** Cause from its raw heads: the two Archers form ONE heatmap blob (cells .81/.81/.77 over 3×3 cells), so
  peak extraction (3×3 max-filter on 0.5-tile cells) yields one peak, a **merge**. The second Minion IS a separate peak but scores .31
  (first .53), below .5: the **undamaged-unit low-confidence** pattern (no badge). ft-r6: same (.48 / .23).
- **YOLO V4lo-e14: all four bodies, right teams** (Archers .94/.87, Minions .90/.81); v2l-e24 also 4/4.
- Fix: the model (box detector, per-body boxes), not a post-processing setting: lowering r5e3's threshold to .3 would recover the second
  Minion here but r5e3's own sweep shows precision falling elsewhere, and the merge is structural (one peak per blob).

### Held-out errors, r5e3 → v4lo1024-e16 (counts / truth units of that slice)
| pattern | r5e3 | e16 |
|---|---|---|
| miss Minions ours undamaged | 79/145 | 8/145 |
| merge Minions ours undamaged | 41/145 | **21/145** |
| miss Archers ours undamaged | 75/150 | 11/150 |
| merge Archers ours undamaged | 26/150 | 6/150 |
| miss Musketeer ours undamaged | 26/33 | 2/33 |
| miss MiniPekka ours (undamaged + damaged) | 40/72 | **25/72** |
| miss Knight ours undamaged | 14/21 | 0 |
| miss GoblinCage opp | 17/20 | 2/20 |
| merge opp swarms (Skeletons, Minions, SpearGoblins, Barbarians, Goblins) | 30 | 10 |
| wrong-class Tombstone/SpearGoblins/Barbarians opp | 24 | 3 |
| wrong-owner | 3 | 6 (1 each: SpearGoblin, Archer, Musketeer, MiniPekka opp→ours; 2 ours→opp) |
| phantoms | 16 | 40 (minion ours 12, valkyrie ours 5, mini-pekka ours 5, archer ours 3, giant opp 3) |

### Live dense frames (aud1, Sol review, 41 sheets, 324 visible unit bodies; YOLO panel = V4lo-e14 on 40 of them)
Counts are bodies (merge = bodies lost to a merged detection). `review-live.json` on 05 scratch has every item with its frame id.

| kind | live r5e3 | YOLO V4lo-e14 |
|---|---|---|
| miss | **160** (49%) | 13 (4%) |
| merge (bodies lost) | 55 | 15 |
| wrong owner | 4 | 6 |
| wrong class | 11 | 2 |
| phantom | 2 | 6 |
| card attribution (right body, card name of another card, e.g. BarbLog on a Barbarian) | 10 | 0 |

Top live (r5e3) patterns: miss Minions ours undamaged **66**, miss Archers ours undamaged 26, merge Minions ours undamaged 19, miss
Skeletons ours undamaged 15, merge Barbarians opp 13, miss Goblins opp 7, miss Giant opp 6, wrong-class Barbarians opp 6. This is
Sam's report in numbers: on the busiest live frames r5e3 misses about half of all bodies, mostly our undamaged swarms.

Top YOLO patterns: merge Barbarians opp 5, **phantom Skeletons ours 4 (on our Skeletons' deploy clouds, before bodies appear; s22 is the
first session with Skeletons in our deck)**, miss Archers ours 4, merge Minions ours 4, merge Archers ours 3, **wrong owner 6: enemy
Musketeer ×2 (both above the left bridge), enemy Knight, Barbarian, Goblin, Bomber tagged ours** (each next to one of our units).

### Weakness list (e16 = the next live model) and fixes
1. **Own Minions merged (21/145) + minion phantoms (12).** Mechanism (one box spanning two bodies vs a box
   between them) to be confirmed on the aud1 sheets. Fix (data): own-deploy labels from s20–s22 (Sol own-1..4, one tight box per body, 160 frames) and compositor crowded
   swarms with per-body overlapping boxes (v1team3). Slice: swarm per-body recall is already a gate (≥ .80).
2. **Own MiniPekka missed 25/72.** Of the 25: 5 have a mini-pekka box within 0.7 tile at score .33–.47 (low confidence), 3 a box
   1.0–1.3 tiles ABOVE the truth point (ground point too high: attack pose / the box's bottom edge), the rest no nearby box. Fix (data):
   own-deploy frames include 30+ own MiniPekka deploys; ask the compositor for more MiniPekka (both teams, attack poses). New slice:
   **per-card recall for our deck cards** (MiniPekka currently .65) joins the gates if it does not recover in V6lo.
3. **Valkyrie / MiniPekka own phantoms (5 + 5).** Not yet inspected (duplicate/offset boxes vs real
   misplacement); aud1 will show. Same data as 2.
4. **Enemy copies of our cards tagged ours** (Musketeer, Knight; v4lo-e14 4+3, e16 1+0): mirror-battle labels (Sol hard2-1..3, 120
   frames) + equal official-art rates per team in v1team3. Gate already (≤ 3%).
5. **Live loop (not perception): logged card ≠ played card.** In the 135 own deploys sampled from s20–s22, the card in
   `decisions.jsonl` differed from the card that appeared on the field 0/47 (s20), 1/50 (s21), **6/38 (s22)** (e.g. logged Minions →
   Giant / Archers / Valkyrie played; logged MiniPekka → Valkyrie / Musketeer). s22 is the first session with Skeletons in our deck.
   Reported to the LIVE LEAD 07:18Z (hand read vs tap slot). Perception labels use only visible units, so they are unaffected.
6. **Deploy-cloud phantoms (YOLO, own Skeletons).** Fix (data): deploy-cloud frames as negatives: the OWN labels already treat
   clouds as "not a unit yet" (brief rule) and include s22 Skeletons deploys, so V6lo/V7lo1024 see them; ask the compositor for
   deploy-cloud/clock overlays without boxes. Watch in audit 2.
7. **Enemy units tagged ours next to our units (YOLO 6 in 40 live frames; e16 on held-out 4/240).** Musketeer again the top card. Fix:
   mirror labels (119 frames) + v1team3 now in training (V6lo, V7lo1024). Slice: owner gate already; audit 2 rechecks on live frames.
8. **Enemy Barbarians merged (YOLO 5, r5e3 13).** Five bodies in a tight pack. Fix (data): compositor crowded Barbarian packs with
   per-body boxes (requested 07:22Z); slice: add Barbarians to the swarm per-body gate once ≥ 20 held-out bodies exist
   (held-out now 16).

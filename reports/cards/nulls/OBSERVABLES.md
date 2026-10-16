# Focused measurement contract

This describes derived observations, not captured results. Raw native data remains
in jobs. Every measurements document supplies `arm` (`native`, `ours`, `rsim`),
`scenario_id`, `script_sha256`, `replay_sha256`, `native_version`, `provenance`, and
an `observables` mapping. `native_version` identifies the originating fixture;
the actual simulation ruleset/table belongs in `provenance`.

Example **template**, with placeholder measurements to replace from evidence:

```json
{
  "arm": "native",
  "scenario_id": "GoblinCage.giant",
  "script_sha256": "<scenario hash>",
  "replay_sha256": "<actual native opening state and accepted script hash>",
  "native_version": {"client": "15.535.13", "content": "15.535.86"},
  "provenance": {"raw": "<jobs path>", "attestation_sha256": "<hash>"},
  "observables": {
    "GoblinBrawler.first_impact_after_ready": {
      "value": null,
      "available": false,
      "classification": "mechanics",
      "field": "first_impact_after_ready",
      "unit": "ticks",
      "tolerance": 0,
      "evidence": "<rich stream ticks, body/parent/target identities, controls>"
    }
  }
}
```

`available=false` means unmeasured. `value=null, available=true` is allowed only
when the evidence actually proves the event did not occur over the full stated
window. Every observable needs evidence in each arm. Use identical field, unit,
classification, tolerance and `multiset` contract in all three documents.

Additional metadata such as `preconditions`, `stat_control`, `basis`,
`raw_sha256`, `first_divergence`, `repeat_id` and `coverage` may accompany an
observable; keep the raw values and explain any normalization. The helper does
not infer that a reviewer has established those controls.

| Observable | Required evidence / control | Classification |
|---|---|---|
| Max HP, configured damage/speed/hitSpeed/loadTime, shield capacity, configured radius/duration | Actual instantiated/native-level value; distinguish base versus level-scaled values | stat |
| Initial direct summon birth/deploy stagger | Accepted command + identical script, prior empty arena, no combat dependency; per-body/wave positions | mechanics |
| Brawler deploy-ready minus birth | Actual deploy gate in rich runtime; same initial conditions and death release; do not infer ready from first movement | mechanics after phase verification |
| Brawler first launch/impact minus ready | Already-in-reach target at ready, no movement, no intervening freeze/stun, explicit load stat or version control | mechanics after stat/phase verification |
| Tombstone death child birth displacement | Same death anchor/target geometry; distinguish birth frame from next frame and death wave from periodic children | mechanics after reach/phase verification |
| Minion/Princess first local target/launch/impact divergence | Shared causal state before the divergence, target identity and range, load/hit/projectile clocks; compare Wizard control | dependent until controlled |
| Witch wave semantic records | Complete per-unit records joined within a wave by parent/root, birth and geometry; full records compared as multisets, not separately sorted columns | ordering with multiset=true |
| Enumeration order | Native object order/IDs retained separately; reused RS array slots cannot establish gameplay priority | ordering |
| Attack interval | Explicit configured hitSpeed and whether haste/stun/retarget intervened | dependent until clocks controlled |
| Mortar rejects target inside min range | Positions, hitboxes and configured min range; exclude lack of readiness/stun as alternate cause | mechanics after radius control |
| FlyingMachine cannot be targeted by Knight | Both bodies alive/in range, Knight otherwise ready and path/target trace shows eligibility | mechanics |
| Shield break absorbs overkill | Shield before, impact amount, HP before/after, no concurrent hit; lethal capping accounted for | mechanics |
| DoT/heal/cast order, stun/freeze entry and reacquire | Tick-local status/HP/phase evidence, attribution, configured duration/control; no ring gaps | mechanics after stat/phase verification |
| Spell target set or boundary | Positions, hitboxes, radius and target cap/tier; moving-target geometry must be matched | dependent until geometry controlled |
| Clone count/offset/flags or Curse conversion | Parent/source mapping, kill ownership, full newborn set and first update; clone/curse aliases normalized only semantically | mechanics after trigger verification |
| Graveyard coordinates | Same-seed native repeat plus independent seed set; unrelated native/Python/RS PRNGs do not imply equal coordinates | stochastic |
| Graveyard spawn cadence/readiness | Actual birth and deploy gate on each skeleton; condition on spawn ordinal/event, not PRNG coordinates | mechanics after phase verification |
| Death, lifetime outcome, total damage, hit count, aggregate tower result | Changes to HP/damage/speed/range/duration can alter all downstream decisions | dependent |

Target/source keys and birth/death events from phase/combat rings must refer to
the same generation/epoch and complete tick window. Top-level `truncated=false`
does not establish that a bounded diagnostic ring never overwrote events. When
that cannot be checked, positions/HP at tick boundaries remain observations but
the unobserved intra-tick order is **missing evidence**.

The legacy HP loader intentionally excludes projectiles, spells, bombs and areas.
Use retained rich frames for those; do not turn their absence in `Fixture.units`
into an assertion that the mechanic is missing. `replay.py`'s common HP trace is
insufficient for a bomb fuse, projectile source, clone flag or status timer; a
focused engine measurement must use the reviewed adapter's real runtime state.

For a matched-state control, either use the nearest old-table RS arm and a
separately reviewed same-stat scratch engine, or a nonlethal/phase-local native
observable that does not depend on differing values. The native collector itself
does not patch stats. If the control cannot be established, leave the result
dependent or unavailable; that is a useful exploration finding.

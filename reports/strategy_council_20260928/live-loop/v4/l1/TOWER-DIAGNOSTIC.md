# Tower validation diagnostic — 2026-10-09

This is a diagnostic of the completed **epoch 2**, fixed body threshold **0.5**, event threshold **0.5** capture. It covers all 64 validation matches / 106,744 frames. It is an early, unselected checkpoint, not the Mac suite, a selected model, a heldout result or a change to any gate. Completion clocks were never opened. Input and source SHA256 values are in `receipts/tower-diagnostic-20261009/epoch02-body05.json`; execution exited 0 on 09 at 01:36:28Z.

Identity presence requires correct native side, exact tower identity and distance <=3 tiles from its known anchor. Tower and PrincessTower are not silently equated for exact identity; both are included in the diagnostic spatial tower family. Native owner 1 is own, 0 opponent. Only coherent, visible, non-deploying, positively identified native truth with HP>0 enters the alive denominator. Coverage is sparse: only 2,380–2,759 eligible observations per anchor out of 106,744 frames (2.23–2.58%). Unknown/absent truth is masked, never declared destroyed. No explicit zero-HP eligible observation occurred, so destroyed-state accuracy is **unmeasured**. Native truth is diagnostic evidence, never input to a public runtime.

| Tower | Eligible alive frames | Correct identity among candidates >=0.1 | Correct emitted identity at body0.5 | Candidate present→missing / preceding-present pairs |
|---|---:|---:|---:|---:|
| opponent king | 2759 | 149 (5.40%) | 0 | 11/48 |
| opponent left princess | 2703 | 2642 (97.74%) | 0 | 1/647 |
| opponent right princess | 2424 | 2375 (97.98%) | 0 | 2/595 |
| own king | 2759 | 2606 (94.45%) | 0 | 3/624 |
| own left princess | 2380 | 2367 (99.45%) | 0 | 2/587 |
| own right princess | 2667 | 2649 (99.33%) | 0 | 2/650 |

At threshold 0.5, all six correct tower identities were absent on every eligible alive frame. The own King was missing in 2,759/2,759 eligible alive observations. A missing packet therefore cannot establish destruction. Emitted-identity dropout **conditional on a previous correct emitted detection is undefined** here: there were no such detections; reporting zero transitions as stability would be misleading. Candidate dropout counts above use adjacent source frames with eligible alive truth on both frames, resetting across unknown truth and match boundaries. They do not describe the selected model.

Low-threshold records show strong identity duplication: both KingTower and PrincessTower appear within the own King anchor radius on 2,051/2,759 eligible frames (74.34%). The same mixed labels occur at own left/right princess anchors on 2,361/2,380 and 2,645/2,667 frames. Opponent King identity recall is only 149/2,759 (5.40%), while any tower-family identity is present on 491/2,759 (17.80%). These are diagnostic confusion/duplicate counts, not calibrated probabilities or formal precision. This capture does not establish the Mac report's specific HP≈0.123 phantom rate.

The implementation independently confirms a temporal hazard: BodyTracker retains unseen tracks internally up to 600ms, but returns only tracks observed this frame with at least two hits. Internal retention is not packet persistence. A one-frame missed observation can therefore remove a tower from the published body list while it is alive.

**Recommendation:** use a dedicated public tower-state channel for six stable side/slot identities, visibility/confidence, HP-known state, last observation and explicit destruction evidence. Anchor identity should come from public arena geometry; missing observation should be unknown/occluded, not destroyed. Persist a previously observed living tower until an authenticated public destruction signal; do not make up HP or derive a terminal result from detector absence. Keep HUD slots/elixir and tower HP/state as typed channels separate from transient body detections. Test initialization, intermittent misses, identity duplicates, contradictory HP and genuine public destruction separately. This is runtime architecture advice only; raw captures, sealed evidence and frozen L1 gates remain unchanged.

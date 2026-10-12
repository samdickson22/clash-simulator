
## 2026-10-12 09:17Z: 08 released to perception B (GO); 01 stays T1-reserved

T1 END timing is complete: the pool was committed at 95774e86 and only release paperwork remains. **127x08 is released to the perception owner for B.**
- **Frozen on 08:** all T1 paths (`t1-*`, `fleet-end-attempts-0108*`, `end-*`) stay untouched until release, because R7 re-lists the host roots.
- **How B runs:** under nice, with headroom, after checking `who`.
- **Plan first:** the B plan gets posted before it runs. Anything beyond these limits needs my approval.

**127x01 stays T1-reserved.** Its four job directories are frozen, the hub mirror stays paused, and 01 holds the only copy of the counted blocks. A durability copy and the mirror retarget come after the release review.

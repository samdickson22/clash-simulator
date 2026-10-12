
## 2026-10-12 10:38Z: Registration prep: golden-order ruling (conditional)

T1's metadata diagnosis compared the delivered sets with the actual A5 sets.
- **Speed:** all 4 lists match the A5 sets byte-for-byte and in order (300 each).
- **Golden:** the same 125 IDs, with none added or missing, but in a **different order**.

The stop came from T1's own extra ordered-equality check, not from any handed-off SHA or count.

**Ruling:**
- Speed keeps exact-order equality.
- Golden switches to membership equality, keeping the **A4-delivered order**. That is the order the fixture fingerprint 0de69958 and the Mac run use, so registration seals that order.
- Condition: T1 first proves with file:line evidence that every consumer of `sets.golden` keys by state ID, not by position. The consumers are the exactness checks, the Mac-vs-END comparison, the registration seal and `fleet_pool`.
- Any dependence on position means STOP, with no reordering.
- The builder's independent answer has to agree.

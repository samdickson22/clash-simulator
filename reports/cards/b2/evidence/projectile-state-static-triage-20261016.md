# Static continuation triage while semantic-v1 awaits admission

2026-10-16, before affected dynamic results. This note changes no comparator rule,
engine source, approved script or acceptance verdict. Semantic-v1 remains strict
for every field beyond its reviewed finite cache applicability and strict-r2 baseline.

`lib.rs:2380 combat_one` creates a character shot with `let mut shot = a.clone()`.
It retypes to Projectile, clears target/route/goal and sets flight fields, but also
retains other actor history. Python creates a fresh Projectile in
`entities.py:4159` / `entities.py:5109`; differential/live_snapshot exports its own
fields. Thus a longer comparison may expose additional **preexisting** observation
or state differences once ranged actors shoot. This prediction is not evidence
that any particular dynamic case fails, or that the fields are safe to omit.

Fields needing diagnosis **if observed** include deployed `age`, ordinary actor
clock/target history, actor stats such as max_hp/sight, and route/heading metadata.
Current v1 permits its existing narrowly scoped Tower-arrow exclusions only;
other projectiles retain strict comparison. Source actor buffs, targets and hit
history must not receive a blanket exemption.

`tick_once` combat dispatch, periodic damage and actor buff aging are class-gated
to Troop/Building (`lib.rs:2914`, `2950`, `2957`). This alone is insufficient to
prove arbitrary projectile fields inert: flight, impact, child creation, death
and leaf exports still need their own read/propagation analysis. A raw mismatch
must remain FAIL under the current contract. Do not copy current shooter state
into the expected projectile to reconstruct unknowable birth history, and do not
extend exclusions case by case to manufacture a successful semantic receipt.

The reviewed v1 continuation deliberately records all distinct semantic deltas
while digests agree. Use that evidence to distinguish a meaningful engine defect,
an independently observable exporter error, or a separately justified applicability
proposal. Any changed host script needs independent review before affected execution;
the existing single queued run3586969 and frozen original3422841 stay untouched.

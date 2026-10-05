# L1 v2 event experiment

Use the unchanged offline native renderer and the v1 pixel boundary, geometry,
body checkpoint and HUD reader. Native state is collection/scoring truth only.
The temporal detector receives sanitized images, media time and v1 predictions.
It never receives commands, deck assignments, event labels or native objects.

Freeze eight seed/deck pairs before collection: four training, two validation,
two heldout. Complementary decks cover P16 on both sides within every split.
Exclude all earlier L1 decks. Collect each tick from six ticks before to thirty
ticks after scripted commands, plus deployment-free windows. Heldout matches
retain the continuous tick stream, including intervals without commands.
Single-tick native advancement and unchanged observations across capture are
required. Screenshot production timestamps are checked after stepping. The
unchanged renderer has no compositor fence, so exact pixel/tick alignment remains
a measured limitation rather than a claimed guarantee.

Use temporal pixel differences and short image stacks to recognize deploy clocks,
spawn appearance and spell effects. Fuse these with persistent v1 tracks and own
HUD changes. Choose thresholds on validation only. Freeze inference before
scoring heldout events with one-to-one matching, correct side/card, causal delay
at most 500 ms, and placement error at most one tile across all true events.
Sample the tick stream at 10 and 10.9141 FPS; 20 Hz is diagnostic only.

Copy the exact public-state implementation into v2 before extending it. Permit
event uncertainty and recovery from inconsistent histories without reading private
state. Evaluate all frames, counting unknown hands as failures whenever the
true-event reference determines the hand. Run separate seeded event corruption
experiments with misses, insertions and wrong identities. No truth repair enters
perceived-state inference.

Limits: one 3072 MiB, two-core emulator; game UID IPv4/IPv6 egress REJECT rules;
no external connections. New data <=1.5 GiB, total live-loop <=4 GiB. Raw pixels
remain in memory and are immediately masked and JPEG-encoded. Do not delete v1
or foreign artifacts. Record source hashes, dataset hashes, process ownership,
timing, split coverage and failures. Passing isolated-event diagnostics alone
does not establish L2 readiness.

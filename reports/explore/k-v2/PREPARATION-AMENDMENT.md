# K-v2 preparation amendment

Recorded 2026-10-10T02:05:33Z before any retained reporting game.

First excluded smoke exposed21 cut calls beyond deadline+8ms. All had completed=0/fallback. A stage-timed replay locates a191ms call in165ms belief update, with only0.16ms GC. The worker collector itself already returns without drains. The reporting attempt admitted01:55:10Z was stopped01:55:30Z with zero terminal games; no reporting outcomes were read. Its receipts/partial work are retained and excluded.

Owned belief.py retains the frozen no-deadline implementation. Timed updates execute identical posterior row transformations in4096-row blocks and commit only complete public histories. Cutoff suspends the private transaction; next decision completes that history before processing newer events. State/weights/order/resource ledger/sampling/RNG remain exact when work completes. Sampling derivation is similarly bounded by rows. All arms, including K0, receive this exact preparation fix. The K4 scorer, deadline/reserve, native44874fd6, v1 adapter and all scientific seeds/statistics remain unchanged. Preparation time remains inside the full timer. No work is moved outside the timer.

Four additional tests prove exact posterior/ledger/sample/RNG equality, cancellation without partial publication, resume into newer public events, and deadline-off equality. Full125-history ON/OFF audit is required before smoke-r2/reporting-r2. Diagnostic replay after fix:160 calls, no overrun, maximum119.4ms at120ms deadline. Repeat all32 excluded smoke games, require zero cut calls beyond deadline+8ms before reporting-r2. Archive the owned K-v2 STOP, retain G STOP-03, do not restart G.

# Shared03 admission receipt repair

The 09:21:24Z proposal staging attempt1 exited before copying proposals or
scoring, because the shared freeze statically pinned pre-shared admission bytes.
The 07:49:13Z shared admission refreshed the authorized lane and bound the new
freeze; its bytes necessarily differ. Preserve all old receipts and failed log.

Remove only the circular static admission-file pin. Instead validate the receipt
against the current pushed evaluation SHA, pinned grant and drain evidence, exact
56–59 lane, Other/nice10, manager59/three workers56–58 and max4 processes. Every
other static source/native/input pin and actual G/STOP/memory guard stays intact.
Nineteen injected AST tests verify incomplete replay and stale/forged admission
rejection. Commit/push/scan before deploying and refreshing the admission.

After independent attempt1 vacancy and fresh guard audit, manually launch
proposal staging attempt2, then the original once-only regret-pool-attempt1.
No model/scorer/gates/calibration/seeds/reduction changes; no scoring outcomes
exist yet. The failed preflight preceded the meter: retain that limitation as
small unmetered failed-preflight CPU overhead, rather than inventing a zero.
All three arms remain binary-killed; no Stage2/timing03/01 games or G stop.

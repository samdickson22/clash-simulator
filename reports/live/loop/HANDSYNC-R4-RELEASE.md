# Handsync and conservative navigation r4 — independently GO

Deploy ONLY the following four frozen files (all source/test hashes in SHA256SUMS):
- live/loop/drive.py df928901c4094cc73ec711d3ce28309bccdeff28840a9f35ff78cfbda4504bc4
- live/loop/handsync.py 2a518add1abd0dceb49fa0246c4ad42cffefe7d9611cd0ce763501b2b49f1a38
- live/loop/handui.py b972af1ab914a6a8ecbd3b2280bc802a625f078c4004921e5dd5ccaa4e81ed1e
- live/loop/screens.py e0eec3039cc129b72f2e25d0e730dc9381b377d5a6d8f0eab26062be7607c4cd

Exact installed driver base required: aa98505f02932bd63163ad0e4176c1e1078690734cc3f9d38753d77c0e7d17da (reviewed capture-only, deployed31→32).
Preserve tower58033f080ecafe1f80d45e43c287253cd0ebd5010f04de695f3cad060edbfdf4, adapter091350df, models/runtime/exports/deck/pins/args/--perc-threads. No manifest/guard WIP. Capture LiveFrames/ReplayFrames and background event AST identical aa98505; no secondary grabber helper. preservation.json and drive.diff record exact comparison.
Tests/report_run.py are05-only; do not ship them to host. Viewer overlay modules are a separate independently reviewed package and remain untouched here. Shared dirty drive.py is NOT this candidate; commit/copy only isolated package bytes.

Prior findings and response
R1 GO AFTER FIXES / autonav NO-GO fixed busy source/destination protection, reliable confidence, finite opening/refusal bounds, exceptions/no tap, distinct captures and no unsafe generic reward tap.
R2 GO AFTER FIXES fixed phantom acknowledgment from grey/low-confidence identity and same-poll replacement tap omitted by pending length1→1: use stable positive empty or reliable coloured replacement per command/capture, and monotonic queue.submitted.
R3 GO AFTER FIXES (NOT accepted): during gap catch-up current/buffered external events are stripped, permitting HUD synthesis then a duplicate tracker mutation despite public event guard. R4 suppresses UI-based confirmation in catch-up only, preserving actual-poll complete external event check and capture identity; no-UI baseline remains unchanged. Host delta r3→r4 is only handsync.py, driver unchanged df928901. No runtime/model strategy change.

Checks and evidence
- R4 selected command_path_test.py10/10, exact pinned queue AST plus actual SyncSession/Translator/accept_events/OwnCycle/DerivedD1, verbatim driver submission predicate and AdbTaps writer into StringIO. Prior7cases plus current external-event gap, buffered external-event gap and HUD-only gap: exactly1tracker play/no own_reanchor or cycle conflict, exact expected hand+queue and1correct Fireball replacement submission/tap. /tmp/handsync-r4-command-probes.json, package command-probes.json. Test SHA7b306bcd8a408d3916840b9423f92b5fcf04aebfe9f0abd7538987dd6f5719fe.
- R4 module64/64 /tmp/handsync-r4-module.log. Exact commands/failures in COMMANDS.txt. No Runtime/model initialization for these probes.
- Prior unchanged driver screens/handui exceptions, LL_HANDSYNC0 import bypass, latched hold/no autonav all passed /tmp/handsync-r2-driver-0whfjcha. Actual normal source7s fake-I/O SyncSession/Translator driver passed on r3 /tmp/handsync-r2-driver-672mw65g; one verified colored-card fake tap, no errors/holds; exact argv.json there. R4 host driver is identical and new gap logic covered directly with actual event guards. No full runtime rerun needed.
- Screens32/32 incl1437 calibration frames/55reward presenters None and syntheticBuyNone; reporter3/3. Prior tests not rerun without changes. No universal safety claim for existing Collection/Pass footer heuristics.
- R4 manifest11/11 passes; git diff --check in actual repository passes. No heavy replay/new enforced-efficacy claim. Historical measure-mode raw4/517 all4guardflagged,25baselineactions omitted; zero residual is not enforced recovery evidence.

Release gates and exact procedure
1. Fresh independent loop-handsync-autonav-review-sol-20261016-r4 is GO, no blocking findings (REVIEW.txt; original /tmp/handsync-r4-independent-review-a40gmJNy/REVIEW.txt). Parent scoped commit/required scanner/release remain. Frozen r1–r3 must NOT deploy. No blanket Opus hold; substantive failed checks still block. Any host source change requires rehash/delta review.
2. Sole babysitter stages ONLY four files to ~/clasher-live/tmp/handsync-autonav-r4 and verifies shasum -a256 against above. Resolve active code root from existing receipts; no new watcher/capture/helper or duplicate driver. At ordinary boundary verify driver gate empty and installed driver base exactly aa98505; different hashes require attribution, not overwrite.
3. Backup ONLY installed drive.py and any prior three helper files to unique .bak-pre-handsync-r4 in active code root; verify backup driver aa98505. Replace four reviewed files, verify exact hashes. Preserve deployed tower and viewer source, PAUSE/deck/control state, all authorized arguments/pins. Launch same authorized runtime/new unique session through existing reviewed launcher with LL_HANDSYNC=1 explicit.
4. Session-config must show handsync.SyncSession and handsync.SyncTranslator. Existing sole babysitter records guard/reconciliation/refusal/hold/elixir/FPS/decisionp95/navigation/errors/verified cards; capture/tower receipt separate. No new Mac script or capture client. Own PID only; never pkill.

Navigation/holds and rollback
Latched opening/refusal hold after24frames/refusals or6s is explicit fail closed; no forced taps, no bot/autonav across held false-match replacement. Known authorized manual free DailyBonus/Snippet/reward presenters remain UNKNOWN and nav_stuck is reported; sole babysitter may clear only known safe free flows with verified single taps and manual/account receipts under existing runbook. Unknown/unsafe/payment/signin/unclassifiable or cannot safely clear retains existing hold/escalation. No generic reward tap or hidden suppression of nav_stuck/errors.
Existing rollback criteria unchanged: traceback/step_error, refusalrate>10%, full>=9.5elixir>8s, nav_stuck under accepted known-manual interpretation, wholeFPS<7, decisionstep95>45ms. Fail-closed hold must be reported/operator resolved.
Quick hand rollback: at safe boundary restart same args LL_HANDSYNC=0, which does not import/call hand reader/session; navigation candidate remains. Full package rollback: restore ONLY exact driveraa98505 verified backup and any previous helper backups, safe normal-boundary restart; unused helpers can remain. Never restore fbf34ebe/oldautonav driver: that reintroduces second SCK. Preserve tower58033f and independent viewer package. No account/input changes by implementation/reviewer.

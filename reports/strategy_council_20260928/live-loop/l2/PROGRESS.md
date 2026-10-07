# L2 progress

2026-10-04: Read workspace instructions, L1 survey/results/progress, stream capture, v3 posterior, L3 plumbing, P16 mixture and C56 deadline player. Implementation is confined to this L2 directory. No evaluation games started. L1 has failed perception/timing gates; L2 will measure the resulting closed-loop cost without relaxing those findings.

Player boundary: bottom HUD is seat 1; opponent is seat 0. Only sanitized pixels and capture timestamps may enter the player. Probe state is restricted to lifecycle setup, opponent control, action submission and segregated evaluation receipts. Planned search deadline 200 ms. Foreign extraction, Stage 6, watchdog and caffeinate processes are preserved. One owned read-only offline emulator planned, network blocked before app launch; no official client. Output cap 1 GiB, at most three owned heavy processes. Resume from this file and owned launch receipts.

Preflight renderer launch and calibrated visual/legacy-hook tap trials completed. Network UID reject rules and pinned APK attestation verified. See touch-preflight.json and screenshots. Evaluation has not started.

Action calibration passed through adb using the existing 1080x1920 hook coordinates. Visual 1080x2280 taps caused no change at ticks 220-250. Hook-coordinate taps spent two elixir, replaced Log with Ice Golem, and spawned Log at x=6.5, y=22.62 after advancement from requested y=22.5. No command-channel action fallback is needed. Four adb tap durations were 67-132 ms individually; these are preflight timings, not end-to-end evaluation latency.

The first player smoke test reached the unchanged C56 controller and stopped at `ValueError: uncertain own hand or elixir`. Both public-script paths also require confidence-one Crown HP and body identities/geometry/HP. L1 supplies uncertain fields and no King HP reader. This is an integration prerequisite, distinct from its 64% event recall. No evaluation games have run. Investigating a transparent model-hypothesis boundary rather than altering engine guards or using native truth.

Terminal preflight at 4x reached tick 6068 and a visible Match Over / Tiebreaker banner; the probe reports finalized draw. The first attempted speed 16 was rejected by the unmodified probe; supported maximum is 4x. These are setup diagnostics only.

2026-10-04 20:56:31: Smoke pair -1 complete: frames=255, actions=21, terminal=False, pixel_end=False. No interim aggregate strength inspection.

2026-10-04 20:56:31: Native c56 worker finished.

2026-10-04 20:58:25: Native p16 worker finished.

2026-10-04 20:58:59: Worker exception; preserve all partial evidence. Traceback (most recent call last):
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 187, in <module>
    try:main()
        ^^^^^^
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 139, in main
    if operror:raise RuntimeError(operror[0])
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
RuntimeError: Traceback (most recent call last):
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 128, in opponent
    receipt=call(f'replay-schedule-card 0 {ids[card]} {round(x*1000)} {round(y*1000)} {at}')
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 54, in <lambda>
    call=lambda c:request(owner['probe_port'],c)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/sam/Desktop/code/clasher/scripts/smoke_reference_battle.py", line 21, in request
    raise ValueError(f"native command rejected: {result}")
ValueError: native command rejected: {'ok': False, 'error': 'scheduled replay action execute tick is not in the future'}



2026-10-04 21:03:08: Worker exception; preserve all partial evidence. Traceback (most recent call last):
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 189, in <module>
    try:main()
        ^^^^^^
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 154, in main
    action,diag=player.decide(public,public_tick)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/pixel_player.py", line 147, in decide
    ranked=r.bot._ranked_actions(packet,all_plays=True);script=int(r.bot.decide(packet).action_id)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/runtime/src/clasher/rl/public_scripted_opponent.py", line 213, in _ranked_actions
    packet.validate()
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/runtime/src/clasher/rl/public_observation.py", line 289, in validate
    _missing_values_are_zero(
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/runtime/src/clasher/rl/public_observation.py", line 183, in _missing_values_are_zero
    raise ValueError(
ValueError: hand ids fabricates values where confidence is zero at (3,): value=np.int64(1) confidence=np.float32(0.0)


Preregistration draft and 48-match schedule written before evaluation. Seed audit checked ignored/nonignored report text plus 3,946 NPZ files containing 124,196 seed values, with no overlap. The first C56 loop smoke completed 255 frames / 21 adb attempts in 35 seconds. Cold diagnostic latency was production-to-action p50 245.7 ms, p95 630.6 ms, max 2046.3 ms. Nine observed own hand transitions are not yet an audited acceptance count. Perception warmup was added before evaluation. Original confidence arrays remain logged; search receives a separate declared point model because the unchanged scripts reject uncertain sensor packets. This adaptation and missing King HP are limitations in PREREG.md.

P16 smoke r2 stopped on an opponent command scheduled too close to the current tick. Increased opponent lead from two to eight ticks and log dispatch rejection rather than aborting actor playback. P16 r3 launch vanished before output/exit receipt; no evaluation evidence exists for it and no duplicate worker remains. P16 r4 retries the smoke with explicit launch logging. A frozen L2-local copy of Python runtime sources and helper scripts avoids concurrent Stage 6 source drift; shared files remain untouched.

2026-10-04 21:04:34: Smoke pair -1 complete: frames=309, actions=21, terminal=False, pixel_end=False. No interim aggregate strength inspection.

2026-10-04 21:04:34: Native p16 worker finished.

2026-10-04 21:04:48: Simulator exception: Traceback (most recent call last):
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/simulator.py", line 77, in <module>
    try:main()
        ^^^^^^
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/simulator.py", line 10, in main
    r,_=setup(a.mode)
        ^^^^^^^^^^^^^
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/bootstrap.py", line 12, in setup
    from fair_player import Resources
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/engine-speed/stage5/fair_player.py", line 16, in <module>
    from differential import config, initial, entity, Position
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/runtime/helpers/differential.py", line 20, in <module>
    from es_common import battle_digest
ModuleNotFoundError: No module named 'es_common'


2026-10-04 21:06:42: Simulator pair -1 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-04 21:06:42: Simulator c56 worker finished.

P16 smoke r5 completed 309 frames / 21 adb attempts in 35 seconds after mapping unrecognized hand tokens to abstained slots. C56 clean-simulator smoke reached a real terminal at tick 3601, using the excluded native smoke's seed/decks/opening order. Frozen-helper relocation needed an L2-local CLASHER_ROOT fix; the shared helper is untouched. Boundary test fixtures now use the canonical PublicVisionFrame parser. Evaluation has not started.

Four boundary checks pass: opponent-HUD masking invariance, original-confidence preservation, actor decisions with all file/socket reads denied and deterministic identical pixel input, and balanced/disjoint registration. Clean C56 simulator full-game smoke passed. Provisional pixel result reading now records crown-count result or unknown before the evaluator reads the native winner. Equal-count/tiebreak reading remains a readiness limitation. Ready to seal and start the 48 registered pairs; no confirmatory games have started yet.

2026-10-04 21:09:16: Evaluation driver starting after source-pin verification.

2026-10-04 21:10:00: Simulator pair 0 complete, terminal tick 6001; no interim aggregate strength inspection.

2026-10-04 21:14:55: Native pair 0 complete: frames=1941, actions=268, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-04 21:15:30: Simulator pair 1 complete, terminal tick 6001; no interim aggregate strength inspection.

2026-10-04 21:18:11: Worker exception; preserve all partial evidence. Traceback (most recent call last):
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 200, in <module>
    try:main()
        ^^^^^^
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 173, in main
    for cmd in commands:subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=5)
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/sam/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/lib/python3.12/subprocess.py", line 571, in run
    raise CalledProcessError(retcode, process.args,
subprocess.CalledProcessError: Command '['/Users/sam/.cache/clasher-native-reference/android-sdk/platform-tools/adb', '-s', 'emulator-5580', 'shell', 'input', 'tap', '182', '1224']' died with <Signals.SIGABRT: 6>.


2026-10-04 21:18:16: Evaluation driver stopped: RuntimeError('Worker failure /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/eval-native-p16.exit')

Run 1 stopped on adb SIGABRT during pair 1 after a successful terminal pair 0. Preserved the complete native receipt, two clean simulator receipts, partial second native game, logs and original sources/registration in interrupted-r1. No win/loss outcomes inspected. Stopped only owned waiting simulator PID 91440 after checking its exact command; emulator remains owned and paused. The repair uses absolute-adb posix_spawn via close_fds=False, matching L1's documented active-gRPC fork precaution. Replacement registration retains the player and all gates and uses entirely fresh seeds. Running transport smoke before sealing run 2.

2026-10-04 21:20:55: Smoke pair -1 complete: frames=259, actions=27, terminal=False, pixel_end=False. No interim aggregate strength inspection.

2026-10-04 21:20:55: Native p16 worker finished.

Transport repair smoke completed 259 frames and 27 adb attempts in 35 seconds with no active-gRPC fork warning or adb abort. Inclusive replacement seed audit passed, including interrupted-r1 and all ignored report text/NPZ seed arrays. The original interrupted evaluation is preserved and excluded; no player/perception parameter changed. Sealing replacement sources and starting all 48 fresh pairs.

2026-10-04 21:21:21: Evaluation driver starting after source-pin verification.

2026-10-04 21:21:50: Simulator pair 0 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-04 21:27:09: Native pair 0 complete: frames=2365, actions=253, terminal=True, pixel_end=True. No interim aggregate strength inspection.

Resumption: run `.venv/bin/python -B reports/strategy_council_20260928/live-loop/l2/status.py` for counts, worker liveness, exits and disk without printing outcomes. Do not relaunch pipeline.py while an eval worker is alive. Current replacement pipeline is detached; source manifest is sealed. It runs P16 native+simulator, then C56 native+simulator, preserving the three-heavy-process limit with the one emulator. After all 48 pairs, run analyze.py, inspect final-audit.json and RESULTS.md, then stop only the emulator bound by emulator/complete.json. Final reporting must distinguish native pixel result estimates from evaluator-only winner labels. The temporary emulator overlays were about 211 MiB at the replacement launch and count toward a conservative total disk check.

2026-10-04 21:27:37: Simulator pair 1 complete, terminal tick 3601; no interim aggregate strength inspection.

A detached finalizer now waits for the evaluation-complete receipt. It runs analyze.py only after all 48 pairs, then verifies the owned emulator identity and firewall, stops only that emulator, and writes stop.json/complete.json. It exits without touching the emulator if the evaluation reports an error. This protects completion/reporting across agent capacity interruptions; it does not alter gameplay or inspect interim strength. Do not launch a second finalizer while the current one is alive.

2026-10-04 21:33:00: Native pair 1 complete: frames=2233, actions=263, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-04 21:33:24: Simulator pair 2 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-04 21:37:28: Native pair 2 complete: frames=1858, actions=185, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-04 21:38:02: Simulator pair 3 complete, terminal tick 4557; no interim aggregate strength inspection.

2026-10-04 21:42:18: Native pair 3 complete: frames=2177, actions=203, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-04 21:42:42: Simulator pair 4 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-04 21:45:43: Native pair 4 complete: frames=1363, actions=122, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-04 21:46:09: Simulator pair 5 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-04 21:50:53: Worker exception; preserve all partial evidence. Traceback (most recent call last):
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 150, in main
    if operror:raise RuntimeError(operror[0])
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
RuntimeError: Traceback (most recent call last):
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 121, in opponent
    obs,fence=consistent_observation(call)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/sam/Desktop/code/clasher/scripts/l1_native_capture_v3.py", line 22, in consistent_observation
    begin=time.perf_counter_ns();before=call('status');key=identity(before)
                                        ^^^^^^^^^^^^^^
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 63, in <lambda>
    call=lambda c:request(owner['probe_port'],c)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/sam/Desktop/code/clasher/scripts/smoke_reference_battle.py", line 19, in request
    result = json.loads(response)
             ^^^^^^^^^^^^^^^^^^^^
  File "/Users/sam/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/lib/python3.12/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/sam/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/lib/python3.12/json/decoder.py", line 338, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/sam/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/lib/python3.12/json/decoder.py", line 356, in raw_decode
    raise JSONDecodeError("Expecting value", s, err.value) from None
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)


During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 200, in <module>
    try:main()
        ^^^^^^
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 186, in main
    call('pause')
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 63, in <lambda>
    call=lambda c:request(owner['probe_port'],c)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/sam/Desktop/code/clasher/scripts/smoke_reference_battle.py", line 12, in request
    with socket.create_connection(("127.0.0.1", port), timeout=30) as connection:
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/sam/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/lib/python3.12/socket.py", line 865, in create_connection
    raise exceptions[0]
  File "/Users/sam/.local/share/uv/python/cpython-3.12.13-macos-aarch64-none/lib/python3.12/socket.py", line 850, in create_connection
    sock.connect(sa)
ConnectionRefusedError: [Errno 61] Connection refused


2026-10-04 21:51:02: Evaluation driver stopped: RuntimeError('Worker failure /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/eval-native-p16.exit')

2026-10-04 21:51:11: Finalizer stopped because evaluation reported an error; preserve run for repair.

Run 2 transport interruption: five complete native receipts and six complete simulator receipts retained. Emulator PID 75156 and app PID 1743 remained alive; adb forward --list was empty. Restoring only emulator-5580 tcp:26789 immediately recovered the probe. Paused/render-suppressed the owned game and archived incomplete pair 5 under recovery-forward. Stopped only owned waiting simulator PID 98303. No outcomes inspected. Added bounded read-only reconnects, exact mapping ownership checks and --no-rebind; mutation-response loss is not blindly retried. PREREG.md records this prospective repair and retains completed games. manifests/ preserves the prior source manifest and driver source. The replayed pair 5 opening order must match its archived setup before its existing simulator receipt is reused.

Coordinator confirmed the likely external cause: another task's BlueStacks Air launch ran bundled hd-adb kill-server, restarting shared port 5037 and dropping forwards. That task is now stopped, and no further adb interference is expected. Our native pair 5 has no completed result JSON and no terminal receipt; gzip/public/decision partial logs are preserved under recovery-forward, not counted as a result. The emulator/app stayed alive and the restored forward is healthy. Retaining this run's server configuration with bounded owned-forward recovery. The resumed driver now checks exact opening tick, both hands/queues and elixir against the archived setup before replaying pair 5. Existing simulator results are reused only after that equality check.

2026-10-04 21:56:11: Evaluation driver starting after source-pin verification.

2026-10-04 21:56:36: Worker exception; preserve all partial evidence. Traceback (most recent call last):
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 227, in <module>
    try:main()
        ^^^^^^
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 218, in main
    if not a.smoke and not final['ended']:raise RuntimeError('Pixel lifecycle stopped before native terminal; incomplete game retained')
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
RuntimeError: Pixel lifecycle stopped before native terminal; incomplete game retained


2026-10-04 21:56:41: Evaluation driver stopped: RuntimeError('Worker failure /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/eval-native-p16.exit')

Reconnect replay opening matched tick 220, both hands/queues and elixir exactly. Startup-only attempt then falsely classified a delayed intro banner as terminal at tick 235: three public frames, no decisions, no completed result. Its screenshot and intact logs are retained under recovery-startup. Corrected only the lifecycle ordering: end-cue detection is enabled after a running match has first been detected from pixels. PREREG amendment precedes another same-seed technical retry; all five completed native and six clean receipts remain unchanged. No strength outcomes inspected.

2026-10-04 22:06:54: Evaluation driver starting after source-pin verification.

2026-10-04 22:08:22: Worker exception; preserve all partial evidence. Traceback (most recent call last):
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 227, in <module>
    try:main()
        ^^^^^^
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 177, in main
    if operror:raise RuntimeError(operror[0])
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
RuntimeError: Traceback (most recent call last):
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 148, in opponent
    obs,fence=consistent_observation(call)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/sam/Desktop/code/clasher/scripts/l1_native_capture_v3.py", line 36, in consistent_observation
    raise TimeoutError('No stable native observation within deadline')
TimeoutError: No stable native observation within deadline



2026-10-04 22:08:34: Evaluation driver stopped: RuntimeError('Worker failure /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/eval-native-p16.exit')

2026-10-04 22:08:36: Finalizer stopped because evaluation reported an error; preserve run for repair.

Resumption now verified beyond a PID: native worker 99051, clean worker 99058 and finalizer 99093 stayed detached; pair 5 passed exact opening equality and has active pixel decisions after the intro cleared. Empty-log launch attempts produced no games and are not completion evidence. Five lightweight recovery regression checks passed against the actual nested source: missing owned forward restores without rebind, lost mutation response is not repeated, a foreign mapping is preserved, an existing owned mapping is not replaced, and the preserved intro cue cannot end an unstarted match. Four original actor-boundary checks remain applicable; player code is unchanged.

Pair-5 active replay stopped at native tick 743 after the two-second coherent-observation deadline. The probe remained responsive; paused inspection had nativeStockStepCallbacks=steps=743 and count=returned=10, truncated=false. Preserved this incomplete trajectory in recovery-observation. Kept the helper's exact fence unchanged; transient misses now log observation-skips.jsonl and retry after 100 ms, with a ten-second stale-state hard stop. The actor never receives these observations. Missed opponent opportunities remain an execution confound, not silently clean data. This prospective technical amendment preserves all five completed native and six clean receipts. Same-seed replay still requires exact opening equality.

2026-10-04 22:19:34: Evaluation driver starting after source-pin verification.

2026-10-04 22:26:53: Worker exception; preserve all partial evidence. Traceback (most recent call last):
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 234, in <module>
    try:main()
        ^^^^^^
  File "/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/offline_loop.py", line 225, in main
    if not a.smoke and not final['ended']:raise RuntimeError('Pixel lifecycle stopped before native terminal; incomplete game retained')
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
RuntimeError: Pixel lifecycle stopped before native terminal; incomplete game retained


2026-10-04 22:26:55: Evaluation driver stopped: RuntimeError('Worker failure /Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/live-loop/l2/eval-native-p16.exit')

2026-10-04 22:26:56: Finalizer stopped because evaluation reported an error; preserve run for repair.

Corrected diagnosis of the latest stop: pixel_end was false. The generic exception followed the 400-second wall guard; native tick 4155 and the saved timeout image show active overtime at 1:33. Preserved all 1116 public frames and observation/action logs under recovery-wall-time. No result JSON was produced. Status speed remains 1; this attempt progressed about 10 native ticks per wall second. Raised only the wall allowance to 1200 seconds, with explicit incomplete-reason receipts. Search remains 200 ms, nominal renderer speed remains 1x, and no player/perception parameters or registered worlds change. Five completed native and six clean receipts stay retained; incomplete seed 5 is retried under the coordinator-confirmed technical-rerun rule.

2026-10-04 22:44:18: Evaluation driver starting after source-pin verification.

2026-10-04 22:51:23: Native pair 5 complete: frames=1926, actions=316, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-04 22:52:06: Simulator pair 6 complete, terminal tick 3601; no interim aggregate strength inspection.

Registered pair 5 completed a real terminal with 1926 processed frames and 316 adb deployment attempts after the technical wall-allowance retry. Pixel end detection fired and the native terminal receipt passed. Exact opening equality passed before the replay. Six primary native games and six matching simulator games are now complete; pair 6 is active. The original partial attempts remain excluded and preserved. No aggregate strength results inspected.

2026-10-04 22:59:28: Native pair 6 complete: frames=2063, actions=317, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-04 23:00:07: Simulator pair 7 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-04 23:08:15: Native pair 7 complete: frames=2210, actions=309, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-04 23:08:55: Simulator pair 8 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-04 23:16:22: Native pair 8 complete: frames=2052, actions=322, terminal=True, pixel_end=True. No interim aggregate strength inspection.

Deferred-report verification: fixed a missing parenthesis in the unsealed analyzer, then parsed analyzer/finalizer successfully. Two in-memory paired-bootstrap sanity checks passed for identical-arm differences and constant negative differences. No episode outcomes were read for these checks. Gameplay source pins and collected data are unchanged.

2026-10-04 23:17:00: Simulator pair 9 complete, terminal tick 3631; no interim aggregate strength inspection.

2026-10-04 23:23:54: Native pair 9 complete: frames=2016, actions=284, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-04 23:24:34: Simulator pair 10 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-04 23:31:58: Native pair 10 complete: frames=2188, actions=342, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-04 23:32:29: Simulator pair 11 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-04 23:39:13: Native pair 11 complete: frames=2218, actions=304, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-04 23:39:43: Simulator pair 12 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-04 23:45:15: Native pair 12 complete: frames=2308, actions=257, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-04 23:45:40: Simulator pair 13 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-04 23:48:25: Native pair 13 complete: frames=1421, actions=125, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-04 23:49:00: Simulator pair 14 complete, terminal tick 4314; no interim aggregate strength inspection.

2026-10-04 23:56:30: Native pair 14 complete: frames=2057, actions=335, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-04 23:57:08: Simulator pair 15 complete, terminal tick 6001; no interim aggregate strength inspection.

2026-10-04 23:57:08: Simulator p16 worker finished.

2026-10-05 00:07:42: Native pair 15 complete: frames=2310, actions=396, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 00:07:42: Native p16 worker finished.

2026-10-05 00:07:51: p16 native and simulator workers exited zero.

2026-10-05 00:08:44: Simulator pair 16 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 00:22:27: Native pair 16 complete: frames=2497, actions=434, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 00:23:03: Simulator pair 17 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 00:30:20: T3 restart recovery: all 493 pre-restart source pins match. Validated terminal receipts and complete JSON/gzip streams for native pairs 0-16 and simulator pairs 0-17 without aggregate strength inspection. Native pair 17 has no terminal or result receipt; its 357 decisions, 977 public frames and 1188 evaluator rows parse cleanly but are incomplete. Preserved all partial evidence and old emulator/worker receipts under recovery-t3-restart. No L2 jobs or emulator survived; foreign processes are untouched. Technical rerun retains every completed outcome, replays only native pair 17 with exact opening equality, and isolates adb on port 5041. README/RESULTS files do not yet exist; the RESULTS draft is embedded in analyze.py and was read.

2026-10-05 00:31:05: Emulator booted on dedicated adb server 5041. Launcher root handshake returned a closed connection while adbd restarted; follow-up reports adbd already root. No app launch or evaluation occurred. Retained launcher attempt and continuing setup on the same owned emulator.

2026-10-05 00:31:43: Evaluation driver starting after source-pin verification.

2026-10-05 00:31:43: p16 native and simulator workers exited zero.

2026-10-05 00:35:34: Restart replay opening equality passed at tick 220; native pair 17 is processing pixel decisions. All processes launched through detach.sh; owned emulator and workers use dedicated adb port 5041. Five recovery checks and L2 syntax parsing passed. Expanded deferred analyzer with descriptive hand/elixir, spatial body/HP and event-window diagnostics plus receive-to-submission deployment quantiles and explicit gate booleans. Validated only against excluded smoke logs, including accounting and JSON serialization; no primary outcomes inspected. Gameplay pins are unchanged by reporting work. Added README.md with recovery and receipt semantics.

2026-10-05 00:42:15: Native pair 17 complete: frames=2874, actions=374, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 00:42:56: Simulator pair 18 complete, terminal tick 5882; no interim aggregate strength inspection.

2026-10-05 00:46:40: Native pair 18 complete: frames=1578, actions=139, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 00:47:05: Simulator pair 19 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 13:42:08: SIGSTOP recovery (UTC 2026-10-05T20:42:08Z, coordinator agent on f35 via ssh): the previous coordinator SIGSTOPped pipeline 95700, native worker 95753 and simulator worker 95820 at about 07:49Z for about 12 h 50 min. The owned emulator 89739 kept running, so native pair 19 ended in-engine with no controller input (probe lifecycle: tick 6219, ended; winner not read). A plain SIGCONT would have written a terminal pair-19 receipt through the exhausted wall-guard path, so the stopped owned groups were SIGKILLed before running. No exit, error or receipt file was written. Native 0-18 and simulator 0-19 receipts are retained. The pair-19 partial (287 decisions, 1,092 frames, 1,201 evaluator rows, perceived tick 2368, clean parse), logs and pre-change sources are preserved in recovery-sigstop-20261005 (incident.json). 493 pins matched before the change. Owner and IPv4/IPv6 UID REJECT verified. The emulator was paused with render off, as the worker's own finally block would have done. The PREREG amendment is dated before the replay. offline_loop.py gains only the recovery-sigstop opening-equality lookup. Re-sealed: 493 pins, of which only offline_loop.py and PREREG.md changed. test_recovery 5/5 OK. Relaunching the pipeline and one finalizer via detach.sh/run.sh on adb port 5041. Only native pair 19 is replayed, and exact opening equality is required. No interim strength outcomes inspected.

2026-10-05 13:42:14: Evaluation driver starting after source-pin verification.

2026-10-05 13:42:14: p16 native and simulator workers exited zero.

2026-10-05 13:46:11: Native pair 19 complete: frames=748, actions=115, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 13:46:51: Simulator pair 20 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 13:51:20: Native pair 20 complete: frames=910, actions=210, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 13:51:36: SIGSTOP recovery verified (UTC 2026-10-05T20:51:36Z). The pair-19 technical rerun passed exact opening equality at tick 220 against recovery-sigstop-20261005/native-pair-19-partial and completed a real native terminal with pixel end. Its existing simulator pair-19 baseline is retained. Pair 20 native and simulator are complete, and the workers continue. One read-only forward reconnection has occurred since relaunch, handled by the amended reconnect path. A single finalizer is running (75174). No interim strength outcomes inspected.

2026-10-05 13:52:02: Simulator pair 21 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 13:54:23: Native pair 21 complete: frames=513, actions=105, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 13:54:56: Simulator pair 22 complete, terminal tick 2836; no interim aggregate strength inspection.

2026-10-05 13:59:33: Native pair 22 complete: frames=801, actions=206, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 14:00:15: Simulator pair 23 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 14:02:37: Native pair 23 complete: frames=507, actions=101, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 14:03:21: Simulator pair 24 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 14:06:39: Native pair 24 complete: frames=645, actions=142, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 14:07:22: Simulator pair 25 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 14:11:25: Native pair 25 complete: frames=717, actions=180, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 14:12:04: Simulator pair 26 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 14:16:34: Native pair 26 complete: frames=922, actions=229, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 14:17:32: Simulator pair 27 complete, terminal tick 5135; no interim aggregate strength inspection.

2026-10-05 14:19:37: Native pair 27 complete: frames=515, actions=97, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 14:20:18: Simulator pair 28 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 14:22:40: Native pair 28 complete: frames=574, actions=107, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 14:23:18: Simulator pair 29 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 14:25:43: Native pair 29 complete: frames=559, actions=102, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 14:26:17: Simulator pair 30 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 14:28:47: Native pair 30 complete: frames=534, actions=115, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 14:29:35: Simulator pair 31 complete, terminal tick 3934; no interim aggregate strength inspection.

2026-10-05 14:33:56: Native pair 31 complete: frames=805, actions=217, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 14:34:29: Simulator pair 32 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 14:37:51: Native pair 32 complete: frames=773, actions=132, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 14:38:27: Simulator pair 33 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 14:40:54: Native pair 33 complete: frames=605, actions=91, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 14:41:32: Simulator pair 34 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 14:46:03: Native pair 34 complete: frames=924, actions=195, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 14:46:37: Simulator pair 35 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 14:51:14: Native pair 35 complete: frames=1004, actions=202, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 14:51:51: Simulator pair 36 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 14:54:18: Native pair 36 complete: frames=583, actions=91, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 14:54:55: Simulator pair 37 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 14:57:21: Native pair 37 complete: frames=574, actions=97, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 14:57:58: Simulator pair 38 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 15:01:08: Native pair 38 complete: frames=683, actions=115, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 15:01:46: Simulator pair 39 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 15:05:06: Native pair 39 complete: frames=735, actions=129, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 15:05:37: Simulator pair 40 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 15:08:10: Native pair 40 complete: frames=569, actions=91, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 15:08:45: Simulator pair 41 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 15:13:20: Native pair 41 complete: frames=874, actions=209, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 15:14:00: Simulator pair 42 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 15:17:21: Native pair 42 complete: frames=746, actions=126, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 15:17:54: Simulator pair 43 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 15:20:24: Native pair 43 complete: frames=581, actions=89, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 15:20:59: Simulator pair 44 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 15:25:34: Native pair 44 complete: frames=1031, actions=193, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 15:26:12: Simulator pair 45 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 15:28:38: Native pair 45 complete: frames=573, actions=91, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 15:29:11: Simulator pair 46 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 15:33:47: Native pair 46 complete: frames=974, actions=216, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 15:34:23: Simulator pair 47 complete, terminal tick 3601; no interim aggregate strength inspection.

2026-10-05 15:34:23: Simulator c56 worker finished.

2026-10-05 15:38:56: Native pair 47 complete: frames=941, actions=187, terminal=True, pixel_end=True. No interim aggregate strength inspection.

2026-10-05 15:38:56: Native c56 worker finished.

2026-10-05 15:39:00: c56 native and simulator workers exited zero.

2026-10-05 15:39:09: All registered evaluation workers completed. Starting frozen-outcome analysis.

2026-10-05 15:39:32: Analysis exit 0

2026-10-05 15:39:35: Owned emulator cleanup verified=True. No foreign process touched.

2026-10-05 15:39:35: L2 evaluation, analysis, report and owned-emulator cleanup complete; L3 verdict remains NOT READY.

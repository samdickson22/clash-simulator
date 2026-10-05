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

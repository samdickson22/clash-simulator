# L2 offline pixel-loop evaluation

PREREG.md defines the 48 registered seed pairs and technical rerun rules. PROGRESS.md records execution and recovery. RESULTS.md and metrics.json are produced only after every pair reaches a terminal state. The pending RESULTS text lives in analyze.py.

The actor reads sanitized screenshots through the frozen L1 sensor and submits adb taps using the installed legacy touch mapping. Native truth is reserved for opponent control and separate evaluation logs. Native receipts are in native/ and paired clean-state receipts in simulator/.

The October 5 T3 restart left native pairs 0-16 and simulator pairs 0-17 complete. recovery-t3-restart preserves pair 17's incomplete native logs, prior emulator receipts, source pins and the incident audit. Only its native match is replayed; opening equality is required before retaining the existing simulator baseline.

All jobs use pilot/detach.sh and run.sh. run.sh sets ANDROID_ADB_SERVER_PORT=5041 and applies nice -n 10. The owned emulator uses console 5580, probe 26789 and gRPC 8554, with the documented read-only AVD, SwiftShader, two cores and 3072 MiB. Verify emulator/complete.json ownership and both UID firewall rules before any interaction. Do not restart or kill a shared adb server.

Use status.py for counts and worker health without reading interim strength outcomes. pipeline.py resumes missing receipts and stops on worker errors. finalize_when_done.py waits for full completion, runs analyze.py, then stops only the verified owned emulator. complete.json is the final success receipt; a PID or evaluation-complete.json alone is not evidence of a finished report.

The report includes the registered family-stratified paired bootstrap and timing gates. Additional hand, elixir, body/HP and deployment diagnostics are descriptive. They neither alter the primary estimator nor tune any player or sensor.

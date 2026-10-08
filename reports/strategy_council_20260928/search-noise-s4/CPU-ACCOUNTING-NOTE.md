# CPU-log attribution limitation

Game CPU is measured in all 1,280 immutable confirmation receipts: 29.622947980936942 core-hours. Confirmation supervisor/worker time is independently metered with host-specific labels.

During final accounting, 127x04's s4-seed-audit-r1.log first contained only a header and later contained the completed 127x01 audit output (including an explicit host=127x01 and 466.01 CPU seconds), identical to the hub log. The 04 seed audit itself completed successfully earlier, with its own host=127x04 JSON receipt. This demonstrates a log-attribution problem; the actor that copied the log has not been identified. The same label was used on both hosts. No study source or receipt hash mismatch was found.

The final audit records SHA256 per top-level log, omits logs declaring another host, and counts identical log bytes only once. Missing/unattributable CPU is listed explicitly; total metered time is a lower bound. The initial attribution-unchecked total is retained in compute-audit-before-log-attribution.json and must not be used as an exact total. No game score, CI, identity receipt or materiality result depends on these operational timing logs. Future tasks should use host-qualified labels for every detached command.

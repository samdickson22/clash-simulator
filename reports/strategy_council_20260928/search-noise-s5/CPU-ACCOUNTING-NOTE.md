# S5 CPU attribution note

Final attributable metered CPU is **37.983466667 core-hours**, including 37.099358333 confirmation supervisor/worker core-hours and 0.884108333 preflight/operations core-hours. Game CPU is 36.954092616 core-hours and overlaps the supervisor total. Small finalization/copying operations and unidentified mirror-process CPU are unmetered.

The frozen compute_audit.py discovers S5-prefixed logs. Six foreign-host log copies appeared under the 04 jobs directory, reproducing S4's documented mirror contamination. Five completed hub logs were identical; a sixth was an exact prefix of the completed hub startup log. Their names identify 01, and the startup script can run only on 01. The copying process is unidentified; no process was stopped or changed.

The original generic aggregate double-counted 342.53 seconds and treated the partial copy as missing timing. audit_cpu_attribution.py is a **post-analysis reporting audit**, outside the frozen execution manifest. It verifies byte equality/prefixes, excludes foreign-host copies, and preserves compute-audit-before-attribution.json, RESULTS-before-cpu-attribution.md, and cpu-log-evidence/. All genuine owned detached-command records have timing. It does not modify any frozen source, raw game receipt, outcome statistic, CI, or game CPU total. Do not rerun finalize.py or overwrite these retained accounting versions.

# Collector startup ordering

2026-10-08 03:48 UTC. Initial hub collector s2-collect-r1 exited 1 before admitting any receipt: rsync source confirmation directory did not yet exist while supervisors imported the runtime. Both hosts were reachable and both directories were verified present at 03:48 UTC. Game supervisors were not restarted. Original JSON/log/exit are retained. The unchanged sealed collector is relaunched once under s2-collect-r1b with --attempt r1 (the game attempt). No outcome read, code change, exclusion or game replay.

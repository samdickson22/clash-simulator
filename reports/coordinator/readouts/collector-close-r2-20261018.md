# Collector close round2 — 2026-10-18T08:51:38Z

PT1 and NS2 are final; each result was sent immediately to coordinator b4f05b1c-9d3a-4e38-a58a-98ab4407fa25 (steer, then auto after thread_not_sendable). No collector study remains pending. Current origin/main `c65f2f214d0d3971326305d2e6d7b7a05570d43b`.

PT1: all16 fresh shards,2400 clean unique games; both lambda arms meet the candidate gates and require fresh-bank replication. Observed+201 R3a bank is PRIMARY; both pre-outcome audits pass, with PREREG+301/driver+201 mismatch disclosed. Source `68816487f5bbd4d9594b437e02a7f42c3c327dd4`; `pt1-20261018.md`.

NS2:3600 scored games,24 excluded smoke; strong search−rl5-alone +.110 [+.040,+.180], registered superiority PASS. Source `add0b9844da8efa98f6f7f4aa7afd077d391e425`; `ns2-20261018.md`.

Fleet: expected RL/P1 CUDA processes retain all three devices, with fresh trainer metadata; no confirmed idle GPU or broken/stalled job. Latest load1/GPU observations:

- 127x01: 2026-10-18T08:50:52.259909+00:00; 01:50:52 up 24 days,  8:15,  0 users,  load average: 43.71, 43.58, 43.33; GPUutil%,MiB=0, 15221; who=''.
- 127x04: 2026-10-18T08:50:51.912341+00:00; 01:50:51 up 19 days, 10:49,  0 users,  load average: 14.57, 14.88, 26.89; GPUutil%,MiB=0, 31344; who=''.
- 127x08: 2026-10-18T08:50:51.980143+00:00; 01:50:51 up 24 days, 10:54,  0 users,  load average: 24.17, 53.05, 80.97; GPUutil%,MiB=26, 27543; who=''.

Hourly monitoring ends here; a continuing owner is needed for future checks. P1, RL snapshots, play-quality A/Bs and perception remain with their designated owners.

All fleet work was read-only; scoring/parsing ran on data hosts under nice19. No jobs, queues, worktrees, refs or protected groups changed. No collector monitor remains running. Fleet details: `fleet-20261018.md`. Reproducibility and helper scripts: `/tmp/clasher-results-collector/` (`pt1-bank-audit.json`, `pt1-final.json`, `ns2-final.json`, `watch-r2-history.jsonl`, `gpu-health-r2.json`).

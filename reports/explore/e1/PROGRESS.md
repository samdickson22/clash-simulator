# E1 progress

**Active: reporting arms 1–4 on03/04; reserve arm runs last.**

Plan/config/seed audit were frozen and pushed at **bfb9b107**, before any game. Config SHA256: `633e21dbc97ad4dda2576c1cdd1bd1d24d4ed563ad5d5c1834765a61d82fd9b4`. B1 implementation: **47e97277**; reducer and smoke audit: **a4d23f8d**. Five arms, 3,000 reporting games, 600 paired seeds. No PREREG or reporting-seed tuning.

2026-10-09 10:50Z: first four arms **109/2,400 terminal** (03:90/1,600;04:19/800).03 has62 workers + manager + supervisor (64 processes);04 has30 workers + manager + supervisor (32). Latest MemAvailable:86.87/74.16GiB. No memory pauses or serving failures.03 owns seeds0–399,04 seeds400–599, with identical matched arm schedules. Reserve arm is not started.

Qualification: native OFF250/250 frozen score/action/trace digest; E1 floorOFF/deadlineOFF symmetric125/125; W125/125 frozen choices/scores; v1 byte/action250/250; native zero-budget immutable root125/125;12 injected-clock/filter tests PASS.03 and04 corpus/adapter receipts are identical. Adapter source is byte-identical to sealed gate(c), and checkpoint SHA is verified. Receipts under `receipts/`.

All10 separate smoke games were terminal and passed schedule/channel/single-core/reducer audits. Smoke supervisor exited0, peak4 processes, minimum96.887GiB MemAvailable, no pauses. Smoke games are excluded from reporting. Provisional unlimited W-v-v1 smoke rate:4.880 decisions/sec/core, superseded by the reporting estimate after completion.

04 was admitted only after the GRU park receipt at10:25:44Z and an empty GPU check. No01,08,leased-host or Mac work.05 performs light authoring and compact receipt reads only. All workloads use setsid, nice10, SCHED_IDLE, and one pinned core per game worker. Supervision pauses only its own process group below28GiB, resuming at32GiB to protect the24GiB floor.

Runtime/raw receipts: `/mpac/sdicks02/jobs/clasher/e1-20261009-r1` on03/04. `main/pids.json` records task-owned identities; `progress.json` and `main/census.jsonl` track progress/resource checks. No raw game logs enter Git. Earlier private build/import-path qualification attempts failed before games and were corrected; no reporting outcome was omitted or replaced.

2026-10-09 11:03Z — Arms1–4 remain healthy (835/2,400 as of11:02Z). Before any reporting reserve game, corrected the reserve filter to match the frozen crown-tower definition: the shared catalog's broad `tower` flag also labels defensive buildings, so the filter now recognizes only `Tower`/`KingTower` body names. No threshold/rule/config change. Reserve is OFF in every running/reporting arm, so their decisions and runtime remain unchanged.The additional pytest suite has not yet run: local05 lacks a project .venv, so its first command failed to start. Original12-testreceipt remains valid. A focused standard-library public InfernoTower fixture passed (including OFF identity); the full13-test suite will run on an authorized compute host before reserve launch. The premature13-test claim was corrected immediately to the coordinator. The10 earlier smoke games, including the old reserve draft, remain preserved and excluded. The final reserve arm will pin the corrected source separately. No reporting game restarted or omitted.

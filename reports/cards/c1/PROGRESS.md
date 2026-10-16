# Batch C1 — progress (restart notes)

Worker: CARD LEAD engine owner for Batch C1 (Opus). Worktree `/mpac/sdicks02/repos/clasher-cards-c1`, branch
`cards/c1` (from b16716481 on `cards/lead`). Edits only `engine-cards/**` and `reports/cards/c1/**`. Spec:
`reports/cards/specs/C1-SPECS.md`. Results: `RESULTS.md`.

## Layout
- 127x08 `/mpac/sdicks02/jobs/clasher/cards/c1/`: `base/` (engine-cards @ b16716481), `tree/` (rsync of the
  worktree), `root|baseroot|rootstats|basestats/` (Batch A-style roots), `out-base/` (native de11f124 = base),
  `stats/gamedata.json` (scratch overlay from `fid/stats-spec.json`, 4 rows; never in git), `fid/` (fidelity harness
  copy + `final-{base,mech,stats}.jsonl`, negative control `pns-negctl.*`), `nd/` (native-diff replays, base arm),
  `ctools/` (`reports/cards/c1/tools` + `replay.sh`, `pns.sh`).
- 127x04 `/mpac/sdicks02/jobs/clasher/cards/c1/`: `tree/`, `out/` (C1 native), `root|rootstats/`, `rt/` (r1 mirror
  for the gate, src/engine-rs -> tree), `roots -> ../batchA/roots`, `gate-tools/` (Batch A copy), `tools/` (Batch A
  tools incl. `gate.sh`), `ctools/` (`env.sh`, `verify.sh`, `nd_sample.sh`, C1 tools), `verify/` (native==Python
  evidence), `nd-plan.json` (native-diff plan copy).
- Builds: `build.sh tree out` under `cpu_job.sh 8` (04; 08 is saturated by the BOT LEAD full-pool generation).

## Log (UTC)
- 2026-10-16T06:45Z start; baseline fidelity (base root): C1 12/36 PASS.
- §13–16 native-only fixes; native-diff named games 11/11 full-length match (base arm reproduces 10; 548 no longer
  diverges on base either).
- Cards in spec order. Python fidelity per card first, then the native mirror, then lockstep:
  Bowler 3/3, Assassin 3/3, BossBandit 3/3, ZapMachine 3/3, MegaKnight 3/3 (full timed-dash port after the
  4-tick-recovery-only fix left the second leap 2 ticks late), Fisherman 3/3, ElectroDragon 3/3, IceWizard 3/3,
  ElectroWizard 2/3 (C56 Knight residual), AxeMan 3/3, InfernoDragon 3/3, Ronin 3/3 with the overlay.
- Native fixes found by lockstep: ZapMachine template clock seeded at LoadTime; Electro Dragon chain template
  exported alive; the boulder and axe hit filters skip dash-travel / stealthed units without marking them hit
  (mixed game 4: Bowler boulder vs BossBandit in travel).
- 07:40Z verification on 04 (native 6741bb91): 36/36 ×2 roots, 70/70 focused cases, 21-path audit 42/42, Batch A
  review cases 4/4, native-diff 11/11; negative control live; C56 config export byte-identical (e52e8a96).
- 07:46Z mixed sample (96 games with ≥ 2 C1 cards): 81 match; 12 known causes (IceGolemite alias 10, Poison×Bandit,
  Mirror×Barrel); 72 also diverges on the base arm; 4 = the hit-filter bug above (fixed, rebuild); 173 under triage.

- Native 2ac024c7 (hit-filter fix): game 4 matches; 173 = the known C56 X-Bow clock cause (reached by the new
  trajectory; base arm never gets there); 72 also diverges on the base arm. Full rerun of `verify.sh` +
  `nd_sample.sh`: 36/36 ×2, 70/70 cases, 42/42 paths, 4/4, 11/11, sample 82 match + 14 known causes.
- Committed e0ade18d3 on `cards/c1`; C56 gate launched 2026-10-16T08:04Z on 127x04: `cpu_job.sh 8 bash c1/tools/gate.sh`,
  PID = PGID 2082511, output `c1/gate/compare.json`, log `c1/gate.log`; patched native 2ac024c7 (pinned 681b5f2c).

- 2026-10-16T08:45:42Z gate shepherd: **C56 parity PASS** vs pinned 681b5f2c, patched native 2ac024c7
  (engine e0ade18d3 / handoff bc8eba7c2): fixtures **577/577 byte-identical**, Rust-only chains **577/577**,
  roots **300/300 full + 300/300 cut identical**. PID/PGID 2082511 completed normally (08:04:25Z–08:45:16Z);
  no relaunch. Independent byte/ID/hash audit passed; evidence 04 `c1/gate/compare.json` and `c1/gate.log`,
  details RESULTS §6. No triage needed; no engine edits or sealing.

## Next
- Gate shepherd complete: C56 parity PASS; see RESULTS §6.

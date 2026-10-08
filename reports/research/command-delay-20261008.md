# Command delay: what d really is (research, 2026-10-08)

Research sub-agent for the 127x05 coordinator. Read-only on 127x05; this file is the only write. No Mac mini,
emulator, game client or login was touched. The FirstLight probe source was read as plain text from its public
upstream (`luody21/FirstLight_CR@28d66cc`, the commit our probe build pins). The ClashAI tree was read from the existing
clone at `/mpac/sdicks02/tmp/clashai-research/repo` (`8d4053d`). Nothing from either was executed.

Reliability grades: **A** = our own code or measurement with the file in hand; **B** = reproducible third-party
measurement or source code; **C** = community statement with some method; **D** = claim without a method or source.

## Summary

- **"Native acceptance" in T2 is the command's execution tick, not the moment the unit becomes active.** Acceptance
  means the card has left the native hand *and* native elixir has dropped by the cost (`actuation/bench.py:104-107`).
  Both happen in the same engine step that creates the unit in its deploying state. Deploy time then runs on top of
  that, in the native engine and in both of our simulators.
- **There is no double counting.** The planner applies our action at `t + d` through `apply_discrete` →
  `apply_action`. That spends elixir, empties the slot and spawns units whose `deploy` timer equals the card's
  `deploy_time` (Rust `lib.rs:3676-3679`, `3039-3042`; Python `battle.py:1294`, `2004-2016`). So d is "frame → execute",
  and deploy time is added exactly once, by the engine.
- **The 20-tick "live-command age" is FirstLight's constant, but it mirrors the real game.** The probe formats every
  native deploy command as `{"t":T,"t2":T+20}` (`cr_replay_probe.cpp:638, 5828-5841`). Touches use `T = current+2`
  (`native_touch_probe_glue.inc:34,54`), so execution lands 22 ticks after the touch. This path bypasses the stock
  UI's own tick stamping. Even so, ClashAI's 6,721 official-client plays show the same structure: board-tap return →
  execution has a median of 22.6 ticks and **p1 19.9 ticks**. That is a hard 20-tick floor (`ClashAI HANDOFF.md:4687-4693`,
  `L74/latency/budget_20261008.txt`).
- **Our d is about right for both backends: 26 ± 1 ticks for the renderer, 26-27 ± 2 for the official client
  (p50).** The official client also has a network-driven tail (ClashAI p95 is about 44 ticks decision → execution).
  The current 27 counts the ~25 ms two-tap interval twice and includes T2's polling bias, so it is about 0.5-1 tick
  conservative. Keeping 27 is defensible; 26 is the better point estimate.
- **The bigger modelling errors are elsewhere:**
  - **Opponent asymmetry in sim.** Our simulator gives the opponent zero command delay, while real opponents also pay
    about 22 ticks. This inflates the measured "latency cost" (LEDGER's +7.3 pp, S6's +2.7 pp).
  - **Imitation timing skew.** Human labels sit at the *execution* tick, with the board at that tick, but the bot must
    decide about 26 ticks earlier.
  - **A self-imposed throttle.** We allow only one outstanding command, so we can't decide again for about 1.3 s after
    each play. The game itself doesn't impose that limit.

## Q1. What "native acceptance" measures, and whether deploy time is double-counted

### The T2 probe criterion (A)

- `reports/strategy_council_20260928/live-loop/v4/actuation/bench.py:92-107`: `start` is taken right before the
  two-tap (`inp.play`). The loop polls `r.observe()` and sets `truth_time` the first time the target card is **absent
  from the native hand** *and* native elixir has fallen by at least `cost − 0.8`.
  - Nothing in the criterion looks at unit activity, deploy timers or bodies.
  - `backend-timing.json` labels the value `"submission to first observed native acceptance; polling upper bound"`.
  - `T2-RESULTS.md:12` adds: "first native observation, not exact native execution … the unchanged hook's nominal
    command delay is 22 ticks."
- **Measured value (A):** gRPC D_b p50/p99 = 1151.7 / 1187.3 ms = 23.03 / 23.75 tick-equivalents (n=320). The spread
  is tiny (p99 − p50 = 0.7 tick), which is what a fixed scheduled delay plus polling jitter looks like. The bench
  plays each seed's second-cheapest hand card (`bench.py:55-56`), so cards vary across trials. A deploy-time
  component would have shown up as card-dependent spread of tens of ticks (for example 0 for spells, 20 for troops).
  The four misses were HUD-reader errors, not slow acceptances.
  - The retained `trials.jsonl` lives only on the Mac (hash in `backend-timing.json`). The per-card split was not
    recomputed here.

### When the native engine changes hand and elixir (A/B)

- **The collector's exact-label rule** (`live-loop/v4/collector.py:249-253`) accepts a play only when
  `tick >= executeTick` *and* the card is gone *and* elixir is spent, with `queuedAtTick == executeTick − 1`. Hand and
  elixir change at `executeTick`, not at registration. If they changed at registration, T2 would have measured about
  2 ticks, not 23.
- **The probe's deploy command** (`cr_replay_probe.cpp:5828-5841`) is `{"ct":86,"c":{"t":T,"t2":T+20,…}}`. `t2` is
  the execute tick. For scheduled replay actions the probe sets `t = boundary − 20`, so `t2 = boundary`
  (`cr_replay_probe.cpp:6005`).
- **The 2026-09-15 command-timing controls** (`docs/history/HANDOFF.md:321-329`): with `t70/t2=90` the body spawns
  at 91, and with `t=t2=200` at 201. "Body/elixir spend proof" appears on the same boundary.
- **Native deploy time runs after spawn:**
  - The native observation carries `deployRemainingMs` per object (`collector.py:227`, DESIGN §3.1 `deploying`).
  - Native Tesla fixture (`tests/fixtures/native_tesla_deploy_combat_15_535_86.json`, from
    `reports/native_first_body_hp_20260915/tesla-deployment-clock.json`): no target at elapsed tick 19, first target
    at elapsed tick 20. That is its 1.0 s deploy, counted from the spawn.
  - Native Log: command at 1440, child at 1449, first move at 1450 (`tests/test_native_spell_command_timing.py:33-36`).
  - Native Fireball: command 1020, visible 1021 (`:15`).
- **The official client behaves the same way** (ClashAI memory reader, B): `T_el − T_rot` = 0 at p5/p50/p95, so
  elixir charge and hand rotation share a frame. `T_sp − T_rot` (new own entity) has median 0 and p95 42 (the p95 is
  spells and other delayed bodies) (`budget_20261008.txt`). Hand rotation, elixir charge and body creation are one
  event, the command execution.
  - The native hand slot is emptied at execution and refilled after a refill delay (`src/clasher/player.py:84-96`).
  - "Rotation" in both datasets therefore means the slot changed at execution, not the refill.

### How the simulators apply our delayed action (A)

- **S6 planner** (`search-noise-s6/delay.py:39,105,109-110`): a candidate becomes
  `PendingCommand(due = t + command_delay)`. At `due` it calls `native.apply_discrete(sim, seat, action)`, then steps.
  `IMPLEMENTATION-NOTES.md:22` confirms "The own candidate executes at t+d".
- **Rust `apply_discrete`** (`engine-rs/src/scripts.rs:695-721`) → **`apply_action`** (`engine-rs/src/lib.rs:3546`):
  - It spends elixir, empties the slot and appends the card to the cycle (`:3676-3679`).
  - It pushes unit templates with `birth = self.tick` (`:3706-3781`).
  - Templates are built by calling Python `deploy_card` and snapshotting the new entities
    (`engine-rs/differential.py:532-533`), with `deploy = e.deploy_delay_remaining` (`:367`).
  - The timer counts down 0.05 per tick (`lib.rs:3039-3042, 3088-3091`). Deploying units don't target or move
    (`:2041`, `:1849-1852`).
- **Python `deploy_card`** (`src/clasher/battle.py:1218-1316`): `player.play_card` spends and empties the slot
  (`:1294`, `player.py:76-92`). Units spawn with `deploy_delay_remaining = deploy_time/1000` (`battle.py:2004-2016`).
- **S6 test** `test_delay.py:104-110`: execution happens exactly at `info.tick + 22`, there is one native debit, and
  elixir afterwards is `10 − cost + regen`.

### Verdict on double counting: no (A, definitive)

- d (T2's D_b plus the pipeline) runs from the frame to the **execution** tick, the tick the deploying body appears.
- The simulator applies the action at `t + d` and then charges the card's deploy time once, as the native engine
  does.
- Deploy time is never inside d. A Knight placed by the planner at decision tick t becomes active at about
  `t + 27 + 20`, which is what happens on the renderer and, per ClashAI, on the official client.
- **One small real double count:** the ~20-30 ms two-tap interval appears both in `frame_to_tap` (measured to the
  *completed* second tap, `runtime-mac-latency.json` `timing_ms.frame_to_tap`) and in D_b (timed from *before* the
  first tap, `bench.py:92-93`). That is worth about 0.5 tick. Add T2's polling upper bound (mean ≈ half a 17-25 ms
  poll) and 27 overstates the median by about 0.5-1 tick.

## Q2. Where the 20-tick live-command age comes from

### Provenance (A/B)

- **Origin.** `kLiveCommandAgeTicks = 20` is a constant in FirstLight's probe (`cr_replay_probe.cpp:638`, upstream
  `luody21/FirstLight_CR@28d66cc`). Our build pins that commit (`scripts/build_reference_probe.py:38-43`; probe
  sha `2ea5e10d…` per `reports/external_review_20260928/clashai.md:102`).
  - It is used in three places: every deploy command's `t2 = t + 20` (`:5828-5841`), the boundary scheduling
    `t = boundary − 20` (`:6005`), and the default advance after a `play`/`transition` (`delay + 20 + 1`, `:6129`).
  - The live touch path adds `kTouchCommandDelayTicks = 2` (`native_touch_probe_glue.inc:34,54`). Total: execute at
    touch tick + 22.
  - Abilities use `t2 = t + 1` (`:5845-5856`), so the 20 applies to card deploys only.
- **It bypasses the stock path.** `cr_replay_probe.cpp:90-94` says the stock UI "finishes every player command through
  c893d0. That second function owns the validation, command tick stamping and ClientInput network-message enqueue."
  The touch interceptor (`native_touch_interceptor.cpp:180-181`) calls the probe's own `submit_hand_action` instead.
  On the renderer, the 22 is therefore FirstLight's choice, not the stock client's stamping.
- **Our history:**
  - 2026-09-15: source inspection found the constant and attributed the observed 21-22-tick play offset to it
    (`docs/history/HANDOFF.md:203`).
  - The same day, disassembly of libg found that the **native command queue itself** (`d2f37c`) "checks t2/current
    plus 20-tick age" (`:323`). The game binary has its own notion of a 20-tick command age; it isn't only a probe
    convention.
  - Later that day, short-delay failures were traced to a startup confound, "not a broken helper or mandatory 20-tick
    command age". Commands with `t2 = current + 1` execute (`:329`), so the engine does not *enforce* a 20-tick lead
    offline.
  - The hook was pinned with the L1/L2 attestation `864227bf…`.
  - The 2026-10-07 amendment chose "keep the hook" (option B) precisely because "the official client also schedules
    commands ahead of the server tick. Its delay is unknown and probably not near zero"
    (`amendments/2026-10-07-t2-actuation-timing.md:41-48`).

### Is it real netcode or an artifact?

- **Mechanism: an artifact of the probe on the renderer.** There is no network. The stock stamping is bypassed, and
  the engine accepts a 1-tick lead.
- **Value: it matches the real game.** The best evidence (B) is ClashAI's official-client latency budget
  (`ClashAI HANDOFF.md:4687-4693`, `L74/latency/budget_20261008.txt`). Of the 1.40 s decision → rotation, "after our
  board tap returns, median 22.6 ticks (1.13 s; **p1 19.9**)".
  - A 19.9-tick first percentile over 6,721 plays on a home connection is a hard floor at 20 ticks. That is what a
    client-side `t2 = t + 20` stamp would produce. A floor of `RTT + small` would look very different.
  - Together with the native queue's built-in 20-tick age and FirstLight's (presumably copied) convention, the most
    likely explanation is lockstep-style scheduling: the official client stamps each deploy to execute about 20 ticks
    (1.0 s) after it is issued. The lead absorbs network latency, and every client executes the command on the same
    tick.
  - Confidence: high (B) that the floor is about 20 ticks; moderate (C) on the exact mechanism, because the stock
    stamping function was not read.
- **Small offset in our human data.** FirstLight and Jason-XII re-drive RoyaleAPI/IL_Replay commands at `data-t` + 1.
  Our human-replay builder applies them at `data-t` (`human_replay_demonstrations.py:159`, `human_replay_v5.py:339-402`).
  The 1-tick offset is immaterial to d, but note it if replay-fidelity work resumes.

## Q3. What the official game does (public sources)

A web sweep by a delegated sub-agent (Opus, high effort, 2026-10-08) plus my own searches. **No Supercell talk, blog
or engineering post on Clash Royale netcode, tick rate or placement delay exists that we could find.** No public
frame-counted measurement of tap → execution was found either. ClashAI's ledger (Q4) is the only large measurement.

| Topic | Finding | Source | Grade |
|---|---|---|---|
| Tick rate | 20 ticks/s (50 ms). The "10" in some sources is ticks per server *turn*, not the rate. | Reverse-engineered server `Time.cs` (`20*s`) and `BattleManager.cs` (`BATTLE_UPDATE_TICKS = 10`, timer 50 ms × 10) in [BerkanYildiz/ClashRoyale](https://github.com/BerkanYildiz/ClashRoyale); FirstLight `TICKS_PER_SECOND = 20`; RoyaleAPI timelines are `ticks/20` ([cochon123/clash-royale-ai](https://github.com/cochon123/clash-royale-ai)); ClashAI measured 19.94-19.98 ticks/device-second | B (agreeing independent sources) |
| Architecture | Deterministic lockstep with a relay server and checksums. `EndClientTurn{tick, checksum, commands[]}`; `SectorHeartbeat{turn, checksum, commands[]}` every 10 ticks in the 2017-18 emulators. | [SC-DevTeam/cr-messages](https://github.com/SC-DevTeam/cr-messages); BerkanYildiz `SectorManager.cs`; [ZrdRoyale LogicBattle.cs](https://github.com/Zordon1337/ZrdRoyale) (500 ms heartbeats); official "Fixed server out of syncs" notes ([wiki version history](https://clashroyale.fandom.com/wiki/Version_History/2019)) | B mechanism; A that desyncs exist |
| Command scheduling | Every battle command carries **`TickWhenGiven` (`t`) and `ExecuteTick` (`t2`)**. These are the same keys our probe writes. ZrdRoyale has a commented `AddCommand(Type, ClientTick - 20, ClientTick, …)`, i.e. `t2 − t = 20`. | BerkanYildiz `Command.cs`; ZrdRoyale `LogicBattle.cs` | B for the fields; D for the 20 on its own |
| Execute-tick lead in today's client | Not published. Inferred to be about 20 ticks from three independent lines of evidence: FirstLight's `t2 = t + 20`, the native libg queue's 20-tick age check (`HANDOFF.md:323`), and ClashAI's 19.9-tick p1 floor. A fixed 20-tick lead is exactly two 10-tick server turns, enough to relay a command through one turn plus RTT before it is due. | Inference across the rows above | B− |
| Turn quantization | The old emulators batch commands into 10-tick turns. Quantization at the *execute* tick would spread tap→exec uniformly over about 10 ticks. ClashAI's decision→exec IQR is only 3 ticks (26-29) including host jitter, so today's execute tick is set by the fixed lead, not by turn boundaries. | ClashAI budget vs. BerkanYildiz | B (inference from measured spread) |
| Local feedback at placement | A floating "−N" elixir text appears at the drop point (KataCR detects plays this way). The emptied hand slot refills about 1 s later ("a 1-second delay when a card slot becomes empty"). This matches our engine's refill rule (`player.py:84-96`). A hovering card that returns to hand ("card drop glitch") suggests a local pending state that can be rejected. | [KataCR paper arXiv 2504.04783](https://arxiv.org/abs/2504.04783), [action_builder.py](https://github.com/wty-yy/KataCR); Sportskeeda (not fetched) | B; C for the glitch |
| Instant local ghost vs. delayed body | No source describes whether the client draws a placement preview instantly while the command waits for `t2`. ClashAI's memory reader shows the *engine* changes hand, elixir and bodies together at execution, but the UI layer could still show a placement marker earlier. Unresolved; the protocol's E1 measures it. | — | unknown |
| Typical tap → card leaves hand | No public number. ClashAI: tap return → execution median 22.6 ticks (1.13 s), p1 19.9. | ClashAI `budget_20261008.txt` | B (one setup, one network) |
| Tap → unit appears (deploying) | Same tick as the hand change (ClashAI `T_sp − T_rot` median 0). So about 1.1 s after the tap. | ClashAI | B |
| Tap → unit active | Tap → execution plus the card's deploy time: 1.0 s for 57/59 characters in old CSVs; Golem 3 s, Royal Giant 2 s, Goblins 1.0 ↔ 1.2 s across patches. Troops enter with load time preloaded (Sparky excepted). For a Knight that is about 2.1 s after the tap. | [ZrdRoyale characters.csv](https://github.com/Zordon1337/ZrdRoyale) (old data); [Supercell balance notes](https://supercell.com/en/games/clashroyale/blog/release-notes/balance-changes-coming-3), [April 2025 balance](https://supercell.com/en/games/clashroyale/blog/release-notes/april-balance-changes/); [RoyaleAPI secret stats](https://royaleapi.com/blog/secret-stats) | A/B for deploy-time values |
| Fixed delay "so regions aren't penalized" | Vendor claim. It would be consistent with a fixed lead, but it gives no number or source. | [ExitLag blog](https://www.exitlag.com/blog/clash-royale-lag/) (403; snippets only) | D |
| Official latency changes | "Testing new network technology…" (2016 soft launch); "Fixed lag and poor connection issues" (2019); 7/6/2021 fix for lag when a just-dealt card was played; "Latency has been improved" (31/3/2025, no numbers). | [wiki 2016](https://clashroyale.fandom.com/wiki/Version_History/2016)/[2021](https://clashroyale.fandom.com/wiki/Version_History/2021); [Supercell April Update](https://supercell.com/en/games/clashroyale/blog/release-notes/april-update/) | A statements, uninformative |
| ADB input latency | `adb shell input tap` dropped from about 500 ms to under 10 ms on-device in Android 11+ (AOSP, 2020). The host-side `adb` spawn dominates: about 197 ms per tap on BlueStacks/Win10, 73 ms per `adb.exe` start for ClashAI. | [AOSP commit 9a7d7db](https://android.googlesource.com/platform/frameworks/base/+/9a7d7dbfb55e19e56f932c8820448514837f39c6); [sendevent-touch](https://pypi.org/project/sendevent-touch/); ClashAI `adb_spawn_local.txt` | A/B |
| Replay tick semantics | FirstLight and a 2026 native-engine project rebuild IL_Replay/RoyaleAPI games by scheduling each command at `data-t` + 1 tick. Recorded human ticks are therefore (within 1 tick) **execution** ticks, not tap ticks. | [Jason-XII/clash-royale-battle-engine](https://github.com/Jason-XII/clash-royale-battle-engine); FirstLight; ClashAI "ACTION DELAY" | B |

**Separating the two quantities:**
- **Deploy time** is a per-card simulation rule (`DeployTime` ms, plus a `DeployDelay` stagger for multi-unit
  cards). It starts at the execute tick, is identical for both players, and is modelled by our engines.
- **Command latency** decides *which tick* is the execute tick:
  - our pipeline (frame → tap);
  - the input path (about 0 on-device; host spawn if ADB);
  - the client's fixed lead of about 20 ticks;
  - network, which in this model matters only when RTT and turn wait exceed the lead.

  None of it changes deploy time.

## Q4. Reconciling ClashAI's 1.40 s

ClashAI's `budget_20261008.txt` (B, 6,721 confirmed plays, read-only memory reader, 10 Hz reads, official client
build 160402012 on MuMu):

| Segment | Median | Comment |
|---|---:|---|
| T0 = decision frame tick → T_rot (confirmation frame) | 28 ticks (1.40 s); p95 44 | T_rot is an upper bound: reads arrive every 2 ticks |
| Midpoint of (T_prev, T_rot] − T0 | 27 ticks | best estimate of decision → execution |
| decide | 72 ms (≈1.4 ticks) | their code |
| two adb taps incl. 50 ms gap (`tap_ms`) | 150 ms (≈3 ticks) | per-tap `adb.exe` spawn alone is 73 ms (`adb_spawn_local.txt`) |
| board-tap return → T_rot | **22.6 ticks (1.13 s), p1 19.9** | "game/emulator/server, NOT ours" |
| T_el − T_rot, T_sp − T_rot | 0, 0 (median) | elixir, rotation and spawn land on one tick |

- **ADB/emulator input latency is about 0.15-0.2 s, not 1.13 s.**
  - The two `adb shell input tap` spawns cost about 150 ms together (p95 272).
  - Android's `input` returns after injecting the event. Whatever remains between tap return and the game reading the
    touch is at most a frame or two of game-thread pickup plus the 0-1 tick phase. The +2 in FirstLight's touch path
    is a comparable allowance.
  - The 1.13 s "outside our code" therefore splits into about 1.00 s of the 20-tick command lead, about 0.05-0.1 s of
    touch → command pickup and tick phase, and about 0.05 s of read quantization: T_rot overstates by up to 2 ticks,
    about 1 on average, since the midpoint is 27 versus T_rot 28.
- **Rotation happens at execution, not later.** `T_el = T_rot = T_sp` on the median, and native hand slots empty
  at execution and refill later (`player.py:84-96`).
- **Their own decomposition supports a fixed lead.**
  - OLS: gap = 25.97 + 12.1 ticks/s × (decide+tap). The slope is below 20 (expected from regression dilution, since
    host timings don't capture the whole host path). The intercept near 26 ticks at zero host time is the fixed
    game/emulator part.
  - Binned medians rise from 26 to 32 ticks as decide+tap goes from <200 ms to >400 ms.
  - Their HANDOFF says "Gap rises ~1:1 with host time", so pipeline latency adds directly and the game lead is
    constant.
- **The renderer matches the official client to within about one tick.** Hook: touch → execute = 22 ticks, measured
  D_b 23.0 tick-equivalents including polling. Official client: tap return → execute 22.6 ticks (upper-bound reads)
  or about 21.6 (midpoint). Under the same pipeline, the offline renderer is a faithful timing proxy for L3.

## Q5. Conclusion: d values and pipeline changes

### Recommended d

| Backend | Components (p50) | d_total p50 | Uncertainty / tail |
|---|---|---:|---|
| **(a) Offline renderer (hook, gRPC, Mac v4 runtime)** | frame→tap 186 ms (3.7 t) + hook 22 t + tick phase 0-1 t − duplicate tap/poll bias ≈ 0.5-1 t | **26** (27 is acceptable, ~0.5-1 t conservative) | ±1 tick; p99 about 28-29 (frame_to_tap p99 334 ms + D_b p99 23.7 t). No network. |
| **(b) Official client (same Mac pipeline, gRPC touch)** | frame→tap 3.7 t + client lead ≈ 20 t + pickup/phase ≈ 1-2 t | **26-27** | p50 ±2 ticks until measured. Network tail: ClashAI p95 decision→exec 44 t (about +16 over median), p75 only +1 t. Use a distribution, not a constant. |

**Does d depend on network RTT?**
- At the median, apparently not. The 20-tick lead is a client-side stamp that absorbs RTT up to roughly 1 s, and
  ClashAI's floor sits at 20 ticks regardless.
- In the tail, probably yes. Late arrival, server-side rescheduling or client stalls produce the p95 44-tick tail.
  Whether the server re-stamps late commands, and by how much, is not established (C).
- So d should be **a fixed 26-27 plus a measured, RTT-conditioned tail**. Log per-match RTT and the verification
  timestamps live; don't model RTT as an additive term at the median.

### Required pipeline changes (ranked)

1. **Keep d as frame → execute, and keep deploy time in the engine.** No change to the S6 planner's semantics. The
   double-count suspicion is unfounded. Optionally set `planner_total_delay_ticks` to 26 after the protocol below
   gives an exact native execute tick (not a polling upper bound). Until then 27 is a deliberate, small conservative
   bias.
2. **Give the opponent the same command delay in simulation.** Today opponent scripts act "without added command
   delay", both in the physical sim (LEDGER §Evidence; `IMPLEMENTATION-NOTES.md:23-24`) and inside rollouts.
   - Real opponents pay about 22 ticks from tap to execution, plus their own reaction time. They can't answer our
     executed Hog at t+27 before about t+27+reaction+22.
   - The current asymmetric setup is super-human on the opponent side by about 1.1 s. It inflates every measured
     latency cost: the LEDGER's +7.3 pp, S6's +2.7 pp and the planned S-d anchor.
   - Fix: give opponent scripts a pending-command channel with d_opp = 22 in the physical S-d arm and in loss
     reviews. Inside rollouts, give the opponent a delayed command too, so search doesn't over-value only-instant
     answers. Re-run the d=0 vs d=27 contrast with both sides delayed. This is the cleanest "latency cost" number we
     can get.
3. **Imitation timing.**
   - **Current state.** Human labels are recorded at the **execution** tick. `replay_tick_20hz`
     (`src/clasher/rl/human_replay_demonstrations.py:159`) is applied directly in the sim at the row tick
     (`human_replay_v5.py:339-402`). ClashAI confirmed by native re-drive that pro rows pair the play with the board
     at the tick it executed (`ClashAI HANDOFF.md:5624`, "ACTION DELAY 2026-09-25").
     - So the model learns π(execute now | board now): a policy that sees the board at execution time.
     - The human had to commit about 22 ticks (plus reaction) earlier, and the bot commits about 26 ticks earlier.
       Run on s(T0), the model's play lands on s(T0+26). That is 1.3 s stale: defensive placements trail moving
       troops, and spells aim at where units were.
   - **Option 1 (primary, cheapest): predict, then imitate.** Feed the proposal model the planner's own simulated
     state at the due tick, `t + d`. The delay-aware search already rolls the root forward to `due` with our pending
     command and the opponent's sampled actions. Score the proposals there.
     - ClashAI's crude linear extrapolation over 26 ticks recovered all of one model's lag cost (`v6lat` D26 0.845
       → 0.914 = its D0).
     - We have a full engine, so our forward state should be better.
   - **Option 2 (ablation): latency-shifted training rows.** Use the input at `exec − d_bot` (26) with the label at
     exec, and exclude the hand/elixir changes from the bot's own pending play. ClashAI's lat26 retrain did **not**
     beat delay-26 plus extrapolation (D vs C, train −3.3 pp [−7.7, +0.7]), so don't adopt it without a paired test.
   - **Option 3 (evaluation).** Every imitation-prior gate and screen must run at the same d as live (LEDGER item 1
     already asks for this). An imitation agreement metric computed at d=0 overstates live quality.
   - **Does the data need a timing transform?** The stored data doesn't, provided option 1 is used at inference. If
     the prior is ever used without a forward model, then yes, shift inputs by d_bot.
4. **Allow at least two outstanding commands.**
   - We block all decisions while one command is pending (`src/clasher/live/decision.py:117-119`; S6 single channel).
     With d ≈ 26 that is about 1.3 s of forced silence after every play.
   - The official client stamps every play independently. Humans drop two-card combos within ≤35 ticks in about
     3.5% of plays (ClashAI lat26 dataset note), and the live pending lock can't execute those.
   - Keep the ledger and the R2 double-spend protection, but let the ledger hold N≥2 reservations with distinct
     cards. Gate this behind a sim test first.
5. **Make the verifier and rollback per-backend, using distributions.**
   - This is already per-backend (`backend-timing.json`). For L3, D_b must be re-measured on the official client
     with the same probe-free method below.
   - Size the rollback from p99 of the **official** tap → execute distribution (likely ≥2 s given ClashAI's p95). The
     renderer's 1.19 s p99 is too short for it.
6. **Make the planner's d a distribution in rollouts once L3 data exist**, for example by sampling the due tick from
   the measured histogram per rollout. The ±1 tick matters little. The official-client tail (p95 +16 ticks) is where a
   constant d misleads search.

## Measurement protocol (for the coordinator; not run here)

**Goal:** exact tap → execute ticks and their split on (i) the offline renderer and (ii) the official client on the
authorized Mac emulator. No probe in (ii), plain taps only, Training Camp so no ladder opponent is affected.

1. **Setup (official, Training Camp, throwaway account, Mac mini emulator only).** Fixed deck with Knight (1 s deploy),
   Golem (3 s), Skeletons (≈0), Fireball (spell flight) and a building. Screen record at **60 FPS** with the emulator's
   own gRPC screen stream timestamps (`produced_at`). Log every injected tap with `perf_counter` at send and return.
2. **Trials.** 200 plays: 50 per card class, at random intervals (no rhythmic timing), elixir always sufficient. Use the
   production gRPC two-tap path at 20 ms inter-tap. Add 30 adb-spawn plays as a comparison arm.
3. **Frame-count events per play** (two independent annotators, or the v4 HUD reader with manual audit of
   disagreements):
   - E1 first frame the selected card's slot or the placement ghost/marker changes after the board tap (local UI
     acknowledgment);
   - E2 first frame the card slot empties and the elixir bar drops (execution, by Q1);
   - E3 first frame the deploying body/timer clock is visible at the tile;
   - E4 first frame the unit moves or attacks (active; E4 − E3 must equal the card's deploy time if E3 is execution).
   Convert to ticks with the in-game clock and the 20 Hz rate; ClashAI measured 19.94-19.98 ticks/s.
4. **Network arm.** Repeat 100 plays with macOS Network Link Conditioner on the emulator host at +100 ms and +300 ms
   RTT (and baseline). Record measured RTT per match. Prediction under the fixed-lead model: the E2 − tap median shifts
   by < 1 tick until RTT approaches 1 s; only the tail moves. If instead the median shifts about 1:1 with RTT/2 or RTT,
   the lead is server-assigned and d must be RTT-conditioned.
5. **Renderer arm.** Run the identical script on the offline renderer, adding probe `replay-schedule-status`-style
   receipts (or a native observe per tick at speed 1) to get exact `executeTick`. That replaces T2's polling upper
   bound and should yield exactly 22 + phase.
6. **Turn-quantization check.** Histogram E2−tap at 1-tick resolution. A uniform 10-tick (500 ms) spread, or a
   sawtooth against tap phase modulo 10 ticks, would mean execute ticks snap to server turns; d would then need a
   uniform 0-10-tick component. The fixed-lead model predicts a spike at 21-23 ticks.
7. **Replay cross-check (optional, after an authorized ladder match).** Frame-count our own taps in the screen
   recording against the in-game replay of that match (its timeline gives execute ticks). Use RoyaleAPI's `data-t` only
   if it is reachable without logging in. This measures tap → `t2` on the live network directly.
8. **Outputs.** Write `backend-timing.json` rows `official-client-grpc` / `offline-renderer-grpc` with exact-tick
   p50/p90/p99 histograms for E1-E4 minus tap, the per-RTT table, and the full histogram for the planner.
   - Acceptance: E2−tap renderer median = 22 ± 1, and E4−E3 = deploy time ± 1 tick (which confirms E2/E3 is
     execution and closes the double-count question empirically).
   - If the official E2−tap median differs from 22 by more than 2 ticks, update `planner_total_delay_ticks` and S-d
     before L3.

## Sources

Repo (A unless noted): `live-loop/v4/actuation/bench.py`, `backend-timing.json`, `T2-RESULTS.md`, `collector.py`,
`DESIGN.md` §2.5-2.8/§3.1, `runtime-mac-latency.json`; `amendments/2026-10-07-t2-actuation-timing.md`;
`search-noise-s6/delay.py`, `test_delay.py`, `IMPLEMENTATION-NOTES.md`, `RESULTS.md`; `src/clasher/live/timing.py`,
`decision.py`; `engine-rs/src/lib.rs`, `scripts.rs`, `differential.py`; `src/clasher/battle.py`, `player.py`;
`tests/test_native_spell_command_timing.py`, `tests/test_native_acquisition_load.py` + Tesla fixture;
`docs/history/HANDOFF.md:203,321-329`; `reports/explore/loss-review/LEDGER.md`; `reports/clashai_deepdive_20261008.md`;
`src/clasher/rl/human_replay_demonstrations.py`, `human_replay_v5.py`.

Web (graded in the Q3 table): BerkanYildiz/ClashRoyale (`Time.cs`, `BattleManager.cs`, `SectorManager.cs`,
`Command.cs`), SC-DevTeam/cr-messages, Zordon1337/ZrdRoyale, KataCR (arXiv 2504.04783), Jason-XII/clash-royale-battle-engine,
AOSP commit 9a7d7db, sendevent-touch, Supercell release/balance notes, Clash Royale wiki version history, RoyaleAPI
"secret stats", ExitLag (D). The web sweep was delegated to an Opus sub-agent at high effort; its URLs are in the Q3 table.

External source code (B): FirstLight_CR @ `28d66cc` `native_runner/probe/cr_replay_probe.cpp`,
`native_touch_probe_glue.inc`, `native_touch_interceptor.cpp`
(https://github.com/luody21/FirstLight_CR/tree/28d66cc0a5d65888515e22fdf22f11d783b65efb/native_runner/probe);
ClashAI @ `8d4053d` `scratchpad/gauntlet/L74/latency/{budget_20261008.txt,latency_budget.py,adb_spawn_local.txt}`,
`HANDOFF.md` (latency budget block 4687-4693; "ACTION DELAY 2026-09-25", "EXTRAPOLATION" and "LAT26 SCREENS 2026-09-26" inside the line-5624 block)
(https://github.com/vegetableleaf/ClashAI/tree/8d4053dfea1be589c4b487154ed2da1b98d6aa9e).

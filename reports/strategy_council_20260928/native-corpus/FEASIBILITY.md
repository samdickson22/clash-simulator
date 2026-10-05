# Offline native replay feasibility

Completed feasibility study, 2026-10-04. Recommendation: no-go for an unfiltered full-corpus build today; proceed only with a bounded reconstruction and public-observation prototype. The best same-50 pass configured and finalized 50/50 matches, injected every recorded command in 28/50, and agreed on crowns in 39/50, winner in 41/50, and all tower HP in 2/50.

The experiment uses only the existing offline Null's Royale reference and its installed FirstLight probe. No official client, accounts, game network, APK change, probe rebuild, or ClashAI artifact is involved. All new scripts are independently written under this directory. The external ClashAI review supplies ideas only; its Linux/KVM rates are not Mac measurements.

## Scope and source limitations

The 50 unique matches come from the already-local, unfiltered 5,000-row IL_Replay parquet. The source SHA, exact indices and sampling rule are in `sample-inventory.json`. Twenty evenly spaced records plus thirty greedy coverage additions cover 122 base cards, 180 card/form labels and all four tower troop labels. All 50 have evolution decks; 42 have hero decks; 49 contain ability events; 10 mix card levels; six use non-Princess tower troops. Deck levels range from 11 to 16. This is a coverage sample, not a random prevalence estimate for 252,238 matches.

The C56 payload wrapper preserves the same normalized payload, but filters out tower troop matches. Its existing payloads therefore cannot test full tower scope. The P16 pipeline also documented two source details that affect validation: princess HP fields are survivor-first, not lane identities, and timeline duration includes a post-game offset. Our six-HP comparison sorts the two princess values per side, retains king identity, and uses native terminal state. Exact recorded tower-kill ticks are absent, so kill-time agreement cannot be computed.

The source manifest explicitly says battle dates and collection timestamps were removed. Payloads lack client/content version. Version parity with the corpus is unknown; dates cannot be reconstructed from this dataset. Native attestation is content 15.535.86, APK 15.535.13, libg build `90e6f351f0dec4a28b494c3812d2629fd45d5a83`, installed probe SHA `2ea5e10dff5cfe763218d07ec17acdb4be1379eac51d6b4f827d887edc3c645c`.

## Input contract

The payload is RoyaleAPI action data, not native replay-loader JSON. Native `configure` needs numeric deck/support IDs, a location, mode/rule settings, native avatar/home-battle fields, `rndSeed`, and empty `cmd`/`evt` arrays. Historical actions enter separately through `replay-schedule-card` and `replay-schedule-ability`. `configure-native` also requires empty streams and adds rendering, not a route around missing source information.

Available source fields include deck card/form names, card levels, tower troop and level, side, 20 Hz action tick, native world coordinates, final crowns and tower HP. Missing or ambiguous fields include RNG seed, initial hand/queue ordering, independent king level, native mode/rule identity, exact active form at each play, authoritative ability source, client version, and tower-kill timestamps. Form-at-play is explicitly unknown. Initial deck order is a displayed deck list, not verified native shuffle order.

Baseline reconstruction assumptions are recorded in `study.py`: team is owner 0; native world coordinates and action ticks are used directly; seed is 1; mode is the exercised Ladder template; card level is the match's modal deck level; king level is assumed equal to tower-card level. Mixed levels are therefore not faithfully configured in this baseline. Native `sp.el` masks carry evolution/hero availability from source suffixes. They are not claimed to recover missing active-form history.

Action schedule success means native command injection succeeded. It is not independent evidence that every command took effect or that its ability target/form matches the real game. Pending actions after an early native terminal are failures of full timeline reconstruction.

## Measured replay agreement

Three passes reuse the same 50 matches. The first uses an arbitrary shuffle. The second assigns first-appearance card order to the observed shuffled hand/queue slots. The final pass also supplies explicit per-card and support-card levels. This last pass is the main result. It is still an inferred reconstruction, not a complete historical native replay.

| Measure | Arbitrary order | First-use order | First-use order + real levels |
|---|---:|---:|---:|
| Configuration accepted / finalized | 50 / 50 | 50 / 50 | 50 / 50 |
| Every recorded command injected | 1 / 50 | 26 / 50 | 28 / 50 |
| Exact crown pair | 16 / 50 | 37 / 50 | **39 / 50, 78%** |
| Winner/draw agreement | 28 / 50 | 40 / 50 | **41 / 50, 82%** |
| Exact six tower HP, lane-invariant | 1 / 50 | 2 / 50 | **2 / 50, 4%** |
| Mean absolute HP error per tower | 1,459.7 | 663.1 | **622.8 HP** |

Final-pass load/failure reasons, disjoint and in priority order:

| Result | Matches |
|---|---:|
| All recorded commands injected | 28 |
| At least one card-unavailable failure | 3 |
| Ability-unavailable, without card-unavailable | 3 |
| No explicit scheduling failure, but native terminal leaves commands pending | 16 |
| Configuration rejection, engine crash or transport exception | 0 |

Across 3,772 recorded actions, 3,356 were injected, 13 failed with card-unavailable, three with ability-unavailable, and 400 remained pending. Eighteen matches have pending commands when counting overlaps with explicit failures. No evidence supports calling all 28 injection-complete matches faithful state/action supervision: injection is weaker than execution, and HP agreement is low. The tick-20 diagnostic demonstrates this distinction directly: a command can be injected without a unit appearing. Our corpus sample has no actions at tick <=20.

Final-pass subgroup crown agreement is 30/40 for uniform card levels, 9/10 for mixed levels, 33/42 with hero decks, and 5/6 with non-Princess tower troops. These groups overlap and are too small and deliberately selected to estimate corpus-wide yield. Elite Barbarians evolution appears in native observations and caused no crash here. The external review's reported failure rate does not transfer to this reference.

Recorded tower-kill ticks are unavailable in all 50 inputs. Native deaths are recorded as intervals between observations, at most 20 ticks wide in the fidelity pass. There is no legitimate kill-time agreement denominator. End-of-replay duration is not a substitute for each tower's destruction time; the source includes post-game time. Native-vs-recorded outcome discrepancies conflate missing initial state, ambiguous abilities/forms, mode/king-level assumptions, timing conventions and unknown balance-version skew. They do not isolate an engine defect.

### Real level support

The existing command accepts `battle.deckN.sp[i].l` as a rarity-relative level index. A bounded read through the existing native level reader verified Giant values 0, 1, 9 and 13 as displayed levels 3, 4, 12 and 16, with max HP 1,875, 2,061, 4,355 and 6,339. Princess support `sc.l=1` reads level 2. The final pass uses displayed level minus the rarity start level, with Common/Rare/Epic/Legendary/Champion starts 1/3/6/9/11, and clears global level normalization. Sparse final-frame reads verify level-16 towers and level-15/16 bodies in mixed-level matches. This is concrete support for real level inputs, not exhaustive validation of every rarity, form, spawned child or Royal Chef level-up.

`levelled-order.jsonl` retains the exact native configuration, initial observations, final state and per-action receipts for each match. `summary-levelled.json` and `group-summary.json` contain the aggregate arithmetic. Earlier passes remain as controls.

## Throughput on this Mac

One owned read-only arm64 AVD used host GPU, render off, two vCPUs and 3 GiB guest RAM. Its serial/port were emulator-5584 / 26791. L1's emulator-5580 / 26789 and emulator-5582 / 26790 were not used. Attestation and both IP-family app firewall rules were checked before collection and again before shutdown.

The M4 Pro host has 12 CPU cores and 24 GiB RAM. Two L1 software-rendered emulators consumed about six to eight CPU cores together while C56 extraction, RoadForge and other work ran. Swap was already about 4–5 GiB. Our host-GPU emulator sampled around 0.4–1.0 GiB RSS during capture, with a 3 GiB guest allocation; the Python collector reached hundreds of MiB. These are loaded-host measurements, not isolated scaling tests.

The paired transport experiment runs two fixed reconstructed matches to native terminal at ticks 3,601 and 2,961. Both terminal states match exactly across all eight command/cadence combinations. The 3,288 retained compact benchmark frames contain at most 27 objects and zero truncations. Board density and long-match timing are not broadly sampled.

| Command and transport | Every N ticks | Mean seconds/attempt | Attempts/hour/emulator |
|---|---:|---:|---:|
| observe, session-v1 | 20 | 1.066 | 3,378 |
| observe, session-v1 | 5 | 3.054 | 1,179 |
| observe, new TCP connection | 20 | 1.909 | 1,886 |
| observe, new TCP connection | 5 | 6.344 | 567 |
| observe-rich, session-v1 | 20 | 19.069 | 189 |
| observe-rich, session-v1 | 5 | 75.879 | 47 |
| observe-rich, new TCP connection | 20 | 20.128 | 179 |
| observe-rich, new TCP connection | 5 | 77.661 | 46 |

These include configuration, scheduling, observations, JSON handling, gzip output and final action receipts. They are attempts/hour, not accepted human imitation matches/hour. Rich-only lacks the ordinary own-hand/elixir packet, and compact-only lacks rich visibility/shield/body metadata. Neither row alone is an admitted complete public observation generator.

Session-v1 reduces compact observation calls from about 4.13 ms to 1.90 ms. Rich observation calls remain about 69 ms either way. A terminal rich packet with only five surviving objects is about 9.9 MB because it includes cumulative combat/phase/runtime rings. A single 5-tick row-0 run transfers about 4.09 GB of compactly reserialized rich JSON, compressed to 72.5 MB on disk. Full-rich serialization and compression add further cost. The installed probe rejects `observe-rich-since` and `observe-atomic-levels`; source files for a newer phase-B build do not make those commands available on this APK.

A separate research projection uses existing `observe-atomic`, keeps own hand/elixir/next and rich entity identity/position/HP/shield, drops enemy invisible or visibility-unknown objects, and writes two perspectives without the diagnostic rings. One complete reconstructed match took **14.890 s at 20 ticks** and **63.659 s at 5 ticks**, producing 16,227 and 50,461 gzip bytes. Atomic reading consumed 90–91% of the time. This is still missing qualified public play-history extraction and dynamic body levels, and its visibility rule is not validated. It is a measured timing prototype, not a deployable actor adapter.

### 252,000-attempt planning projection

To avoid projecting prematurely ended reconstructions as full matches, this table scales elapsed time linearly to a 6,000-tick, 300-second gameplay budget. It is an extrapolation, not a measured long-match or multi-emulator result. Dense boards, finalization, retries and validation can increase it. Using the exact manifest count of 252,238 adds about 0.094%.

| Capture path | Cadence | Seconds / 6,000 ticks | Attempts/hour/emulator | 1 emulator, days | 2, days | 4, days | 8, days |
|---|---:|---:|---:|---:|---:|---:|---:|
| Compact session, incomplete public fields | 20 | 1.95 | 1,847 | 5.68 | 2.84 | 1.42 | 0.71 |
| Compact session, incomplete public fields | 5 | 5.59 | 644 | 16.29 | 8.15 | 4.07 | 2.04 |
| Atomic + small public-field prototype | 20 | 24.81 | 145 | 72.36 | 36.18 | 18.09 | 9.05 |
| Atomic + small public-field prototype | 5 | 106.07 | 33.9 | 309.37 | 154.68 | 77.34 | 38.67 |
| Full rich session archive | 20 | 34.87 | 103 | 101.71 | 50.86 | 25.43 | 12.71 |
| Full rich session archive | 5 | 138.76 | 25.9 | 404.72 | 202.36 | 101.18 | 50.59 |

The 2/4/8 columns are ideal division only. Eight 3 GiB guest allocations consume all 24 GiB before macOS, collectors and existing jobs; eight instances are not a supported plan on this loaded Mac. One additional instance was measured. One or two scheduled workers is the defensible initial planning range, with throughput remeasured under the eventual load. Nothing here establishes two-worker scaling, let alone eight.

The prototype's 6,000-tick storage extrapolation is 6.35 GiB at 20 ticks or 19.73 GiB at 5 ticks for both perspectives. That omits history, labels, full level evidence and final token arrays. Budget roughly 50–150 GiB of working storage for a full from-scratch dataset build, as an engineering allowance, and measure the actual schema before allocating it. Full raw-rich archival would be terabytes and is unnecessary. No full build fits the current approximately 14 GiB free disk with a safe margin.

## Public observation and full-scope vocabulary

| Information | Existing output | Remaining work |
|---|---|---|
| Unit/spell identity and active form | observe.cardId includes ordinary IDs, class-13 evolution IDs and class-203 hero IDs; rich adds dataGlobalId | Bind IDs to pinned native content; distinguish summoned body types; reject unknown or invalid dynamic identities |
| Position, owner, HP/max HP | Both ordinary and rich | Remove target coordinates/target identities and other private internals; handle disappearing/dead objects |
| Shields and invisibility | Rich shield/invisibleCount/visibilityState | Owner-relative public visibility is explicitly unavailable; validate a conservative actor filter for all stealth/form cases |
| Own hand, elixir and next card | Ordinary, or observe-atomic.ordinary | Keep only the actor's hand/elixir/next; decode own form from cardParameter low nibble; exclude opponent hand/cycle/elixir |
| Evolution progress and champion/hero ability state | Rich player evolutionRuntime/abilityRuntime | Own-side projection and validation; no opponent private cooldowns or future cycle |
| Card/body levels | Source deck/support levels; separate existing native level reader | Ordinary/rich contain no level field. Spawn inheritance, transformations, Mirror and Chef changes need validated treatment; per-frame external reads add cost |
| Opponent revealed plays | Timed scheduling plus native effects/command and hand changes | Build an accepted, causal public event history. Never copy future source plays or count an injection acknowledgement as proof of a visible play |
| Tower type | Input support-card ID plus rich towerTroopRuntime | All four types configured; validate public semantic interpretation and abilities |

Across the fifty baseline trajectories, ordinary observations emitted **169 distinct positive spell/form IDs: 118 ordinary, 36 evolution and 15 hero IDs**. All 169 map to names in the existing native asset tables. This is actual emission evidence; 122 base deck IDs configuring successfully is broader input coverage, not proof that every card/form mechanic or every source form was observed correctly. The sample contains 180 deck card/form labels. `vocabulary-inventory.json` records emitted IDs and names. The probe's complete-object limit is 256, so a generator must fail or explicitly mask truncation rather than silently train on clipped swarms.

A new vocabulary should use a stable base-card embedding for all 122 corpus cards, a separate active-form embedding, a content-qualified body-type token, and separate tower/support identities. Add spawned units, projectiles and public status types from the native catalog. Keep source card identity separate from body identity and native runtime object ID. None of this needs the Python 56-card engine or its fixed actor mask. The existing 360-token S122 work is a useful scope reference, not an automatically compatible native observation contract.

The action head should select wait, a hand slot, or an applicable ability, then predict placement on a **36 × 64 half-tile lattice**, 2,304 cells. Preserve source native coordinates for replay; quantize labels explicitly and record residuals. Ability source/action labels need their own validity mask. Own-hand legality and public placement masks must not inherit a 56-card restriction or consult opponent private state.

## Recommendation and conditional build estimate

**No-go for an unfiltered 252k full-corpus imitation-state build under the current data/instrument contract. Go for a bounded reconstruction prototype.** The native engine can configure all sampled cards/forms/towers and replay many actions at real levels. It is not confined to C56. The remaining problem is qualifying reconstructed states: 22/50 timelines remain incomplete, nine winner outcomes disagree, 48/50 final HP vectors differ, and there is no kill-time/version ground truth. Capturing richer public state through the unchanged probe also turns a full local build into weeks or months.

The next bounded milestone should independently implement seed/order inference with ambiguity tracking, verify mode/timing and all rarity/form level encodings, resolve ability attribution, and retain only causally valid prefixes. Repeat on a disjoint coverage sample, audit public visibility and revealed-play labels, and measure a complete compact actor record including serialization. Do not infer a full-corpus acceptance yield from this deliberately broad 50-match sample. This study did not test whether prefix cutting produces enough balanced data for a generalist.

Estimated engineering effort, all new code from scratch and conditional on resolving those gates:

| Work | Estimate |
|---|---:|
| Bounded input/initial-state/ability and public-boundary proof | 3–5 engineer-days |
| Resumable generator, per-action rejection ledger, schema, sharding, checksums and resource controls | 4–7 days |
| Dataset contract, match-disjoint splits, form/level/tower coverage audit and retention study | 3–5 days |
| Generalist BC model, card+form embeddings, entity encoder, recurrent/public history, half-tile placement and ability heads, training/evaluation pipeline | 5–10 days |
| Total engineering | **15–27 engineer-days, roughly 3–6 weeks** |

A roughly 3–10M-parameter first model is a design estimate, not an implemented architecture. At a 300-second budget there are about 151.2M two-perspective decisions at 20 ticks, or 604.8M at 5 ticks before retention/downsampling. Five full epochs would expose 0.756B or 3.024B rows. For illustration, a measured future rate of 10k rows/s would imply about 21 or 84 training hours before evaluation; at 1k rows/s, about 8.8 or 35 days. No model throughput or GPU performance was measured here, so these are sizing formulas, not promised training ETAs. A from-scratch full build on the unchanged richer observation path adds the capture times above, about 36–155 ideal days on two workers at 20/5 ticks, plus validation and fitting. A faster build requires a separately qualified observation path; simply using session-v1 does not remove the rich telemetry cost.

## Evidence and shutdown

- Input selection and source SHA: `sample-inventory.json`, `sample50.jsonl.gz`.
- Final replay configurations, receipts and results: `levelled-order.jsonl`, `summary-levelled.json`, `group-summary.json`.
- Controls: `results-terminal-50.jsonl`, `inferred-order.jsonl` and their summaries. `results-50.jsonl` is the preliminary pass with three nonterminal cutoffs and is not the final fidelity denominator.
- Command/level tests: `diagnostics.json`, `levels-probe-tick100.json`, `levels-verified.json`. The earlier tick-20 level smoke did not spawn a unit and is not used to establish level support.
- Timing: `benchmark.jsonl`, `benchmark-summary.json`, `public-benchmark.jsonl`, `public-benchmark-summary.json`, `public-exit.json`.
- Coverage and resource records: `vocabulary-inventory.json`, `measurement-validation.json`, `resources.jsonl`.
- Ownership, attestation and network isolation: `emulator/launch.json`, `emulator/complete.json`, `emulator/adb-operations.jsonl`, `shutdown.json`.
- Raw benchmark trace sizes/hashes and retention decisions: `benchmark-frame-manifest.json`. Six redundant full-rich traces generated here were removed after hashing; two representative rich traces and all compact traces remain.

The owned emulator was shut down with its serial after verifying PID/command ownership, unchanged attestation and both firewall rules. All owned study workers have exited. L1's two serials remain connected. New artifacts occupy approximately 41 MiB, below 500 MB. No protected source, frozen runtime, C56 data or L1 file was edited; no unrelated process was signalled.

Local source references: `m0/readiness/start_local_reference.py`; `src/clasher/rl/native_probe_transport.py`; `scripts/collect_native_public_game.py`; the installed probe source at `~/.cache/clasher-native-reference/firstlight-source-28d66cc/native_runner/probe/cr_replay_probe.cpp`; `m0/level-extension/sources/firstlight_match_factory.py`; `c56/data/scripts/fetch_payloads_c56.py`; `human-prior-p16/PROGRESS.md`; and the local IL_Replay `hf_manifest.json` beside the source parquet. The requested `live-loop/PROGRESS.md` does not exist; ownership was checked in `live-loop/l1/PROGRESS.md`, live processes and `adb devices`.

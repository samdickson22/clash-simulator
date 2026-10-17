# BOT LEAD progress (exploration)

Mandate: the strongest bot, judged by a trusted win rate. Coordinator ruling: COORDINATOR 91e2bb67 (exploration
tier). Report to coordinator thread 0523ae6f.

## Plan of record (coordinator direction, recorded 2026-10-16 19:37 UTC / 12:37 PT) — Opus BOT LEAD

Supersedes the Sol-interim handoff below (its grant process, STRICT SILENCE rule and "no relaunch" gates are void:
coordinator reset 2026-10-16, full authority, light process, use all compute).

**Findings that set the plan (reports/bot/live-diag/RESULTS.md):** Sam's live symptoms (late defence, few spells,
odd Cannon) are POLICY, identical in sim. The search leaf (engine-rs leaf.rs, 8 s) prices tower chip and gives
nothing for cards in hand, so search dumps elixir on cheap bridge plays and hoards Giant/Fireball (in hand ~90%).
Against R3a/v1/rext-bc (base wins 88–99%) 8 config fixes were null; against the search opponent LIVE-K4CW-r16 the
elixir reserve `-res` is +0.18 [+0.07, +0.30] (BASE3, 100 paired). Weak opponents hide flaws.

**STANDING RULE (2026-10-17 05:01 UTC): deck-diverse evals for the learned leaf / value work.** Sam picks and changes the live deck,
so improvements must generalise across OUR decks. At L16 the bot plays Sam's s62 deck (Bats, Zap) −9 pp pooled and
−17 pp vs K4C-r16 worse than the old e16 deck with -res, which suggests the leaf undervalues small spells and swarm air.
Every leaf/value gate gets a deck-diverse strong row: our deck ∈ {Sam s62, old e16, Inferno pick, ~5 Battle Log decks}
vs LIVE-K4CW-r16 at L16, reported per deck plus pooled, with spell and Bats usage. Leaf/value training data also rotates
our deck.

**STANDING RULE (2026-10-17 02:44 UTC / 19:44 PT, Sam via coordinator): evaluate PLAY at MAX card levels.** "When testing in the future, test
its play with decks at the max possible level for the card, not the current." All evaluations of the bot's play (deck-
quality screens, strong-opponent evals, A/Bs, gates, HEADLINE) run with every card on BOTH sides at the game's max level
(levelCount 16 in live16402c gamedata `items.rarities`; towers at max King level). Engines that cannot set levels must say
so in the report. Account-level reachability (current or reachable levels with our gold/copies) is reported only as a
SECONDARY row, and only where an actual upgrade-spending decision depends on it. Sam chooses the live deck himself (the
deckopt2 Inferno pick is superseded for live, 2026-10-17).

**Amendment 2026-10-16 20:02 UTC / 13:02 PT — Sam (binding): "we should train our model to hold back. The wait is fucking
reaction time up / quick plays."** Target design = per-tick receding-horizon decisions with holding back LEARNED,
not committed timed waits. Interim BASE5 vs K4C-r16: `-rh` −0.20 [−0.39, 0.00] vs base, `-res-rh` −0.04 vs -res,
i.e. today's scorer cannot bank on its own; that is the problem to fix, not the destination.
- **Learned-value track is judged in -rh mode:** success = a learned leaf/value under which receding-horizon beats
  today's timed-wait bot vs K4C-r16 and rext-bc; then timed waits retire from live. Train on paired spend-vs-bank
  continuations + strong-opponent games. A/B arms `-rh+leafcorr` vs base and vs `-res`. ETA first A/B
  ~2026-10-17 03:00–06:00Z (live-diag).
- **Policy side:** the fast student/RL learns per-tick play/wait that banks well (ClashAI-style), via RL/ExIt vs
  strong opponents with the FIXED teacher, not imitation of today's hoarding teacher. Starts after the fixed teacher
  exists; ETA ~2026-10-18 (full-pool owner).
- **Reaction-time stopgap:** `-res-wint` (interrupt the timed wait on a new enemy threat) vs `-res` vs K4C-r16, top
  priority now. If not negative (Δ ≥ −0.02) and reaction/undefended improve, it becomes the live treatment: before
  s53 if ready (~20:20–20:30Z), else at the next A/B restart (likely the full-pool bundle, tonight).
- **Every eval and the live A/B report reaction time** (enemy play → our first response) and undefended pushes.

1. **Today — live.** `LIVE-K4L-R-gs-rw-fc-w200-t4-p4-res` (main 7b693b8e4) goes to the ladder A/B at s52,
   alternating per session with base, preregistered in live-diag RESULTS §7 (mechanism metrics primary, win rate
   secondary). It is packaged against the Mac's pinned bot/ snapshot (live-diag, in progress). `-res-rh` (receding
   horizon: WAIT = no-op, re-decide next poll) replaces it if it beats -res vs K4C-r16 (testing now, ETA ~2 h).
   The full-pool bundle (pin live16402b-r3, extended nets, open-world belief, translator OOV path, Mac parity build)
   goes live when its gating A/B clears: aliased C56 K4L-R-gs vs full-pool K4L-R-gs, live deck vs 91 Battle Log
   decks, incl. a strong-opponent row. Owner bot-lead-fullpool-prep-r1, ETA ~23:00–01:00Z.
2. **Next main track — learned leaf value.** Replace the hand-made 8 s leaf with a learned value of the rest of the
   game (short search + learned value). Step one is live-diag option 2, an action-conditioned leaf correction from
   paired dump-vs-bank continuations played to the end (opponent mix incl. LIVE-K4CW-r16), A/B ETA ~03:00–05:00Z
   2026-10-17. Then a full value net on outcomes from full-pool self-play and strong-opponent games, features incl.
   hand, elixir, cycle, threats, plugged into K4L's leaf, A/B'd. ETA first A/B ~2026-10-18.
   **Known risk:** the earlier outcome-fitted leaf (bot-value-*) lost 26–43 pp from on-policy confounding (elixir
   got a negative weight). Mitigation: paired counterfactual continuations and diverse/strong opponents, not
   on-policy regression alone; blend with phi first.
3. **Then relabel** G1 student labels and K1 rollout data with the fixed teacher and retrain the full-pool student.
   No further GPU retraining of students on today's teacher labels beyond what the bundle needs (F1 f1a2 done).
4. **Gates.** Every gate includes a strong search opponent (LIVE-K4CW-r16 or better) as its own row, plus rext-bc.
   The daily HEADLINE task has step 1b for this. The ladder A/B is the final word.

**Owners:** full-pool + bundle bot side: bot-lead-fullpool-prep-r1 (Opus). Live diagnosis, -res/-rh, leaf
correction: bot-lead-live-diag-r1 (Opus). Sol helpers for evals/babysitting. Hosts: 01/03 full-pool generation;
04/08 live-diag hold (~20 each) to ~23:30Z, then full-pool.

**Utilization 2026-10-16 20:13 UTC:** the 04/08 hold for live-diag is lifted early (04 had 20 live python, 08 had 15). 04 goes to
live-diag db2 + -res-wint + the deck search; 08 to live-diag db2 + full-pool K1 on live16402c. 01 CPU is full (cap 89
with the LIVE loaders). **01 GPU: no bot GPU job is ready for ~6 h** (student fits done, the K4L trainer is CPU-only,
the leaf fit is small and data-bound). It's offered to the LIVE LEAD for YOLO until the value-net fit (~2026-10-17).

**Sequence amended (2026-10-17 11:52 UTC, LIVE LEAD):** under the measured truth-v2 enemy stream (histnoise v2) noise costs -res
0.00 [−0.14, +0.14], so the soft-cycle gain (measured under the older raw noise) may not exist live. New order: RESUME
res-wint → res-K2-wint (after the bench) → soft cycle ONLY if a v2-stream A/B (v2+hard vs v2+soft+P(real) v1 + clean,
200 paired, same fresh bank as live-diag's v2 replication) passes the ship rule. Translator fixes frozen except owner
v1.3 until the replication ranks a CI-clear component.

**Live sequence (2026-10-17 11:01 UTC, LIVE LEAD approved):**
1. RESUME `…-mk1a1-res-wint` (DD1 2×2: +0.0075 vs res; enemy→decision p50 0.65 → 0.15 s).
2. After 5 clean battles, the soft opponent-cycle model (CYC-L16-1: soft − hard +0.045 [−0.022, +0.112]; noise costs -res
   0.090 [+0.011, +0.169]).
3. Then `…-res-K2-wint` (DD1 +0.060 [−0.003, +0.125]), after the fixed Mac bench (B1–B3 + Sol re-review) passes at a
   planned ~10 min boundary pause.
Each step ships alone with its own rollback. Closed today: rh×cadence (plain WAIT loses up to −0.31; timed waits are
the banking), planner-levels (null), value-net v1 (failed gates; next = Monte Carlo sibling targets). Levels: all 8 +1 =
+33.5 pp at the measured ~1,850 prior, so clan requests go Valkyrie → Cannon → MiniPekka → Giant.

**Live default (2026-10-17 08:03 UTC):** `LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res` becomes the default live player at LIVE restart 4
(BOT LEAD agreed; 9/9 strong banks positive, neutral weak/rext at L16, live per-battle 17–8 vs 15–11). Open: the -res
enemy-noise sensitivity replication (rhcad-live BASE17). Settled nulls today: cadence (timed waits bind), report latency
≤0.7 s, own-play drops at the live clustered rate, cycle-rule noise for base. Next live slot: search budget K2 or rh/wint.

**Queue (2026-10-17 04:44 UTC).**
- **Cadence A/B** (live-diag): search every 10 / 5 / 2 ticks, × base/-res, × observed-play delay, at L16 vs K4C-r16 + R3a. It's the next live lever after -res.
- **own40 sizing** (live-diag): own-play history drops, clustered per battle, ~26% mean (translator OWN-PLAY-PATH.md).
- **Planner-levels re-test, when the CARD LEAD's native `levels` option lands:** live player planning at L11 vs at true levels, with sim truth at true levels, full-pool, vs K4C-r16 + R3a, ~100 paired. The earlier pilot was NOT_PROMISING, but only vs weak opponents. Live wiring (loop owner, flag) only if it wins.
- **Parked:** the cycle model (L11 sizing null; L16 cross-check pending); rlfp1 RL (no gain until the fixed teacher exists).

## Thread ID table (copied from delegate_task / t3_thread_list results; updated 2026-10-16 20:11 UTC)

Copy the ID from this table (or from fresh `t3_thread_list` output) for EVERY send. Never type or assemble one.
Message text is written before the call; a send under ~50 characters is never made.

| who | threadId |
|---|---|
| coordinator | `0523ae6f-baa3-4d4e-b233-b392671670db` |
| BOT LEAD (me) | `thread:delegated-task:command%3Amcp%3A53609d4a-a2de-484a-834d-8566c6339c9f%3Adelegate-task%3Aclasher-bot-lead-20261014-r1` |
| LIVE LEAD | `thread:delegated-task:command%3Amcp%3A53609d4a-a2de-484a-834d-8566c6339c9f%3Adelegate-task%3Aclasher-live-lead-20261014-r1` |
| CARD LEAD | `thread:delegated-task:command%3Amcp%3A7f0bf0df-35b9-48b9-bbf9-8f9cdcc3f584%3Adelegate-task%3Aclasher-card-lead-20261016-r1` |
| full-pool owner (Opus) | `thread:delegated-task:command%3Amcp%3Adfd92f6b-12ec-4f9d-b843-9d07e96ff7c2%3Adelegate-task%3Abot-lead-fullpool-prep-r1` |
| live-diag owner (Opus) | `thread:delegated-task:command%3Amcp%3Ad5b57bd6-719b-4e85-a080-8b8bfc639a49%3Adelegate-task%3Abot-lead-live-diag-r1` |
| deck search (Sol) | `thread:delegated-task:command%3Amcp%3Ad5b57bd6-719b-4e85-a080-8b8bfc639a49%3Adelegate-task%3Abot-lead-deckopt2-r1` |
| cycle-model owner (Opus) | `thread:delegated-task:command%3Amcp%3A9bf3df42-02c3-4805-9a05-5320eca9e4e7%3Adelegate-task%3Abot-lead-cycle-model-r1` |
| max-level HEADLINE (Sol) | `thread:delegated-task:command%3Amcp%3A9bf3df42-02c3-4805-9a05-5320eca9e4e7%3Adelegate-task%3Abot-lead-hlmax-sol-r1` |
| LIVE integration (YOLO/cadence) | `thread:delegated-task:command%3Amcp%3A99d49b81-f9ec-41a6-bede-03f9b418a3db%3Adelegate-task%3Alive-yolo-integration-opus-r1` |
| LIVE loop owner | `thread:delegated-task:command%3Amcp%3A99d49b81-f9ec-41a6-bede-03f9b418a3db%3Adelegate-task%3Alive-loop-owner-r1` |
| LIVE translator owner | `thread:delegated-task:command%3Amcp%3A99d49b81-f9ec-41a6-bede-03f9b418a3db%3Adelegate-task%3Alive-translator-oov-owner-r1` |

## Superseded handoff: Sol interim, 2026-10-16 10:01 UTC

Sam's UPDATED 2026-10-16 direction supersedes the blanket Opus hold: **make obvious decisions now**. Confident,
reversible changes may proceed within authority with meaningful passing checks, required reviews and concrete
rollback. Defer only consequential, hard-to-undo AND materially uncertain choices where Opus could change the
approach. Sol high is default; bounded Astra high where useful; no Claude limit retries. Preserve ownership/data/
gates. All image/crop/zoom work uses Sol. Screen/input-only fairness, Mac-only emulator scope, no heavy work on05
and never hosts09–18 remain binding.

**Coordination:** missing information, clarification and constraints go by `t3_thread_send(mode='auto')` to the
existing owner or parent `0523ae6f-baa3-4d4e-b233-b392671670db`, stating evidence/paths, recommendation and whether
dependent work waits; continue independent work. Do not use user-input tools. Propagate to all active descendants
and future delegation briefs. Actual permission controls remain unchanged. No old pending input request reported.

**STRICT SILENCE (latest Sam rule, supersedes earlier message discipline):** message ONLY when blocked needing
parent action, urgent live failure, explicit request, or essential dependency handoff. Max2sentences+1receiptpath.
No routine status/test/gate/review/queue/receipt/commit updates, acknowledgments or manualcompletion messages,
even if calledmaterial. Detailed commands/hashes/progress liveinfiles; parentreads them. Automatic taskcompletion
suffices; do not duplicate it. Coordinator broadcasts alreadyactivechildren; do NOTrebroadcast. Include thisrule
in every future/resumedchildbrief. Clarifications remain directT3parent/owner,neveruser-inputtools.
Report ONCE to owningparent whenWHOLEassignmentactuallydone(finalresult+artifact+remainingblocker); automaticT3
finaldeliverycounts,no duplicateDM. Essentialcross-ownerhandoffgoesdirectowner. Ownsubstantialend-to-endwork,
no tinypertest/perstepdelegation; independentreviews remainseparate. Includeinfuturechildbriefs.

**S40sharedcontractcoordination12:33Z:** existingloopownerretainse2eproducer/integration/review/release,andits
existingisolatede4v3backendhelperonly. No conflictinginterfaceWIPinthisBOTownedwork; no newworker/sharededit.
FrozenimmutableSlotPermissionAPIacceptedforcoordination(notrelease):independentcapture+backendpollbinding,
session-requiredfailclosed,legacyabsentparity. Criticallynativeaction_maskfeeds e4v3model featuresandmustremain
unchanged;separateeligibility_maskrestrictsactualchoice/proposals/candidates/fallbacksonly,notfeatures/roots/
ledger/cadenceorhypotheticalfuturehands. Detailedcache/capture/fallback/guardacceptanceguidance:
`contracts/S40-SLOT-PERMISSION-COORDINATION.md`. Allsteeringthroughloopowner;no competingimplementation.
At12:43Z actualdeployedbaseprovenanceisnowpreserved:28immutableMacsourcecopies and11BASEsourcepins(7runtime+
4bot),actual5361,source-declaredv5live/simulatorprojection/MRO+consumerentrypoints. Base/rollbackattributionuses
snapshot source/{runtime,code},notarchivalmain. ThisclearsbaseprovenanceONLY;staticMROisnotexecutedclosure,
and noimplementationacceptance/sharededit/integration/release/liveauthority. ReceiptSHA
`292c3544539dad48b2ad15ece31c190d2eebb90346781c5d304a072eaf5ab778` documentedinthecontractcoordinationfile.

**CPU coordination09:41:52Z:** 04literal live91+idleleases7+onepilot=99≤105, no logins; normaladmissionhas7slots.
CARDlead may move ONLYtemplatepilot to04 throughreviewedcpu_job1/nice15 afterexactsource/runtime/nativepreflight
andverified08queuedgroup exit. Normalwrapper remainsauthoritative; no bypass/otherjobmove/pinchange.
BOT read-onlyreceipt: `/mpac/sdicks02/jobs/clasher/bot-sol-resume-20261016/cpu-room04-20261016T094152Z.json`.

**CPU/GPU08coordinationupdate11:54:59Z:** CARDpostanalysisclaim664663naturallyadmitted;analysisPID2382206,
exit-code0,112scenarios/0errors;that specificretrydeferralfulfilled. GPU08/GPU0idle,no BOTleasechange;standing
LIVEownershippreserved. Currentnormaladmissionlive62+idle0/cap105=43slots;proposed12wouldtotal74.
LIVEsolee16clean08-only20epochrepeatCPUallocationconfirmed:normalcpu_job12/nice19,10loaders,single-threadmath;
reservefullconcurrentfootprint(up to16onlyifreviewed/needed),CARDbeforetrainerbeforeNEWBOTretries,no01.
No trainer/transfer/hostinstallauthorizedbythisresourceconfirmation;existingreview/hash/input/offhostcopy/
evaluationgatesremain. Existingrunningjobs/caps/wrappersunchanged,no bypass/preemption/migration/duplicate.
Proposal `/mpac/sdicks02/scratch/live-perc-r3/audit-20261016/clean08-intake/next-trainer-proposal.json`.

- **Best student remains RL r5 v10**, threshold 0.5375, SHA256
  `e188e2aeb9a6828ffbef237aa327e495eb39ca5f8322ae18aa70c63cb81bba19`. Iteration 10 is complete: r9 v4's F10
  delta was −0.003 [−0.026, +0.021], not confirmed (2,000 games, no errors). Details: `exit/PROGRESS.md`.
  C56 feeders deliberately remain OFF for G1. RL r9/r10 are checkpointed and paused; GPUs remain LIVE-owned.
- **Full-pool G1/K1:** existing Sol babysitter `fullpool-g1k1-babysit-r1` is active. Latest 09:36:35Z receipts,
  independently reduced from its log: G1 6,917 attempts / 6,848 successful / 2,748,605 labels / 69 known errors;
  K1 2,244 attempts / 2,233 successful / 1,385,311 recording rows / 11 known errors. No new error type or >8%hostrate.
  All 13 recorded process groups alive. Existing r2 retry/preflight rules remain in force; no new root is promoted.
  Optional newK1shards3/4/5 DISABLED by BOT decision: retain existingjobs+authorizedretries/backoff only.
  01GPU recovered56→99%,lowstreak0,nohalving;04/08idle/nocompute.03preflight4043492 stillqueued/noPASS;
  no03r2 use. Literal03count108 vs97actualPython inherited; no new oversubscription. r2taggedrowsG1=703,K1=1703.
  See `fullpool/PROGRESS.md` and `/mpac/sdicks02/jobs/clasher/bot-fullpool/babysit-g1k1.log` on 05.
- **Revealed-set round 7:** existing Sol collector `revset-r7-collect-1` active. Floorchk 0/60, smoke 0/40 at
  09:05:46–47Z. Both wait on the canonical 03 cpu_room.sh: live count 107, cap 105, leased_idle 0; all five
  lease owners and all three claim owners alive. This is live-count saturation, not a stale lease. Bash wrappers
  containing "python" inflate that conservative count; no accounting script or priorities changed.
  LIVE comparison complete: patched 217 passed / 9 failed / 7 skipped, unpatched 178/9/7, identical failure sets.
  The +39 passing tests do not clear the pending floorchk/smoke gates or authorize deployment.
- **Level pilot: serial design accepted; remaining gates block bank/games.** Mapping-specific hold LIFTED at09:18Z:
  raw equality3/121 versus canonical nativeJSON121/121 proves tuple/list serialization mismatch, not stat mismatch.
  All13 tower checks pass and2 configs regressions pass. L11 export121/0errors; L4/5/6/7/9 each118cards with3known
  errors(Clone/Earthquake/Tornado). Original exports preserved. DEV A runner previously passed4tests and4/4repeat
  hashes/logs/towerHP,8/8wins; this is harness evidence only.
  **Decision:** original serial100case paired A/B/B0 is authorized AFTER all mandatory gates and fresh launcher
  review pass, without another confirmation. A=unchangedL11; B0=existingrootonlyapproximation;
  B=exactownlevels/towers/per-seatpayloads +fairfixedopponentraritymedian +crownmetadata2030/3312.
  B metadata affects leaf AND scripted crown spell lethality/Lightning; learned features match for identicalstate.
  No pooledLIVE claim; no need to solve pooleddeployment to run this serial experiment. Astra diagnostic supports
  this scope; no categorical Opus deferral. Rollback selectA/removeexperimental root/native hooks; frozenruntime,
  pins and weights untouched.
  **Coverage decision:** fixed supported-card prior identically across A/B/B0 and policy pollers before any player
  starts; retain original projection catalog. Excluding Clone/Earthquake/Tornado removes425/2925beliefdecks and
  15371/69380frequency(22.1548%),leaves2500decks; all54true-deckprojections unchanged. This is a conditional-population
  physics pilot, NOT literal deployed-prior equivalence. Require common ordered-prior digest, root reachability,
  provenance/resume and all11 parity checks; no silentL11 fallback/post-outcome exclusions. Receipt owned by level
  worker: `levels/receipts/scope-audit-r1.json`. Mandatory root/card/spell/fairness/fc/rawpooltransport/all11 and
  launcherreview/provenance gates remain. No fresh bank drawn or pilot strength claim. See `levels/PROGRESS.md`.
  At09:28Z the fixed scope is implemented in experiment-only scope.py/playerfactory and bank original-projection
  equality guard; fresh independent scope review active. Existing gateworker drafts actualroots/fairdecisions both
  seats and explicit rawfc A→B→A; harnessworker fixes fullmanifest-before-resume, nonzero failures/completeness/
  parity and owned-childcleanup. Finished bytes receive fresh review before tests. All01exports complete; no01
  compute until reviewedgates. Original03probe verifiedabsent and requeued ONCE09:26:07Z,N4lease/nice10/30mintimeout,
  queuedPIDs287537/287538; no duplicate/spinretry and no bank/primarygames. Final receipt hashes await exact owner
  audit; do not infer from filenames or partial digests.
  Owner published docs/receipts only in `f85c66d375a949e007d9aeff6983c3f028c64b50`; BOT verified all24paths
  underreports/bot/levels and both committedblob/localreceipt hashes. Mapping/towers receiptSHA256
  `cd30432de666b2e58929f59702c358b630298f36bb7c93127038b93a31b04645`; scopeauditSHA256
  `c7f2c5beac6c67da79ddb4295900978b6ae6f41af40d8dbe5fb841005ef8334d`.
  Additional reviewed01scope/configtests4passed0.24s; localreceiptSHA256
  `9c714207acdb4637742c0d3473ba4d87be7b978f65d5b0063c39ad919e6fa9d7`.
  Scope reviewr5 found no new concrete scope/projectionblocker; it approved lightweight tests only, not pilotbank.
  Gate implementation finished; fresh independent executionreview next, harnessprovenancework continues.
  **Historical reviewed gate runr6 FAILED85/90 on01 (superseded by R11 below):** mapping121/121 and13towersPASS; actualBfair-informationPASS4decisions/
  4positive rootcalls, identicalroots/actions underhidden5vs7 bothseats,zero searchfailures.32syntheticpublicbody
  payloadstatsPASS,but native snapshotphysicscomparisonsFAILbothseats. Sides/spell/cutraisedAttributeError because
  pinnedBattleStatehasno deploy_card method; fixtures must use existingNativeScripts.apply_discrete,notrebuildruntime.
  Existingowner repairs/reviews fixtureAPI and adds exactentity/field snapshotdiff before any acceptance change.
  Receipt remains01:bot-levels/dev/gates-all-r6.txt; BOT read it directly09:39Z,localcopy initiallypending.
  At09:40:19Z BOT verified local `levels/receipts/gates-all-r6-failed.txt` SHA256
  `819406620ba64ba8dfaac500c57af5389347e85a1c9b5d194fa3b67838385cab`. Repair prints rawentity/field
  values/types first; only source-proven missing String defaults may normalize. NumericHP/damage/maxHP and
  owner/class/key checks stay strict; freshreview/executed evidence required before accepting any repairedgate.
  Pilotbank/games stillBLOCKEDbyfailures; fair/bodypasses do not waive nativephysics/all11/rollout/harnessgates.
  **09:46Z sourcebug:** Fireball/Arrowscarriers shareempty stats.name; firstproducer selection could applyArrows
  stats toFireball whenbotharebelieved. Existingownerfix usespublictemplate spell_name (not hiddentruth), with
  qualifiedspellhandling andunknowncardrejection; bothspellsruntimefixture/regressionadded. BOTsourceinspection
  confirms path,notacceptance; freshreview/runtimegatepending. ExactrootSHA
  `fb6321a0ce198fdd32de0902280306d4b1eaa11524ad67e322fd96fd88aa91e8`; test_configsSHA
  `762bc666079119d5559fac29401d59f2c3fbc8798bee83168b06b675bbcb0be0` at09:46:59Z.
  **Current R11 pinned-runtime suite254/254PASS**, receiptSHA256
  `11e2cf3b00b465437df396d8b0852701298cc43fbdf5be51d69e92cb408f672c`. Exactsnapshotdifferences areonly20
  absent spell_name→emptyString fields(10/seat); nonumeric/type/entity/order/position/qualifiedkeychanges.
  32publicbodies;30actionvaluesmatchuncut throughcut/snapshot/rawfcworker;A→B→Acontentkeychange/reuse,shipped[1,2,2];
  4fairdecisionspositiveBrootcallsbothseats. Finalmatching-byte114testsPASS1.49s,R12reviewconditionallypermits
  all11thenprimaryafterPASS. Complete-gameall11currentlyrunning4cases,bothseats/controllers,positiveBrootrequired;
  no edits/syncoverexecutingbytes. Finalv2provenance/completeness+all11terminalacceptance remainbeforebank.
  **Probe scope decision:** original03r1/r1-totalexploratoryunvalidatedprobe twiceexpired30mininadmissionwithout
  execution;documentnonblockingresourcedeferral,no03window/retryneeded. Reviewedmatching-runtimegatesprovide
  substantivepilotvalidityevidence; no waivedmandatorygate. Ownerreceiveddirectscopeanswer;no primarybank/outcomes.
- **GPU reconciliation (LIVE/r3 owners):** 04 V7lo1024 completed rc0 at 08:39:34Z; 08 V6lo completed rc0 at
  08:53:40Z. Eval loops remain alive. 01 V8 PID 1967844 remains active around epoch 9/20. Idle 04/08 GPUs are
  completed jobs, not failures. Existing GPU ownership and resource coordination remain; no trainer was restarted.
- **Descendant inventory:** 67 unique descendants at inspection: 4 running (all Sol), 57 completed, 3 interrupted,
  2 cancelled, 1 idle. Interrupted/cancelled tasks are superseded or already delivered results; the idle throughput
  researcher already delivered its result. No actually stopped unfinished descendant needed restarting. No duplicate
  jobs or review rounds were launched. The level helper completed after this inventory snapshot.
  **Later heartbeat correction:** a new revset-fix-r2 report-handling turn failed on Claude after the collector's
  diagnosis. Coordinator switched that exact owner thread to Sol high and resumed only report/handoff acknowledgment.
  The original coding task stays complete; the existing Sol collector and all jobs/gates/priorities are unchanged.
- **Next concrete action:** existing level owner implements/gates the accepted serial design and fixed prior scope;
  run the original pilot once all validity/review/resource gates pass. Keep G1/K1 and round-7 collectors active;
  existing template/root fixes may release only after exact reviewed/gated receipts and host preflights. Fits keep
  their data/resource/review gates. Daily HEADLINE remains enabled for13:00Z with the existing protocol.

### UTC audit

Audit, inventory and exact continuation commands: `audit/SOL-RESUME-20261016.md` and
`audit/sol-resume-descendants-20261016.json`. Parent coordinator was notified on resume; LIVE was notified of
the idle GPU receipt and confirmed clean completion. This continuation has made no account actions, signalled
no process, launched no compute job and changed no runtime/model pin. No rollback was needed.

## Layout

- **Worktree:** `/mpac/sdicks02/repos/clasher-bot` on 05, branch `bot/lead`.
  - Code lives in `bot/`, reports in `reports/bot/`.
  - The tree is synced to 03 and 04 with `rsync -a bot/ HOST:/mpac/sdicks02/repos/clasher-bot/bot/`.
- **Envs on 03:**
  - `/mpac/sdicks02/repos/clasher-bot/.venv` (py3.12, `uv sync`, plus royalesim 0.1.34);
  - `/mpac/sdicks02/repos/clasher-bot-rsim/.venv` (`royalegym[all]` 0.1.24);
  - upstream clones (read-only reference) in `/mpac/sdicks02/repos/clasher-bot-rsim/upstream/{RoyaleSim,RoyaleGym}`.
  - Source `bot/env.sh` for the cargo and uv cache paths.
- **Data on 03:** `/mpac/sdicks02/repos/clasher-bot-data/t1-trainval/` holds the 577 train+val match dirs (no
  video), copied read-only from 01. `t1-split.json` is the registered split.
- **Job dirs:** `/mpac/sdicks02/jobs/clasher/bot-*` on 03 and 04.

## Done

- **2026-10-14 ~03:15Z, step 1 fidelity:** `reports/bot/FIDELITY.md`. Results are in `bot-fid-r2` on 03.
  - No towers, within ¼ tile: RoyaleSim 15.535 **78.8%**, ours **51.4%**, RoyaleSim 16.402 72.1%.
  - Paired: +26.1 pp for RoyaleSim, better in 530/577 fixtures.

- **2026-10-14 ~03:25Z, step 2 speed:** `reports/bot/SPEED.md`.
  - Rust core 34.3k ticks/s with a 5 µs clone; RoyaleSim 30.8k (16.402 rules) or 14.2k (15.535 rules) with a ~5 ms
    save+load branch; Python 521.

- **2026-10-14 ~03:45Z, RoyaleSim clone spike:** `reports/bot/RSIM-CLONE-SPIKE.md`.
  - `restore_from` takes 9.8 µs. The fork is byte-identical to the PyPI wheel on fidelity.
- **2026-10-14 ~04:00Z, step 3 (our engine):** `reports/bot/STRENGTH.md` and `HEADLINE.md`.
  - K4S-b64 pool score 0.864 [0.847, 0.882].
  - Sampling the gate costs −24 pp; v1's calibrated threshold is τ = 0.1387.

- **2026-10-14 ~04:35Z:**
  - RoyaleSim headline: K4S-b64 pool 0.851.
  - Step 4 decision ACCEPTED by the coordinator: plan and train on our Rust core, trusted headline in RoyaleSim,
    calibrate ours behind the 577-fixture gate (`DECISION-ENGINE.md`).
- The v1-τ arm collapsed (−45 pp): thresholds must be calibrated on-policy.

- **2026-10-14 afternoon:**
  - The engine calibration batch 1+2 is merged into main (0ecdd97d, tag `engine-r1`). Fidelity is 72.3/74.5%; parity 574/577.
  - The planner A/B on r2 vs r1 is null. Learned leaf value: negative. Candidate round 2: R3a top-16 confirmed.
  - **Best bot: K4C-r16** (fresh-bank +0.021 over K4S-st). RoyaleSim P1 0.921, v3 0.924.
  - **Best student: it5s2** (ExIt; 0.883 vs v1). HEADLINE-v3 adds the human-clone external `rext-bc`.

- **2026-10-15 ~00:50Z:**
  - **Best bot: K4L-R-gs** (K4C-r16 with a learned rollout opponent). Fresh bank, RoyaleSim: +0.055 [+0.040, +0.069]
    over K4C-r16 at equal CPU (`reports/bot/learned-opponent/`). Turn-based tiers only until its rollouts fit 200 ms.
  - RL fine-tune of it5s2 (PPO, KL-anchored): null (`reports/bot/rl/`).
  - ExIt iteration 7: 9 refits of it5s2, none better; it5s2 stays the best student.

- **2026-10-15 06:42Z:** live K4L variant `LIVE-K4L-R-gs-rw-fc-w200-t4-p4`: 4-core p50/p95 79/126 ms, +0.058 [+0.020, +0.095]
  vs K4CW-r16 at a real 200 ms; fresh bank 2 +0.053 vs K4C-r16. Handed to the LIVE LEAD (hook + Mac timing pending).

## Historical running status (2026-10-15 06:42Z; superseded by current handoff above)

- **ExIt it9** (`bot-lead-exit-it9-r1`, Opus) on 01/04/08 (GPUs + CPU feeders): gentle refits of it5s2 and Kall on all labels.
- **K4L round 2** (`bot-lead-lopp-r2-r1`, Opus), primary host 03: learned-term weight, multi-sample, opponent model v2.
- **Daily headline:** T3 scheduled task at 13:00Z (v1 + v3), best bot from this file.
- **Hosts:** 01, 03, 04, 08 (05 light only). Exclusions: 01 PGID 516161, x4s4-onpolicy, t1-*; 08 v4-b-20261012-r1.

## Next

1. ExIt: next best student, both engines plus rext-bc. Feeders switch to on-policy behaviour.
2. Search scorer: the scripted opponent models inside rollouts. These are the remaining lever after the candidate and
   leaf nulls.
3. Re-headline the best bot when the code changes. Live play is a separate, later authorization.

## Daily recovery deputy — 2026-10-16T13:17:50Z

Canonical BOT scheduled run218 and Sol219/220 failed BEFORE work on provider-handoff context allowance; historical thread preserved, no Claude retry/fleet. Compact substantial recovery deputy task `node:delegated-task:command%3Amcp%3Adf0389d9-158c-4b1a-9667-b7602236a666%3Adelegate-task%3Abot-daily-headline-context-recovery-sol-20261016-r1` owns only unfinished daily/resource reconciliation. Existing owners/jobs unchanged; latest strict quiet and all gates apply.

Exact pre-draw audit found noOct16bank/output/activeheadline on04/08; adopt none. Fresh BASE **3877999783388832**, drawn **2026-10-16T13:17:50Z**, registeredHEADLINE BEFOREgames; planned paired2400games via unchanged reviewed detach/cpu_job/bot-lopp-run launchers,04lease9/workers8/cases0–79;08lease33/workers32/cases80–399. Standardcpu_room/cap105/maxeval08=36; LIVE08lease12admitted3609461/trainer3609621GPU95% retained. Existing fullpoolbabysitter received essential release of retrypriority deferral only; no newshards/speculation. Existing levelR27invalid55rows/16GAME_OVER remainsstopped, R28source-onlyowner/review continues; no retry/acceptance/rebank bydeputy. ChampionK4L-R-gs and fastRLr5v10 unchanged.

Fixedbank continuity re-confirmation source unchanged from accepted daily0cd7fd28 (143trackedbotfilesequal; changed/absentlive-only andaccountingfiles not in turn-based path), prior24/24commandhash equality retained; finalrowslabelselection-biased. R8isolated15-fileSlotPermissionimplementation/freshSolreview pending;all11BASEsactualMacattestedincludinglopp_fast,immutableAPI/twomasks retained,no competingcode/sharedintegration/release/liveauthority. Detailedcommands/receipts/blockers: `audit/SOL-DAILY-RECOVERY-20261016.md` and `/mpac/sdicks02/jobs/clasher/bot-daily-recovery-20261016/`. No gamesstartedatregistration.

**Daily13:18Zactualadmission:** preregcommitbb74fc17 beforejobs;04PGID3261204 lease9/8workers/480rows,08PGID4091359 lease33/32workers/1920rows; bothactuallaunch.json matchBASE3877999783388832/rsim15535/samepairedcases. Conservativecounts04=71,08=75under105. Routineprogress/receiptsinaudit; resultsPENDING, championunchanged.

**Recoverycollectorcorrection:** existingrevset-r7collectorCOMPLETED/parked(commitd4926a9f6679),floorchk30/30hashidentical,40/40terminalsmoke/0errors,patched217vs178passeswithsame9fail/7skip. Supersedes09Zqueuedstatus; no restart or deploymentGO. Fullpoolbabysitter retains authorizedretryownership after08LIVEadmissionpriorityrelease.

**R8coordination13:30Zupdate:** exact15-sourceofflineimplementationnowindependentGO(RELEASE.json,reviewhashverified),supersedesreviewpendingonly; canonicalbot/live/player.py0e1c0d88 differsattestedbase3b4f27d7,preservedprivatebytes/diff,nooverwrite. Executableportdeltafreshreview +existingintegration/release/prehost/separateplaygatesremain;acceptedAPI/twomasks/NO DRIVER/PAUSEunchanged.

**R8sourcepublication13:54Z:** canonicale883a80da015360f6c19b2eb1f2cd6e10c2aa8d8 exactreviewedport/scanner0; deputyverified15sourcepins. Localplayer0e1cWIPpreserved, nooverlappingcodepublication; futuresurgerymustusepublishedsource/reviewexecutabledelta. Actualhost/runtime/pin/playauthorityabsent, NO DRIVER/PAUSE/LL0/separatehostprofileunchanged.

### Daily recovery complete — 2026-10-16T14:15:43Z

**Fresh quoted RoyaleSim15.535 pool: K4L-R-gs 0.878 [0.859, 0.895]; paired K4C-r16 0.826 [0.804, 0.848]; Δ+0.052[+0.028,+0.076].** BASE3877999783388832 preregisteredbb74fc17beforegames;2400/2400uniqueterminalrows,400/opponent/bot,0errors/missing/duplicates,bootstrap4000seed0equalopponents. R3a .810/.740,v1 .9275/.8625,rext-bc .895/.875. Fixedbank(selection-biased)re-confirmedRS P1 .931/v3 .937;oursP1 .935,0rerungames. Champion/faststudentunchanged. Both04/08ownedgroups/leasesgone;before/aftersource/runtime/modelpinsmatch,logs0bytes,noinventedlauncherexitcode. Allcommands/rawmanifest/exactCIs inrecoveryaudit/job; standard summarizer crosscheckPASS.

Existingfullpoolowner ownsnormalr2retries/root/data/reviewbarriers,08LIVElease/trainingprioritypreserved; nospeculativereplacements/partialpromotion. Revsetcomplete/parked. ExistinglevelR30actualownerreport300/300quality_oktrue,parentexit0; thisdoesnoteraseR27invalidrawfailuresorconstitutedeputyacceptance/promotion. Existinglevelowner/parentvalidatesfinalinputs/cache/reportdecision; nofrozenfile/gameactionbydeputy. R8sourcee883/mainhooksandlocalplayer0e1cWIPpreserved; publicationONLYfiveownedreports/contractpaths,nocodeoverlap/host/runtime/pin/playauthority.

CanonicalhistoricalBOTthread remainscontextblocked, nextoriginaldaily17Oct13Zstillboundthere; no retry/compactionfiction/duplicateschedule/fleet. Recoverydeputycompletedonlyunfinisheddaily/resourceassignment, exacttaskID inaudit. Oneautomaticwholeassignmentfinal toowningparent,nomanualDM.

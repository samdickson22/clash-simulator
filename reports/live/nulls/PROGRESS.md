# Null's Royale labelled-frame generator: progress (resume from here)

Owner: live-nulls-generator-opus-r1 (exploration tier). Parent: the LIVE LEAD.
Current scope: full native frames for every detector-supported card, both teams, with synchronized native identity/owner provenance and audited visible-body labels. Historical cut-out phases below are superseded.


## r2 night (Opus capture owner r2), started 2026-10-17 ~09:32Z — resume from HERE

Owner: live-nulls-capture-owner-r2 (Opus). Lean process per Sam/LEAD 10-17: one Sol review per new Mac script, no receipts/seals.
- **Code:** `live/nulls/night/`
  - `nightcap.py`, Mac, one process per instance (`start|run|down|status --inst N`): boot, offline isolation, then capture: paused 1–2-tick `advance-native`, a gRPC native 1080x2280 frame rendered after the advance, observe-rich before and after plus plain observe. Writes chunks + manifest + READY.
  - `pull.sh`, 05: rsync READY chunks to `scratch/nulls/night/raw/`, delete the Mac copy, verify sha256.
  - `label.py`, 05: labels into `scratch/nulls/night/i<N>/<run>/chunk-*/` (format night-label-1, agreed with r3 09:40Z) and writes `scratch/nulls/coverage-night.{json,md}`.
  - `queue.json` holds the card order.
- **Mac layout:** code `~/clasher-live/nulls/night/code/`; state, logs and receipts `~/clasher-live/nulls/night/state/` (inst-N.json, night-N.log, claims/); output `~/clasher-live/nulls/night/out/iN/`. STOP / STOP-N files stop runners. The GO file is written by me after the NULLS-BLOCK handshake.
- **Instance N:** adb 5049 (shared), console 5596+2N, probe 26795+2N, gRPC 8596+N; `-memory 1536 -cores 2`, nice 10, no taskpolicy -b.
- **Guard (3 s):** disk ≥ 10 GiB; swap < 1 GiB and pressure normal (else the highest live instance stops); no live-driver python; STOP files.
- **Scenes:** target card for BOTH teams (team 1 bottom-left lane, team 0 top-right lane). The other side then answers with Zap → Freeze → Knight → Fireball. ≤ 900 ticks. 6 empty background frames per run.
- **Geometry (unverified until the Sol check):** x = 0.048·mx + 108, y = 0.0385·my + 585 (block-1 replay layout + 180 letterbox). Viewport candidate [0,180,1080,2100].
- **Offline check:** label.py run on block-1 frames padded to 2280. Giant/Musketeer boxes at t270 are within ~0–24 px of the audited v3 boxes; overlapping units use class-size priors (flag `split`).
- 2026-10-17T09:46Z: plan sent to the LEAD (approved), format agreed with r3, translator owner informed. Sol review r1 of nightcap.py + pull.sh is pending. No emulator booted.
- 09:54Z NULLS-BLOCK received (loop owner; BlueStacks quit; marker at 09:53:44Z). GO file written, and instance 0 booted at 09:54:16Z. Boot takes 22 s and attest 14 s.
  - Without background QoS the Mortar proof ran 699 frames in 133 s (5.26 fps).
  - Fixes during start: a None-hp compare, a zsh NULL_GLOB in the puller, and a run-id collision (ids now end in -MMDDhhmmss; the 2 partial runs were renamed `*-first0955`). Also adaptive stride and PNG every 50th frame (LEAD storage budget).
  - Instance 1 started 10:00:55Z, instance 2 at 10:04:34Z.
- 10:05Z Sol visual QA (`scratch/nulls/night/qa/first-mortar/SOL-QA.md`): viewport [0,180,1080,2100] verified, no team flips, anchors within ~±8 px. The tower visual-centre dy was fixed. Building bases are no longer clamped, effect frames are clipped to the class prior and flagged, and death rows are never boxed. Relabelled.
- **05 processes** (kill by PID only):
  - puller `pull.sh`: PID in `night/logs/pull.pid`;
  - labellers `label.py --inst 0..3`: one per instance, i0 also writes coverage;
  - storage guard `storage_guard.sh`: PID in `logs/storage_guard.pid`; writes the Mac STOP at 250 GB.
- **Mac runners:** PIDs in `~/clasher-live/nulls/night/state/runner-N.pid`. To reload code: scp to code/, `touch ~/clasher-live/nulls/night/RELOAD-N`, wait for the "RELOAD" log line, then `nightcap.py start --inst N` (it adopts the running emulator).
- **To end:** `touch ~/clasher-live/nulls/night/STOP`. The runners bring their emulators down, and the last one kills the 5049 adb server. Then tell the LEAD and the loop owner.
- 10:06Z: 3 instances, ~17k frames/h landed. Memory 44% free, swap 0, 14 GiB disk. r3 told where batches land and what to admit.

- 10:07–10:24Z: a 4th instance pushed pressure to warn, so the guard stopped it (3 instances = the Mac limit). Memory-yield hysteresis added (15 s persist, one yield per 90 s). A `#solo` swarm variant was added (one team, centre deploy, no counters; queue.json `solo`). Card levels per pass are [11, 13, 15, 9, 14] and arenas rotate over 13 ladder locations.
- 10:30–10:45Z **IDENTITY BUG fixed.** The body catalog's dgid order ≠ the probe's for later characters (SpearGoblin read as giant-skeleton, SkeletonDragon as electro-giant, ...).
  - `dgid_learn.py` (05, loop, PID via ps) learns dgid → body from objects first seen ≤ 3 ticks after our single-body deploys, written to `scratch/nulls/client-tables/dgid_counts.json`.
  - The labeller sets body_source ∈ {empirical, catalog (towers/projectiles), catalog_unverified, unresolved}; `complete` needs empirical identities. Coverage before the fix is in `coverage-pre-identity-fix.json`.
- 10:40Z **box-source bake-off** (Sol, 121 objects on r3's 40 QA frames, `night/qa/cmp-v1/SOL-GRADE.md`): ok = diff v1 36%, v2 43%, x1h 46%, SAM2 31%. x1h ∧ diff within 5 px gives 89–91% ok at ~22% coverage. The LEAD approved the x1h-agreed plan.
  - SAM2 env is on 01 at `/mpac/sdicks02/jobs/clasher/nulls-sam/` (worker; not used further).
- **Labeller v3 (night-label-3):** `box` = x1h_agreed only. Each object also carries box_det/det_conf, box_diff, box_fit (anchor fit for isolated bodies), box_split, box_method and box_agree. Each run dir gets a clean_plate.png. A chunk is relabelled when `night/dets/<rel>/READY` lands. The x1h runner on 01 is being built by a worker (`det_night.py`).
- 10:50Z: 3 instances, ~33k frames/h landed, 17 GB raw at 10:43Z. Full relabel to v3 running.

- 10:54Z **x1h at scale** on the 01 GPU (worker):
  - `det_night.py`, matches r3 exactly; 14.7 fps, 3.4 GB, nice.
  - PID in `/mpac/sdicks02/scratch/nulls-det/det.pid` on 01; log `det.log` there.
  - Stop: `ssh 127x01 'kill -TERM -- -$(cat /mpac/sdicks02/scratch/nulls-det/det.pid)'`.
  - Output `night/dets/<rel>/dets.json` + READY.
- 11:20Z **pass 0 complete** (117/121 cards duel + 19 solo swarms). Pass 1 is at L13. 11:45Z deploy:
  - `targeted` queue in queue.json, run after pass 1: Elixir Collector/Mirror cycled into hand, Mirror of base cards, mirror matchups (same lane, 1-tick stride while overlapping), problem cards @15;
  - gRPC reconnect retry.
- 11:50Z **Sol QA of methods** (`night/qa/methods-v1/SOL-GRADE.md`): ok = x1h_agreed 5/14 beyond bat/knight, anchor_fit 6/22, solo split 8/41; class/team 77/77.
  - LEAD decision: r3 runs a Sol box-correction pass (`night/correction/v1`, built by `make_correction_list.py`) and a low-weight loose-box A/B; badge_team classifier from our anchors.
- **Hand export fixed:** `nextCard` is now read from obs (hand_patch.py rewrote 24k labelled frames).
- **Labellers:** 6 sharded (`--inst N --shard k/2`, logs `label-N-k.out`).
- **Coverage:** `coverage_dedup.py` → `scratch/nulls/coverage-night-dedup.{json,md}` (distinct run × object × 8-tick bucket).
- **Evolutions:** 109 `*_EV1` exist; the deck-entry flag was not found in 20 min. Hero forms (spells_hero_form.csv) likely render as the base card.
- 11:57Z: 3 instances, ~35k frames/h, 39 GB raw.

## Offline follow-up: reproducible test candidate ready, no host restart

- Addedfull_bundle.py explicitgrpc-burstprofile+freshnamespace/plan arguments; includestransport/scenarios/preparation/generatedSDKprotobuf and emitsseparate05tools. Built/manifestverified scratch/nulls/build/transport-proof-offline01 SHA260a7c02eec03c24a0c999c3b4135edbfa9f9a44a16e49b77db124e99d9e2318, NOTdeployed/NOindependentSolGO. Underlyingruntime24logicunchangedapartfromnamespace+eight-scenario testplan, allrawheld. Source live/nulls/transport-proof-plan.json; operatorplan reports/live/nulls/TRANSPORT-PROOF-PLAN.md.
- Finaltargetedofflinechecks33PASS (23pipeline,4burst/binding,4driver,2geometry). Replayfixtureexclusiontestsprotectnativebindingandadmission; oldnativev3sourceunchanged. RealemulatorFPS/Mac-to05rate stillUNMEASURED; physicalorientation/viewport/quarterclock-phase/attackpixelboxesnotproven. NexttestneedsexplicitLEADauthorization/freshpauseproof; no automaticboot/timer/importer/watchremains.

## 04:15Z: BLOCK2 ENDED, emulator/owned adb OFF; offline fixtures only

- LEADended04:09, nofurtherboot. i1c review24GO45e11d08... deployed/manualboot04:08:10 queue11668/watch11678/emulator11693, stoppedthroughidentitycheckedqueue-firstcontrolsasordered. Allfourrolesgone, adb5049devicesempty, ownedserver50108exactcreation/cmdverifiedSIGTERM;ports5049/5596/5597/26795/8596free. Receiptqa/BLOCK2-EMULATOR-OFF-0409.json. All05importersstopped;review19/25obsoletepeerworkcancelled. Streamsourceinstancesemptyatshutdown; leadownsrestoringdisplay/ladder.
- NEWDATA0nativeframes/0QA/0admitted/0completedruns/0shipped. ALL121card×2team×phasecounts0 in scratch/nulls/coverage-block2.{json,md}. Threebootattempts/max1parallel. Watchhistorymindisk12.413GiB,minfreeinactive7.936GiB,normalpressurealways,swapneverallocated. Historical171raw/3admittedv3unchanged; r3+yolosynthnotifiedzerodata.
- Report reports/live/nulls/BLOCK2-20261017.md; machineqa/BLOCK2-FINAL-REPORT.json. Owngeometryrequestmistake(logical1920vsphysical2280) fixedcode20GO, externalpgrepprobeidentifiedbyLEAD, actualPython-scriptargvguard24GO(originalLEADargv[1:]contractclarified;22argv1-onlyfindingattributionsuperseded). No actual2280gRPCframeproductionverifiedbeforeend.
- Offline05ONLY replay192nonqualifyingfixtures/8bursts/31.67s/6.063verifiedfpssinglecore, qa/offline-replay-20261017-0412/REPLAY-BENCHMARK.json; NOTemulatorFPS/NOTMac-to05proof. Newframe_geometry proposes[0,180,1080,2100]viewportunverified/orientationunverified, nevercropsraw. Binding/admissionnowexplicitlyrejectsynthetic_fixture/fixture_only. Tests23pipeline+4burst/binding+4driver+2geometryPASS; newofflinehelpersnotMacdeployed/reviewedforruntime. Needrealboundedtestauthorization+measuredsustained05deliverybeforeanotherblock; no timers/auto-restarts. Pixelattackboxes/phase/cues remainunproven.

## 04:04Z: external probe tripped old driver predicate; LEADordered exactargv guard

- i1b review20GO deployed/boot03:58:48 queue78438/watch78459/emulator78478; STOP03:59:44 beforecapture. watch.err “live driver process exists”; allownrolesoff,0frames, adbon5049wascleanpreviousoff. Failedstateqa/BLOCK2-I1B-DRIVER-GUARD-STOP. Importer1789419identityverifiedTERM. Originalstatenooverwrite.
- LEAD CONFIRMEDnoactualdriver; displayownerpgrep shell03:59:45 causedstrictsubstringfalsepositive, nowfixed/otherworkersavoidliteral. LEADexplicitordersactualargvvenvpython+driverpathargument only, excludeshells/grep/ps/ownPIDs; marker/sharedlock/endpointstillrequired. Read-onlyMacselfKERN_PROCARGS2probevalidatedactualargv0venvpython/-B/argc4. Newguardusesnativeargvboundaries, ESRCHandvanishedonlyskip; unknownfails; noargument-substringmatchinsidecode.
- Freshi1c candidate review22pending `/scratch/nulls/build/full-b2-i1c-review22`, SHAa7098e74875e1f989a013cce343a043d32de072b36abe0412a30c74b34c8e8a9.3newdriverguardtests+23updatedpipelinePASS; oldsubstringfixtureupdatedtoactualvenvdriverargv. NoVMrunningwhileawaitingGO.
- Parallelreview21GOclosedR18F1/F2 (100mockfixtures) butpeerrooti1bnowfailedsoNEVERlaunchthatartifact. Newi2review23candidate preparedONLYcurrentguard+peerrooti1c namespaces, nolaunch; firstgRPCburst+60shealthysettling+3GiB/normal/zeroswap/disk10 remainsrequired. No usableframes/admissionsyet. LEADrevised04:20checkpointtoRATEsincefirstsuccessfulverified05frame, nottotalafterexternaldelay. Hard05:45unchanged.

## 03:56Z: i1 clean STOP at first gRPC geometry; fresh i1b review20 pending

- i1 productionattestation+configure worked withoutANR; pausedsnap failed strictgRPC1080x1920 dimensions/buffer. No newframes; allqueue/capture/watch/emulator identitiesgone03:54:18. Failedstate mirrored qa/BLOCK2-I1-GRPC-GEOMETRY-FAIL, originaluntouched;05importer1055093identityverifiedTERM. Noautomaticretry/STOPclear.
- SDKphysicalAVD1080x2280 whileAndroidwmoverride1080x1920; existing src/clasher/vision/l1_stream.py requests1080x2280. Newcandidate requests/strictdecodesfull1080x2280RGB888 withoutresize/crop; gRPCpausedsnap expected2280x1080, legacyADBstill1920x1080; burstframe_shapeactual. AllrawheldnewcameraQA, dimensionerrornowpreservesactualformat/bytecountinlog. Otherlogic/guardthresholdsunchanged.
- Freshunusedfull-b2-i1b candidate `/scratch/nulls/build/full-b2-i1b-review20`, SHA5a3589c04e2eee0f652b9af7b5205382d08395e62f891050cf1f91e7d79f09dd; review20pending, deployonlyGO. Leasecheckpointstill04:20, noidleVM. LEAD+r3 notifiedessentialblocker/newroot. Parallelreview18NO-GO insufficientshipping-ready/timestampchecks;19closurependingbutnowobsoletepeerrooti1failed, NEVERlaunchthatcandidate. Mustupdatepeerroot+geometryandfreshreviewafteri1bworks.

## 03:51Z: first windowed block2 instance BOOTED under review17 GO

- Review17 GO R16-F1 closed, exactbundle f554d32107b750a1057f3491757391d35eb01ced98626e5dd21655ae361b5cc1, installedverified full-b2-i1/code. Owngrpc1.71 installed viareviewed--targetscript; sharedvenvunchanged. Single05shipper receipt qa/BLOCK2-I1-SHIP-LAUNCH.json; heartbeatprovedbeforeboot.
- Runtime50086/watch50112/emulator50135 boot03:51:05, authoritativepause03:42:03+processabsence/sharedlock+endpointdriverfalse passed. START disk12.619GiB/freeinactive12.630GiB/swap0/0/0/normalpressure;03:51:38 disk12.624/freeinactive11.551, noSTOP. GUIgRPC8596, own5049/emulator5596,1536MiB2cores/nice10. Nativebootmaytake2min; capturehasnotstarted. Streamsourcepublishedactualwindow5596+nulls-1/Tombstonered. Parentessentialhandoffsent.
- Leaseends04:20 checkpointinitially; no automaticcontinuation. Allburstrowshelduntilnativebinding+spritepixelQA. Firstframeson05notificationpending actualchecksumpublication, notclaimed. Second-instanceofflinecandidate review18pending, noadditionalVM; needsfirsthealthy+shipping+60ssettled/3GiBfreeinactive/normalpressure/noallocatedswap/disk10 beforemanualadd.

## 03:49Z: review16 parser blocker fixed; fresh review17 pending

- R16 NO-GO soleP2 swap field/unit substring parsing and impossible total0/free500. Never deployed. Exact full-line M-unit parser now rejects missing/duplicate/malformed fields, nonfinite/negative values and inconsistent allocations; hundredth-MiB rounding tolerance .02, totalzero requires exactallzero. 27guardtestsPASS includingallreviewnegativefixtures. Existing23pipeline plus3burst/bindingtestsPASS.
- Fresh immutable bundle `/mpac/sdicks02/scratch/nulls/build/full-b2-i1-review17`, SHA f554d32107b750a1057f3491757391d35eb01ced98626e5dd21655ae361b5cc1, ONLYguarddelta fromreview16. FreshSolreview17pending. Alltransport/stop/label logic unchanged; rawheldnotadmitted. Need GO17 then deploy unusedfull-b2-i1, owngrpcdependencies, single05shipper and runtime lease03:39–04:20. No emulatorstarted.
- Marker03:42:03 afters64 independentlyverified+sharedlockfree+endpointdriverfalse. BlueStacksclosedsolelyloopowner. Own5049ADBserverabsentbaseline; live5047server25270 read-onlyobserved andneveraddressed. Endcleanupmuststopnewowned5049serverbyidentity/PIDafterowndeviceclean, neverglobaladbkill.

## Block 2 preparation 03:43Z Oct17 (same generator owner)

- LEAD explicit LADDER STOPPED03:39; independent03:41 marker missing, babysitter/LEAD notified. No emulator boot until marker/sharedlock/process/resource gate and fresh Sol GO. Mac12.34GiB free, swap0/0/0, normal pressure, free+inactive9.54GiB; BlueStacks quit solely by loop owner.
- Fresh bundle `/mpac/sdicks02/scratch/nulls/build/full-b2-i1-review16`, SHA a74afbcfe447e177497eb6fc13ca46339209d7767370b8901ad854948c739fc8, review16 pending. 23 existing tests pass. New authenticated gRPC retained-frame burst and independent timestamped native samples remain HELD; no sync/box fix claim. 0.25 speed, native source15.535.13/content15.535.86; all121 available cards both owners priority-first, no heroes.
- New guard approved exactunallocatedswap rule +normalpressure,10GiB diskfloor, memory1.5GiB, existing shipping128MiB/15s/45s and lease/driver/live protections. Initial checkpoint lease ends04:20; any continuation needs measured projection/LEAD decision; hardend05:45. No idle VM; only1instance configured, parallel later requires resource proof and reviewed ports.
- Raw coverage table scratch/nulls/coverage-block2.{json,md}, currently0; raw/phase-unverified never counted admitted. Need actual gRPC FPS/sequence/orientation and native-state binding + sprite-pixel labels before admission. Review16 requested read-only/no host action; owns no capture.

## 23:24Z: final consumer handoff COMPLETE for this released block

- R3 CONFIRMED v3 admission:3frames,8troops (4ours/4opp) plus18KataCR towerboxes,26traininglabelrows; all3frameSHAs/pins/complete flags pass,8bodyboxes match independentSol corrections exactly0px, geometryafterconsumer offset<=1.3croppx. Live V13a/b/c lists/nulls-full-v1.txt on01/04/08 now3lines, readlive share0.12. Receipt qa/FULL-V7-CONSUMER-ADMITTED-2324.json. Roots v1/v2 unused; newrawframes remainhelduntilindividualQA.
- QA troop counts ours/opponent: Giant2/0, Musketeer2/1, Knight0/1, MegaMinion0/1, Cannon0/1; MiniPekka0/0.171rawfullframes/173checksumchunks/120937518bytes shipped05;162pilot+9partialpriority,2completedruns,168framesstillheld. NO5usable-run/1000labelled-frame/fullpool milestone. Finalmachine receipt qa/FULL-BLOCK-FINAL-2324.json, plainEnglish report reports/live/nulls/FULLFRAME-BLOCK-20261016.md.
- All ownMacroles and05importers stopped, blockreleased23:17, nohostrestart/timer. Sameowner may continue offlineaudits in v3 format; any nextMac work needs NEWLEADblock. Startupreview15GO is codeonly/notdeployed; syncrootcauseunknown until actualrejectedpair retained. Do notclaimdiagnostics are asyncfix or reviveoldlease. Parentfinalreport andbothconsumerhandoffs complete.

## 23:22Z: v3 corrected labels handed to both consumers; offline startup review GO

- Fresh labelcontractreview14GO 18tests+66independentchecks, exact full_labels.py3ac50e503899b667f5d068bb882d154573626d89981101871a990e12279cfb12, receipt qa/label-contract-review14.md. v3 complete records PUBLISHED at scratch/nulls/admitted-full-v7-v3 (3frames/8troops), manifest qa/FULL-V7-V3-HANDOFF-2322.json. Exactr3Sol corrections applied to all3attacking boxes and Cannon y1764; flash evidence distinguishes Knight sword from Giant hit tint. towers_boxed:false; camera correspondence team/native_team nativeowner top0/bottom1, separate belong validated. Oldv1/v2 preserved nonqualifying/superseded. R3 finalconsumerchecks/listadmission pending; classownerhanded samefreshroot.
- Raw full-v7 archive120937518bytes (115.34MiB),173hash-verified chunks/171fullframes:2completedpilot81each+9partialpriority; full-v8 diagnostic attempt0frames. Per-card/team raw presence counts qa/FULL-BLOCK-RAW-COVERAGE-2319.json includeghosts and are NOT QA/admission. No >=5 completed usable runs or1000 labelled-frame milestone claimed.
- Offline startupreview15GO 23tests+14independenttests, exactcapture aa1215bfe7ca5299ae3fdd2b2655ecc0830bd1e64e7a47e666f34f7b536cb1da and newtestb7c21bf597518abde10bc94769297fa32c013f43727ffb7ecab22cfeb09b9e9a, receipt qa/startup-null-review15.md. Initial preconfigure HOLD now accepts exactly transientmCurrentFocus=null within same300s deadline/guard, noautoUI; missing/duplicate/otherapp/latefocusreject, strictsnapnull/mismatch stillfatal. Rejected pair/JPEG diagnostic retained and regressiontested. Notdeployed/hosttested, NOsyncrootcausefix claimed.
- AllMacownroles+both05importersgone; no more host launch or timer in releasedblock. Nextblock requires LEAD reservation/freshresources, immutablefreshnamespace, existing1536MiB2cores budget, strictdiagnosticpilot tocollect actualfailedpair and prove fix beforebroad priority. Do not revive oldlease/STOProots or claimnormalcapturefromsynthetic tests. Samegenerator retains offlineownership until consumer receipt/finalreport.

## 23:17Z: block RELEASED early, all own roles stopped; offline label handoff continues

- LIVE LEAD decision point23:16: fixed bounded retry must startby23:30 else release. Fresh full-v8 could not promise a sync fix: startup SystemUI ANR -> Messaging ANR -> transient mCurrentFocus=null made unchanged strict initial gate STOP beforeconfigure,0newframes. All own queue/capture/watch/reference identities confirmed gone23:16:37. No more host launch/UI action in this block. Release sent LEAD+babysitter23:17; receipt qa/FULL-BLOCK-RELEASE-2317.json.
- Single05v8importer1335796 identity-verified SIGTERM afteremptyspool/drain; oldv7importer alreadygone. Data shipped05:162pilot+9priority=171rawfullframes;2completedpilot runs and1partialpriority g1-s1. No complete priority run. All native raw sources held pending individual label QA.
- V8 system-housekeeping manual scope: single CLOSE_SYSTEM_DIALOGS15stimeout(effectunknown), then freshverifiedSystemUI BACK rc0; focus laterbecameMessaging, thennull. PlannedMessagesbroadcastwasNOTexecuted: freshguardfoundSTOPfirst. State mirror qa/FULL-V8-STARTUP-STOP-2317 preservesreceipts/screenshot, no lifecycle/package/reset/globaladb/live action. No failedsyncpairreproduced in v8 (neverconfigured). Strictsyncrootcause remainsunproven; diagnosticpreservationtestedoffline butnot a claimedfix.
- Offline remaining: labelcontractreview14GO then fresh v3 records using r3 actualSol attackweapon corrections + explicit tower metadata; consumer admission/counts/finalreport. Need initialnull-focus boundedstartup handling and captured sync-failurepair before next production block, no speculative sync relaxation. No active timer/helper/operator control remains except bounded read-only label reviewer.

## 23:12Z: strict-sync priority failure preserved; fresh manual diagnostic run booting

- Approved priority01 started23:08:09 producer88465, captured/shipped9frames g1-s1 then strict paired objects equality failed at screenshot; allown queue/watch/capture/referenceVM exited by23:10. No admission/retry/sync relaxation. Failure pair itself was not retained by old code; entire state mirror qa/FULL-V7-SYNC-STOP-2310 and blocker qa/FULL-V7-SYNC-BLOCKER-2310.json.162pilot+9priority retained immutable.
- Normal-engineering diagnostics only: rejected snapshot now writes exact before/after gz and rejected JPG under own STATE/SYNC-FAILURE before rethrowing unchanged ValueError; no READY/admission/retry/threshold or comparison change. Synthetic rejected-pair regression PASS, existing18testsPASS. Fresh full-v8 bundle1cafd6968717ba9b3d2596831556e074ab1a54fec2b7d2361b7bb5a8be55ff79; unchanged reviewed code except namespace and this diagnostics. Full-v7 state/spool/STOP preserved.
- Own old05importer3285104 identity-verified/stopped; single NEW1335796 full-v8 importer, receipt qa/FULL-V8-SHIP-LAUNCH-2312.json. Fresh manual runtime2292/watch2301/reference2314 boot23:12:07 with disk10.9605GiB/swap896.25/freeinactive7.95/pauseproof/heartbeat valid. Receipt qa/FULL-V8-BOOT-LAUNCH-2313.json. Primary plan is existing approved priority plan renamed priority02; no repeated pilot, no duplicate operator, no automatic retry. Hardend23:50. Need watch startupHOLD and fresh identity/modal evidence before authorized manual broadcast only.
- R3 independent actual QA: camera +all162raw position geometry pass, native1 bottom ours and both teams correct.5/5 walking/flying/idle boxes good;3attacking boxes need renderedweapon extents. Corrected candidate v3 audit data at qa/pilot07-audit-v3; not admitted yet. Fresh label-contract review14 pending (explicit native-team tower correspondence + separate belong check, towers_boxed:false); no host label code deploy. New sources always incomplete until actual pixel audit.

## 23:08Z: LIVE LEAD authorizes raw priority immediately; hard stop shortened23:50

- Direct LIVE LEAD instruction supersedes consumer-ready capture gate: run approved priority plan NOW, QA parallel/after, failed frames never admitted. Existing reviewed runtime/plan/watch/label code unchanged. One-time GO-PRIORITY explicitly scoped raw_capture_authorized_only, consumer_admission:false, consumer_ready:false; no fabricated nine-gate quality claim. Authorization mirrored qa/FULL-V7-RAW-PRIORITY-AUTHORIZATION-2309.json.
- Existing lease shortened via own control file to23:50Z, original lease preserved LEASE-BEFORE-2350.json. Same reviewed queue launches/supervises approved priority01 plan SHA82f81874..., no duplicate producer/importer. New sources remain complete:false pending audited admission. Stop immediately on marker loss or any unchanged guard failure; no restart. Own priority remains opponent-frequency grouping/both teams; shipping≤15s heartbeat/READY45s/128MiB unchanged.

## 23:07Z: full-v7 pilot captured and shipped; actual consumer QA pending

- Pilot07 completed two scenes (81+81=162 full frames) between22:57:08 and23:06:27, measured1037.7raw frames/hour including scene setup. Every source passes full_labels.source image/obs SHA, schema and synchronized native checks.05 checksum ACK median2.19s/p953.33s/max3.73s, Mac pruning works. Metrics: scratch/nulls/qa/FULL-V7-PILOT-RESULT-2307.json.
- Current root scratch/nulls/full-v7/ff-20261016-pilot07 remains immutable complete:false. Three producer-audited source frames (8 troop instances) in scratch/nulls/admitted-full-v7-v2; actual per-card/team counts in metrics. R3 independent tower/body/owner QA pending; ZERO consumer-admitted, NO priority release. Initial admitted-full-v7 root withdrawn/preserved after8px Giant head-edge clipping; v2 fresh audit fixes it. withdrawal receipt qa/pilot07-audit/withdrawn-v1.json.
- Camera current native t200 pixel audit: six composite rider-inclusive centres; separate six bottom landmarks residual0.061crop px,3tracked-Musketeer ground checks0.121tile. Scope/caveat explicit in pilot07-audit camera JSON, not a universal pose-extent model. Later clocks can be attack/reload overlays over deployed opaque units: never classify ghosts from clock/native presence alone.
- Queue26295/watch26333/reference26345 remain exclusively owned; capture finished, runtime waits PILOT-DONE nine-gate QA. Single05 shipper3285104 follows through00:05. Latest guard~10.74GiBdisk/896.25MiBswapfree, marker s57/no driver/shared lock proven. No watchdog/label/control code changed after review13. Stay owner through QA, explicit release if all nine actual gates pass, bounded priority capture and00:00 clean stop/handoff.
- Housekeeping causal correction: READY22:56:31.3003 predates BACK22:56:37. CLOSE_SYSTEM_DIALOGS22:56:29 apparently resolved asynchronously; BACK was unnecessary. Corrected receipt qa/FULL-V7-HOUSEKEEPING-2256.json; no game/package/reset action.

## 22:53Z: review13 GO; preconfigure HOLD full-v7 boot active

- Freshreview13GO exactd5c6e7a09a9139e6bb8ee8ac1e065782ae149fb45af99ad3e9757ad541e0d9e8,18tests+33controls; receiptqa/preconfig-focus-review13.md. Exclusivefull-v7/code deployedverified; previousSTOPtreespreserved. No codeeditsafterGO.
- Single05importer3285104 receiptqa/FULL-V7-SHIP-LAUNCH-2252.json/logqa/full-v7-ship-2252.jsonl, output/scratch/nulls/full-v7/ff-20261016-pilot07. Manualruntime26295/VM26345 started22:52:15afterallfreshgates,disk11.110GiB/swap896.25/freeinactive6.887. Bootreceiptqa/FULL-V7-BOOT-LAUNCH-2252.json; healthy22:52:59/noSTOP.
- STAYowneractive throughpreconfigurefocusHOLD. All4rolesguardcheckbeforemanualhousekeeping, actualcurrentANRscreen/focusconfirmed, only5049/emulator5596; userauthorizedCLOSE_SYSTEM_DIALOGS ORBACKthenrecheck, noautoUI/gameinput/packageschanges. AvoidHOLDmax300sexpiry. Nativeattestmaytake~1minafterappstart; focusgateBEFOREconfigureunblocksANRcausalissue. Strictsnapafterconfigurestillrejectsanymodal.
-22:56:24preconfigureHOLDMessagesANR reachedwithall4rolesowned/guardhealthy10.964GiB/swap896.25. OwnerexplicitmanualCLOSE_SYSTEM_DIALOGS22:56:29(result0,modalremained); currentmodalrechecked, manualBACK22:56:37(result0,appfocusrestored). Noautoinput/game/package/resetaction. Receiptqa/FULL-V7-HOUSEKEEPING-2256.json. Continuewatchconfigure+strictfirstframe.
- Ifsourcecannotstartby23:15cleanSTOPallownroles/importer+notifyLEAD/babysitter, hardend00:00. Actualframes0atboot; review09labels70aa... approvedcodeonly. NeedactualQAandninegatematchingreleasebeforepriority; no falsecount.

## 22:50Z: root startup-order issue; preconfigure HOLD in review13

- Full-v6 attestedthenconfigure90stimeoutBEFOREafterconfigureHOLD. Fresh22:48:14all4rolesowned/guardhealthy11.236GiB/swap896.25; focusDigitalWellbeingANR. Authorizedbroadcastattempt22:48:33missedVMalreadycleanstopped/device-not-found: NOinputdelivered,0frames. RootHOLDplacementtooislate; not anadmissionfailure. Statepreserved/mirroredqa/FULL-V6-PRECONFIG-ANR-2249,receiptqa/FULL-V6-PRECONFIG-BLOCKER-2249.json. Importer2270221identityverified+stopped; alloldSTOPtreesretained.
- MoveexistinginitialgateBEFOREconfigure(firstSession.n==0only) soownerhousekeepingunblocksrenderinitialization. ExpandHOLDonlytoAndroid/Google-systemANRpackagefamily(com.android.*|com.google.android.*); rejectNullsgame/thirdparty/malformedfocus. NOautoUI. Sameexactonefocus/300smonotonic/boundedread/sleep/postreaddeadline/guardchecks; strictsnapstillSTOPafterconfigure+everyframe.18testsPASS inclgate-before-configureandfamilyrejects. No hardwatch/label/thresholdchanges.
- FreshSolreview13PENDING `node:delegated-task:command%3Amcp%3A90cb724b-6215-4a0f-ab24-8de5e0afeefa%3Adelegate-task%3Anulls-preconfig-focus-review13-20261016`. Exactcandidate `/mpac/sdicks02/scratch/nulls/build/full-v7-preconfig13`,SHA d5c6e7a09a9139e6bb8ee8ac1e065782ae149fb45af99ad3e9757ad541e0d9e8. Newfull-v7namespace/pilot07 SESSIONONLY; no oldlatchclearing. DeployerdefaultROOT/code/newshiphelperpathsconsistent.
- AFTERGO deployexclusivefreshfull-v7/code; singleNEWimporter05(rootfull-v7) thenmanualruntimewithinlease, watchINITIAL-FOCUS-HOLD-ff-20261016-pilot07 beforeconfigure. Freshguardidentity+screen thenuser-authorizedmanualbroadcastCLOSE_SYSTEM_DIALOGS ORBACK only5049/emulator5596; no packages/gameinput. Ifnotstartedby23:15STOP;00:00hardend. Allactualfullframecounts0, no priorityrelease/admission. Sameownercontinues.

## 22:43Z: housekeeping release received; full-v6 bounded pilot boot active

- Babysitterarchived/checksummed/prunedoldMacrunlogs,shots,benchsnapshots05; toldfree10.8189GiB. Independent22:43:05free11.409GiB, swap888.25/freeinactive6.56, marker s57 present, no driver/referenceproducer. Exactapprovedbundleverifiedagain. No otherownerartifactactionbygenerator.
- SingleNEWimporter2270221,receiptqa/FULL-V6-SHIP-LAUNCH-2243.json,logqa/full-v6-ship-2243.jsonl,followuntil00:05; outputroot/scratch/nulls/full-v6. Manualruntime95544/VM95619 boot22:43:23, freshSTARTdisk11.4078/swap888.25/freeinactive6.782, pause+lockpassed. Receiptqa/FULL-V6-BOOT-LAUNCH-2243.json. Guest1536MiB/2cores/nice>=10, allreviewedguardsunchanged.
- Review12GOinitialHOLDcodeexactde22e2eb8d0efc07e9fab0f11847801ae66c8332cd6a942538ec01ca929c3ca1, codeatfull-v6/code. WatchforINITIAL-FOCUS-HOLD-ff-20261016-pilot06.json afterfirstconfigure, max300s; ownerfreshidentity/guard+actualmodalinspection, authorizedmanualCLOSE_SYSTEM_DIALOGS ORBACK onlyreference5049/5596, thenrecheckfocus. NOautoUI orpackageschanges. Strictsnap/latermodalSTOPunchanged.
-23:15unabletostartcutoff/hard00:00endremain. Source0atboot, explicitnineactualpilotgatesbeforepriority. r3/classownerswaitingfirstcompleteQAchunk; labelsreview09GO70aa... butzeroactualadmissionyet. RemainSAMEownerthroughstartupHOLD+pilot+QA+handoff.

## 22:36Z: review12 GO installed; disk gate/scene margin blocked again

- Review12GOexactbundlede22e2eb8d0efc07e9fab0f11847801ae66c8332cd6a942538ec01ca929c3ca1,18tests+32controls, R11F1/F2closed; receiptqa/initial-focus-hold-review12.md. Freshfull-v6/code exclusivelydeployed+verified. No newVM/importer launched.
- WithALLgeneratorrolesOFF, Macfree22:35:21=8.3577GiB (<9START/<8.5STOP),22:35:46=9.3346GiB. Recordedownqemu29000temp3filesalreadyremovednaturally; ownnulls/dataonly1492KiB, nobulkownsourcelefttoprune. Parentaskedrestore~10.5GiB toallow~0.9GiBscene growthandobserved~1GiBexternalvolumechurn. No otherownerfilesdeletedbygenerator.
- LIVELEADsaysbabysitterarchiving/pruning~1.5GB oldMaclogs/screenshots/bench snapshotsto05 andwillwakeTHISownerat>=10.5GiB. Swap~0.89GBfree;23:15cutoffstands. Do not duplicatepruneortouchotherownerfiles.
- Receiptqa/FULL-V6-DISK-READINESS-2236.json; awaitingresourcehandoff. AllpriorSTOPstate/spool/logsremainpreserved. Do NOT rebootontemporary9.3marginandrepeatknown8.44scene failure. Ifcan’tstartby23:15cleanstop/notifybabysitter+lead,00:00endregardless. Newstartupmanualhousekeepingandreview09labeladapterready; actualsourcecounts0.

## 22:33Z: HOLD review11 edge fixes done; review12 pending

- R11NO-GO2P2: duplicateappfocusacceptedandfocusreadcouldreturnafter300sdeadline. R11NEVERDEPLOYED, preserved. CorrectedexactONEfocusbeforeanybranch; deadlinecheckedAFTERreadbeforepublication, focusreadtimeout/sleepboundedremaining; Session.snapalsorejectsmultiplefocus.18testsPASS inclregressionsandoldhardguardtests.
- FreshSolreview12PENDINGtask `node:delegated-task:command%3Amcp%3A90cb724b-6215-4a0f-ab24-8de5e0afeefa%3Adelegate-task%3Anulls-initial-focus-hold-review12-20261016`. Exactbundle `/mpac/sdicks02/scratch/nulls/build/full-v6-focus12`,manifestSHAde22e2eb8d0efc07e9fab0f11847801ae66c8332cd6a942538ec01ca929c3ca1. SAMEUNUSEDfull-v6/pilot06namespace; onlycapture.pychangesfromR11, allguards/maps/plansotherwiseidentical.
- AFTERGO usefull-v6/code/defaultdeployer andsinglefreshshipper; nooldlatchclearing. StartupHOLDmanualhousekeepingexplicitlyLEADauthorizedbroadcastCLOSE_SYSTEM_DIALOGS ORBACKonly5049/emulator5596; inspectcurrentmodal/identity/guardfirstthenrecheck. No packageschanges/autoinput. Ifsourcecapturestillcannotstartby23:15cleanSTOP; hard00:00end. No activeVM/importer now; allpriorSTOPtreespreserved, actualframes0.

## 22:31Z: pre-first-frame HOLD in fresh review11; user housekeeping release

- Full-v5 boot/nativeconfigure succeeded, thenMessagesANRblockedfirstsnap; supervisorstoppedallownroles,0frames. Statemirrorqa/FULL-V5-MESSAGING-ANR-2228; blockerqa/FULL-V5-STARTUP-ANR-BLOCKER-2228.json. Single05importer101950identityverified+stopped. Allfull-v1..v5STOP/state/spool/logsretained.
- LIVELEADexplicitlyauthorizesOURreferenceonly startuphousekeeping: `am broadcast -a android.intent.action.CLOSE_SYSTEM_DIALOGS` ORkeyeventBACK, recheck; NOT gameinput. No install/uninstall/disablepackages. No changedwatchthreshold. Ifcapturecannotstartby~23:15Z STOPcleanly; hardleaseends00:00regardless.
- Newfull_capture.py initialfocusgate: ONLYbeforeSession.n==0 firstsnap/deploy, max300smonotonic; statuscallsretainALLguard/ownership/healthchecks. ONLYobservedSystemUI/MessagingANRmayHOLD forMANUALownerhousekeeping; unexpected/missing/multiplefocusfails. Atomicper-sessionHOLD/READYreceipt. NOautomatedUI. Session.snapremainsstrictfocusSTOP, laterframesunchanged; prioritynewsessionreceiptkeyedbynewsessionname.18testsPASS inclhold->ready/expiry/unexpected/noUI/snapstillstrict.
- FreshSolreview11PENDING `node:delegated-task:command%3Amcp%3A90cb724b-6215-4a0f-ab24-8de5e0afeefa%3Adelegate-task%3Anulls-initial-focus-hold-review11-20261016`. Exactcandidate `/mpac/sdicks02/scratch/nulls/build/full-v6-focus11`,manifestSHA8d4b8c440d2837bbec44df12b208569e0a596fd99121f435fe53305de40ad7de. Identityreceiptqa/INITIAL-FOCUS-HOLD-REVIEW11-IDENTITY.json. Briefplaceholderhashdeferredtoactualbundleverification; exactactualhashisHERE. No editsafterbundlefreeze.
- AFTERGO deployEXCLUSIVEfreshfull-v6/code(defaultdeployer), startsingleNEW05importer(rootfull-v6) withreceipt, recheckoldrolesabsent/currentpause+resourcegates, manualnewpilot06launch. Guest1536MiB/2cores retained. NeedwatchINITIAL-FOCUS-HOLD-ff-20261016-pilot06.json, inspectactualscreen+freshidentity/guard, authorizedhousekeepingONLY5049/5596 thenfocusrecheck. Do not let300sHOLDexpireunattended. Allsourcecounts0, labelreview09GOstill70aaf68..., no actualQA/priorityrelease.

## 22:25Z: full-v5 prior resource profile active; label-output review09 GO

- Full-v4 reachedfirstsnap butfocuswasSystemUIANR, failedclosedbeforeimage.0frames. Fullstate/STOPmirroredqa/FULL-V4-ANR-STOP-2223. Allownrolesgone22:23:47; full-v4singleimporter3625300identityverified+stopped. AllpriorSTOPtreesretained.
- Existingmac/emu.py priorworkingdefaults1536MiB/2cores restoredafter1024MiB/1coreproducedANR; normalengineeringresource-onlychange, no watchdog/label/stoplogic/thresholdrelaxation. Parentnotified withqa/FULL-V4-ANR-RESOURCE-2223.json. Freshfull-v5namespace/pilot05. Exactbundleaeb9aaaf3acde3cf2da6dca9f3f0baaba7507654264fb451ef0abebd079f5097 deployedverified.
- Runtime28921/single05importer101950 boot22:24:22; startdisk9.8726GiB/swap888.25/freeinactive7.14, allpausegatespassed. Receiptqa/FULL-V5-BOOT-LAUNCH-2224.json,shipreceiptqa/FULL-V5-SHIP-LAUNCH-2224.json,logqa/full-v5-ship-2224.jsonl. OutputrootNOW/scratch/nulls/full-v5/ff-20261016-pilot05. Boothealthy22:25:07disk9.638/swapunchanged/noSTOP. Noautomaticretry/UIaction.
- R3explicitlywantsNOtowersinoutputbodies: downstreampseudo_towersprovidesalltrainingtowerboxes; arena_calibmustbe6namedCOMPOSITEextentCENTRES(riderincluded), finalindependentKataCRcameraQAbyr3.05-onlyfull_labels.py adaptedandfreshSolreview09GO exactSHA70aaf68e5526ccaa19b829b7d9a9031e4218046e85263f626e588b5e03367c44;receiptqa/label-output-r3-review09.md.17tests+45contractchecksPASS. Internalperobjecttowersstillfullyauditedbeforefilter; calibration_evidencepreservesfullvalidatedcamera, arena_calibONLY6namedpointscompatibleconverter. No nativeframeadmittedbyreview.
- FuturepilotQA: actual6compositecentres+separatevalidated6bodybottomcorrespondences/groundchecks; native IDs→visiblebodyform/boxes/teams/pose; completeonlyallvisiblebodyaudit. r3readytoconvertfirstpassedchunkbutNOTbeforecomplete=true. Explicitninegatesbeforepriority; sourcecounts0atboot. Sameownercontinues.

## 22:19Z: LEAD freed space; fresh full-v4 pilot boot active

- LEAD pruned ownarchivedbuild/retiredmodelartifacts andreported10.03GiB, explicitlyGO nextattempt unchanged8.5GiBSTOP. Generator made nootherownerprune. Freshfull-v4namespace/pilot04 ONLYdeltafromv3, exactbundle92cb6dfe1ddf03fc0dfd51e36d4c40de7e2f71419b9b31f699e91b9564fc15e0 deployedverified; watchdog/labels/stoplogicunchanged.
- Singleimporter3625300 receiptqa/FULL-V4-SHIP-LAUNCH-2218.json/logqa/full-v4-ship-2218.jsonl; root/scratch/nulls/full-v4. Runtime8934 started22:18:35afterfreshallgateproofs,disk9.998GiB/swap888.25/freeinactive7.749. Receiptqa/FULL-V4-BOOT-LAUNCH-2218.json. Priorfull-v1/v2/v3STOPtrees/oldimporterspreserved/stopped, no duplicate.
- Boothealthy22:19:02disk9.988/swapunchanged/noSTOP. ContinueSAMEowner intoactualsource/calib/body/poseQA; explicitninegates beforepriority, pilotendshortstatus+blockendfinalrequested. No newhelpers/automaticretry.

## 22:18Z: disk STOP beforefirstframe; awaiting LEAD extraheadroom

- Full-v3 boot/setup succeeded, nativeattestationpins passed, firstsceneconfigured. Duringinitial6srenderwait guardcorrectlytripped22:17:02at8.440GiB (start9.32395,peakdrop0.884GiB); swapunchanged888.25MiB. AllownVM/capture/watchgone22:17:21; diskrebounded9.314GiB.0raw/shipped/admittedframes. No thresholdrelaxation orretry.
- Sourceblocker `qa/FULL-V3-DISK-BLOCKER-2217.json`, statemirror `qa/FULL-V3-DISK-STOP-2217/`. Entirefull-v1/v2/v3STOP/state/spoolpreserved. LEADaskedtofreeanother~0.7GiB tooperatorheadroom>=10GiB before nextmanualattempt; no otherownerfilesprunedbygenerator.
- Oldsingle05importer3014065identityverified+SIGTERM afterconfirmingzerochunks; `qa/FULL-V3-SHIP-STOP-2218.json`. No newimporter/VMrunning. Preparingfreshfull-v4namespace/pilot04 SESSIONONLY, samecodeasv3exceptnamespace. ExistingLEADnormalengineeringcoversnamespacepreparation; no watchdog/label/stoplogicchange. Do not boot untilresourcehandoff+allfreshgates. RuntimecodehardthresholdsremainSTART9/STOP8.5GiB/swap500MiB.

## 22:13Z: normal-engineering startup adapter; fresh full-v3 boot

- Full-v2 successfullybooted/setup/capturelaunched, theninitialattest JSONDecodeError beforefirstframe; supervisorstoppedallownroles. Entirefull-v2STOP/state/spoolpreserved andstatecopied05qa/FULL-V2-BOOT-STATE-2213. Exactresponsewasnotlogged; startupempty/EOFcaseinferredfrompriorforwardreadinessbehavior, notprovedhostcause.
- UnderLEADnormalengineeringinstruction, narrowinitialreadinessadapter acceptsONLYinitialread-onlyattest ConnectionRefused/Reset orEMPTYJSONresponse; same300sboundedreadinesspoll. Nonempty malformedresponse, everyguarderror and ALLpoststartupcommanderrorspropagate. No watchdog/label/stopthreshold/cleanupchange (guardonlynamespacefull-v2=>full-v3).17pipelinechecks+8adaptercasesPASS; no broad exception swallowing/capture retry. Receiptqa/FULL-V3-STARTUP-ADAPTER-2213.json.
- Freshfull-v3/code deployedverifiedexactbundlebd76f1d5346f647af9d70711784fb61384ac8b3cbce4bcece3090e6f0a8afe98. Oldfull-v2importer2632772identityverified+stopped, newSINGLEimporter3014065 withreceiptqa/FULL-V3-SHIP-LAUNCH-2213.json/logqa/full-v3-ship-2213.jsonl. OutputrootNOW/scratch/nulls/full-v3; sessionff-20261016-pilot03, seeds/runs unchanged. No STOPcleared.
- One manualruntime90415 started22:13:12; runtimeperformsfreshallgatesagain, no stalegateuse. Currentmarkerremains s57/disk9.324GiB/swap888MiB prelaunch. Leaseend00:00, allnineactualpilotgatesbeforepriority. Counts0atlaunch. ContinueSAMEownerthroughpilot+QA+consumerhandoff, nohelper/automaticretry.

## 22:10Z: review07 GO; full-v2 supervised pilot boot active

- FreshSolreview07 GO bounded manualpilot,17tests+20bundledheartbeatfaultchecks pass; receipt `qa/fullframe-prehost-review07.md`. ExactbundleSHA1e1080d380cfb8da41d4f384d6e04dc0b91d9d7dc82d19d45d56e23c45753831 exclusivelyinstalled+verifiedatMac~/clasher-live/nulls/full-v2/code. Oldfull-v1STOPandlogsremainpreserved.
- Newsingle05importer2632772,receipt `qa/FULL-V2-SHIP-LAUNCH-2209.json`, log `qa/full-v2-ship-2209.jsonl`, followuntil00:05. Datasetroot NOW `/mpac/sdicks02/scratch/nulls/full-v2`; consumersmustnotuseoldemptyfull-v1. No duplicateoldimporter.
- One manualruntime79272/VM79345 started22:09:53 afterfreshgate:disk9.14465GiB/swapfree888.25MiB/freeinactive6.8694GiB, exactmarker+driverabsence+sharedlockpassed; leaseend00:00. Bootwatchhealthy22:10:01, noSTOP. Receipt `qa/FULL-V2-BOOT-LAUNCH-2209.json`.
- ContinueOWNERSHIP throughactualboot/setup/pilot/camera/body/pose/shippingQA, explicitninegatereleaseonly. Pilot02 namespace ff-20261016-pilot02. Alladmitted/rawfullframecounts0atlaunch, no claimedQA/prioritycompletion. No bootautoretry.

## 22:06Z: supervised boot STOP; heartbeat-race correction in fresh review07

- Pause received22:02:39after s57, independently verified22:02:56. Path-only taskpolicy correction to/usr/sbin was explicitly released by LEAD for normal engineering (no fresh review needed); dry --help passed, exactdiff+16tests passed. Immutable code-r06/bundleeb25c8eee06bf96178966dd1c55713368f3246b8bee795ae332d45df8f310895 preserved. Initialshellfailure/runtime.out also preserved.
- Runtime63453 supervisedVM63506 launched22:04:26with9.07165GiBdisk/888.25MiBswap/6.9774GiBfreeinactive, marker+driverabsence+lockpassed. Guardstoppedboot22:04:34onshippingheartbeat; by22:04:52allownruntime/watch/VMgone,0capturedframes. Actualfailedheartbeatagewasnotlogged; importerremainedalive/fresh.
- Confirmed local race: check samplednow beforeps/budget/telemetry, thenreadheartbeat updatedduringthosechecks andclassifiednegativeageasfuture. New regression FAIL beforefix/PASSafter; now sampletimeafterreadingheartbeat, same strict0..15s window.17testsPASS. Watchdoglogic requiresfreshSolreview per latestLEADinstruction.
- Fresh review07 task `node:delegated-task:command%3Amcp%3A90cb724b-6215-4a0f-ab24-8de5e0afeefa%3Adelegate-task%3Anulls-fullframe-prehost-review07-20261016` PENDING. Exactbundle `/mpac/sdicks02/scratch/nulls/build/full-v2-review07`,SHA1e1080d380cfb8da41d4f384d6e04dc0b91d9d7dc82d19d45d56e23c45753831. Allthresholds/label/stoplogicotherwiseunchanged.
- Newmanualattempt namespace full-v2 forMacROOT/state/spool and05dataset/importer; pilotSESSIONONLYpilot02 (seed/run/deploymentsunchanged). PreserveENTIREfull-v1includingSTOP/usedpilot01; no clearinglatch orolddatareuse. Old05importer3909433identityverified+SIGTERM22:05:31,receiptqa/FULL-V1-SHIP-STOP-2206.json. Do not duplicate/restartoldimporter. AfterGOdeployexclusivefreshfull-v2/code viarevieweddeployer, startsingleNEWshipper, recheckcurrentpause/resources, manuallylaunchpilotwithinlease; no automaticretry/priorityrelease.
- Blockerreceipt `qa/FULL-V1-BOOT-HEARTBEAT-STOP-2205.json`. Parentnotified; no routinefinaluntilblockend. Raw/admittedcounts0.

## 21:44Z: single importer heartbeat healthy; requested pause handoff

- Reviewed05 full_ship.py launched once PID3909433 (creation14:43:18Mac-independent05localtime), follow-until2026-10-17T00:05Z. Exact identity/argv/log in `qa/FULL-V1-SHIP-LAUNCH-2143.json`; log `qa/full-v1-ship-2143.jsonl`.21:43:29Z own Mac SHIPPER.json heartbeat fresh. This writes only new full-v1 state and transports new immutable chunks; no emulator/watch/capture exists. Do not duplicate importer.
- LEAD confirms babysitter archives/prunes s56 video(~0.56GB) after driverexit BEFORE marker; if disk remains<9GiB, reportshortfall, leadownsadditionalpruning. Existing babysitter asked to wake THIS owner thread when marker written at>=21:55 safe boundary. Readiness timer staysdisabled, no duplicate timer/helper.
- Pending external handoff only: marker+driverabsence+lockfree and current9GiBdisk/1.5GiBfreeinactive/500MiBswap. Then one reviewed code-r05 runtime boot; all nine pilot QA gates before priority. No automatic producer start/retry; full-v1frames/admitted remain0.

## 21:40Z: readiness wake consumed; code verified, awaiting pause/disk

- Readiness timer disabled immediately (nextRunAt null). Remote exact code-r05 verifier passes approved bundleSHA98031c16713d7b4406e8cc11b32602728ee66dba5b60dd675b6d30dbeb54e2a8. Review05 GO remains bounded pilot only; no code edits/new revision.
- Read-only21:40:27Z: disk8.83GiB (<9GiBSTART), swapfree880.25MiB, vm_stat free+inactive6.011GiB. Live s56 driverPID52792 active, no NULLS-BLOCK, no reference producer PIDs. Emulator/watch/capture/05shipper remainOFF; no boot attempt. Lead/babysitter owns archived-video pruning/pause.
- Planning-only inventory refreshed against body-mapV2: `qa/FULL-POOL-COVERAGE-INVENTORY-V2-2142.json`,110 deployment targets including5 shared-body cards; ThreeMusketeers native identity remains held pending proof. Approved pilot/priority plan bytes unchanged, actual captured/admitted counts0.
- Receipt `/mpac/sdicks02/scratch/nulls/qa/FULL-V1-READINESS-2140.json`. Continue existing ownership into reservedfirstboundary>=21:55 through00:00; recheck all pause/lock/resources, start single reviewed05shipper before runtime, then bounded pilot. Do not restart timer/create helpers or inferpause from endpoint alone.

## 20:52Z: review05 GO; corrected immutable code-r05 installed/verified

- Fresh Sol review05 closes R4-A and grants bounded two-scene PILOT code GO.16/16 tests, compile checks and23 actual bundled startup fault injections pass. Receipt `/mpac/sdicks02/scratch/nulls/qa/fullframe-prehost-review05.md`. No remaining code objection; actual pilot QA remains pending.
- Exact approved bundleSHA `98031c16713d7b4406e8cc11b32602728ee66dba5b60dd675b6d30dbeb54e2a8`; deployerSHA `0d9f6db8a7282c5ec0cf48aa24dfa4e5099f220083f6db7f35bdb72d571a89ef`. Read-only20:52:21Z ownership confirms no reference roles and unused state. Reviewed --revision r05 deployment created fresh `~/clasher-live/nulls/full-v1/code-r05` and remote verifier accepted exactSHA; old code remains preserved, review04 never deployed. Receipt `qa/FULL-V1-DEPLOY-R05-2052.json`.
- **USE code-r05 runtime/guard/release**, plans from that directory. Single05 shipper continues using byte-identical original code/full_spool.py helper. All producer/VM/watch/shipper roles remainOFF. START disk>=9GiB, vm_stat free+inactive>=1.5GiB, swap>=500MiB, confirmed pause contract and lease only; runtime STOP unchanged.21:40 readiness wake retained, no earlyboot/retry/priority auto-release.

## 20:50Z: review04 parser objection corrected; review05 pending

- R04 NO-GO P2 R4-A: vm_stat regex accepted fractional/trailing-garbage counter prefixes and first conflicting duplicate. R04 was NEVER deployed; receipt `qa/fullframe-prehost-review04.md`. Its deployer/revised budget/unchanged safety controls were accepted.
- Corrected parser requires one full positive-integer page-size header and one complete nonnegative-integer free/inactive counter each; horizontal whitespace and terminal period allowed. Duplicates, fractional/garbage/negative/nonfinite/missing fields reject. Targeted cases plus all16 pipeline tests pass locally; no Mac action.
- Fresh Sol review05 task `node:delegated-task:command%3Amcp%3A90cb724b-6215-4a0f-ab24-8de5e0afeefa%3Adelegate-task%3Anulls-fullframe-prehost-review05-20261016`. Candidate `/mpac/sdicks02/scratch/nulls/build/full-v1-review05`, manifestSHA `98031c16713d7b4406e8cc11b32602728ee66dba5b60dd675b6d30dbeb54e2a8`. Only full_guard.py differs fromR03. AFTERGO use --revision r05 to exclusively install code-r05, never code-r04. No new deployment before review. Reserved pause/headroom/pilotQA gates unchanged;21:40 wake must read latest top here.

## 20:48Z: LEAD revised START budget; narrow review04 pending

- Latest explicit LIVE LEAD rule SUPERSEDES old9.5GiBdisk/1GiBswap START requirement: pause marker + no driver + free sharedlock; disk>=9.0GiB; normal memory pressure OR vm_stat free+inactive>=1.5GiB. We implement the explicit vm_stat alternative. Runtime STOP remains disk<8.5GiB/swapfree<500MiB/FPS<9/p95>45ms, marker/lease/ship checks unchanged. Swap500MiB minimum also applies before start.
- Local guard change parses vm_stat actual page size/free/inactive, rejects malformed/nonfinite/low values, records start free+inactive. All16 tests pass, including exact startup/runtime boundaries and malformed vm_stat. Read-only20:44:37Z Mac page16384/free20516/inactive405256 =6.497GiB free+inactive, but live driver still active: no boot.
- Fresh independent Sol review04 PENDING: task `node:delegated-task:command%3Amcp%3A90cb724b-6215-4a0f-ab24-8de5e0afeefa%3Adelegate-task%3Anulls-fullframe-prehost-review04-20261016`. New bundle `/mpac/sdicks02/scratch/nulls/build/full-v1-review04`, manifestSHA `e887a177f5b281f51260cf87fe7dbc9261e8e20e783122945e23b5b76428c1d4`. Only payload delta is full_guard.py. Outside payload reviewed deployer now offers fresh immutable --revision r04 target code-r04, never overwrite installed code. Do NOT execute new deployer/bundle until review04 GO.
- Existing review03 code remains installed/preserved; VM/watch/capture/shipper OFF. After GO install fresh code-r04 then use its runtime/guard; old code/full_spool.py helper is byte-identical and keeps same isolated new state/spool. Pilot/priority plan and map SHAs unchanged.21:40 wake remains; recheck revised inputs and await pause, never boot early.

## 20:44Z: review03 GO; exact code installed, emulator remains OFF

- Fresh independent Sol review03 grants bounded TWO-SCENE PILOT code clearance only. All15 tests pass; exact17-member bundle verified, no extras. Receipt `/mpac/sdicks02/scratch/nulls/qa/fullframe-prehost-review03.md`. Approved manifest SHA `4749ba76b13350fe5884b34658ae47f430b534d71751eb51abc939e54cb0d7ce`; review01/02 payloads remain preserved and unused.
- Reviewed deployer exclusively created fresh Mac `~/clasher-live/nulls/full-v1/code` and verified installed bytes. No emulator, watchdog, capture or shipper started. Current live s53 driver PID18536 continues untouched; own producer roles absent. Read-only20:43:37Z disk9.356GiB / swap free784.25MiB both below9.5GiB/1024MiB START margins. Receipt `/mpac/sdicks02/scratch/nulls/qa/FULL-V1-DEPLOY-2044.json`.
- Class SHA remains `f033bf1b787d6594bde9296ba7350932a449d367f9635969b354fa8269f95bec`; authorized body map V2 SHA `f39eb4e3392e6dcf344df11c5e810dda9926b501bfae7d58f40d3e0df1e8c72f` is pinned throughout reviewed bundle/plans. Six previous name gaps reconciled; raw runtime IDs still never establish body names.
- Reserved pause at/after21:55 through00:00;21:40 readiness wake already scheduled, disable its recurring timer on delivery. Require marker+driver absence+free shared lock, current headroom, and fresh05 shipping heartbeat before pilot boot. Priority still requires all nine concrete matching pilot QA gates; no automatic retry/release. Actual boot/footprint, source camera/boxes/pose and shipping rate remain unproven until pilot.
- Coverage inventory105 class-primary card keys is not full deploy-card coverage: shared bodies also require SkeletonArmy, GoblinGang, MinionHorde, RoyalRecruits and ThreeMusketeers (at least110 compatible deploy cards). Expand future inventory without editing the reviewed first20 priority plan. Current raw/qualified full-v1 counts are0/0.

## 20:24Z: review02 pending; marker/driver-lock contract adopted

- Fresh Sol review01 correctly rejected unsafe startup/cleanup, endpoint-only idle inference, absent shipping deadlines and weak calibration/admission checks; its payload is preserved and never deployed. Review receipt `/mpac/sdicks02/scratch/nulls/qa/fullframe-prehost-review01.md`.
- Review02 concrete payload `.../scratch/nulls/build/full-v1-review02-final`, bundle manifest SHA `bc84aba18900ee33f5b2f6b94afbe214b5c3d09041275ef66bbd6d07f72d9193`; fresh task `node:delegated-task:command%3Amcp%3A90cb724b-6215-4a0f-ab24-8de5e0afeefa%3Adelegate-task%3Anulls-fullframe-prehost-review02-20261016`. No host mutation yet.14 local tests pass, code compiles; Mac read-only dependency check Python3.12.13/OpenCV4.14.0/NumPy2.3.5 passes.
- LIVE LEAD supplies authoritative pause contract: `~/clasher-live/loop/NULLS-BLOCK` with UTC start and stopped session; no `live/loop/drive.py` process; shared nonblocking probe of its exclusive `driver.lock` must succeed. Babysitter deletes marker60s before an early driver restart. New guard reads all three every check(~2s), releases shared lock immediately and writes no loop files.
- Supervisor now exists before VM execution; a pipe barrier records the own PID/creation-time/exact allowed exec commands before GO. Queue/VM/watch ownership and heartbeat are enforced; queue loss and capture-registration failure stop. Concurrent receipts and exited-PID races no longer abort independent cleanup. No automatic resume/retry/KILL escalation.
- Each completed full frame seals immediately;05 importer polls2s, restrictedMac list/ACK refreshes a required<=15s heartbeat, guard stops production at oldest unACKed READY age>45s. Healthy <=60s shipping latency is still a pilot measurement, not a guarantee during transport outage. Raw/source/qualified counts remain separate.
- Admission shares count/returned/generation/ID/shape synchronization validation and recomputes finite nondegenerate affine/tower/ground residuals. Native source confirms rich players do not contain hand/elixir; deploy waves now use epoch-matched ordinary observation and exact `succeeded` scheduled-action status. Modal focus causes fail-closed stop, never automatic UI recovery.
- Full105-card inventory and arena ordering: `/mpac/sdicks02/scratch/nulls/qa/FULL-POOL-COVERAGE-INVENTORY-ARENAS.json`. Six internal body-name/map gaps sent to class-map owner; affected frames held, not silently mapped. Existing Sol monitor confirms schedule disabled and no further producer/ship/control actions; fresh read-only checks found old emulator/watch/capture and05 ship loop gone. One old read-only log waiter PID68310 remains unclaimed and untouched.

## 20:10Z: dedicated block RESERVED; full-frame implementation in independent review

- LIVE LEAD reserves first safe session boundary at/after **21:55Z through 00:00Z** Oct16/17. Lead owns ladder pause/resume; live BlueStacks remains open and idle. No generator boot before confirmed pause, 9.5 GiB free disk and 1 GiB free swap. Notify lead by21:45 if code/review not ready; if headroom still fails at22:00, lead/babysitter owns further pruning.
- New code is isolated at `live/nulls/full_*.py`, `live/nulls/mac/full_*.py`, and fresh pilot/priority plans. Mac target `~/clasher-live/nulls/full-v1/code`; old emulator/watch/crop queue remain off. Fresh Sol pre-host review task `node:delegated-task:command%3Amcp%3A90cb724b-6215-4a0f-ab24-8de5e0afeefa%3Adelegate-task%3Anulls-fullframe-prehost-review01-20261016` is pending. Bundle `.../scratch/nulls/build/full-v1-review01`, manifest SHA `b86059a3e5b97d378711ef7b5360d1b93fb00214217df54e3084fb2cf2800dd2`. No Mac mutation yet.
- Local six safety/admission tests pass under producer venv Python3.11: runtime/start thresholds, missing live data, reused PID protection, queue-first stop ordering, immutable manifests, complete native-instance audit and non-overridable native team. Full code compiles. No claim of runtime or body-label correctness yet.
- R3 and class-map owners confirmed frozen class SHA `f033bf1b787d6594bde9296ba7350932a449d367f9635969b354fa8269f95bec` and body-map SHA `a65a2a1c65bfdf678e56962e6b4b8afb38d7ff77b845f15e11d20cf2fea2fe8e`; contract `reports/live/yolo_synth/NATIVE-ADMISSION.md`. Runtime IDs are not catalog IDs; identity mappings need evidence. Unknown/new visible bodies hold whole frames; classless effects explicitly mapped skip.
- Source chunks go promptly to `/mpac/sdicks02/scratch/nulls/full-v1/<fresh-session>/chunk-*`; each full frame has hash, paired native observations, tick/epoch, card scheduling status and held candidate identities. **complete=false until actual body/ghost/pose audit and calibration**; empty source, raw captured, shipped and consumer-admitted counts stay separate. R3 owns canonical crop mapping and consumer QA; generator owns source boxes and pilot evidence.
- Two short pilot runs precede the 15-scene priority queue. Runtime waits for an explicit matching QA receipt; no priority auto-release, retries or same-name capture. 100examples/card/team across>=5runs is an eventual per-card target; the first block can be partial and its actual per-card/team and pose coverage must be reported without blanket completion claims.
- Hard guard: disk<8.5 GiB, swap free<500 MiB, active live FPS<9 or p95>45ms; unknown safety inputs stop. Only recorded PID+creation-time+argv identities; queue first, capture/VM next; no global adb/BlueStacks access or automatic resume. Nice10,1core,1024MiB guest pilot. All Mac actions still await pre-host review.

## 19:49Z: RESUMED — full detector pool, plan before host execution

- LIVE LEAD supersedes prior HOLD and deck-only scope: EVERY detector-supported card, both native owners, prioritized by91BattleLog opponents, then18-card collection, arena unlock, remainder. Current156-name map has105 card identifiers requiring canonical alias reconciliation. No emulator restart yet.
- Selected dedicated22:00–00:00UTC proposal, after CARD parity/smoke ETA21:30–22:00 and at LIVE LEAD safe session boundary, excluding s51->s52/s52->s53. CARD job uses no emulator/adb; overlap is CPU/disk only. Do not pause other jobs or ladder ourselves.
- Baseline50completed/46fresh; measured6765 distinct labelled ticks over5.749h =1177frames/hour. New-path forecasts alongside500–900/dedicated1200–1800 per hour are estimates; replace after10–15min pilot. First20frequent cards targeted first2h, full supported pool estimated8–12dedicated capture-hours across approved blocks.
- Plan changes supervision to full frames with team cues intact + synchronized native ID/owner/pose metadata; existing cutout/inpaint artifacts remain preserved. Start1GiBguest/1vCPU/nice10; strict stop thresholds disk8.5GiB/swapfree500MiB/liveFPS9/p9545ms;128MiBnew-data spool,checksum ship<=60s,reviewed guards before boot.
- Current8.98GiBdisk/752MiBswapfree does not meet proposed9.5GiB/1GiBstart margin. Window timing, resource headroom, and full-frame label/guard pilot are pending. Detailed plan: `/mpac/sdicks02/scratch/nulls/qa/FULL-POOL-RESUME-PLAN-1949.json`.

## 19:06Z: EXPLICIT LIVE LEAD HOLD — NO RESTART

- LIVE LEAD stopped watchdog37239 and reference emulator5596 on adb5049 for live-priority resource protection (disk7.7GiB,swap5.4/6GB,concurrent CARD native build). Nulls synth v2 is lower priority than V9a. Generator issued no restart or emulator/ADB operation.
- **Do not restart emulator, capture or watchdog until LIVE LEAD explicitly releases this hold. No timer or automatic restart.** Read-only19:06:24Z ps confirms queue28203/emulator37238/watch37239 gone. Capture queue had naturally completed15:56:29Z; shipping drained15:58:39Z and monitor schedule disabled16:03:47Z.
- Resume checkpoint:50 raw completed shipped runs,46 from fresh seed2026101610; consumer last verified7 body-bearing runs/61 originals/0 inpaint, separate scopes. Preserve all artifacts and historical invalid runs.
- When explicitly resumed, post current capture counts plus a reviewed plan using fresh native-build/live/disk/swap baseline, conservative start headroom, strict disk/swap stop budget, low emulator cores/RAM/QoS and bounded pilot. Existing guards/footprint must be reassessed before boot; no new host-touching script runs without review.
- Receipt: `/mpac/sdicks02/scratch/nulls/qa/HOLD-LEAD-STOP-1906.json`.

## 11:31Z: ANR recovery + targeted recapture/center handoff complete; approved queue continues

- Reviewed one-tap SystemUI recovery succeeded; gamePID1799 persisted and no app reset/lifecycle retry occurred. One fresh queue28203 progressed through lane+center to stage3, current capture32640; emulator37238/watchdog37239 unchanged. At11:30:17Z:10.37GiB free,swap5.55 vs6.386baseline,gates clear,noSTOP/ANR,only emulator5596 on5049,WiFi off and both app firewalls verified.
- All10 targeted fresh runs completed/shipped/validated:5374 original source rows,6391 including variants.1518 historical good/invalid source files retain exact hashes; old partial Minions is preserved on Mac.
- Independent producer gate7 explicit original-subset runs differs from actual consumer staged5 body-bearing runs/33 originals/0 approved inpaint; overlay-only runs never count. Consumer receipt corrected its12->5 metadata count. Center Archer contributes5 admitted originals total; Minion bodies remain conservatively held, including center t1 open head cuts and t0 floor/silhouette uncertainty. No filter or source-policy relaxation.
- Current staged source_plan remains official for Archer/Minion/MiniPekka, Nulls fallback for SpearGoblin; canonical443/historical457 preserved. Consumer independently promoted/synced the reviewed bank03/04/08 under its standing refresh authority at11:32Z (generator made no actions on those hosts); any new generation/v2 remains HOLD pending separate authorization.
- Full handoff: `/mpac/sdicks02/scratch/nulls/qa/ANR-RECOVERY-HANDOFF-1131.json`; measured center/consumer coverage: `qa/CENTER-COVERAGE-RESULTS-1124.json`. Existing Sol monitor continues ship/QA. Generator retains exclusive driver/lifecycle ownership for future incidents; no new operator, automatic retry or queue edit.

## 11:12Z: original-source gate 5 reached; center coverage validation continues

- Independent monitor first qualified original-source gate5/5 at11:10:39Z: historical SpearGoblins both teams, fresh lane Archer t1, lane MiniPekka t0, center Archer t1. Explicit clean-original subsets only; no blanket raw-row approval. Monitor sent the essential threshold handoff once; generator retains ownership for the requested BOTH-team center assessment.
- Center Archer t0 completed11:10:55Z and shipped11:11:25Z,577 originals+86 variants; source/schema checks pass. Local unchanged-importer preflight yields57 originals/58 variants before actual sampling/exclusions,13 originals need no opaque component cleanup; owner sees clean complete precombat red Archers. Center t1 preflight16 originals/81 variants,2 unchanged originals. These are candidate counts, not exact post-import admission.
- Current stage2 capture56047/queue28203 now runs center Minions; preserve approved order/guards. Await both center Minions runs, independent actual-body QA, and consumer-owned exact post-import source-plan coverage.

## 10:51Z: coverage steering incorporated; center stage follows MiniPekka

- Complete and validate the already queued Archer/Minions center stage for BOTH teams after MiniPekka, with no stage reorder or driver change. Compare actual isolated precombat bodies and exact post-import source eligibility against lane, preserving strict filters and original-versus-cleaned scopes.
- Coverage assessment: `/mpac/sdicks02/scratch/nulls/qa/CENTER-COVERAGE-ASSESSMENT-1049.json`. Current compositor counts (including approved inpaint) need +9/+5 Archer, +10/+4 Minion, +3/+0 Spear across compositor teams to reach shared min_src10; producer gate and compositor-cleaned counts differ. Current preset4 Nulls source support is SpearGoblin only; Archer/Minion remain official.
- MiniPekka t1 completed/shipped with425 originals+26 variants and schema/provenance pass. At10:58 owner adopted monitor counterproof: examples238/250/278 retain helmet notches and overlay_px725, so the initial positive recognition verdict is superseded; current original-source gate remains3. MiniPekka t0 completed and shipped10:56:19Z; independent original eligibility pending. Center Archer/Minions stage is now active (capture56047, queue28203). Continue ownership through center QA and verified data handoff.

## 10:45Z: recovery holds; quality gate remains 3/5

- Single fresh queue 28203/capture 28207 is progressing through the unchanged approved deck-first order, seed 2026101610. Both Archer and both Minions runs have completed and shipped with verified hashes; MiniPekka t1 is capturing. No ANR has returned in sampled fresh full frames.
- Actual-body QA qualifies Archer t1 only on its explicit clean original subset (00388/00390); source gate is 3 including the two user-accepted historical SpearGoblins runs. Fresh Archer t0 fails: all 18 nonsplit nondeath bodies retain effects/puffs or a bar remnant. Minions samples are heavily clipped/crowded/effect-contaminated and are not owner-qualified pending monitor evidence. Raw schema/provenance passing is insufficient.
- Existing Sol monitor owns SOURCE-GATE.json and shipping/QA control. Owner QA receipts are `qa/<fresh-run>-validation.json`, `-recovery-sheet.jpg`, and `-visual-decision.json`; images remain outside git. No >=5 handoff has been made.
- Continue through clean MiniPekka candidates and independent actual-body QA, then verified data handoff; do not relaunch, repeat the tap, or change lifecycle/watchdog policy. Current protection is healthy (~9.9 GiB free, swap 5.56 GiB vs baseline 6.386); one earlier live gate parked/resumed normally.

## 10:03Z: SystemUI ANR recovery owned by existing generator (Sol high)

- Queue 56819 and capture 56821 stopped using the identity-verified existing rollback; reference emulator 37238 and watchdog 37239 remain active.
- Archer t1/t0 and partial Minions t1 from seed 20261016 are preserved and nonqualifying: a confirmed SystemUI ANR obscures the arena. Qualified source count remains 2.
- Independently reviewed GO and LEAD released: exactly one reference-only Close app tap at10:10:01Z removed SystemUI ANR; game PID1799/UID10208 persisted and native attestation stayed production_ready. One fresh queue28203 launched10:11:34Z with seed2026101610, unchanged deck-first stages/protections; queue hash c4ffb6f9. First actual-body QA pending.
- Receipt: `/mpac/sdicks02/scratch/nulls/qa/ANR-RECOVERY-REVIEW-1003.json`. Existing Sol monitor coordinates shipping and QA; generator retains end-to-end ownership.

## 08:15Z: fixture window restarted, 08:15:18Z → 10:15:18Z

- The 06:54Z ready message was only queued and apparently never reached the CARD LEAD; the probe stayed untouched (headless, tick -1).
- On the LIVE LEAD's wake-up I resent it with mode=auto; it was steered into their active turn.
- The resume job is re-armed for 10:15Z, or earlier on release.
- Capture runs on 05 so far: 2 (SpearGoblins t0, t1). The deck-first queue hasn't completed a run yet.

## 06:54Z: CARD LEAD fixture slot LIVE, 06:53:43Z → 08:53:43Z

- Emulator PID 37238 has been up since 06:50Z; the probe has been ready (headless, tick -1) since 06:53:43Z. Watchdog clean: 9.37 GiB free, swap +0.
- The ready message was sent to the CARD LEAD (clientRequestId nulls-fixture-slot-ready-0653).
- A background job on 05 resumes the deck-first `queue.sh` at 08:54Z, unless the watchdog fired.

## 06:50Z: CARD LEAD fixture slot (120 min) on LIVE LEAD GO

- Capture is not running (no queue). The emulator starts alone when free ≥ 9.08 GiB, with the watchdog (disk hold, swap, live protection) up.
- When the probe reports `production_ready`, the ready message goes to CARD LEAD thread `thread:delegated-task:command%3Amcp%3A7f0bf0df-35b9-48b9-bbf9-8f9cdcc3f584%3Adelegate-task%3Aclasher-card-lead-20261016-r1`, copied to the LIVE LEAD.
- Worker `cards-nulls-fixtures-sol-r1` drives only the probe (127.0.0.1:26795; emulator-5596; adb port 5049). We own the emulator.
- After +120 min: resume the deck-first `queue.sh`.

## 06:47Z: resumed after the usage-limit gap; disk HOLD instead of stop

- **03:52:58Z:** the watchdog fired again on a transient dip (7.98 GiB), about 10 min into the deck stage, before any deck run finished. Nothing ran from 03:53Z to 06:45Z (session limit).
- **watch.py change (allowed by the LIVE LEAD's "stop or hold"):**
  - free < 8 GiB → HOLD: gate, capture parks, qemu SIGSTOP. A stopped VM writes nothing.
  - Release at ≥ 9 GiB. Full stop only if held > 30 min.
  - Disk is checked every 2.5 s. Swap and p95 rules are unchanged (stop).
  - This avoids a ~5 min reboot plus client load on every ~1.3 GB dip.
- **Restart:** a background job waits for free ≥ 9.08 GiB, then runs `emu.py up` plus the same deck-first `queue.sh` stages.

## 03:48Z: deck-first queue running (queue PID 6369); adb hardening

- **Watchdog fired twice** on transient Mac disk dips: 03:21Z (7.77 GiB) and 03:35Z (7.86 GiB). Free disk swings about 1.3 GB within a minute (live video write and prune), with our emulator idle or frozen.
  - The AVD is unchanged: userdata qcow2 is still 5,160,435,712 bytes, mtime Sep 28, and there's no snapshots dir.
- **03:25Z:** a protection trip at battle start froze qemu mid-boot, so `emu.py up` died before setup; I finished it manually.
  - Protection now ignores the first 30 s of a battle and needs 2 consecutive strikes.
  - The watchdog SIGCONTs qemu at startup, and SIGTERM runs its cleanup (SIGTERM had left qemu frozen once).
- **adb:** BlueStacks `emulator-5554` was re-attached to our 5049 server twice.
  - Verified fix: `ADB_EMU=0` plus `ADB_LOCAL_TRANSPORT_MAX_PORT=5553` in every path (emu.py env, capture.py import, a.sh, queue.sh). A fresh server sees only emulator-5596 over 50 s.
  - lsof: our server holds only 127.0.0.1:5597. Port 5555 is held only by the live adb (PID 7114).
- `capture.py` waits up to 5 min on "native content runtime is not initialized yet" instead of failing the whole batch (which happened at 03:29Z).
- **LIVE LEAD priority (03:40Z):** our deck, both teams, first. `mac/queue.sh` runs these stages:
  1. Archer, Minions, MiniPekka (lane);
  2. Archer, Minions (center);
  3. Valkyrie, Giant, Musketeer, Cannon, Fireball, Arrows;
  4. batch-1 rest (lane);
  5. SpearGoblins, Barbarians (center).

  Then the CARD LEAD slot on GO, then the KataCR gaps.

## 03:32Z: GO to restart at ≥ 9 GiB; the always-on battle gate is replaced by live protection

- **LIVE LEAD:** the FPS cost is live-side, so qemu now runs during battles.
- The watchdog checks every 10 s during a battle. If live FPS over 60 s < 5.6 or step p95 > 40 ms, it gates (capture parks, qemu SIGSTOP) until that battle ends.
- Disk (stop < 8, start ≥ 9) and swap (+1.5) rules are unchanged. Transient ~1 GB dips may stop us again; restart at ≥ 9 GiB.
- The restart waits on the Mac for ≥ 9.08 GiB (9300 MB), then runs `emu.py up` and batch 1 with `--skip shipped.txt`. Fixture slot after batch 1, on GO.

## 03:22Z: live-battle gate built and verified; WATCHDOG FIRED on a transient disk dip; emulator DOWN

- **LIVE LEAD 03:18Z:** YOLO live perception made the loop CPU-bound (FPS ~6.0, target ≥ 6.5). The emulator must not compete during live battles.
- **Implemented SIGSTOP/CONT gating:**
  - `watch.py` polls `localhost:8765/state` every 2.5 s. On `state == battle` it writes `state/LIVE-BATTLE`.
  - `capture.py` parks before its next frame or scene load and writes `state/CAPTURE-PARKED`.
  - The watchdog then SIGSTOPs qemu (immediately if capture isn't running; after 20 s regardless). At battle end it SIGCONTs, clears the gate, and capture waits for adb to answer.
  - The limit checks (every 30 s) now also log live FPS.
- **Verified at 03:20:43Z:** gate set, capture parked, qemu SIGSTOPped 5 s later (state T, 1.3% CPU).
- **Live FPS during battle:**

  | condition | live FPS | qemu CPU |
  |---|---|---|
  | qemu running, capture active (03:20:06–:22) | 5.92–5.94 | 83–93% |
  | qemu SIGSTOPped (03:21:14, 03:21:45) | 5.91 | ~1% |

  **So our emulator is not what holds live FPS below 6.5.** It's live-side CPU (YOLO perception).
- **03:21:45Z: watchdog fired** on free 7.77 < 8 GiB, a transient ~1 GB dip from something else on the Mac (qemu was frozen, our data is 1 MB, swap flat). By 03:21:58Z it was back to 9.0 GiB.
  - The emulator was stopped by `emu.py down`; capture exited.
  - Restart needs free ≥ 9 GiB plus the LIVE LEAD's go.
- Shipped so far: SpearGoblins t0 and t1.

## 03:15Z: capture crash fixed; source clean-up; relaunch (capture PID 3653)

- **Crash at ~03:00Z:** an adb screencap timed out after 30 s, raising `subprocess.TimeoutExpired`, which wasn't caught, so the whole capture died.
  - Lost: SpearGoblins t1 (a socket timeout at 02:45) and a partial Tombstone t1.
  - Fix: screencap gets a 45 s timeout with 1 retry; every exception is a per-run failure; after a failure the emulator and probe must answer, else stop with exit 3.
- **Source clean-up for the compositor:**
  - `main_body`: keep the largest component plus touching or sizeable pieces; `dropped_px`.
  - Erode 1 px, tagged `matte: "erode1"`.
  - Spawn sampled every 2 ticks.
- **`--skip state/shipped.txt`** skips runs already on 05. Regenerate it with `ls cutouts | grep -- -L1500` before every relaunch.
- Batch 1 now ends about 05:00Z.

## 03:25Z: inpainted variants (compositor request)

- `live/nulls/inpaint.py` adds extra rows with `inpainted: true` and a `-inp.png` for bodies with badge holes, filling only the enclosed hole pixels.
  - On SpearGoblins t0: 159 rows; median inpaint_px 47 vs overlay_px 461.
- ship.sh runs it in staging before `body_names.py`, using a dedicated venv at `/mpac/sdicks02/scratch/nulls/venv` (opencv-python-headless).
- Applied in place, reader-safely, to the shipped t0 run: 789 rows, and all PNGs resolve.

## 03:10Z: compositor yield feedback

- On SpearGoblins t0, only 21 of 228 bodies pass the compositor's filter: most are split/crowded (the trio walks touching), and many have overlay_px > 40 (badge holes).
- **The badge never fades in this client:** it is on 100% of bodies at every second after deploy.
  - Hiding it needs a probe or client patch. That's not done; noted as a possible later probe feature (render-layer gate).
- **Added `--place center`:** deploys on x=9 so multi-body troops fan out to both lanes. cards.json now has `count`. Runs get the suffix `-center` and rows a `place` field. It's deployed to the Mac; the running batch is unaffected.
- **Queue after batch 1 + fixture slot:**
  - `--place center` for SpearGoblins and Barbarians (both teams);
  - then batch 2, with `--place center` added for any multi-body card.

## 03:00Z: path field; first enemy run verified

- The compositor adapter skipped every PNG because it joined run + `file`, but `file` is cutouts-root-relative.
  - Rows now also carry `png` (run-relative), added by `body_names.py`, applied atomically. FORMAT.md has a Paths section.
- **SpearGoblins t0 (enemy), 630 rows:**
  - red badges: 224 overlays, owner 0;
  - **HP bars: 23 found for 25 damaged body rows**;
  - deploy dials: 67;
  - state attack 59, walk 144, spawn 59, death 41, idle 13;
  - body_name SpearGoblin 228. Unmapped projectile ids 10000003 and 10000019 have body_name null.

## 02:40Z: HP-bar fix; batch 1 restarted (capture PID 20220)

- **The first real run** (SpearGoblins t1, 622 rows) had badges removed correctly (259 badge and 29 dial overlay rows), but the HP bars were missed.
  - Measured own bar: dark-blue outline, grey-blue track, light-cyan fill, about 13 px tall, right of the badge.
  - New rule: count bar-like pixels per column. On frames reconstructed from shipped data it finds the bar in 21 of 23 ticks with a damaged body, with tight boxes.
- **State fix:** a body that has a target and isn't moving counts as `attack` (between swings).
- The superseded run was moved to `/mpac/sdicks02/scratch/nulls/superseded/`.

## 02:40Z: body ids

- The probe's `dataGlobalId` is runtime numbering, not body-catalog.json's csv order (probe SpearGoblin 34000019 vs catalog 34000021; tower projectile 10000003).
- `live/nulls/body_names.py` learns `probe_ids.json` from own-card majority and adds `body_name`.
- `ship.sh` now stages into `cutouts/_incoming`, verifies, names, then moves into place in one step (zsh `(N)` glob, so no "no matches" noise).
- The compositor (live-yolo-synth-compositor-opus-r1) was told to key on `body_name`.

## State, 2026-10-16 02:32Z: batch 1 restarted with overlay separation (capture PID 86406)

- **LIVE LEAD 02:24Z:** the "11" level badge, HP bar and deploy dial must not be baked into bodies (the official client shows badge + HP bar only on damaged units).
  - New `overlay.py`:
    - the badge is matched by its white glyph, with the owner taken from its hue;
    - HP bars are searched only next to badges of probe-damaged bodies;
    - the deploy dial is the gold ring during spawn.
  - Overlays are removed from body masks and cut out as `row_type=overlay` rows with `offset_from_anchor`.
  - Body rows carry the badge, hpbar, deploy_dial and overlay_px flags.
  - Template: `live/nulls/templates/badge_own_l11.png`.
  - Format spec: `/mpac/sdicks02/scratch/nulls/cutouts/FORMAT.md`, sent to the compositor thread for `yolo-synth-sol-monitor-r1`.
- The two old-code SpearGoblins runs were deleted before shipping. `capture.py` now wipes a partial run dir before re-capturing it.
- **CARD LEAD fixture slot:** about 90 min right after batch 1, worker `cards-nulls-fixtures-sol-r1`, on the LIVE LEAD's GO.
  - During the slot, capture stays paused; the emulator and watchdog stay up.
  - Resume afterwards with batch 2: GoblinMachine, Goblinstein, MergeMaiden, Mirror, SuspiciousBush, Vines, FirespiritHut, GoblinCurse, GoblinHut, ThreeMusketeers.

## State, 2026-10-16 02:23Z: CAPTURING batch 1; Sol helper monitoring

- The emulator has been up since 02:05Z (PID 14886, -memory 1536). The watchdog is clean: swap +0.00, free about 9.6 GiB.
- **Smoke at 02:20Z:** SpearGoblins t1 gave 138 cut-outs over 60 ticks (3 bodies, data_global_id 34000019). The contact sheet shows real sprites.
- **Batch 1** (capture PID 65718) started 02:21Z: SpearGoblins, Tombstone, Bomber, GoblinCage, Barbarians, Berserker, BossBandit, DarkMagic, GiantBuffer, GoblinDemolisher × teams 1, 0.
- **Sol helper** (codex gpt-6.1-sol high, task `nulls-sol-monitor-r1`) monitors, ships and writes QA to `/mpac/sdicks02/scratch/nulls/qa/QA-BATCH1.md`.

## HANDOFF (self-contained; owner = Opus generator thread; Sol helper = monitor and ship)

### What runs where

- **Mac mini** (`ssh macmini-fleet`; it always exits 0, so append `; echo __RC=$?` and parse that):
  - **Code:** `~/clasher-live/nulls/code/`, a flat copy of repo `live/nulls/*.py`, `cards.json`, `base-config.json`, and `live/nulls/mac/*`.
  - **Emulator instance A:** the reference AVD `clasher_reference_api35`, started `-read-only` (nothing persists), console 5596, serial `emulator-5596`.
    - Flags: `-memory 1536 -cores 2 -gpu host`, under `nice -n 10 taskpolicy -b`.
    - Receipt: `~/clasher-live/nulls/state/inst-A.json` (pid, swap_at_start_gib, app uid).
    - Client: **15.535.13** (versionCode 150535013), content 15.535.86. It is offline, never signed in, and has iptables REJECT on app uid 10208.
  - **Watchdog:** `watch.py A`, auto-started by `emu.py up`. Log: `~/clasher-live/nulls/state/watch.log`.
  - **Capture:** `capture.py`. Its PID is in `~/clasher-live/nulls/state/capture.pid`.
    - Logs: `~/clasher-live/nulls/data/capture.log` and `state/capture.out`.
    - Output: `~/clasher-live/nulls/data/out/<card>-t<team>-L<loc>-s<seed>/`.
- **127x05:**
  - Ship loop: `bash -c 'while true; do live/nulls/ship.sh; sleep 180; done'`, log `/mpac/sdicks02/scratch/nulls/logs/ship.log`, PID in `logs/ship-loop.pid` (it was 2438578; its bash child is 2438582).
  - Destination: `/mpac/sdicks02/scratch/nulls/cutouts/<run>/`.

### Commands (on the Mac, `cd ~/clasher-live/nulls/code`; python = `~/clasher-live/venv/bin/python -B`)

- **Start:** `emu.py up --inst A`.
  - Preflight refuses if free < 9 GiB, and waits out the first 30 s of a live battle.
  - After start, wait about 90 s for `production_ready`. `capture.py` waits up to 10 min, then saves `data/not-ready.jpg` and exits. **Don't retry in a loop. Report.**
- **Capture:** `PYTHONHASHSEED=0 nice -n 10 taskpolicy -b <python> capture.py --cards A,B,... --teams 1,0`.
  - It is resumable: runs with `done.json` are skipped, but shipped runs are gone from the Mac and will be re-captured. Pass only the remaining cards.
- **Stop capture:** `kill $(cat ~/clasher-live/nulls/state/capture.pid)` (only after checking with `ps` that the PID is capture.py).
- **Stop the emulator:** `emu.py down --inst A`. It runs `adb emu kill`, then kills only the receipt PID, then kills our adb server.
- **adb:** `./a.sh <args>`, which is adb `-P 5049 -s emulator-5596`.

### Hard rules

- **adb isolation:**
  - Our adb server is **port 5049 only**, started with `ADB_LOCAL_TRANSPORT_MAX_PORT=5553`, so it never scans to 5555.
  - **`emulator-5554` is the live BlueStacks bot: never address it.** If `./a.sh devices` (no `-s`) ever lists it, kill our server: `<sdk>/platform-tools/adb -P 5049 kill-server`.
  - Never use ports 5042–5047.
- **Live protection:** during a live battle, gate only when FPS(60 s) < 5.6 or step p95 > 40 ms (see 03:32Z).
- **Mac limits (watchdog, every 30 s):** it stops the emulator if free disk < 8 GiB, or swap used grows by more than 1.5 GiB over `swap_at_start_gib`, or the live step p95 is ≥ 45 ms for 2 min. Capture backs off while live p95 ≥ 40 ms.
  - Our Mac footprint must stay ≤ 3 GiB (the overlay in `/private/tmp/android-sam` was about 150 MB, plus unshipped runs).
  - **Never run broad `find`/`du` over `~` or `/`.** Use exact paths only.
- Kill only our own PIDs: the emulator receipt PID, capture.pid and watch.py. Never touch BlueStacks, the live bot, other users, the UTM/colima VMs, Codex, Chrome or `~/Desktop/code`.
- No commits; the LIVE LEAD commits. No images in git.

### Capture order

1. **Faced non-C56:** SpearGoblins, Tombstone, Bomber, GoblinCage, Barbarians.
2. **KataCR missing:** Berserker, BossBandit, DarkMagic, GiantBuffer, GoblinDemolisher (these complete the first 10), then GoblinMachine, Goblinstein, MergeMaiden, Mirror, SuspiciousBush, Vines.
3. **KataCR partial:** FirespiritHut, GoblinCurse, GoblinHut, ThreeMusketeers.
4. **The remaining C56 and others,** for the art refresh.

Ronin is not in 15.535. The card list with ids is `live/nulls/cards.json`.

### Per-run method (capture.py)

- **Scene:** `configure-native` on Goblin Stadium (location 15000002), level 11. The deck is the target plus 7 fillers.
  - The seed is retried until the target is in the deploying team's starting hand. A repeated-card deck breaks `replay-schedule-card` (`card-unavailable`).
- **Backgrounds:** 10 paused frames give a median background and a dilated flicker mask.
- **Deploy:** `replay-schedule-card`. Placement:
  - team 1 (bottom): troops at (3.5, 19.5), buildings at (6.5, 21.5);
  - team 0 (top): troops at (3.5, 12.5), buildings at (6.5, 10.5);
  - spells land on the enemy princess tower.
- **Stepping:** 1 tick for the first 30 ticks and around death, otherwise 2. Each paused frame is screencapped, with an `observe-rich` before and after.
- **Differencing:**
  - Changed pixels are blobbed. Blobs entirely inside tower boxes are dropped.
  - Each blob goes to the object whose ground anchor falls in or near it. Shared blobs are split per pixel by nearest anchor and flagged `split`.
  - Blobs near a vanished object's last position become `death` cut-outs.
- **Alpha:** 255 for body, 90 for shadow (uniform darkening), 0 otherwise.
- **Row fields:** card, card_id, kind, team, owner, tick, ticks_since_deploy, entity (nativeObjectId), data_global_id (body), obj_card_id, x/y milli-tiles, hp, state (spawn/walk/attack/idle/active/death), bbox, anchor_px, mask_px, shadow_px, near_tower, split, crowded, frame_shape, official_scale (1.074 official px per replay px), location, seed, client.
- **Geometry:** the native-render **replay layout** at 1080x1920 has both hands shown and the arena shifted down. x = 540 + 48.0·(tx−9); y = 1021 + 38.5·(ty−16), with tiles from the native milli-tiles. This was measured from bridges and the river, not refit per arena.
- **Speed:** about 1 tick/s under background QoS, so about 4–6 min per run (card×team).

### Shipping

**Reader-safety rule (02:45Z):** the compositor reads `cutouts/<run>/` as soon as `done.json` exists.
- Never delete or edit a run in place.
- Stage replacements in `cutouts/_incoming/` and swap them in with one rename.
- Log any move in `/mpac/sdicks02/scratch/nulls/SUPERSEDED.md` before doing it.
- `body_names.py` copies to raw (never renames) and rewrites through tmp + rename.


`ship.sh` (on 05) rsyncs each run that has `done.json`, compares a sha256 tree of all files on both sides, and deletes the Mac copy only on a match. A mismatch is logged, and the Mac copy is kept.

### Known failure modes

- **The probe port accepts before the app listens:** empty reply or JSON error. `capture.py` retries attest for 10 min.
- **Plain `observe` truncates its deck array if a deck repeats a card.** That's why the deck uses one copy plus fillers; per-frame state uses `observe-rich`.
- **The raw `deploy PLAYER CARD PD X Y` is accepted but spawns nothing.** Use `replay-schedule-card` only.
- **"nothing spawned" in the log** means the deploy failed. The schedule status is logged; `failed`/`card-unavailable` raises.
- **The live p95 spikes (~60 ms) at the start of each live battle.** That's normal and transient; the watchdog needs 2 minutes ≥ 45 ms.
- **Mac disk drifts down** from other projects (the colima-canvasdoc VM disk, live video); the babysitter prunes live runs. If the watchdog fires, report and don't restart below 9 GiB.
- **Emulator start under heavy swap:** the 10-15 attempt never reached `production_ready` in 300 s. Now it's about 90 s.
- **Swarm cards** (SpearGoblins, Barbarians, etc.) produce mostly `split=True` cut-outs early on. The compositor can filter on `split`.
- **Level badge ("11") and HP bars** are part of the cut-out when they're near the body. The badge is real render.

### Native-fixture slots for the CARD LEAD

- **Same host and AVD:** Mac mini, `clasher_reference_api35`, client 15.535.13 / content 15.535.86, no Ronin.
- **Probe:** `127.0.0.1:26795` on the Mac (forwarded to guest 26789), or instance B at 26797 / `emulator-5598` (`emu.py up --inst B`) if RAM allows. Today it doesn't, so one instance only.
- **Switching modes:** fixtures use headless `configure`/`step`/`observe`, and switching modes destroys the native-render scene. So a slot means pausing capture: kill capture.pid between runs, and leave the emulator up. The CARD LEAD then drives the probe directly with the commands in `scripts/smoke_reference_battle.py`, and capture resumes after they're done.
- **Offer:** slots on request, 1–2 h, coordinated by the LIVE LEAD. Who drives: the CARD LEAD's worker, over `ssh macmini-fleet` with the probe socket. Opus/Sol owns start and stop of the emulator.

## State, 2026-10-16 02:02Z: HOLD (LIVE LEAD); emulator stopped; code ready; waiting for GO

- **Refocus (01:35Z):** per-card cut-outs with masks, not bulk frames.
- **Capture order:**
  1. The non-C56 cards we face: SpearGoblins, Tombstone, Bomber, GoblinCage (+ GoblinBrawler), Barbarians.
  2. KataCR missing (`/mpac/sdicks02/jobs/clasher/katacr-20261016/katacr-coverage.json`): Berserker, BossBandit, DarkMagic, GiantBuffer, GoblinDemolisher, GoblinMachine, Goblinstein, MergeMaiden, Mirror, SuspiciousBush, Vines. Ronin is not in 15.535.
  3. KataCR partial: FirespiritHut, GoblinCurse, GoblinHut, ThreeMusketeers.
  4. The C56 art refresh.
- **Restart conditions (LIVE LEAD):** Mac free ≥ 10 GiB and swap used < 5 GiB; `-memory 1536 -cores 2`, `nice 10` + `taskpolicy -b`.
  - `watch.py` checks every 60 s and stops the emulator if free < 8 GiB or swap > 6 GiB.
- **02:01Z Mac reading:** free 9.32 GiB, swap 6.66 GiB used, so not yet.

### Code

Repo: `live/nulls/`. Mac copy: `~/clasher-live/nulls/code/`, a flat directory.

- **`mac/emu.py up|setup|down|status --inst A`:**
  - read-only AVD, console 5596, own adb server on 5049 with `ADB_LOCAL_TRANSPORT_MAX_PORT=5553`, so it never scans to BlueStacks (`emulator-5554`);
  - network isolation: wifi off, iptables REJECT on app uid 10208;
  - `wm size 1080x1920` and the probe forward to 26795;
  - starts `watch.py`; `down` also kills our adb server.
- **`mac/watch.py`:** the disk, swap and live-p95 watchdog; logs to `~/clasher-live/nulls/state/watch.log`.
- **`capture.py --cards A,B --teams 1,0`:**
  - per run: a fresh scene, 6 paused backgrounds (median plus a flicker mask), deploy, then step 1–2 ticks;
  - each paused frame is differenced; blobs are assigned to observe objects by ground anchor, and shared blobs are split per pixel (flag `split`);
  - output: RGBA PNG plus `cutouts.jsonl` (card, body `data_global_id`, team, state, tick, bbox, anchor, flags, scale);
  - it backs off while the live step p95 is ≥ 40 ms.
  - A mock end-to-end test passes (`/tmp/nulls-mock/mock_test.py` on 05).
- **`ship.sh`** (run on 05): rsync the finished runs, compare a sha256 tree, delete the Mac copy only on a match.

### Incidents

- **01:38–01:45Z:** the first boot ran unattended (2048 MB). The Mac went into swap, the live FPS fell from 6.9 to 5.8, and the LIVE LEAD stopped it.
  - My broad `find` (disk search) added Spotlight load. **Never again.**
- **01:52–01:58Z:** a second boot (2048 MB). The runtime never reached `production_ready` within 300 s. The HOLD arrived and I stopped it at 01:58Z.
- **My adb server on 5049 auto-attached to BlueStacks `emulator-5554`** through adb's 5555 port scan. I never addressed it. I killed my server at 01:59Z; it is fixed by `ADB_LOCAL_TRANSPORT_MAX_PORT`.

## Earlier state, 01:35Z: plan sent, no host writes yet

Read-only probes only. Nothing is launched on the Mac, and no file is written there.

### The instance

- **AVD:** `/Users/sam/.cache/clasher-native-reference/avd/clasher_reference_api35.avd`.
  - It has its own SDK at `.../clasher-native-reference/android-sdk` (emulator 37.1.11, API 35 google_apis arm64). This SDK survived the 10-15 cleanup.
  - Config: pixel_4 at 1080x2280 and 440 dpi, 4 cores, 2 GB RAM.
  - Its userdata qcow2 is 5.16 GB.
  - The last launch (emu-launch-params.txt) used `-no-window -no-snapshot -gpu host -memory 3072 -cores 2 -read-only`, console 5586.
- **App:** `nullsroyale.rel.free`, activity `com.supercell.clashroyale.GameApp`.
  - APK versionName **15.535.13** (versionCode 150535013), with on-device content update **15.535.86**.
  - It carries the injected native probe `libcrprobe.so`. The guest listens on tcp 26789, reached with `adb forward`.
- **Probe commands that matter:**
  - `configure-native JSON`: the stock battle scene, rendered. The location id selects the arena.
  - `pause`, `resume`, `speed`, `advance-native N`.
  - `deploy PLAYER CARD PD X Y [DELAY]` and `replay-schedule-card OWNER CARD X Y TICK`.
  - `observe` and `observe-rich`: every object's owner, cardId, dataGlobalId, x/y in milli-tiles, hp, attackSequenceStage, projectiles and effects.
  - `status`, `attest`, `render on|off`.
  - The source is at `.../firstlight-source-28d66cc-phaseb/native_runner/probe/cr_replay_probe.cpp` (dispatcher around lines 6640–7640).
- **Prior launchers to copy:**
  - `scripts/start_local_reference.py`: offline boot, `adb root`, wifi and data off, iptables REJECT on the app UID, attest.
  - `scripts/collect_l1_rendered.py`: paused native-render capture with paired observe.
- **Base battle config:** `reports/strategy_council_20260928/live-loop/v4/base-config.json` (location 15000199, level 11).
- **Card coverage:** 121 of 122 cards exist in the 15.535 tables. **Ronin is missing**.
- **Locations:** 199 rows in locations.csv, 102 of them PvP. Ladder arenas start at index 2 (PvP_goblin), so location id = 15000000 + row.
- **Live geometry:**
  - Official frames are 1080x1920 Android px.
  - From `live/loop/canvas.py`: official = 1.806 × (renderer px / 2) + (51.5, −275.5).

### Mac baseline at 01:30Z

- Free disk 11 GiB; memory_pressure reports 44% free; swap 4.2 of 5.1 GB used; load average about 21.
- Live s11 `step_ms` (no emulator): p50 6.6–6.9 ms, p90 21.8–28.1 ms, max 81–103 ms.

### ADB ports

- adb server ports 5042, 5043, 5044 and 5047 are in use by others.
- Mine is **5049**. Planned consoles are **5596** (instance A) and **5598** (instance B).

## Next

1. Get the review GO on the script list.
2. Boot instance A and run the smoke test.
3. Calibrate.
4. Capture the first 10 cards.

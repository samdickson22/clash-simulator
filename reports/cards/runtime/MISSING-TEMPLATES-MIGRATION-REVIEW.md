# Independent host-script review brief — valid pilot08→04

Parent explicitly authorized moving ONLY valid queued pilot2967873 if still unadmitted; BOT LEAD measured04 room
live91+idle7+1=99≤105 at09:41:52Z. No B2 move/bypass. Existing protocol source1802 approved; script changes review first.

Review two new scripts, read-only (do not execute/touch hosts/edit):
- template_host_preflight.py 356f3a370cb48b97b66740a795f13b09df9f1826efc59e18c9b148e7563f1b1e:
  reads own candidate/source/runtime, checks exact approved7source manifest, Python executable hash/version,
  numpy/torch versions, full runtime, bot and reports/cards/tools file inventories (including pool.py) (including symlink file referents), native/data,
  Per-host *RECEIPT.json provenance is separately recorded; executable/data dependencies and full root inventory
  hashes remain explicit. Config-generating input hash (explicitly not emitted R.config hash), exclusive freshout. Directory/dangling symlinks failclosed.
- cancel_queued_template_pilot.py dae2223bfca9398b204966dcdb20052e1dffe6561ad95be761a615461f599ece:
  hardcoded exact owned queuedPID2967873, expectedUID/PGID/startticks/rawargvSHA captured before action,
  expected immutablecandidatepath/fulltargets/output argv. If Python or lease already present leave intact.
  Otherwise SIGSTOP exactgroup, wait allmembersstopped, revalidateidentity/groupUID/lease/Python tocloseadmissionrace;
  if admission won, SIGCONT and leaveintact. Else allowonly known cpu_room utilities thenTERMexactgroup,
  CONTtohandlependingTERM; confirm no livegroup/no lease before reporting superseded-for-scheduling.
  try/finally resumes any stoppedgroup onerror; no broadkill/rm. Preservealloldsource/logs/receipts.

Planned protocol (J=/mpac/sdicks02/jobs/clasher/cards/missing-templates-r3):
1. Read-only04preflight already confirmsownedJ/freshsource+outputs absent.08identitycurrentlysameowner3822945,
   PID=PGID2967873,startFriOct16 02:24:57,expectedargv,noPython/lease at09:40:32.
2. Ordinary source copy, nohardlinks, unchangedfrozeninput:
   ssh127x08 'nice -n15 tar -C J/class-checkpoint-1802e899c-source -cf - .' |
   ssh127x04 'mkdir J/class-checkpoint-1802e899c-source; nice -n15 tar -C J/class-checkpoint-1802e899c-source -xf -'
   (Freshdirchecked; set-e/pipefail oncoordinator; neverreusepartialcopy.)
   rsync ONLYpreflight/cancel scripts+approvedmanifest into ownfreshJ/migration-tools onbothhosts.
3. Read-only preflight helper on04/08 withnice15/python-B/one-thread env, outputownfreshJ/preflight-<host>.json.
   This is bounded file/metadata census, noRuntime/engine stepping. Compare dependencies_sha256,
   native/data/runtime/config-dependency/bot hashes and7source hashes exact; abortmigrationonANYmismatch.
4. Read08/proc PIDidentity (startticks/rawargvSHA) pluspsgroup/UID/start; preserveJSON inJ, runreviewedcancelguard
   nice15 systempython-B only if dependencyparitypassed. If admittedresult, no04job. If provenexited/nolease,
   queueexactreviewedpilot04 via unchangedcpu_job.sh1,nice15,source2dce, freshclass-1802e899c-pilot-04 paths.
5. Afteractual5/15 pilotPASS, fullreviewed4shards122/366 usingrun_object_templates.sh undercpu_job4.
   No simultaneous08+04 pilot/full. No publication/activepins implied.

Rollback: retained08source+logs canrequeueonlyifneeded afterverifyingnootherpilot; no roots/pins changed.
Need independent verdict/hashes and admissionrace correctness. No duplicated implementation review.

Coordination: missing info/routinequestions directparent T3auto, never userinputtools. Sam spam rule:
only action-needed/blocker/material result; default<=3shortlines/80words. Do not rebroadcast to existing children.
Record detailed commands/hashes in audit. This applies to any future/resumed descendants.

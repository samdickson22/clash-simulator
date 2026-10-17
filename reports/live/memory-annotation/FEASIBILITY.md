# Memory annotation for LIVE perception: feasibility (phase 0, read-only)

Owner: memory-annotation feasibility owner (Opus), for the LIVE LEAD. Direction: Sam 2026-10-17, annotation-only
(the play path stays screen-only). Every Mac fact below comes from read-only commands on 2026-10-17 ~21:50Z
(versions, listings, `ps`, `codesign -d`, `csrutil status`, key names in bluestacks.conf). No Mac writes, no adb, no SCK.

## Verdict

**GO, conditionally, for stage 0 (offline static work, no Mac contact) and for stage 1, which needs a planned pause.**
**NO-GO for the host-side route and for the AVD route.**
Stage 1 needs the LIVE LEAD to schedule a ladder-paused window and Sam's App-Management/admin approval for one write into `BlueStacks.app`.
The decision on production (stages 2–3) waits for the stage-1 proof and the side-by-side measurement.

## 1. Access

Mac today:
- macOS 27.0 (26A428), SIP **enabled**, M4 Pro, 12 cores, 24 GB RAM, 13 GiB free on the Data volume.
- BlueStacks Air 5.21.790 runs as a single host process, `BlueStacks`, with RSS ~2.6 GB.
- It is signed with the hardened runtime (flags=0x10000(runtime)). Its entitlements are hypervisor, camera and audio-input, with **no get-task-allow**.
- There is one instance, `Tiramisu64` (Android 13, arm64), with `enable_root_access="0"` and `bst.feature.rooting="0"`.
- The system image `Contents/img/Root.qcow2` (1.81 GB) is shared by every instance. Each instance has only its own `data.qcow2` (userdata, 7.1 GB).
- The "BlueStacks Air multi-instance manager.app" is installed.

| route | what changes vs stock | verdict |
|---|---|---|
| A. Root inside the guest (Air) | Air has no root toggle: the conf flags are Windows-era and community reports say the server overrides them. Root means patching the **shared** system image: either a `su` injected into `Root.qcow2` (RobThePCGuy BlueStacks-Root-GUI, GPL-3.0) or Magisk in `initrd_hvf.img` (paststrange/root-bluestacks-air, no licence). This breaks the bundle's code seal (an installed app still launches), applies to **all instances**, and is reverted by every BlueStacks update. It needs App-Management/admin approval to write into `/Applications/BlueStacks.app`. | **Pick.** Smallest effort, and the revert is a byte-exact restore of one file. Precedent: ClashAI ran a read-only reader on rooted MuMu, 16.402 build 160402012, on ladder for weeks, and its notes say "no disturbance: decide_ms and log cadence normal". |
| B. Host side (guest RAM via Hypervisor.framework is mapped into the `BlueStacks` process) | `task_for_pid` on a hardened, SIP-protected process is denied even to root. It needs SIP debug protection off (recoveryOS, physically present on Apple Silicon, a machine-wide security downgrade on a Mac shared with another user) or an ad-hoc re-sign of BlueStacks (also a bundle change, and it risks TCC grants). On top of that it needs guest VMI: page-table walk plus task list from `kernel_hvf` (a GKI kernel, BTF likely). | **No-go now.** The guest stays perfectly stock, but it costs a security downgrade plus Sam's physical action plus 4–6 extra days of VMI. Keep it as the fallback if the client rejects a rooted guest. |
| C. Separate rooted AVD (Google APIs, `adb root`) | Nothing changes on the live instance. | **No-go.** Client 160402017 already crashed at `nativeLoad` ("02") on both a Google-APIs AVD and a Google-Play AVD on 10-04 (`strategy_council_20260928/live-loop/l3/PROGRESS.md`). Getting past that would be evasion. |
| D. Second Air instance | Root is global (shared Root.qcow2), so it gives no isolation. A *fresh* instance needs a new Google sign-in, which is off-limits for us. A *clone* carries the same CR account, so it would kick the live session. | Gives no isolation. Use the live instance in **Training Camp during a planned ladder pause** (allowed by the brief). |

Inside the guest the reader is a static aarch64 binary run as root. It does `pread` on `/proc/<pid>/mem` of
`com.supercell.clashroyale` (no ptrace attach, so the game is never stopped) and writes NDJSON to stdout or a guest
spool, pulled to `~/clasher-live/annot/` (a new dir, outside `loop/`). Constraints:
- No Magisk modules, no DenyList/Zygisk/hiding.
- No writes to process memory: the binary opens the mem file `O_RDONLY`, and the Sol review checks for it.

## 2. Reuse or reverse-engineering; licence verdict

**ClashAI (vegetableleaf/ClashAI): reference only, no code or values reused.**
- There is **no LICENSE file in any of its 2,463 commits**, so the default is all rights reserved.
- Its owner deliberately purged the reader on 10-09: 65 files untracked (commits 5f1c1872/7526a02e, "owner: no usable reader in the public repo").
- The sampler binary is marked "not ours to redistribute".
- The upstream sources it was built on lived in git-ignored `research/ext/` "each with its own licence"; they are not in the clone and are unidentified.
- History was not rewritten, so the old sources are still reachable in git objects. **I did not open them, and nobody on our side should.** We respect the author's evident intent and keep our own work clean-room.
- The build differs anyway (theirs 160402012, ours 160402017, so libg offsets differ).
- What we take is only what their public docs say: it is feasible; the object model (root chain → battle → per-body list with an attack component, effects and projectiles); a 50 ms tick; read cost of a few % of a core; a validation method (coherent frames, tick monotonicity).

**Null's Royale 15.535 (ours) transfers well on *semantics*, not *offsets*:**
- The `observe-rich` field set (owner, cardId/dataGlobalId, x/y in milli-tiles, hp, attackSequenceStage, projectiles, effects) tells us what each object holds and what its value ranges are. That is the hard part of the RE.
- dgid → CSV-row mapping logic transfers; Supercell `.csv` tables from our own installed APK give names, costs, hitpoints by level and deploy times.
- Estimate: ~70–80% of field semantics transfer and 0% of addresses.

**Other upstream:** no licensed public 16.402 reader identified.

**Effort (own RE, arm64 libg 160402017), ~9–11 Opus-days:**
- Stage 0, static RE offline on 05: 3 d. Source is the APK, from a mirror with the Supercell cert checked, or from our own install later. Ghidra on libg, CSV loader and class strings, candidate layouts from the 15.535 probe.
- Stage 1, live validation in Training Camp: 2–3 d across 1–2 one-hour windows. Anchor scans on values we already read from the screen (tower HP numbers, our own deploy tile and time) to find the object list; then id, team, x/y, hp, level, state.
- Stage 2, measurement: 1–2 d, mostly battle wall-clock.
- Stage 3, label pipeline: 3 d.
- Maintenance: 1–2 d per client update. Locate structures by byte signatures rather than fixed RVAs; the reader fails closed (no labels) on a build mismatch.

## 3. Fields and time alignment

Per entity, every reader frame:
- frame-level: tick and frame coherence (tick read before and after);
- character/building data id (dgid) → card name and body class;
- the card that spawned it (SkeletonArmy vs Skeletons);
- team; x/y (milli-tiles); hp/max hp; level;
- deploy timer (cloud, not yet a body); attack stage; buffs (frozen, slowed, stun, rage, shield, invisible);
- evo/hero form;
- projectiles and spell areas.

Battle-level: both decks with levels (evaluation only).

Alignment to the ~10 Hz driver frames (`runs/<s>/mNN/frames.jsonl`, Mac clock):
1. Every reader frame carries the game tick plus the guest monotonic clock. A guest↔Mac offset is estimated per battle.
2. The offset is then fixed by events: our own taps (logged Mac time) vs the tick our body appears, and tower-HP drops (our on-tower reader) vs memory HP.
3. Fit offset + drift per battle. Target residual ≤ 1 capture frame. Battles whose residual is too large are dropped.

The reader samples at 20 Hz, so positions interpolate to the frame time.

**Labels are points, not boxes:**
- **Class/owner:** set by memory on the YOLO box whose ground point matches within 0.5 tile.
- **Misses** (memory body with no box): a card-size box prior plus Sol review, or a box refiner trained on Null's Sol-corrected boxes. Attack-stage frames are flagged for review, because Null's attacking boxes needed Sol fixes.
- **Visibility filter, mandatory:** drop bodies still deploying, invisible (Royal Ghost/Miner underground/Tesla hidden), or off-canvas, so that invisible state never becomes a positive label.

## 4. Risk to the ladder

| risk | mitigation |
|---|---|
| Image patch breaks BlueStacks or the client | Stage 1 only in a planned pause: back up `Root.qcow2` (1.8 GB; 13 GiB free) with sha256; smoke test = boot, CR launch, Training Camp battle; restore byte-exact plus `codesign --verify` on any failure. The rollback script is reviewed before the window. |
| Client integrity check/ban on root | Ban accepted (throwaway); no hiding. If the client refuses to start rooted, revert, and route B becomes the only option (Sam decides on SIP). |
| Broken bundle seal re-checked later (macOS update, Gatekeeper) → BlueStacks won't launch | Keep the stock image plus a restore script on the Mac; the babysitter checks the BlueStacks launch after any macOS update. |
| BlueStacks auto-update silently reverts root | Fail-closed: no labels, play unaffected; the reader logs a build/root mismatch. |
| Reader CPU/IO slows the bot | Measured A/B *with the bot playing* (stage 2): alternate reader ON/OFF by session, ≥ 6 battles per arm; metrics are tap→first-visible-deploy (s65 method, baseline ~80–90 ms), decision p95, driver fps, -3805 count, guest frame pacing. **Stop rule:** +10 ms tap→deploy or any fps drop. Expected cost is small (≤ ~1% of a guest core, ~0.1–0.4 MB/s). |
| Torn reads | Per-frame coherence check (tick before == after); incoherent frames dropped. |
| Leak into the play path | Rules and guard below. |
| Public repo | Reader source, offsets/signatures and binaries stay **private** (05 scratch, not git). Same reason ClashAI purged: no usable official-client reader in a public repo. Only the label schema, guard test and results are committed. |

Hard rules:
- The reader is a separate process.
- Output goes only to `~/clasher-live/annot/` and is copied to 05 for training/eval.
- No memory writes.
- No credentials, account settings, purchases or sign-in.

**Guard test** (`live/loop/tests/annotation_isolation_test.py`, joins `run_tests.sh`):
1. Static: AST-scan every module under `live/loop/` and `bot/live/` (and the deployed manifest). Fail on any import of the annotation package, or any string literal containing `annot/`, `memory-annotation` or the reader env var names.
2. Runtime: run the control_test fake-driver path under `sys.addaudithook`. Fail on any `open`/`os.listdir`/`subprocess` touching the annotation dir. Also check the fake environment has no reader env vars.
3. Manifest: `MANIFEST-*.json` must not list any annotation file.

## 5. Expected value

Today, x1h enemy troops are ~87% class+owner correct on fresh raw slices. Errors, in order:
1. misses, the biggest bucket (Hog at towers ~29%);
2. own-Bat ↔ enemy flips in defensive melees;
3. wrong-card pairs FireSpirits/Musketeer, SpearGoblins/Bats, SkeletonArmy/Skeletons.

| bucket | label-limited? | Null's exact labels + Sol | memory labels add |
|---|---|---|---|
| Misses at towers / in melees | Mostly yes: official occlusion/effects on official art, and the official labelled set is a few hundred frames | Partial: exact positions, but 15.535 art and private-server arenas | Thousands of official frames per hour of ladder at exactly these moments, real arenas at our trophy range |
| Team flips | Yes, an official-domain cue: badge/bar only on damaged units, otherwise sprite tint | Weak: 15.535 HUD art didn't transfer for team cues | Exact team on every body, every live badge colour, every arena |
| FireSpirits/Musketeer, SpearGoblins/Bats | Yes (visually distinct) | Yes | More volume, plus real opponents' evo/hero forms |
| SkeletonArmy/Skeletons | **No** (same sprite) | No | Spawn-card truth for play-level attribution and eval; the fix is sprite-level body classes plus temporal grouping |

**Estimate (low confidence):**
- Memory labels could take enemy-troop class+owner from ~87% to ~92–94%.
- Null's + Sol alone: ~89–90%.
- Gain comes mostly from misses and team flips on official art.

**A second gain, probably the larger one: exact truth for every ladder battle.** The play-level gate (d), opponent play detection, cycle guard and translator could all be scored on unlimited fresh windows without Sol video audits:
- this addresses the "unit gate pass ≠ play-level pass" problem and the play-gate noise floor;
- opponent decks and levels serve evaluation only.

**Cheap pre-check, run in parallel with no Mac contact:** a label-scaling probe. Fine-tune x1h with +100/+300 extra Sol-labelled fresh official frames on the error classes. If gain keeps rising with labels, the memory channel's ~100× volume is worth it; if it saturates, the value is mostly the eval channel.

## Staged plan

0. **Offline static RE** (05, no Mac): APK 160402017 (cert-checked) → libg/CSV; candidate layouts; reader + rollback scripts written; ONE Sol review (gpt-6.1-sol, high).
1. **Offline proof** (planned ladder pause, LIVE LEAD's go, Sam approves the bundle write):
   - back up and patch `Root.qcow2`, then smoke-test;
   - Training Camp: validate fields against video (≥ 2 battles, ≥ 95% of visible bodies matched with the right id/team, tick coherence ≥ 99%);
   - restore stock before the ladder resumes unless the LEAD approves leaving it rooted.
2. **Measured side-by-side with the live bot:** reader ON/OFF alternating sessions, ≥ 6 battles per arm, metrics and stop rule as in §4. Abort means restore stock.
3. **Label pipeline:**
   - reader frames → alignment → visibility filter → class/owner on YOLO boxes plus box-prior misses;
   - Sol review on attack/occluded flags;
   - output in r3's label format (EVAL-SPLIT held-out discipline: split by battle, a fresh slice held out);
   - the guard test lands **before** the first reader run on the ladder.

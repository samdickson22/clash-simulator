# K4S END B3: open questions for the coordinator (CANDIDATE b3-r4)

**r4b status (2026-10-12, `b3-r4b/`):** E5 is **implemented through the layer** (safe_input r3 `806e5ebb…`): S4 keeps no E5 list; the nine `si.E5_RUNTIME_MEMBERS` are accepted in the runtime (hash only, pinned blob OID, must equal the committed HEAD entry by metadata) and every other family-named member still refuses. The §r4 item "E5 — … production list EMPTY (blocking for production)" is therefore closed for S4, pending Sol review of safe_input r3 and of b3-r4b. Still open from §r4: the full-clone ruling (S4 must use the runner-owned full clone as `--repository`; safe_input r3 does not yet refuse a promisor clone) and an explicit E4 OID ratification line.


Offline, written 2026-10-12 (after 15:26Z); r2 status notes added after 16:00Z; r3 status notes added at 17:17Z; r4 status (safe_input adoption) added after 21:28Z. The r4 items are at the END (§r4); earlier text is kept as written.

**r4 status (summary; details in §r4):**
- Ruled and implemented: E1 materialised (D2), E2/E4 through the layer's pinned SHAs and blob OIDs, E3 (unchanged), R6 (strict END pair refused by the shared denylist), R7 (plain single-link copies), P2-4 (every git call through `si.git_run`; whole-tree metadata before blobs).
- **Open (blocking for a production assembly at origin/main):** E5. The coordinator ruled exact path + blob OID exemptions for nine runtime members (21:28Z). The S4 hook exists, but its production list is EMPTY by design in this round; the values must be recorded (preferably in the shared layer, so S9/S10/S4 honour one list) before S4 can hash a runtime that contains those nine names.
- Acknowledge: the two r4 behaviour changes (guard-job freshness is host-side only; a failed write keeps its `.partial` stage).

**r3 status:**
- R1–R3 are ruled by E3/E1–E2 (COORDINATOR `2026-10-12 16:55Z`, ab1715910) and implemented exactly; see each item.
- R4 and R5 have Sol's support (r2 review) but no coordinator ruling yet.
- New: R6 (blocking for production assembly) and R7.

 **r2 status:** Q1 ruled in 7270b5fa (completion-v2 of record); Q2–Q6 and Q9 ruled in fa89baa9 (15:41Z); the assembler now enforces the Q2/Q4/Q6 rulings (DESIGN §C.3). New r2 items are R1–R5 at the end. Section references are to `DESIGN.md`. Items marked **blocking** must be ruled on or resolved before any K4S END bundle can be assembled or any END attempt claimed.

## Q1. Which completion is of record (B1: v1 or v2)? (blocking for the evidence, and so for the bundle)

**r2: RULED (7270b5fa): completion-v2 is of record.**

- The bundle pins the committed END evidence. The evidence binds the completion, and the completion binds the counted inventory.
- The frozen `end_evidence.counting` refuses the v1 inventory `f10ab943` (schema and keys; plan draft §0 B1).
- The candidate is `run-r1/completion-v2/`: inventory `22c41cb7…`, completion `3794d953…`, with the same 3,900 rows.
- **Ruling needed:** adopt completion-v2, under a Sol review of its re-emitter, before the evidence (B4) is built and committed.
- **Downstream:** PC4 and the release receipt item 1 must name the same completion.
- The assembler is agnostic here: it copies whatever the committed evidence pins.

## Q2. Admission sources on each host (blocking)

**r2: RULED (fa89baa9): latest K4S `system-bus-admission.json` per host + `idle-services.json` on 03, fetched by the reviewed exact-path reader and committed outcome-blind before the END-JOB. Enforced: `--committed-admission` (DESIGN §C.3).**

- **Which existing K4S job's `system-bus-admission.json` does each END guard job copy?**
  - Candidates: the reporting job or the latest `k4s-confirm-replacement-r4` job on that host. Their bytes differ, because of `utc`.
  - Live identities at r4 (14:04Z): 03 PID 2049 / start_ticks 1273; 04 PID 2005 / start_ticks 1032.
  - Not committed anywhere. It needs a reviewed, exact-path name listing and copy, with nothing globbed.
- **03 `idle-services.json`** (perception v4 cache, PID 2180947): pin it in the END guard job, as recommended?
  - If it is pinned and the service exits during END, idle `retired` fails the attempt.
  - If it is not pinned, the service's process tree is foreign compute (T1 `host_audit.foreign_compute`), so pinning looks required while it runs. **Inference.**
- **Recommendation:** commit both hosts' admission copies, outcome-blind, before the END-JOB, as T1 did (`t1/receipts/system-bus-admission-127x0N.json`). The bundle's SHAs are then reviewable.

## Q3. Where `admit()` runs `git show` (blocking risk; new)

**r2: RULED (fa89baa9): Option A, a K4S-owned git clone with b2f9e25e and ce042b97; preflight `git cat-file -e` first (S3/S5, not S4).**

- T1's freeze makes `parent_source_seed.admit` run `git show b2f9e25e…:…127x03.json` and `git show ce042b97…:…127x08.json` on both 03 and 04, at the admission checkpoint. That is after the claim, so a failure there **burns an attempt**.
- K4S reporting never ran this path, because FROZEN-K4S has no seeds.
- **Ruling needed: Option A or Option B** (DESIGN §A.4).
  - **A (recommended):** `job/repo` is a K4S-owned git clone that contains both commits, with the four seed paths checked out.
  - **B:** keep the T1 precedent, a plain `job/repo` that relies on the host's `/mpac/sdicks02/repos/clasher`. That checkout is unverified on 03/04 and may be shared or owned by another thread.
- Either way, the reviewed on-host preflight (DESIGN §A.6, item 5) must run the frozen `committed_binding` for both bindings first.

## Q4. Guard-job namespace and lifetime

**r2: RULED (fa89baa9): one fresh guard job per attempt at the proposed namespaces. Enforced: mandatory `-rdRR-aNN`/`-pfNN` suffix and non-existence at assembly (see R4).**

- **Proposed** (enforced by the assembler):
  - 03: `/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rdRR-aNN`
  - 04: `/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-rdRR-aNN`
- These are never T1 directories, K4S reporting jobs, `repos/clasher-v4-cache`, or 04's `/mpac/sdicks02/jobs/clasher/` perception root.
- **Approve the per-attempt fresh guard job?** This is the T1 precedent, and it implies a per-attempt bundle, since `guard.job` is in the manifest. The alternative is one job per host per round.
- **Confirm that 04's `/mpac/sdicks02/jobs-k4s/` is K4S-owned and acceptable for END.** The plan draft used it for `$J` on 04.

## Q5. The END runtime tree (blocking; new)

**r2: RULED (fa89baa9): runtime at the END-JOB commit; the 33 from SHA-matched bytes already on 05 only; same tree to 03 and 04.**

- A plain git export at any commit ≥ 133f3ae4 fails the frozen `runtime_pins` rule. 33 files named by `reports/explore/s1/receipts/runtime-pin-r2.json` are not in git (DESIGN §E): `imitation/*`, `student-source/exit_r3/*`, seven `src/clasher/analysis/loss_review/*`, four JSON support files, and eight tests.
- **Ruling needed:** where these come from. Candidates:
  - T1's END runtime lineage on 01/08 (3,785 files);
  - the K4S reporting runtime overlay;
  - the S1 runtime-pin / external-runtime-provenance bytes (`t1/receipts/external-runtime-provenance-0108.json`).
- The same runtime tree must be **byte-identical on 03 and 04**, because the canonical `runtime_files` SHA is a shared pin. `measurement_files` is fixed at `42b8986d…`.
- **Which commit** is the runtime: the END-JOB commit, or the evidence commit? (Plan draft §8 Q4.)

## Q6. Model, state and set inputs for the bundle

**r2: RULED (fa89baa9): T1's byte-exact copies on 05. Enforced as production pins (verified sha256 of the pool-context copies on 05).**

- **Reuse T1's `states.pkl` `0addf7c0`, `states-rows.json` `bcd30777`, `states-rows.bin` `8cc2f611` and T1's own-tier `sets` (golden 125; speed 4×300) from `END-A3-manifest-*-f6cebbaa.json`?**
  - These are the background-slot corpus (the reporting load profile), not the K4S timed corpus, which is K4-states `a97b1fbf`, already staged at `$J/end-corpus/`.
  - The bytes are on T1 storage (01/08) only. They need a coordinator-authorized, SHA-verified, read-only copy to 03 and 04, as was done for the corpus.
  - **Note:** T1 marked `0addf7c0` as "authoritative bytes only on host; 05 reserialized a7… NOT substitute" (`END-A5-CANDIDATE-offline-preparation-20261012T0439Z.json`). The copy must be the original bytes, not a re-serialization.
- **Source of `v1.pt`, `R3a.pt` and `R3a-calibration.json` on 03/04** (frozen `d77005d5`, `37509a43`, `e3003533`). Not verified.

## Q7. Telemetry files `mhz.jsonl` / `census.jsonl` (B2; blocking for the evidence)

- Twenty files are needed (10 phases × 2) and are not yet copied or committed.
- They need a reviewed exact-path copier, never a glob: the phase directories also hold block folders.
- The copied blobs must then be committed, because the evidence items require `git show` equality and ancestry.
- The size (possibly 40–60 MB per `mhz.jsonl`) is an inference.

## Q8. The END evidence's location (constraint on the B4 builder)

- Artifact paths cannot contain `..` (`fleet_end.py:13-17`), so the committed evidence must sit at or above every artifact. With `plan.json` at `reports/explore/k4s-confirm/plan.json`, that means `reports/explore/k4s-confirm/<name>.json` or higher, and not under `…/end/`.
- **Confirm the name and path,** and that `--end-evidence` points at the bundle copy `<bundle>/k4s-end-evidence/end-evidence.json` (DESIGN §B.3).

## Q9. Disclosure: END runs T1's guard semantics, not K4S's reporting guard

**r2: RULED (fa89baa9): disclosed in plan v2.**

- Five of the nine guard modules differ between T1 and K4S (DESIGN §A.2).
- In particular, during END there is no apt-helper classification and SSH-family CPU uses T1's older accounting.
- Should the END disclosure state this explicitly? The frozen `fleet_validity` cannot use the K4S modules, so there is no alternative without a TIERS-side amendment.

## Q10. Review scope

- This candidate needs a **Sol review** of `assemble_fleet_reference.py` and its tests, plus a review of DESIGN §A (the guard-job construction), before any use.
- The on-host preflight (DESIGN §A.6) and any guard-job staging or admission-copy script **touch hosts**, so each needs its own review before running (memory rule). Neither was written here.

## r2 items (new)

### R1. Committed admission location (needed by S1/S3 and the Q2 commit)
**r3: RULED (E3, ab1715910): `reports/explore/k4s-confirm/end-guard-admissions/<host>-<name>.json`. Enforced as an exact path:**
- `127x03-system-bus-admission.json`;
- `127x03-idle-services.json`;
- `127x04-system-bus-admission.json`.

Any other path is refused.
- r2 text: the assembler required each Q2 copy at a repository path under `reports/explore/k4s-confirm/` (not `end/`), ending `.json` and containing the host name, e.g. `reports/explore/k4s-confirm/end-guard-admissions/127x03-system-bus-admission.json`. **Confirm or name the path** the exact-path reader will commit to.

### R2. One outcome-named runtime file is hashed (acknowledge)
**r3: RULED (E1 + E2, ab1715910).**
- **E2:** exempt only at that exact path and with SHA `d1492d0f…`. The exemption is a code constant, and test mode can substitute only the SHA. The file is hashed once and never parsed (both tested). Every other `complete.json` is refused.
- **E1:** `visualize_battle.py` is exempt only as the committed mode-120000 entry of `--repository` HEAD, with link text `examples/visualize_battle.py` (checked through git). It is never opened as an alias. Its target passes the confined walk and the hard-link gate.
- r2 text follows.
- The frozen runtime membership rule (S1 `runtime-pin-r2.json`) requires `imitation/model/receipts/throughput-0935/complete.json`, an imitation throughput receipt, not a K4S/T1 block. It is the only `complete.json` the assembler will open: by exact path, never parsed, bound to SHA `d1492d0f…` from T1's A3 manifests (the frozen `validate_bundle` hashes it on the host anyway). Every other outcome-named entry refuses.

### R3. Pinned admission identities may go stale
**r3: RULED (E3, ab1715910): pinned from r4; stale identities are refused.** The refusal message names the required coordinator re-pin ruling, which must be made from fresh outcome-blind admission copies. The assembler has no override.
- r2 text: bus 03 PID 2049 / start_ticks 1273, 04 PID 2005 / 1032; idle on 03: PID 2180947 / start_ticks 139691386 (r4 committed evidence). If a host reboots or the cache service restarts before END, the committed Q2 copies and these pins both need a new ruling; the assembler refuses until then.

### R4. Preflight guard-job name
*(r3: Sol supports it (r2 review); no coordinator ruling yet. S3 must still enforce distinct host jobs per preflight and attempt: 05's `lexists(job)` cannot prove nonexistence on 03/04.)*
- r2 accepts `k4s-end-guard-r<N>-pf<NN>` for the S5 preflight's own fresh job (plan v2 S5), besides the per-attempt `-rd<RR>-a<NN>`. **Confirm the `-pfNN` form.**

### R5. Topology pin
*(r3: Sol supports it as an offline reference (r2 review), conditional on the live S5 `validate_topology` before any claim. No coordinator ruling yet.)*
- Pinned to T1's value (P = 0..127, E = []). S4 cannot observe 03/04; the S5 preflight's live `validate_topology` is the binding check and must run before any claim.

## r3 items (new)

### R6. The runtime tree given to S4 must exclude the strict END namespace (blocking for production assembly; acknowledge)
- r3 refuses any runtime tree that contains `reports/explore/k4s-confirm/end/`, without listing it. The review requires the strict END namespace to be rejected for every runtime inventory member, so the alternatives were to list it or to skip it silently.
- The runbook runs `end_reference.py --runtime-root R … --repository R`. The END-JOB is committed at `reports/explore/k4s-confirm/end/END-JOB.json` before the first attempt, so a plain checkout at the END-JOB commit **will** contain the namespace.
- **Proposal:** the staged runtime that S4 hashes (Q5: END-JOB commit plus the 33 external files) is staged with `reports/explore/k4s-confirm/end/` excluded.
  - By the runbook rule, that namespace holds only JSON, so membership under the frozen `rglob('*.py')` rule is unchanged. This is an **inference**.
  - Host side (verified in code at fa32ab3f): `end_reference` calls `validate_bundle` pre-claim (`end_reference.py:101, :294`). That reaches `receipts.verify_files(root, manifest["runtime_files"])` (`tier_backend.py:457`; `receipts.py:22-33`), which hashes only the **listed** names.
    - It does not recompute membership, so files present only on the host, including the host's END namespace, are not hashed there.
    - Excluding the namespace from S4's tree therefore has no host-side effect. It matters only for parity with the frozen `prepare_bundle.runtime_pins` rule, which is the inference above.
- **Needs:** coordinator acknowledgement, and an S3/staging step that copies the runtime without that directory, as plain single-link copies (R7).

### R7. Every input must be a single-link regular file (acknowledge)
- r3 refuses `st_nlink != 1` for every input, in the walk and at the descriptor gate. Staging must use plain copies, never `cp -l`, `cp -al`, `ln` or hard-link-based rsync options.
- Verified: the three Q6 copies on 05 (`end-a5-pool-context-20261012-r1/bundle/`) have `st_nlink == 1`.
- Unverified until they exist: the runtime tree, the committed evidence and its artifacts, and the committed admissions. Git work-tree files are normally single-link; local `git clone` hard-links objects, not work-tree files.

## r4 items (safe_input adoption; rulings P2-1..P2-4, D1–D4, E1–E5)

### E1 (D2: materialised) — implemented
- Committed: `--repository` HEAD must carry exactly the mode-120000 entry `visualize_battle.py` with blob OID `a79f7391…` (= sha1 of the 28-byte link text `examples/visualize_battle.py`), screened in `si.git_plan` phase 1; the link blob is read with `cat-file` and never followed; its target must be a screened regular blob.
- Shipped: the runtime's `visualize_battle.py` must be a REGULAR single-link file whose bytes equal that target blob (`plan.e1_verify_shipped`). Any runtime symlink, including one with the exact link text, now refuses (r3 accepted the link). This matches T1's END runtime convention and S9's D2 export.

### E2/E4 — implemented through the layer
- The four paths, SHA-256s and git blob OIDs are `si.E4_COMPLETE_JSON` / `si.E4_GIT_BLOB_OIDS` (single source; S4 keeps no copy; production re-checks the layer fingerprint). Phase 1 refuses any other `complete.json` component and any E4 entry whose mode/type/OID differs, before any object read. The OIDs were matched to the ruled SHAs by the runner (`safe-input-r2/RUNNER-E4-OID-RATIFICATION.txt`, 21:27Z) and noted in the coordinator's 21:28Z entry; an explicit ratification line is still worth recording.

### E3 — unchanged
- Exact path `reports/explore/k4s-confirm/end-guard-admissions/<host>-<name>`, pinned identities, stale identity refused with the re-pin message.

### E5 — ruled 21:28Z; S4 hook present, production list EMPTY (blocking for production)
- **Ruling (21:28Z):** nine runtime members match the outcome-name family denylist only by name (8 `*games*.py` sources and `tests/fixtures/native_friendly_completed_15_535_86.json`); they are exempt at exact path + blob OID, copied byte-exact, hashed, never parsed; the family pattern is not narrowed.
- **S4 now:** `E5_RUNTIME_EXEMPT = {}` and `PRODUCTION_PINS["e5_runtime_exempt"] = {}`. A production run on a runtime containing any of the nine refuses in the runtime walk (`[name]`). Only synthetic pins can name entries; with entries, the walk exempts exactly those paths from the outcome FAMILY rule (ancestors still gated; regular, single-link; git blob OID of the gated bytes must equal the entry; hashed, never parsed; must be a runtime member). Tests: refusal with the empty list, acceptance of an exact entry, wrong OID, hard link, symlink, neighbouring name, non-member, invalid entries (E4 path, END claim, strict END pair, non-family name, bad OID, unsafe path), production constant fixed.
- **Needed:** record the nine `(path, blob OID)` values. Recommendation: add them to the shared layer (safe_input r3: an exact, fingerprinted E5 map honoured by `walk_tree`, `git_plan`, `remote_receive`), then S4 takes the map from the layer and `walk_runtime_e5()` is deleted. Recording them only in S4 would leave S9 (export) and S10 (receive) refusing the same names.

### D1 — S4 side
- S4 hashes the runtime that S9 exports (D1: members only). Any non-member family-named file present in the runtime refuses the whole walk (no pruning). S4's own committed reads are D1-style: `git_plan` members are exactly the paths S4 reads; non-member blobs (e.g. `games/`, `hub-ack.returned.json`) are never requested (tested).

### D2 — implemented (E1 above). D3 — not S4 (S6 only). D4 — not S4 (S10).

### Full clone (21:28Z)
- S4 needs every planned blob locally (transports are off; a promisor clone's missing blob refuses instead of being fetched). Use the runner-owned full clone (`end-prep/repo-full`, checked out at the evidence commit) as `--repository` for a production assembly.

### Frozen-reader interim (21:28Z)
- Not applicable to S4: the assembler runs no frozen code that spawns git (frozen consumers run in tests as separate interpreters, and on the host under S5/S7).

### r4 behaviour changes (acknowledge)
1. **Guard-job freshness is host-side only.** r3 called `os.path.lexists(job)` on 05 for a path on 03/04; that probe could not establish freshness and is removed. S4 now checks the job's form, parent and name (remote policy for the target host, exact `guard-job` grant), with no local filesystem access to it. S3 creates the job exclusively; S5/S7 must check it is fresh on the host.
2. **A failed write keeps its `.partial` stage.** The layer never deletes. The stage is exclusive and never published; a later run refuses until an authorized step removes it (r3 removed its own partial).
3. **Stricter reads:** the S1 runtime pin and qualified binding are pinned (`f81f3655…`, `56b67dd4…`; r3 read them unpinned and fell back to `runtime-pin.json`); every JSON input is parsed strictly (duplicate keys, NaN/Infinity refused).

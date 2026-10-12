# K4S END B3: open questions for the coordinator (CANDIDATE b3-r2)

Offline, written 2026-10-12 (after 15:26Z); r2 status notes added after 16:00Z. **r2 status:** Q1 ruled in 7270b5fa (completion-v2 of record); Q2–Q6 and Q9 ruled in fa89baa9 (15:41Z); the assembler now enforces the Q2/Q4/Q6 rulings (DESIGN §C.3). New r2 items are R1–R5 at the end. Section references are to `DESIGN.md`. Items marked **blocking** must be ruled on or resolved before any K4S END bundle can be assembled or any END attempt claimed.

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
- The assembler requires each Q2 copy at a repository path under `reports/explore/k4s-confirm/` (not `end/`), ending `.json` and containing the host name, e.g. `reports/explore/k4s-confirm/end-guard-admissions/127x03-system-bus-admission.json`. **Confirm or name the path** the exact-path reader will commit to.

### R2. One outcome-named runtime file is hashed (acknowledge)
- The frozen runtime membership rule (S1 `runtime-pin-r2.json`) requires `imitation/model/receipts/throughput-0935/complete.json`, an imitation throughput receipt, not a K4S/T1 block. It is the only `complete.json` the assembler will open: by exact path, never parsed, bound to SHA `d1492d0f…` from T1's A3 manifests (the frozen `validate_bundle` hashes it on the host anyway). Every other outcome-named entry refuses.

### R3. Pinned admission identities may go stale
- Bus: 03 PID 2049 / start_ticks 1273, 04 PID 2005 / 1032; idle on 03: PID 2180947 / start_ticks 139691386 (r4 committed evidence). If a host reboots or the cache service restarts before END, the committed Q2 copies and these pins both need a new ruling; the assembler refuses until then.

### R4. Preflight guard-job name
- r2 accepts `k4s-end-guard-r<N>-pf<NN>` for the S5 preflight's own fresh job (plan v2 S5), besides the per-attempt `-rd<RR>-a<NN>`. **Confirm the `-pfNN` form.**

### R5. Topology pin
- Pinned to T1's value (P = 0..127, E = []). S4 cannot observe 03/04; the S5 preflight's live `validate_topology` is the binding check and must run before any claim.

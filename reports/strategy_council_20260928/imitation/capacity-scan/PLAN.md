# Human-prior capacity scan — frozen exploration plan

Freeze before fitting, 2026-10-09. Coordinator 0523ae6f-baa3-4d4e-b233-b392671670db.
Plan (h), §3 and B5; B5 commits39b6adf6/f98d8926 read. This is an exploration
lane: no reporting-data tuning, no held-out eval/eval_ood access, no strength claim.

## Question and arms

Does increased width improve full-human-dev natural joint NLL enough to warrant
an **offline** teacher, proposer or distillation source? Widths288/384/480 versus
192. Coordinator replaced512 with480 before freezing, preserving six heads.
Four transformer layers, six heads, FFN4×width; all other architecture fields
remain the T11 defaults. Frozen T11 trainer and imported sources stay byte-identical.
B5 live budget p99≤15ms:19214.92ms passes;28817.98ms and38427.55ms fail;
76890.30ms.480is offline-only by prospective restriction; no live adoption.

## Data, recipe and matched control

Qualified v2 human train/dev store, T11 manifest SHA
`a4801df32d4a546ed7df07faf070a138d4075cf4db6c193d38373f9194ff2e44`; root store SHA
`7180964c1d470807a97ad7a990ac8eb145fb25d15f1c95edf165b3f87743d20f`.
LANcopies from04qualifiedstore (or09only when its receipt passes), with every
train/dev array and parent public mask SHAverified. No evaluation roles copied.
Frozen T11 sampler: seed2026100821, six epochs; original wait thinning/IPW,
all plays/abilities; exact ascending candidates, hash rule and PCG64shuffle.
8192effective batch, AdamWlr3e-4/weight-decay.05, warmup2000then cosine,
clip1.0, bf16, dropout.1, EMA.999, patience3, checkpoint every1000steps.
Microbatch2048for wide arms versus control's historical7168: exact effective-batch
loss denominators are unchanged; this memory accommodation can change floating-point
rounding and dropout draws. Four bounded loader workers, same ordered batches;
original CLI workers1retained. No throughput-driven scientific recipe adjustment.

Reuse seed21's complete192curve (380,571,633rows) and checkpointstep11000
SHA`ca26a92e1c26509c229bff3035ff4e84cd56c09b7f9631d450e5a748cd34a2de`; clone/replay only the missing quarter point
on16, without modifying original files. Exact optimizer/scheduler/RNG resume,
same data/recipe; replay uses original7168microbatch. Total cosine schedule is
6×ceil(epoch0rows/8192), matching T11 rather than a shortened schedule.

## Frozen decision and reporting

25%target=ceil(380571633/4)=95,142,909rows. First completed effective batch
at/above target is **step11615,95,144,680rows**, shared by all arms. At that
point save a full checkpoint, compute EMAfull-dev NLL on all11,776,480rows,
and restore training mode and every RNGstate after the extra measurement.
Gain=NLL192−NLLwide. **Stop if gain<0.005**; equality survives. No early
result-based changes. Arm waits at the boundary until exact-rowcontrol exists.
Control replay ends there; its already-completed six-point curve supplies all
later exactlymatched controls. Every surviving arm completes its T11schedule
and reports all epochpoints plus the quarterpoint, including disappointing ones.
Report row counts, gains, kills, loader-inclusive rows/s and wall GPU-hours.
No best-arm hyperparameter tuning or reporting-split selection of a live policy.

## Resource contract and censoring

13→288,14→384,15→480;16→short192controlreplay. Onearm/GPU. All launches
setsid/nice≥10; caches/outputunder/mpac/clasher-owned trees only. Per leasedhost
≤16totalClasherprocesses, PSS≤48,000,000,000bytes, ≥8192MiBGPUfree. Check lease,
refusal/reclaim, expiry and console status beforelaunch and throughout. No CPU-heavy
sims, no08, noMac, no05heavywork, no roader reads/writes, no tailscale/crontab,
no broadpkill. Student fits01/04/09havepriority; copyworkercoordination required.
OwnedSTOPfile supports preemption; preserve artifacts/checkpoints. Hard stop
2026-10-11T03:30Z (two hours before leaseexpiry), reclaim drain≤30min.
Aggregate fitting/scoringwall ceiling40GPU-hours. If surviving arms cannot finish
within compute/lease constraints, checkpoint and mark resource-censored; never
claim a scientific kill or a full curve for a censored arm. No weights enter git.

## Config and source SHA256 pins

- Width 192: `a6963c7efe6668271e72bd49df24ba65e7fa2e649a7f399033ccac9977a2ec85`
- Width 288: `ad20c4cb9e76d23067b0866bdeba44b907c116b06feeee77c7825212935e66a2`
- Width 384: `1e24eae893b29731efeb5ae1dd30f401b889dbb24562329b923ff7115a6e0406`
- Width 480: `52a168b92d30e5850fe505b23227ce60207c8f003cdbeec0e3f83b8a497f4151`

Adapter SHA`56d132b3633df6ea6fdbe063bfe832417fef39ddc445bf93aab680a2c15ae7bd`. `freeze.json` binds source manifest,
configs, row boundary, controlcheckpoint, hosts and resource ceilings. This PLAN,
configs, adapter and freeze are committed/pushed **before first fitting**.
Operational scripts may be repaired only with receipts and no recipechanges.
Commit onlycapacity-scanownedpaths afterclasher-secret-scan; push and relay SHA.

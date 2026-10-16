# Play-detector dataset jobs

Run bulk generation **only on 127x03 under the LIVE LEAD's CPU lease**. This
package does not acquire a lease or launch a pool. Each command runs one process,
sets BLAS/Torch to one thread, and uses `nice -n 19`. Wrap each invocation below
with the supplied `cpu_job.sh`; let that wrapper assign cores. Do not copy the
05 smoke affinity (cores 6–7) to a bulk job.

From the synced checkout `/mpac/sdicks02/repos/clasher-live` on 03, with the pinned
runtime available at `/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1` (or set
`CLASHER_BOT_RUNTIME` and the matching `CLASHER_BOT_RUNTIME_PINS` explicitly):

```bash
cd /mpac/sdicks02/repos/clasher-live
bash bot/live/playdet/jobs/commands.sh /mpac/sdicks02/jobs/clasher/playdet-r1 16
```

This **prints**, without executing, all 48 independent invocations: 16 shards
each of train, validation, and sim. Examples (repeat with shard 1/16 … 15/16):

```bash
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -m bot.live.playdet.build --source t1-train --shard 0/16 --threads 1 --out /mpac/sdicks02/jobs/clasher/playdet-r1/t1-train
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -m bot.live.playdet.build --source t1-validation --shard 0/16 --threads 1 --out /mpac/sdicks02/jobs/clasher/playdet-r1/t1-validation
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -m bot.live.playdet.build --source sim --shard 0/16 --threads 1 --out /mpac/sdicks02/jobs/clasher/playdet-r1/sim
```

Defaults: all 1920 train or 240 validation matches, 2000 sim matches, sim seed
bank 2718281828+j, sim pool `v1,scripted-pressure`, maximum 6001 sim ticks.
The instance-local stepping wrapper additionally attempts legal champion
abilities once every 20 ticks from tick 90, recording accepted commands and
exact engine hidden-to-visible transitions. `--no-abilities` retains the
stock card-only play_match loop.
T1 uses each recording's registered seed and full recorded duration. To change
the bot pool: `--players v1-greedy,scripted-defense` (or other existing pool
names). Decks use the human catalog/X4S plus deterministic spawner, champion,
Golem and swarm coverage. Exactly one champion per sampled deck.

Use separate output roots for experiments (`--seed`, `--perfect`, `--players`,
`--max-ticks`); configuration mismatches refuse to resume. Never mix train and
validation directories for training. `--perfect` bypasses empirical and augment
noise; every ordinary run also retains `perfect_units` for all sampled frames.

Re-run the same commands to resume. Complete gzip files are checksum-checked,
structurally validated and skipped. Temporary files never count as finished.
An interrupted rename/manifest update is recovered by validating the finished
file and adding its checksum to the manifest. Each shard has its own advisory
lock and atomic manifest; match writes use fsync and atomic replace. One shard
topology per output root: do not run overlapping jobs with different N.

On **05**, only the bounded smoke suite is permitted:

```bash
PLAYDET_SMOKE=1 PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 taskset -c 6-7 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -m pytest -q -s bot/live/playdet/test_build.py
```

It builds two full train recordings and one full sim game, plus two 250-tick
sim prefixes to verify byte determinism and perfect mode. It also replays noise
determinism and a perfect-unit UnitTracker sanity check. Regular pytest omits
the integration fixture. Single CLI
smoke: add `--limit 1`; `--max-ticks 500` truncates deliberately and must use a
separate root from full data.

## Files and schema

`MATCH_ID.jsonl.gz` has deterministic gzip metadata (`mtime=0`, no filename),
sorted JSON keys, and three row types:

* `header`: schema `clasher.live.playdet.v1`, match/source/seed, decks, accepted
  `truth_deployments` (index, owner, card, tick, x, y, is_spell), per-match `noise`,
  `origins`, split SHA for T1, source limitations, deterministic sim result;
  sim `ability_commands` and `origin_events`; generation settings and code/stats
  SHA256s plus runtime pins. Resume rejects artifacts from another generator.
* `frame`: tick; `units` as `[label,owner,x,y,score,spawn_card_or_null]`;
  parallel `true_uid` and `false_positive` arrays; class-only `unknown_units`
  objects (including true_uid); towers (alive/hp_frac); frame_dropped;
  `perfect_units` dictionaries with source-card identity and true_uid.
* `summary`: frame/detection totals and `origin_counts` by exactness/kind.

`origins` has one row for every perfect unit ID encountered, including unsampled
sim births: uid, deployment_index (nullable), kind/origin, source_card, owner,
parent_uid, first_tick, exact, is_building, is_deployment. Each frame's perfect
units join this header. Main bodies have their accepted deployment index;
production/death descendants inherit that root index and have a body parent.
An ability return keeps its stable uid and original birth row (`main`); its
separate header `origin_events` row has kind/origin `ability`. Perfect units
within five ticks of that return carry `origin_kind='ability'` and
`origin_event_index` into the header. This covers reappearances without falsely
inventing a new unit ID or changing the original deployment truth.
False positives have null true_uid and `false_positive=true`. Unknown buildings
retain true_uid. No spatial matching assigns detection IDs after noise.

All coordinates are seat-0 bottom/our frame, x in 0…18, y in 0…32, ticks at 20 Hz.
Sim frames alternate 2/3 ticks (8 FPS). Native T1 frames are irregular: select
at most one per alternating 2/3-tick bucket; keep actual recorded ticks, never
interpolate or repeat snapshots to claim a higher native capture rate.

Noise parameters are sampled once per match: empirical strength (recall,
jitter/hp and FP rate); empirical card confusion; independent sampled family
and rare cross-family flips; per-UID 5–40 tick dropout bursts; whole-frame drop
p in .02–.04; building class-only augmentation enabled with p=.3; per-deployment
provenance probability with 1–2 initial visible frames. Empirical Markov dropout
uses the existing implementation's body-position association; burst dropout
and provenance explicitly use true IDs/deployment IDs. Provenance applies only
to main bodies, not children. Whole-frame drops have empty units/unknown_units
but retain tower telemetry and perfect truth for supervision.

## Origin evidence and limitations

T1 uses `T1Match`, after checking the exact registered split SHA **before opening
any match directory**. Episodes come exclusively from the selected registration
entries; the dataset root is never listed. Main joins are exactly the accepted
`events.jsonl.spawned_native_ids`. The bounded code/receipt investigation found
no certified parent link for raw objectIndex/secondaryIndex: these indices are
not used as parents. Non-main bodies have `kind=origin='child_unresolved'`,
`exact=false`, `is_deployment=false`, source_card known and null parent/index.
These are valid non-deployment negatives but not spawn-vs-death supervision.
No parent guesses are fabricated. Snapshot loss can leave an accepted main
body unobserved; the manifest reports `unobserved_nonspell_deployments`.

Sim has stable engine IDs but no persistent source-card/parent columns. An
instance-local dictionary observer intercepts all `battle.entities` insertions.
The synchronous creation stack supplies the actual spawner/death-source entity
receiver or source argument. Delayed spells join through PendingSpellCast.sequence;
projectiles and areas retain lineage internally until their unit payload spawns.
This is exact call-context capture, not nearest-neighbor attribution. An unknown
sim source or a missing body parent makes validation fail. Instrumentation is
process-local and restored after play_match; no existing engine/bot file is edited.

The stock play_match loop disables champion commands; the dataset wrapper
optionally activates legal abilities deterministically without changing existing
files. Reappearance events come from actual `_stealth_until` /
`_underground_deployment` hidden-to-visible transitions after an accepted
activation, with no position-distance heuristic. Invisible/underground opponent
units are absent from the perceptible perfect stream, but remain in the origin
ledger. A Queen that dies cloaked has no fabricated reappearance. Goblinstein's
tether command alone is not labelled a relocation. The pinned engine itself
describes some champion cast/geometry details as awaiting native traces; the
dataset guarantees engine truth, not certification of official-client fidelity.

Manifests hold per-file SHA256, byte count, per-match wall/CPU seconds (runtime
startup excluded), frame count, origins, and missing-main count. Timings are
outside gzip files so identical inputs stay byte deterministic. CPU estimates
should use process CPU seconds, not elapsed time on the shared nice-priority host.
Two T1 samples are not a measured 100-match audit: normalize their counts to
100 only as an explicitly small-sample projection. Do not run 100 games on 05.

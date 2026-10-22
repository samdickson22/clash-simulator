# Supplemental M BC seeds on leased GPUs

Registered before launch under Sam's compute-max instruction. These seven supplemental random seeds use the
same frozen119,970-source-match snapshot and reviewed M settings as the three active own-host seeds.
L remains cancelled. No model-size, dropout, optimizer, reward or strategy variant is introduced.
The primary three-seed run and its existing selection remain intact; supplemental candidates are labelled
separately. Full DEV selection and the frozen game comparison are required before any better-M handoff.
FINAL remains unused. No candidate is automatically promoted or deployed.

| Host | Supplemental seed | GPU sequence | Target until useful GPU work |
|---|---:|---|---|
| 127x09 | 2026102004 | Reviewed R40 M physical-memory probe, then M BC | R40 within15min of operational GO; BC30–45min |
| 127x12 | 2026102005 | Reviewed R40 S100 physical-memory probe, then M BC | R40 within15min of operational GO; BC30–45min |
| 127x17 | 2026102006 | M BC | 30–45min |
| 127x13 | 2026102007 | M BC on CPUs0–31 | 45–60min |
| 127x14 | 2026102008 | M BC on CPUs0–31 | 45–60min |
| 127x15 | 2026102009 | M BC on CPUs0–31 | 45–60min |
| 127x16 | 2026102010 | M BC on CPUs0–31 | 45–60min |

These are staging/review targets, not measured launch times or launch GO. The 17GiB store must be SHA-verified
on each host.13–16 also require pinned environment readiness, inherited affinity and measured PSS admission.
The exact source/model/data/launch receipts bind every actual launch and supersede these estimates.

The existing40ea trainer remains immutable on01/02/08. Supplemental training preserves d320/L6/H8/FFN1280,
dropout0.1, BF16, batch512, three Torch threads, AdamW2e-4/weight decay0.01, one-pass warmup/cosine,
eight-pass maximum/patience2, domain/Hog/IPW/value weights, age augmentation and R7 consumed-future release.
Inputs are the same240 sealed batches,119,475 usable matches and23,498,034 rows. Manifest SHA256 is
1aa01c37fdd18ac7c23a5e9cf7b875b674d5021309ab4b4b79603fd29661b264.
The same6241 files are mirrored through LAN hubs; no mutable/open re-drive batch enters this store.
All leased destinations are under repos/clasher* or jobs/clasher, including the relocated dataset and caches.

The mandatory lease contract needs a minimal opt-in checkpoint-and-exit hook, not an optimizer resume or
new yield controller. At a safe completed optimizer/scheduler or DEV boundary, it validates its own generation's
stop request, atomically preserves a clearly not-admitted model/progress checkpoint and exits. A reclaimed run
stays interrupted/cancelled-by-lease with consumed work recorded. It is not silently resumed, replaced or topped
up. No optimizer-continuation claim is made. Initialization without a model records its zero-progress stop.
A signal handler only records a request. All other errors retain fail-closed behavior. Parent independent
resource/timeout enforcement and the existing watcher bound hung calls and final exit. This narrow adapter and
its concrete launch config require fresh Sol-high review before any supplemental GPU training.

Existing09/12/17 watchers remain unchanged on R37. New13–16 watchers have exact995579193 independent GO,
are live, and retain all32-process/32GiB/CPU0–31/nice10 limits.09/17 process caps96,12 cap64, all with64GiB PSS.
All ancestors, wrappers, monitors, children and staging tasks count. Every job retains GPU free at least8GiB,
host memory above28GiB/load at most90, earliest reclaim/expiry bound and hard expiry2026-10-25T07:53Z.
No owner lease is edited. No process belonging to HP1, RoadForge or another owner is changed.

Implementation owner is pv1-sol-leased-M-bc-compute-20261022-r1. R40's separate owner retains09/12 SSH until
its attempts drain. The failed old Claude lease implementation was completed by Sol and is not restarted.
New Claude children use the currently available instance. The main and sjeother instances have known weekly
limits in this session, so assistant_ui is the usable instance; Sol-high remains the review/monitor default.

Future M handoffs go to live-integration r2,
thread:delegated-task:command%3Amcp%3Aa07d278b-f44c-496d-b560-8f7055630599%3Adelegate-task%3Aclasher-live-m-integration-opus-20261022-r2,
with file SHA, admitted selection and game evaluation. That owner already has the current947af5cb handoff.
This task performs no deployment or Mac changes.

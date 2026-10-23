# Terminal actor recycling fixture

This fixture is implementation only until the parent obtains independent Sol
high review of the committed source. Its outputs are test-only and cannot enter
training, evaluation banks or scientific comparisons. A completed attempt still
needs independent post-execution review. It issues no launch or precision receipt.

For each selected 41k anchor, M and S100, and each acting seat, the parent compares
two consecutive actual calibrated-engine games in one persistent process with
the identical games across a terminal process handoff. There are 16 games total,
12 sequential workers, one live worker at a time and no replacement games.
The second arm's original worker closes the true terminal, receives every
publication acknowledgement, calls production `ActorCheckpoint.capture`, waits
for the parent to durably retain its digest and cursor, then exits. The parent
reaps it before starting the successor. The successor uses production
`restore_record` with the one canonical durable claim directory. A failed claim
or failed game stops the attempt; there is no retry or top-up.

The actor is the exact production `StreamingPolicyOursPlayer` and `Session`.
The production bootstrap verifies all 9,409 runtime and 17,010 actor-source files
before bot/engine imports. Origins are checked before successful completion.
Selected FP32 anchors load through production `policy.load`, then convert to
FP64 before actor construction, matching the reviewed R38/R42 conversion. Both
known FP64 policy hashes are checked. The math attention backend and one CPU
math thread are explicit. There is no optimizer or PPO update.

Both games use the registered `scripted-pressure` controller, exact real Hog
card levels and King/Princess level 9. Cards and towers use JSON seat mappings
that restore integer keys before `play_match`. A CPU contract test extracts only
the four pure resolver functions from the exact pinned actor source, without
importing bot or the engine. The opponent's actual class and controller source
hashes accompany each game. Opponents are fixed at game start. Seeds occupy the
separate `2**61 + 202610220000 + 2*seat + sequence` namespace, disjoint from the
registered training interval and evaluation namespace. Frozen historical and
three evaluation-bank seed inventories are checked too. Cases are paired across
sizes and arms; this does not change the approved per-arm version protocol.

Every retained NPY array, including feature arrays, dtypes and shapes, and every
publication scalar, boundary, bootstrap, version and runtime pin contributes to
the game hash. A per-poll NPY journal also preserves unpublished sampled tails
on failure, including empty entity arrays. The parent verifies raw publication
file bytes before acknowledging. Ordinary
terminal/chunk publications receive the same version. Exact 257-row quota
barriers receive the next version with identical frozen weights and another
257-row quota. A midgame quota never triggers recycling. Full next-game hashes,
per-poll observer bytes, counters, command logs and operational-rejection
provenance must match. The first differing poll, array byte or metadata field
is reported. Rejected taps remain unchanged samples under DECISIONS item 8.
All other execution errors fail closed. The R7 trace cleanup is unchanged.

Limits are fixed in `LIMITS`: 3,600 seconds for the parent, 600 seconds per
worker, 30 seconds per whole control frame, parent checks every 0.1 seconds, worker
RSS at most 2 GiB, parent RSS at most 1 GiB, 2 GiB retained output, at most
6,001 engine ticks and 1,183 own polls per game. The unchanged lifetime budget
is 8,192 steps, safely above the two-game ceiling. The parent monitors even
when the engine or acknowledgement blocks, and after `done` until actual exit
and reap. The final wait uses the remaining original worker and parent deadlines.
Host, RSS, child accounting and retained output checks run on every monitor pass.
Output accounting walks only the fixture output tree at that cadence, with no
one-second throttle. Parent frame age starts with the first header byte and
covers header and body together. Partial headers, payloads and late completion
fail at 30 seconds; idle computation keeps the separate worker deadline.
Transport uses `poll`, including above descriptor 1024.

It rejects extra child processes. Before any worker spawn, cleanup admission
exercises Linux x86_64 syscalls 434 and 424 on the parent with signal zero and
enables child adoption. These minimal R37-equivalent helpers are included in the
canonical source digest. They work with the documented Python 3.12 interpreter,
which exposes neither `os.pidfd_open` nor `signal.pidfd_send_signal`. Unsupported
ABI, kernel or permissions refuse before spawn. Each discovered PID/start
identity is recorded before pinning, and its pidfd stays held until cleanup.
Signals require matching PID/start before and after pinning plus a live held
pidfd. A race refuses the signal; there is no numeric PID or process-group kill
fallback. Cleanup uses one bounded five-second window for the discovered set,
including descendants found during drain. The deadline is stored once and is
never renewed by discovery or another cleanup call. It reaps exact children and
records survivors. Held pidfds stay open if cleanup cannot finish; the exclusive
owner remains reserved and refuses another worker. Failure receipts retain the full
discovered ownership set, the original failure and traceback, and separate
cleanup errors even when cleanup fails. Host admission requires MemAvailable
strictly above 28 GiB, load1 at most 90, nice at least 10, CUDA hidden and all
math thread environments one. A lease
environment is refused; no leased host, watcher or job is needed.

The output directory must be fresh and outside the checkout under local
`/mpac/sdicks02`. Failed outputs, arrays, process receipts and partial polls stay
in place. Use a fresh path for any separately approved attempt. Never overwrite
or reinterpret a failed prefix. Engine and process resume qualification flags
remain false.

## Retained evidence and remaining gates

`rl-readiness/registered-driver-inputs-r1/gate-audit.json` still lists exact
recycled rollout proofs and the six-hour exposure as pending. R41's component
review proves process transfer with mocked battles. Retained `stream-M-03.json`
and `stream-S100-03.json` contain actual single-game streaming proofs with 703
and 1,183 polls, respectively. R38's retained selected-anchor fixtures contain
8,448 polls each and numerical/PPO evidence. None compares two actual games
against a forced terminal process handoff. R48/R49/R52 permit composition of
unchanged components and explicitly leave actual exposure gates open.

The fe6 checkout's older scientific documents are not changed. This fixture pins
the current DECISIONS amendment from git object `148ead65e`, and the byte-matching
RL-DUAL-PREREG in the R44-v2 document bundle. It retains boundary-declined
accounting and `paired-case-draws-game-start-version-v1` unchanged.

After reviewed execution, only this bounded terminal-parity piece can close.
The six-hour 32-actor/learner exposure, real-process GPU memory, source/config
receipts, staging/admission, registered launch, midgame engine continuation,
promotion and deployment remain separate parent-owned gates.

## Parent execution after independent review

Run from this clean committed new-files-only branch. Obtain the candidate digest
without importing bot or the engine:

```sh
/mpac/sdicks02/repos/clasher-pv1-rl-env271-20261022/bin/python -B \
  bot/pretrain_v1/checks/qualify_terminal_recycle.py --print-source
```

The parent supplies a hash-pinned JSON review receipt with schema
`pv1-terminal-recycle-review-v1`, verdict `GO`, scope
`offline-terminal-recycle-only`, this `source_sha256`, exact `base`, exact
`limits` object, model `gpt-6.1-sol`, effort `high`, `independent: true`, and
`engine_resume_qualified: false`. This implementation creates no such receipt.
The parent must read the actual review; the fixture checks its binding.

With `SOURCE_SHA`, `REVIEW_JSON` and `REVIEW_SHA` set to those exact parent-owned
values, the proposed single attempt is:

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
NUMEXPR_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
nice -n 10 /mpac/sdicks02/repos/clasher-pv1-rl-env271-20261022/bin/python -B \
  bot/pretrain_v1/checks/qualify_terminal_recycle.py --test-only \
  --source-sha256 "$SOURCE_SHA" --review "$REVIEW_JSON" --review-sha256 "$REVIEW_SHA" \
  --out /mpac/sdicks02/scratch/pretrain-v1-dev/rl-readiness/terminal-recycle-reviewed-attempt1
```

CPU tests use spawned fake engines and the real actor/Session/checkpoint APIs.
They do not authorize or execute the command above.


## R59 CPU regression scope

The retained 29 mock cases and 17 R41 cases remain required. Added regressions
cover the pinned resolver contract, documented-interpreter syscall capability,
refusal before spawn, PID/start races, exact fork-child reap and cleanup-error
accounting. Fake workers send `done` then violate the original worker deadline,
parent deadline, host guard, RSS, output or child-count contract. Frame cases
cover truncated headers and payloads, EOF, stalls, late bytes, late completion,
successful fragmented completion, idle computation and high descriptors.
New process fixtures explicitly clean up their own children on failure and
retain whether the independent test fallback assisted. Assistance cannot count
as candidate cleanup success. Test logs and failed fixture directories stay
outside the checkout; each test run uses a fresh directory.

These tests do not run calibrated-engine games or establish actual parity.
A fresh independent parent review of the frozen commit remains required before
one separately admitted bounded CPU engine attempt. This change grants no
six-hour exposure, production, RL, GPU, precision or midgame-resume approval.

## R62 ownership boundary and CPU regressions

`run_process` requires a dedicated standalone parent with one OS thread and no
preexisting children, including zombies and multiprocessing resource trackers.
Admission reserves exclusive ownership before taking this empty baseline. A
parent with a foreign child is refused before worker creation. That foreign
lifetime is never signalled or reaped by the fixture. Refusal also avoids the
unresolvable case of a foreign child forking and orphaning an unseen descendant
while an owned worker runs. The fixture does not offer a shared-parent API.

The reservation allows one recorded `Popen` and rejects nested owners. A scoped
Python audit hook blocks other `Popen`, `fork`, `forkpty` and `posix_spawn` calls
from the parent until drain completes. Even a caught launch rejection latches
failure. The hook is inert outside the reservation and in the worker. Each
discovery pass rechecks the parent PID/start, parentage/session and single-thread
condition. These checks enforce the boundary for the frozen standalone caller
and its guard. They do not sandbox arbitrary native extensions that create
threads or processes outside Python's audited paths. Such parent integrations
are unsupported; they cannot be admitted as unrelated concurrent work.

Within this boundary every new kernel child of the parent belongs to its single
launch, regardless of SID. Discovery enumerates only this parent's task children
and retained owned descendants. It records exact PID/start before pinning, and
latches unexpected descendants even if first found in cleanup after the final
ordinary check. Drain enumerates again after signalling and reaping, then requires
both retained lifetimes and kernel children to be absent. It keeps collecting
descendants that fork during drain. An unavailable PID/start fails the attempt;
unresolved enumerated PIDs remain in the receipt and prevent a successful reap
claim. Initial identity-read failure after `Popen` enters monitored cleanup.

The bounded real-fork regressions cover fast worker exit with a detached live
child or zombie, a fork after the last successful monitor check, and a detached
grandchild born during drain. They require all identities retained, failure
latched, actual exit/reap, no survivors and zero independent cleanup assistance.
Other cases cover live/zombie foreign-child survival, future foreign adoption
after refused admission, concurrent launch refusal, a multithreaded parent,
transient and persistent missing identities, and a fixed cleanup deadline with
the original monitor failure retained. A deliberately blocked-signal negative
control requires explicit exact independent cleanup and is never candidate
cleanup evidence. Foreign fixtures have their own separately labelled cleanup.

The retained terminal checkpoint test uses a private-pipe plain subprocess to
avoid leaving a resource tracker in later monitor tests. Run terminal tests in
their own Python process, then the unchanged 17 R41 cases in another process;
each command uses the documented interpreter, CPU environments, `-B`, nice 10,
disabled pytest cache and a fresh external basetemp. No calibrated engine is run.
The original 76 cases remain required alongside these new regressions. The
canonical source digest and exact commit need fresh parent-owned R69 review.

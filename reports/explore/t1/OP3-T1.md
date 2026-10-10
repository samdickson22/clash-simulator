# T1 operational delta OP-3

Coordinator authorization: 2026-10-10 15:58Z user instruction. Scientific and
OP-2 base: `78c9bd5bafd1d4d0b4bb8f5570a37da5e4e17c36`. The unreviewed
16a168c2 first-fork refinement is absent from these admitted candidate bytes.
Reporting remains zero and SEALED until fast confirmation and fresh smoke.

The previous03 failure was the separately confirmed OP-2 perception race.
On01 and08, excluded smoke-after-freeze-r3 marked its own run.py group leaders
as foreign at exit:01 PID/PGID293675, parent293613;08 PID/PGID1549259,
parent1549128. Both captured commands name that exact owned job. The old
ownership predicate attempted cwd lookup first, returning false on lookup failure
before it examined the already-captured command.

The OP-3 fast path requires both the unchanged owned-job CMD predicate and
authenticated supervisor-tree membership before any cwd lookup. The supervisor
records its actual PID/PGID/start/UID/raw cmdline SHA/exe at admission, verifies
itself against the live process, and refuses an existing admission receipt. Each
explicitly launched block group is appended with PID/PGID/start/UID and must be a
direct child of that supervisor. No command-only exited-worker exception exists.

Membership requires the still-identical recorded supervisor. A captured row must
have its UID and either its supervisor PGID or direct supervisor parent, or a
registered worker PGID/parent with a still-identical leader. An exited registered
group leader can instead prove its own PID/PGID/start/UID from the captured row.
Changed/reused root or leader identities fail closed. The existing live cwd path
remains unchanged in meaning; its lookup is now strict, so an absent/unreadable
cwd cannot silently satisfy the captured-command branch. A matching command
with a foreign parent and PGID receives no exit fallback.

`owned-supervisor-admission.json` records the root admission and owned block
groups. OP-2, the reader command/path set, idle-service and system-bus identities,
the scientific runner/reducer/decks/seeds and all outcome sealing remain unchanged.

Seven OP-3 tests plus the reviewed19 OP-1/OP-2 tests pass on stopped03 (26/26),
nice10/SCHED_OTHER, physical cores0–4. Tests cover owned exit, unowned exit,
matching command with foreign parent/PGID, supervisor-PGID proof, root PID
generation changes, worker leader generation changes and the final foreign guard.
The source-bound78 qualification meanwhile finished on all three hosts:74 tests,
125 exactness states and125 belief histories, stable sources and inputs.

Candidate review is required before staging this delta for fresh smoke. The
candidate changes host ownership, supervisor admission bookkeeping, the
qualification test list and OP-3 tests/records only. Qualification and admission
on the final reviewed source will precede a wholly new smoke namespace.

# Fleet top

Installed on 127x05; the `fleet` tmux session is running detached.

## Commands

On 127x05: **`fleet-top`** (dashboard + grid), or **`fleetmon`** (dashboard only).

From Sam's laptop:

```bash
ssh -t 127x05 '~/.local/bin/fleet-top'
ssh -t 127x05 '~/.local/bin/fleetmon'
```

Quote the remote path: unquoted `~/.local/bin/...` expands on the laptop and may
send the wrong `/Users/...` path. Both programs passed fresh SSH tests from
127x03 to 127x05, without relying on an existing shell or multiplexed connection.

- `Ctrl-b n` / `Ctrl-b p`: next / previous window (`overall`, `grid`).
- `Ctrl-b` then an arrow: select a pane; `Ctrl-b q` shows pane numbers.
- `Ctrl-b z`: zoom to the client terminal; repeat to restore the grid.
- `Ctrl-b d`: detach and leave it running; rerun `fleet-top` to attach.
- Dashboard: `q` quit, `s` name/CPU/GPU sort, `g` GPU-only, `[` / `]` pages.
  Resizing adjusts cards. `fleet-top` restores an overall window closed with `q`.

## Grid, configuration, and hosts

The full 16-pane grid uses **384×120** cells; allow 384×121 including the status
line to see it all at once. Smaller terminals show a cropped viewport: select a
pane and zoom. Zoom automatically fits the client and restores the full grid on
unzoom. A **120×42** zoomed GPU pane was tested successfully.

Shared `~/.config/btop/btop.conf`: 2000 ms updates; preset **1** = CPU + GPU0 +
memory, **2** = CPU + memory (03/05), **3** = CPU + GPU0 + memory + processes.
Logging and config autosave are disabled. The Mac runs its existing Homebrew
btop with config/log persistence disabled; nothing was installed there.

**Minimum GPU pane: 60×27**, measured on a 128-thread A6000 host. 95×28 also works;
59×27 and 60×26 correctly report too small. Allow **60×29 terminal cells** for
pane title and status. Aggregate CPU covers all threads; only core rows that fit
are displayed. Secondary memory rows can be omitted at the absolute minimum.
A small btop patch relaxes its memory-box minimum only when disks, memory graphs,
and swap are hidden; unmodified btop requires 60×30.

Edit `~/.config/fleet-top/hosts`, then restart the session. Defaults: 127x01, 03,
04, 05, 08, 09–18 and `macmini-fleet`. Offline **02/06/07** are commented out;
uncomment to monitor their return. Their binaries are on shared NFS, but execution
could not be verified while they were down. `FLEET_HOSTS=/path fleet-top` and
`fleetmon --hosts /path` select another list. Optional two-host windows:

```bash
~/.local/bin/tmux kill-session -t fleet  # stops only this monitor
FLEET_PAIR_WINDOWS=1 fleet-top
```

## Measurements and limits

Parallel polls reuse private SSH ControlMaster sockets in local `/tmp`, one poll
per host in flight, with timeouts and 30-second failure backoff. Roles refresh
from `/mpac/sdicks02/cc/FLEET-SHARING.md`. Down hosts retain last-seen times and are
excluded from totals; GPU-only filtering does not change header totals. GPU sum
uses percentage points (100% = one busy GPU). CPU needs two initial samples.

Linux uses `/proc` counters and NVIDIA CSV telemetry; the Mac uses `top`,
`vm_stat`, `sysctl`, and qemu `pgrep`. Mac memory excludes reclaimable pages; Apple
GPU metrics are excluded from NVIDIA totals. C/R process counts match absolute
command paths under `/mpac/sdicks02/repos/clasher*` and `roader*`; relative-only
commands are not attributed. Console counts exclude SSH PTYs; login counts include them.

Verified **16 hosts up, 1932 threads, 13 A6000s / 618.0 GiB VRAM, 2 Mac emulators**.
Linux polls took about 86–141 ms wall time, Mac about 757 ms. One complete GPU
collector used **60 ms CPU / 70 ms wall**, not literally a few milliseconds:
about 3% of one core at a two-second interval. All monitoring is read-only.

## Files and proof

- Executables: `~/.local/bin/{btop,btop-nogpu,tmux,fleet-top,fleetmon}`.
- Configuration: `~/.config/btop/btop.conf`, `~/.config/fleet-top/{hosts,README.md}`.
- Source, patch, build scripts, original config backup, package checksums, evidence:
  **`/mpac/sdicks02/cc/tools/fleet-top/`** on 127x05.
- Toolchain/builds: **`/mpac/sdicks02/build/fleet-top/` on 127x03**, nice 15, eight jobs.
- This report: `reports/strategy_council_20260928/fleet/FLEET-TOP.md` in the 05 checkout;
  text screenshots and receipts are beside it in **`fleet-top-evidence/`**.

btop **1.4.7 + compact-layout patch**, GCC 14.4.0 / glibc 2.17 sysroot,
GPU_SUPPORT=true; libstdc++/libgcc are static, glibc dynamic. tmux **3.6a** has
static libevent/tinfo and dynamic glibc. Both `ldd` lists contain only glibc
libraries; both executables ran on all 15 reachable Linux hosts. The previous
musl btop is preserved as `btop-nogpu`. Python is `/usr/bin/python3` 3.8, stdlib only.

Downloaded release assets and compiler archives were checksum verified; btop's
tag commit was pinned and Git object checksums verified with `git fsck --full`.
See `build-and-verification.txt`, `SHA256SUMS`, and the package manifest for details.
No root/system packages, roader local changes, cron/tailscale changes, or git commits.

Evidence: `dashboard.txt`, `grid.txt` (16 `tmux capture-pane` outputs composed at
pane coordinates), `btop-127x04-60x27.txt`, no-GPU 03/05 panes, down-host/retry and
resize captures, fresh SSH captures, all-host versions, library lists, connection
reuse, and three passing parser/backoff/recovery tests. `fleetmon --once` produces
an up-to-date JSON sample.

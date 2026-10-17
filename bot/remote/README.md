# Remote-search latency probe

**Phase A is code and local pipe tests only.** Do not deploy or run the probe on
the fleet/Mac until a separate Sol review clears this exact SHA and the BOT LEAD
authorizes phase B. No search runs here: the responder returns a dummy action.
The question is whether Mac → persistent SSH over Tailscale → 08 → Mac can meet
a p95 RTT of 20–25 ms inside the bot's roughly 65 ms step budget.

## Safety and execution gates

The LIVE LEAD owns the Mac. Their conditional windows do not authorize starting
the probe now.

1. Idle: ride the loop owner's next native stop. Send the reviewed SHA and Sol OK
   to both owners below, then wait for the **loop owner's explicit GO**. The default
   is **150 requests per payload at 2 Hz**: 450 requests take **225 seconds**
   (3.75 minutes). With the 30-second usual-CPU baseline and about 20 seconds of
   context timings, this targets a roughly five-minute slot. Use a 240-second
   probe wall limit for this slot, and STOP if the owner's window ends sooner.
   Counts remain configurable up to 300 per size; larger runs need a longer GO.
2. Battle: only after idle shows client CPU **<1% of one core**, tailscaled staying
   within its usual approximately **10–17% CPU** with no spike, and a stable SSH
   session (no errors/timeouts/reconnects). Missing sampler data or baseline is a
   failed gate. Send the results to the LIVE LEAD/loop owner and obtain a separate
   approved window for **one non-dump battle**, realistic payload only at 2 Hz.
3. A babysitter compares the battle's step p95, FPS and tap→deploy against its
   normal values. If running step p95 **>65 ms** or FPS **<9.8**, create STOP
   immediately. The probe intentionally does not read or monitor the live driver;
   the owner/babysitter supplies these metrics and decides when to stop at battle
   end. Do not run through a second battle.

Owner references (for the BOT LEAD's coordination; these scripts never message
anyone):

- Loop owner: `thread:delegated-task:command%3Amcp%3A99d49b81-f9ec-41a6-bede-03f9b418a3db%3Adelegate-task%3Alive-loop-owner-r1`
- LIVE LEAD: `thread:delegated-task:command%3Amcp%3A53609d4a-a2de-484a-834d-8566c6339c9f%3Adelegate-task%3Aclasher-live-lead-20261014-r1`

## Payload and measurement

`payload_size.json` records a read-only measurement on 127x05 of
`/mpac/sdicks02/scratch/live-loop/runs/s76/m01/`. Its label is
**proxy: per-frame perception row + 30 s play history**.

- Nearest-rank p95 of 2,680 raw `frames.jsonl` row sizes, excluding the LF: 1,698
  bytes. The selected row is n=1972, ts_ms=199564.718584.
- Join decisions.n to frames.n/ts_ms. The 120 decisions rows in the preceding
  `(ts_ms - 30000, ts_ms]` window total 45,583 bytes, including their newlines.
- Realistic proxy: **47,281 bytes**. The other sizes are **5,120** and **51,200**
  bytes (5 and 50 KiB). Including all telemetry rows conservatively overestimates
  a compact play-history encoding. Frames contain units/HUD summaries and timing
  fields; this is a sizing proxy, not a true serialized search input.

The checked-in hashes identify both source files. Reproduce sizing locally on 05
without contacting any other host:

```sh
python3 -B bot/remote/measure_payload.py /mpac/sdicks02/scratch/live-loop/runs/s76/m01
```

Actual traffic is anonymous random base64 padding in valid NDJSON. Sizes above
are **total request wire bytes, including envelope and LF**. Random padding is
generated once and reused to minimize CPU; SSH compression is disabled. No game
records, screenshots or real actions are sent. The action object is about 200
bytes; the full response also includes the ID and two monotonic timestamps.

RTT starts before the first write and ends when a complete response is read. It
includes SSH transport and server JSON work. Startup/first exchange is reported
separately as `warmup`, followed by exactly `--count` measured requests per size.
One session serves all sizes sequentially. Fixed-rate scheduling skips missed
slots instead of bursting. A timeout or malformed response aborts the session;
there are **no reconnect attempts**, and reconnect count is explicitly zero.
Percentiles use nearest rank. Do not infer one-way latency by subtracting clocks
on different machines; only server send-minus-receive is meaningful.

## Local verification (phase A)

```sh
python3 -B -m unittest discover -s bot/remote -p 'test_*.py' -v
```

Tests launch local Python responders over pipes, including idle/partial input,
blocked stdout, EOF, invalid messages, request/wall limits, stalled request
reads/writes, STOP, exact wire sizes and SSH options. Regression tests SIGKILL the
client, simulate SSH disconnect via SIGHUP, close the parent lifetime pipe,
SIGTERM the context helper with a stalled child, and flood stderr before/after
warmup. Effective forwarding settings are checked with local `ssh -G` against a
synthetic config; it opens no connection. Sampler discovery and CPU reads are
mocked; tests never contact a host or sample a live daemon.

## Deployment and runs (phase B only, after the gates above)

Use only **127x08** (default), or explicitly approved **127x04**, as responder.
Do not use any other fleet host. Copy only the reviewed files after GO:

- `latency_responder.py` → 08 at
  `/mpac/sdicks02/jobs/clasher/bot-remote-probe/latency_responder.py`.
- `latency_client.py`, `probe_process.py`, `tailscaled_sampler.py`, `network_context.py` and
  `payload_size.json` → Mac at `/tmp/bot-remote-probe/`.

The client launches `python3` remotely through one SSH command, with
`ControlMaster=no`, `ControlPath=none`, `ControlPersist=no`,
`ServerAliveInterval=5`, strict existing host-key verification, no host-key
updates, no local SSH command, batch authentication and no compression.
`ClearAllForwardings=yes`, `ForwardAgent=no`, `ForwardX11=no` and `Tunnel=no`
override inherited local/remote/dynamic forwards, agent/X11 forwarding and tunnels.
Existing trusted keys/authentication and the Mac's 127x aliases are prerequisites.
Do not change SSH configuration or install any service to make this run.
Use `sha256sum` on Linux / `shasum -a 256` on the Mac to compare deployment hashes
against the reviewed checkout; use `date -u` for timestamps.

The fleet's `ssh macmini-fleet` exit status is unreliable. Every remote shell
operation must print its **own** final `__RC=<n>` token; parse the final token and
fail closed if it is missing. For example, after deployment, the following
commands are issued **on the Mac** in the approved window:

```sh
# 30-second usual-CPU baseline while the loop is natively stopped, before probe.
python3 -B /tmp/bot-remote-probe/tailscaled_sampler.py \
  --label usual --max-seconds 30 \
  --output /tmp/bot-remote-probe/tailscaled-usual.json
rc=$?
printf '__RC=%s\n' "$rc"

# Idle: 150 measured requests per size (default), one session, <=240 seconds.
python3 -B /tmp/bot-remote-probe/latency_client.py \
  --payload all --count 150 --hz 2 --max-seconds 240 \
  --stop-file /tmp/bot-remote-probe/STOP \
  --output /tmp/bot-remote-probe/idle-08.json
rc=$?
printf '__RC=%s\n' "$rc"

# Separate context run in the approved idle window only (not during battle).
python3 -B /tmp/bot-remote-probe/network_context.py \
  --output /tmp/bot-remote-probe/network-context.json
rc=$?
printf '__RC=%s\n' "$rc"
```

The client starts/reaps a separate tailscaled sampler at ≤1 Hz for the probe's
duration. PID discovery is exactly `pgrep -x tailscaled`. Reads are
`ps -o %cpu= -p PID`; if several exact-name processes exist, their CPU is summed.
No daemon is signaled. PID disappearance/ps failure is recorded, not concealed
by rediscovery. `ps %cpu` is a **smoothed estimate**, not instantaneous CPU; compare
the usual and during raw samples, p50/p95/max and mean delta. An absent/failed
sampler makes the client return nonzero even if network traffic completed.

`network_context.py` times one fresh `ssh 127x04 true` with the same isolation
options and at most 20 TCP connects per host at ≤2 Hz, using no ICMP. It obtains
the destination from `ssh -G` on the Mac. Direct-connect context requires a
numeric `HostName` and no ProxyCommand/ProxyJump; unsupported routing is recorded
as an error rather than measuring a different route. It does not time search.
If an approved 04 responder comparison is needed, deploy the same reviewed stub
there and run the client with `--host 127x04` in a separately sufficient idle
window. TCP/SSH-startup timings alone do not establish persistent 04 search RTT.

For a separately approved live battle, start at the owner's cue, and create STOP
at battle end or at either abort threshold:

```sh
python3 -B /tmp/bot-remote-probe/latency_client.py \
  --payload realistic --count 300 --hz 2 --max-seconds 180 \
  --stop-file /tmp/bot-remote-probe/STOP \
  --output /tmp/bot-remote-probe/battle-08.json
rc=$?
printf '__RC=%s\n' "$rc"
```

Here 300 is a ceiling, not permission to outlast the one battle. STOP produces
a partial summary and a nonzero token deliberately. Do not remove a preexisting
STOP until the owner explicitly clears the abort for a new approved run.

## Stop, limits, cleanup and reporting

```sh
touch /tmp/bot-remote-probe/STOP
```

STOP is checked before spawning SSH, between requests and every ≤50 ms while
waiting on either pipe. Existing STOP launches no SSH or sampler. Child cleanup
is bounded; local stalled-pipe tests assert exit within the default one-request
interval (500 ms). SIGINT/SIGTERM/SIGHUP also request shutdown in both the client
and context helper. Each long-lived local child runs under a tiny guardian in
`probe_process.py`, which watches a dedicated parent-owned pipe. Only the client
holds its write end. Closing it, disconnecting the SSH shell (SIGHUP), or killing
the client with SIGKILL triggers EOF: the guardian terminates and, if necessary,
kills and reaps its own SSH/sampler child before exiting. The guardians inherit
nice priority and use no threads or sockets. They are included in child CPU
accounting. Only Popen children are terminated/killed; never pattern-kill or
signal a preexisting PID. The remote
responder exits on EOF, after its request limit (default 1,000, hard maximum
10,000), or at its wall limit (default/hard maximum 600 seconds), even on partial
stdin or backpressured stdout. Requests are bounded to 1 MiB. It never listens
on a port and cannot perform any game action.

The production client/samplers refuse non-Mac hosts. Client caps are 300 measured
requests per payload, 2 Hz and 600 seconds. All run processes are nice ≥+10;
there are no Python worker threads. The configurable default is 150 requests per
payload. Self CPU uses `resource.getrusage` user+system
seconds divided by monotonic elapsed time as percent of one core. The summary
also reports waited child CPU and total local CPU, including SSH, the sampler
and its process reads, to expose transport overhead beyond the <1% client gate.

The Mac runtime writes only beneath `/tmp/bot-remote-probe/`: scripts, summaries
(including raw RTT samples), per-run SSH/sampler stderr and per-run tailscaled
summaries. Stderr is drained nonblockingly through a shared **64 KiB** buffer;
crossing that byte limit aborts the run. The diagnostic file is written from that
buffer after cleanup and cannot grow beyond 64 KiB. No child writes it directly.
Output overwrites and paths escaping that directory are refused. The probe never
touches BlueStacks, screen capture, ADB, live processes, tailscaled configuration,
crontab or any live input path. It does not need a listener, daemon or background
service. No command-line argument contains the watchdog's forbidden driver path.

After STOP/shutdown and after archiving the outputs if wanted, remove **all Mac
probe artifacts** with one command:

```sh
rm -rf /tmp/bot-remote-probe/
```

Report completed count/timeouts and RTT p50/p95/p99 for each idle payload, plus
realistic in-battle results and their actual sample count. Include client/child
CPU, usual vs during tailscaled values, session stability, 04 SSH/TCP vs 08 TCP
context (and persistent 04 RTT only if measured), and the LIVE LEAD's battle step
p95/FPS/tap→deploy metrics. Separate aborted samples from complete runs. No phase
B measurements or live-impact claims are established by the local tests.

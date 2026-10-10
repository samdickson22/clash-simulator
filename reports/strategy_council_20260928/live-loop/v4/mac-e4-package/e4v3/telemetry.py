"""Per-CPU accounting using Mach or procfs, without a psutil dependency."""
import ctypes
import json
import os
import platform
import resource
import subprocess
import time


def command(argv):
    result = subprocess.run(argv, text=True, capture_output=True, check=False)
    return dict(argv=argv, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)


def cpu_counters():
    if platform.system() == "Linux":
        rows = {}
        with open("/proc/stat") as stream:
            for line in stream:
                fields = line.split()
                if fields and fields[0].startswith("cpu") and fields[0][3:].isdigit():
                    values = list(map(int, fields[1:]))
                    # Linux guest counters are already included in user/nice.
                    rows[int(fields[0][3:])] = (sum(values[:8]), values[3] + values[4])
        return rows
    lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
    lib.mach_host_self.restype = ctypes.c_uint
    count, length = ctypes.c_uint(), ctypes.c_uint()
    info = ctypes.POINTER(ctypes.c_int)()
    # PROCESSOR_CPU_LOAD_INFO = 2, CPU_STATE_{USER,SYSTEM,IDLE,NICE}.
    result = lib.host_processor_info(lib.mach_host_self(), 2, ctypes.byref(count), ctypes.byref(info), ctypes.byref(length))
    if result != 0:
        raise OSError("host_processor_info failed: " + str(result))
    try:
        return {i: (sum(info[4*i+j] for j in range(4)), info[4*i+2]) for i in range(count.value)}
    finally:
        lib.vm_deallocate.argtypes = [ctypes.c_uint, ctypes.c_size_t, ctypes.c_size_t]
        task = ctypes.c_uint.in_dll(lib, "mach_task_self_").value
        lib.vm_deallocate(task, ctypes.cast(info, ctypes.c_void_p).value,
                          length.value * ctypes.sizeof(ctypes.c_int))


def idle_delta(before, after, clusters):
    idle = {}
    for index in before.keys() & after.keys():
        total = after[index][0] - before[index][0]
        free = after[index][1] - before[index][1]
        if total <= 0 or free < 0 or free > total:
            raise ValueError("Invalid per-core counter interval")
        idle[index] = free / total
    result = dict(per_cpu_idle={str(k): v for k, v in idle.items()})
    for cluster in ("P", "E"):
        if any(index not in idle for index in clusters[cluster]):
            raise ValueError("Pinned topology includes an unmeasured CPU")
        result["free_" + cluster] = sum(idle[index] for index in clusters[cluster])
    return result


def validate_topology(topology, counters, *, darwin):
    p, e = topology["P"], topology["E"]
    if len(set(p + e)) != len(p + e) or set(p + e) != set(counters):
        raise ValueError("P/E mapping must partition all sampled CPU IDs exactly once")
    if darwin:
        if not topology.get("mapping_evidence"):
            raise ValueError("Mac requires pinned evidence for Mach CPU-index P/E mapping")
        for level, ids in ((0, p), (1, e)):
            value = subprocess.check_output(["sysctl", "-n", f"hw.perflevel{level}.logicalcpu"], text=True)
            if len(ids) != int(value):
                raise ValueError("Topology differs from sysctl perflevel counts")
    return dict(P=p, E=e)


def validate_physical_cpus(cpus):
    """Reject duplicate logical IDs AND SMT siblings in Linux timing slots."""
    from pathlib import Path
    if len(set(cpus)) != len(cpus):
        raise ValueError("CPU groups overlap")
    cores = []
    available = os.sched_getaffinity(0)
    # The runner may have narrowed its own affinity already; topology, rather
    # than current process affinity, determines whether the CPU IDs are valid.
    for cpu in cpus:
        path = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
        core = (int((path / "physical_package_id").read_text()), int((path / "core_id").read_text()))
        if core in cores:
            raise ValueError("Timing CPU groups contain SMT siblings")
        cores.append(core)


def rss():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() == "Linux":
        with open("/proc/self/statm") as stream:
            retained = int(stream.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
        peak *= 1024
    else:
        value = subprocess.check_output(["ps", "-o", "rss=", "-p", str(os.getpid())], text=True)
        retained = int(value) * 1024
    return dict(retained_rss_bytes=retained, peak_rss_bytes=peak)


def identity():
    result = dict(host=platform.node(), platform=platform.system(), machine=platform.machine(),
                  python=platform.python_version(), nice=os.getpriority(os.PRIO_PROCESS, 0),
                  monotonic=time.monotonic(), utc=time.time(), load_average=os.getloadavg())
    if platform.system() == "Darwin":
        result["sysctl"] = command(["sysctl", "hw.model", "machdep.cpu.brand_string", "hw.memsize",
            "hw.perflevel0.physicalcpu", "hw.perflevel1.physicalcpu", "hw.perflevel0.logicalcpu", "hw.perflevel1.logicalcpu"])
        result["macos"] = command(["sw_vers"])
        result["thermal"] = command(["pmset", "-g", "therm"])
        result["rustc"] = command(["rustc", "-vV"])
    else:
        result["affinity"] = sorted(os.sched_getaffinity(0))
        result["scheduler"] = os.sched_getscheduler(0)
    return result


class Census:
    """1 Hz cumulative CPU census; foreign >1-core bursts tracked by PID."""
    def __init__(self):
        self.previous = {}
        self.since = {}
        self.last = time.monotonic()

    def sample(self, owned):
        now = time.monotonic()
        rows = []
        if platform.system() == "Linux":
            ticks = os.sysconf("SC_CLK_TCK")
            for name in os.listdir("/proc"):
                if not name.isdigit():
                    continue
                try:
                    value = open(f"/proc/{name}/stat").read()
                    tail = value[value.rfind(")")+2:].split()
                    rows.append((int(name), value[value.find("(")+1:value.rfind(")")],
                                 (int(tail[11]) + int(tail[12])) / ticks))
                except (OSError, ValueError, IndexError):
                    continue
        else:
            output = subprocess.check_output(["ps", "-A", "-o", "pid=,time=,comm="], text=True)
            for line in output.splitlines():
                pid, elapsed, name = line.strip().split(None, 2)
                fields = elapsed.split(":")
                total = 0.
                for field in fields:
                    total = total * 60 + float(field)
                rows.append((int(pid), name, total))
        result, current = [], {}
        for pid, name, total in rows:
            current[pid] = total
            cores = max(0., (total - self.previous[pid]) / (now - self.last)) if pid in self.previous else None
            if pid not in owned and cores is not None and cores > 1:
                self.since.setdefault(pid, now)
            else:
                self.since.pop(pid, None)
            result.append(dict(pid=pid, name=name, cpu_cores=cores, owned=pid in owned,
                               foreign_over_one_core_seconds=now-self.since[pid] if pid in self.since else 0.))
        self.previous, self.last = current, now
        self.since = {pid: start for pid, start in self.since.items() if pid in current}
        return result


def monitor_worker(stop, phase, owned_pids, clusters, output):
    """Independent 1 Hz sampling continues while Python decision glue is busy."""
    from pathlib import Path
    from receipts import canonical
    import traceback
    census = Census()
    before, previous, origin = cpu_counters(), time.monotonic(), time.monotonic()
    wall_offset = time.time()-previous
    try:
        with Path(output).open("x") as stream:
            index = 1
            while not stop.wait(max(0., origin+index-time.monotonic())):
                now = time.monotonic()
                after = cpu_counters()
                owned = {p for p in owned_pids if p > 0} | {os.getpid()}
                row = dict(timestamp=now, utc=time.time(), phase=phase.value.decode(),
                    interval_seconds=now-previous, load_average=os.getloadavg(),
                    processes=census.sample(owned), **idle_delta(before, after, clusters),
                    sample_gap_over_3_seconds=now-previous > 3,
                    wall_monotonic_offset_change_seconds=time.time()-now-wall_offset)
                if platform.system() == "Darwin":
                    row["thermal"] = command(["pmset", "-g", "therm"])
                    row["boottime"] = command(["sysctl", "-n", "kern.boottime"])
                else:
                    with open("/proc/cpuinfo") as cpuinfo:
                        row["cpu_clock_mhz"] = [float(line.split(":")[1]) for line in cpuinfo if line.startswith("cpu MHz")]
                stream.write(canonical(row) + "\n")
                stream.flush()
                before, previous = after, now
                index += 1
    except BaseException:
        with Path(str(output) + ".error.json").open("x") as stream:
            stream.write(canonical(dict(error=traceback.format_exc())) + "\n")
        raise

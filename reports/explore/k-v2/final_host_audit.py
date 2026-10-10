"""Read-only final census; record a missing former cache PID explicitly."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    groups = {1718083, 1718091, 1575208}
    remaining = []
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit() or int(directory.name) == os.getpid():
            continue
        try:
            fields = (directory/'stat').read_text().rsplit(')', 1)[1].split()
            group = int(fields[2])
            command = (directory/'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
            executable = Path(os.readlink(directory/'exe')).name
            if group in groups or (str(args.job) in command and 'python' in executable):
                remaining.append(dict(pid=int(directory.name), pgid=group, state=fields[0]))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    assert not remaining, remaining
    topology = {}
    for cpu in range(46):
        root = Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        topology[cpu] = {name:(root/name).read_text().strip() for name in ('physical_package_id', 'core_id', 'thread_siblings_list')}
    assert len({(row['physical_package_id'], row['core_id']) for row in topology.values()}) == 46
    cache_present = Path('/proc/1655741').exists()
    receipt = dict(utc=subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'], text=True).strip(),
                   host=socket.gethostname(), who=subprocess.check_output(['who'], text=True),
                   fully_vacated_pgids=sorted(groups), remaining_owned_processes=remaining, topology=topology,
                   G_STOP03_retained=Path('/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010/STOP-03').exists(),
                   former_cache_pid=1655741, former_cache_pgid=1655728, former_cache_pid_present=cache_present,
                   original_final_host_audit='Failed its cache-PID persistence assertion; recorded PID absent. Start/warm audits passed. No K-v2 cache/controller signaling or affinity change was issued; external exit timing/reason unknown.',
                   cache_affinity=sorted(os.sched_getaffinity(1655741)) if cache_present else None,
                   memavailable_bytes=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))*1024)
    assert receipt['G_STOP03_retained']
    args.out.write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({key:value for key,value in receipt.items() if key != 'topology'}, indent=2))


if __name__ == '__main__':
    main()

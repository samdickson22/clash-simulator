"""Read-only host accounting for the canvasdoc Colima VM during Mac benchmarks."""
import datetime
import math
import platform
import subprocess
import time

TARGETS = ('/.colima/_lima/colima-canvasdoc/', '/.colima/_lima/_disks/colima-canvasdoc/')


def parse_ps(raw):
    rows = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        fields = line.split(None, 4)
        if len(fields) != 5:
            raise ValueError('incomplete process telemetry')
        pid, ppid, cpu, rss = int(fields[0]), int(fields[1]), float(fields[2]), int(fields[3])
        if pid < 0 or ppid < 0 or not math.isfinite(cpu) or cpu < 0 or rss < 0 or pid in rows:
            raise ValueError('invalid process telemetry')
        rows[pid] = dict(pid=pid, ppid=ppid, cpu_percent=cpu, rss_kib=rss, args=fields[4])
    if not rows:
        raise ValueError('empty process telemetry')
    return rows


class CanvasdocLoad:
    def __init__(self):
        self.samples = []
        self.attributed = {}
        self.next_sample = 0

    def sample(self, force=False):
        now = time.monotonic()
        if not force and now < self.next_sample:
            return
        self.next_sample = now + 2
        sample = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), monotonic_s=now,
                      state='unknown', processes=[], error=None)
        try:
            if platform.system() != 'Darwin':
                raise RuntimeError('canvasdoc host telemetry requires macOS')
            raw = subprocess.run(['ps', '-axo', 'pid=,ppid=,%cpu=,rss=,args='], capture_output=True,
                                 text=True, timeout=5, check=True).stdout
            rows = parse_ps(raw)
            self.attributed = {p: v for p, v in self.attributed.items() if p in rows}
            selected, uncertain = {}, False
            for pid, row in rows.items():
                args = row['args']
                if any(t in args for t in TARGETS):
                    selected[pid] = 'colima-service'
                # The VZ helper's argv lacks the VM name. Attribute it by its open VM disk/EFI files.
                if 'com.apple.Virtualization.VirtualMachine' in args or 'qemu-system-' in args:
                    if pid not in self.attributed:
                        files = subprocess.run(['/usr/sbin/lsof', '-p', str(pid), '-Fn'], capture_output=True,
                                               text=True, timeout=5)
                        if files.returncode != 0:
                            uncertain = True
                            continue
                        self.attributed[pid] = any(t in files.stdout for t in TARGETS)
                    if self.attributed[pid]:
                        selected[pid] = 'virtual-machine'
            while True:
                children = {p: 'descendant' for p, r in rows.items() if r['ppid'] in selected and p not in selected}
                if not children:
                    break
                selected.update(children)
            for pid, role in sorted(selected.items()):
                sample['processes'].append(dict(role=role, **{k: rows[pid][k] for k in
                                                            ['pid', 'ppid', 'cpu_percent', 'rss_kib']}))
            vm = any(v == 'virtual-machine' for v in selected.values())
            # A visible Colima service without an attributed VM is incomplete accounting, not zero VM load.
            sample['state'] = 'unknown' if uncertain or (selected and not vm) else ('present' if vm else 'absent')
            sample['cpu_percent_total'] = sum(r['cpu_percent'] for r in sample['processes'])
            sample['rss_kib_total'] = sum(r['rss_kib'] for r in sample['processes'])
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as ex:
            sample['error'] = f'{type(ex).__name__}: {ex}'
        self.samples.append(sample)

    def report(self):
        complete = len(self.samples) >= 2 and all(s['state'] != 'unknown' for s in self.samples)
        return dict(schema='clasher.pretrain_v1.canvasdoc-load.v1', classification='shared-load',
                    complete=complete, cpu_unit='ps %CPU, 100 percent per logical core', rss_unit='KiB',
                    scope='canvasdoc VM host process including guest Docker work, Colima services and descendants',
                    vm_observed=any(s['state'] == 'present' for s in self.samples), clean_result=False,
                    idle_observed=complete and all(s.get('cpu_percent_total', 0) <= 5 for s in self.samples),
                    idle_cpu_percent_limit=5,
                    cpu_percent_peak=max((s.get('cpu_percent_total', 0) for s in self.samples), default=0),
                    rss_kib_peak=max((s.get('rss_kib_total', 0) for s in self.samples), default=0),
                    samples=self.samples)


def budget_result(total, load):
    passes = total['p95'] <= 30 and total['p99'] <= 50
    return dict(p95_limit_ms=30, p99_limit_ms=50, latency_passes=passes, clean_result=False,
                qualification=('telemetry-incomplete' if not load['complete'] else
                               'pass-under-shared-load' if passes else 'fail-under-shared-load'))

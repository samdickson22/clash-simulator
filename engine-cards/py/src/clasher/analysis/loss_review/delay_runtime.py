"""Task-owned throughput guard, idle scheduling, active clocks and end time."""
import json
import multiprocessing
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from .throughput_guard import PauseClock, ThroughputComparator, throughput_sample, gpu_task_cores, idle_and_pin


class GPUWatch:
    def __init__(self, path, enabled, config_path=None):
        self.path,self.enabled=Path(path),enabled
        self.config_path=Path(config_path or os.environ.get('CLASHER_THROUGHPUT_CONFIG', self.path.parents[2]/'guard-config.json'))
        self.done=threading.Event();self.thread=None;self.paused=set()
        self.clock=PauseClock(self.path.with_name('pause-clock.json'))
        self.allowed=set(os.sched_getaffinity(0));self.previous={};self.recent_cores={}

    def sample(self):
        try:
            values=subprocess.check_output(['nvidia-smi','--query-gpu=utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=5)
            gpu=min(map(int,values.strip().splitlines()))
            apps=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True,timeout=5)
            pids={int(p) for p in apps.splitlines() if p.strip().isdigit()}
        except (OSError,ValueError,subprocess.SubprocessError):gpu,pids=None,set()
        try:config=json.loads(self.config_path.read_text())
        except FileNotFoundError:config={}
        cores,self.previous=gpu_task_cores(pids,self.previous)
        now=time.monotonic()
        for core in cores:self.recent_cores[core]=now
        self.recent_cores={core:at for core,at in self.recent_cores.items() if now-at<30}
        metrics=[];pause=False
        for job in config.get('jobs',[]):
            if int(job['pid']) not in pids:continue
            try:
                sample=throughput_sample(job)
                comparator=ThroughputComparator(job['baseline'])
                bad=comparator.should_pause(sample['rate'] if sample else None)
                metrics.append(dict(pid=job['pid'],baseline=job['baseline'],sample=sample,below95=bad,
                                    baseline_samples=job.get('baseline_samples')))
                pause|=bad
            except (OSError,ValueError) as error:
                metrics.append(dict(pid=job['pid'],error=str(error),below95=False))
        # Idle GPUs and missing interval throughput are exempt. Utilization is receipt-only.
        return dict(gpu=gpu,gpu_compute_job_present=bool(pids),gpu_job_pids=sorted(pids),
                    throughput=metrics,should_pause=pause and bool(pids),excluded_gpu_cores=sorted(self.recent_cores))

    def prepare(self):
        sample=self.sample()
        pin=idle_and_pin([os.getpid()],sample['excluded_gpu_cores'],self.allowed)
        self.clock.set_paused(False)
        return pin

    def __enter__(self):
        if self.enabled:
            self.thread=threading.Thread(target=self.watch,daemon=True)
            self.thread.start()
        return self

    def watch(self):
        with self.path.open('a',buffering=1) as f:
            while not self.done.is_set():
                sample=self.sample()
                children={p.pid for p in multiprocessing.active_children() if p.is_alive()}
                try:pin=idle_and_pin(children|{os.getpid(),threading.get_native_id()},sample['excluded_gpu_cores'],self.allowed)
                except RuntimeError as error:pin=dict(error=str(error))
                stop=datetime.now(timezone.utc)>=datetime(2026,10,9,4,29,tzinfo=timezone.utc)
                should_pause=sample['should_pause'] and not stop
                # Publish before stopping workers; close the interval after resuming.
                if should_pause and children:self.clock.set_paused(True)
                for pid in children:
                    try:
                        if stop:
                            os.kill(pid,signal.SIGCONT);os.kill(pid,signal.SIGTERM)
                        elif should_pause and pid not in self.paused:
                            os.kill(pid,signal.SIGSTOP);self.paused.add(pid)
                        elif not should_pause and pid in self.paused:
                            os.kill(pid,signal.SIGCONT);self.paused.remove(pid)
                    except ProcessLookupError:self.paused.discard(pid)
                self.paused &= children
                if not self.paused:self.clock.set_paused(False)
                f.write(json.dumps(dict(utc=time.time(),**sample,paused=len(self.paused),workers=len(children),
                    cutoff=stop,policy='own-throughput-below95-v1',pin=pin,pause_clock=self.clock.snapshot()))+'\n')
                if stop:return
                self.done.wait(2)

    def __exit__(self,*args):
        self.done.set()
        if self.thread:self.thread.join(timeout=6)
        for pid in self.paused:
            try:os.kill(pid,signal.SIGCONT)
            except ProcessLookupError:pass
        self.clock.set_paused(False)

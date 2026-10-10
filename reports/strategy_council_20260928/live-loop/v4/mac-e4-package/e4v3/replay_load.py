"""Spawned paced TRAIN replay load, using the RUNBOOK capture/perception ABI."""
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback

from receipts import canonical
from tier_backend import setup_imports, validate_bundle


def load_worker(bundle, root, native, dry_run, ready, stop, output, load_cpu=None, preparing=False):
    try:
        import os
        if load_cpu is not None:
            os.sched_setaffinity(0, {load_cpu})
        manifest = validate_bundle(bundle, root, dry_run=dry_run, require_references=not preparing)
        setup_imports(root, native)
        # The already SHA-verified historical Ultralytics checkpoint contains
        # modules, rather than a state_dict. No unpinned checkpoint is admitted.
        os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1"
        os.environ["YOLO_AUTOINSTALL"] = "false"
        os.environ["YOLO_CONFIG_DIR"] = str(Path(output).parent / "offline-yolo")
        import socket
        original_connect = socket.socket.connect
        def offline_connect(sock, address):
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                raise OSError("Replay measurement forbids all Internet/client sockets")
            return original_connect(sock, address)
        socket.socket.connect = offline_connect
        import torch
        import cv2
        cv2.setNumThreads(1)
        from clasher.live.capture import admit_replay, replay_frames
        from clasher.live.perception import V3Fallback, V4Perception
        config = dict(manifest["load"]["config"])
        for key in ("body", "hud", "geometry", "checkpoint"):
            if key in config:
                config[key] = str(Path(bundle) / config[key])
        if manifest["load"]["kind"] == "v3-body-hud-only":
            sensor = V3Fallback(config)
        elif manifest["load"]["kind"] == "v4":
            launcher = Path(bundle) / manifest["load"]["owner_launcher"]
            spec = importlib.util.spec_from_file_location("e4v3_owner_launcher", launcher)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            selected = module.load_selection(Path(bundle) / manifest["load"]["selection"])
            from clasher.live.selection import AuthenticatedSelection
            if type(selected) is not AuthenticatedSelection:
                raise ValueError("V4 load requires authenticated selection")
            selected.check_sources()
            config["authenticated_selection"] = selected
            sensor = V4Perception(config)
        else:
            raise ValueError("Only real V3/V4 TRAIN replay load is allowed")
        sources = [admit_replay(Path(bundle) / path, Path(bundle) / manifest["load"]["split"])
                   for path in manifest["load"]["matches"]]
        if not sources:
            raise ValueError("No replay sources")
        count, lap = 0, 0
        with Path(output).open("x") as stream:
            while not stop.is_set():
                for source in sources:
                    for frame in replay_frames(source, stop, lambda *args, **kw: None):
                        frame = replace(frame, episode=frame.episode + "-load-" + str(lap))
                        if config["device"] == "mps":
                            torch.mps.synchronize()
                        start = time.monotonic()
                        sensor.step(frame)
                        if config["device"] == "mps":
                            torch.mps.synchronize()
                        finished = time.monotonic()
                        stream.write(canonical(dict(scope=manifest["load"]["label"], episode=frame.episode,
                            sequence=frame.sequence, produced=frame.produced_at, start=start, finished=finished,
                            service_ms=(finished-start)*1000, age_ms=(finished-frame.produced_at)*1000)) + "\n")
                        stream.flush()
                        count += 1
                        if count >= 16:
                            ready.set()
                lap += 1
    except BaseException:
        with Path(str(output) + ".error.json").open("x") as stream:
            stream.write(canonical(dict(error=traceback.format_exc())) + "\n")
        raise
    finally:
        stop.set()


def corpus_load_worker(bundle, root, native, ready, stop, cpus):
    """Linux-only background slot running the SAME frozen full corpus loop."""
    import os
    import platform
    from tier_backend import TierBackend
    manifest = validate_bundle(bundle,root,dry_run=True,require_references=False)
    if manifest["profile"] != "linux-dry-run":
        raise ValueError("Fleet references require FleetBackground and every pinned reporting slot")
    admit_background(platform.system(),platform.node(),os.getpriority(os.PRIO_PROCESS,0))
    os.sched_setaffinity(0, set(cpus))
    backend = TierBackend(bundle, root, native)
    try:
        while not stop.is_set():
            for row in backend.rows[:32]:
                if stop.is_set():
                    break
                backend.work(row, "K4")
                ready.set()
    finally:
        backend.close()


def admit_background(system, host, nice):
    if system != "Linux" or host not in ("127x03","127x05") or nice != 19:
        raise ValueError("Wrong background corpus host/priority for the pinned measurement profile")


class LinuxBackground:
    def __init__(self, bundle, root, native, output, load_cpu, corpus_cpus, preparing=False):
        import multiprocessing as mp
        context = mp.get_context("spawn")
        self.stop = context.Event()
        ready_replay, ready_corpus = context.Event(), context.Event()
        self.workers = [context.Process(target=load_worker, args=(bundle, root, native, True,
            ready_replay, self.stop, output, load_cpu, preparing)),
            context.Process(target=corpus_load_worker, args=(bundle, root, native, ready_corpus,
                                                           self.stop, corpus_cpus))]
        self.readies = (ready_replay, ready_corpus)

    def __enter__(self):
        for worker in self.workers:
            worker.start()
        deadline = time.monotonic()+getattr(self,"ready_timeout",120)
        try:
            while not all(ready.is_set() for ready in self.readies):
                self.check()
                if time.monotonic() > deadline:
                    raise RuntimeError("Background reference load failed to become ready")
                time.sleep(.1)
            time.sleep(2)
            return self
        except BaseException:
            self.close()
            raise

    def check(self):
        if self.stop.is_set() or any(not worker.is_alive() for worker in self.workers):
            raise RuntimeError("Reference/background corpus load died")

    def close(self):
        self.stop.set()
        errors = []
        for worker in self.workers:
            if worker.pid is None:
                continue
            worker.join(10)
            if worker.is_alive():
                worker.terminate()
                worker.join(10)
                errors.append("Background corpus failed to stop")
            if worker.exitcode != 0:
                errors.append("Background corpus exited with error")
        if errors:
            raise RuntimeError("; ".join(errors))

    def __exit__(self, *unused):
        self.close()


def fleet_corpus_worker(bundle, root, native, ready, stop, cpus, slot_index, errors=None):
    """One complete reporting slot, rotating all four own-tier corpora."""
    import os
    from fleet_profile import pinned_profile
    from receipts import TIERS
    from tier_backend import TierBackend
    backend=None
    try:
        manifest=validate_bundle(bundle,root,dry_run=True,require_references=False)
        _,_,(_,background,_) = pinned_profile(bundle,manifest)
        if list(cpus) not in background:
            raise ValueError("Background mask absent from pinned reporting slot layout")
        os.sched_setaffinity(0,set(cpus))
        backend=TierBackend(bundle,root,native)
        backend.search_cpus=list(cpus)
        lap=slot_index
        while not stop.is_set():
            order=TIERS[lap%4:]+TIERS[:lap%4]
            for offset in range(0,max(len(manifest["sets"]["speed"][t]) for t in TIERS),50):
                for tier in order:
                    for identity in manifest["sets"]["speed"][tier][offset:offset+50]:
                        if stop.is_set():return
                        backend.work(backend.by_id[identity],tier)
                        ready.set()
            lap+=1
    except BaseException:
        if errors is not None:
            import traceback
            errors.put(dict(slot=slot_index,error=traceback.format_exc()))
        raise
    finally:
        if backend is not None:backend.close()


class FleetBackground(LinuxBackground):
    """All other reporting slots; deliberately no perception on fleet references."""
    def __init__(self,bundle,root,native,masks):
        import multiprocessing as mp
        context=mp.get_context("spawn")
        self.stop=context.Event()
        self.errors=context.Queue()
        self.readies=[context.Event() for _ in masks]
        self.workers=[context.Process(target=fleet_corpus_worker,
            args=(bundle,root,native,ready,self.stop,mask,index,self.errors))
            for index,(mask,ready) in enumerate(zip(masks,self.readies))]
        self.ready_timeout=600

    def close(self):
        import sys
        preserving=sys.exc_info()[0] is not None
        try:super().close()
        except RuntimeError:
            if not preserving:raise

    def check(self):
        import queue
        if getattr(self,"check_external",None) is not None:
            self.check_external()
        try:
            error=self.errors.get_nowait()
        except queue.Empty:
            error=None
        if error is not None:
            # Keep the full child error; in particular exactness cannot become
            # a generic, repeatable worker crash during cleanup.
            raise RuntimeError("Fleet background failure: "+error["error"])
        if self.stop.is_set() or any(not worker.is_alive() for worker in self.workers):
            # A queue feeder may lag process exit; give the saved error a bounded
            # chance to arrive before declaring a typed process crash.
            try:
                error=self.errors.get(timeout=1.)
            except queue.Empty:
                error=None
            if error is not None:
                raise RuntimeError("Fleet background failure: "+error["error"])
            from fleet_validity import FleetTechnicalError
            raise FleetTechnicalError("crash","Reference/background corpus process died without an exactness error")

    def __exit__(self,kind,error,traceback_):
        if kind is None:
            try:self.check()
            except BaseException:
                try:self.close()
                except RuntimeError:pass
                raise
            self.close()
        else:
            try:self.close()
            except RuntimeError:pass

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
    fleet = manifest["profile"] == "fleet-reference"
    admit_background(platform.system(),platform.node(),os.getpriority(os.PRIO_PROCESS,0),fleet)
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


def admit_background(system, host, nice, fleet):
    hosts, priority = (("127x01","127x03","127x08"),10) if fleet else (("127x03","127x05"),19)
    if system != "Linux" or host not in hosts or nice != priority:
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
        deadline = time.monotonic()+120
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

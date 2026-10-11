"""NON-COUNTED Phase A preflight: v3-body-hud-only TRAIN replay perception on MPS, mirroring
e4v3 replay_load.load_worker's loop (offline socket guard, 1-thread cv2/torch, paced replay).
Measures processed FPS only; no search, no bundle, no counted receipt."""
import json, os, socket, sys, threading, time
from dataclasses import replace
from pathlib import Path
stage, root, out, seconds = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), float(sys.argv[4])
sys.path.insert(0, str(root / "src"))
os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1"; os.environ["YOLO_AUTOINSTALL"] = "false"
os.environ["YOLO_CONFIG_DIR"] = str(out / "offline-yolo")
orig = socket.socket.connect
def offline(sock, addr):
    if sock.family in (socket.AF_INET, socket.AF_INET6): raise OSError("offline preflight")
    return orig(sock, addr)
socket.socket.connect = offline
import torch, cv2
torch.set_num_threads(1); cv2.setNumThreads(1)
from clasher.live.capture import admit_replay, replay_frames
from clasher.live.perception import V3Fallback
cfg = json.loads((stage / "load-config.staged.json").read_text())
c = dict(cfg["config"])
for k in ("body", "hud", "geometry"): c[k] = str(stage / c[k])
sensor = V3Fallback(c)
sources = [admit_replay(stage / m, stage / cfg["split"]) for m in cfg["matches"]]
stop = threading.Event(); threading.Timer(seconds, stop.set).start()
rows = []; t0 = time.monotonic()
with (out / "perception.jsonl").open("x") as f:
    lap = 0
    while not stop.is_set():
        for s in sources:
            for fr in replay_frames(s, stop, lambda *a, **k: None):
                fr = replace(fr, episode=fr.episode + "-load-" + str(lap))
                torch.mps.synchronize(); a = time.monotonic(); sensor.step(fr); torch.mps.synchronize(); b = time.monotonic()
                r = dict(seq=fr.sequence, produced=fr.produced_at, start=a, finished=b, service_ms=(b-a)*1000, age_ms=(b-fr.produced_at)*1000)
                f.write(json.dumps(r) + "\n"); rows.append(r)
            if stop.is_set(): break
        lap += 1
elapsed = time.monotonic() - t0
warm = [r for r in rows if r["start"] - t0 > 10]
span = (warm[-1]["finished"] - warm[0]["start"]) if len(warm) > 1 else 0
svc = sorted(r["service_ms"] for r in warm)
q = lambda p: svc[min(len(svc)-1, int(p*len(svc)))] if svc else None
summary = dict(scope="NON-COUNTED Phase A preflight", device="mps", frames=len(rows), elapsed_s=elapsed,
               warm_frames=len(warm), warm_fps=len(warm)/span if span else None,
               service_ms=dict(p50=q(.5), p95=q(.95), p99=q(.99), max=svc[-1] if svc else None),
               max_age_ms=max((r["age_ms"] for r in warm), default=None))
(out / "summary.json").write_text(json.dumps(summary, indent=1)); print(json.dumps(summary))

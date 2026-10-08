#!/usr/bin/env python3
"""Short, isolated A6000 smoke checks; stdout is one JSON receipt, logs on stderr."""
from __future__ import annotations

import argparse
import contextlib
import datetime
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import traceback

BASE = Path('/mpac/sdicks02')
PROBES = ('imports', 'cuda', 'fp32', 'tf32', 'bf16', 'conv', 'transformer', 'dataloader', 'compile', 'yolo')
REQUIRED = set(PROBES) - {'compile'}


def configure():
    # Explicitly route caches that XDG_CACHE_HOME alone does not cover.
    for key, suffix in {
        'TMPDIR': 'tmp', 'XDG_CACHE_HOME': 'cache', 'TORCH_HOME': 'cache/torch',
        'HF_HOME': 'cache/hf', 'CUDA_CACHE_PATH': 'cache/cuda',
        'TORCHINDUCTOR_CACHE_DIR': 'cache/torchinductor', 'TRITON_CACHE_DIR': 'cache/triton',
        'MPLCONFIGDIR': 'cache/matplotlib', 'YOLO_CONFIG_DIR': 'tmp/clasher-gpu-yolo-config',
    }.items():
        path = BASE / suffix
        path.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(path)
    os.environ.update(PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='4', MKL_NUM_THREADS='4',
                      OPENBLAS_NUM_THREADS='1', YOLO_AUTOINSTALL='false', MPLBACKEND='Agg',
                      CUBLAS_WORKSPACE_CONFIG=':4096:8')
    # Ultralytics 8.1.24 reloads its own trusted full-module checkpoints.
    # Explicit weights_only=True calls in the v3 trainer remain unaffected.
    os.environ['TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD'] = '1'
    tempfile.tempdir = str(BASE / 'tmp')
    current = os.getpriority(os.PRIO_PROCESS, 0)
    if current < 10:
        os.nice(10 - current)


def smi():
    return subprocess.check_output([
        'nvidia-smi', '--query-gpu=name,driver_version,memory.used,utilization.gpu',
        '--format=csv,noheader,nounits'], text=True).strip()


def probe(name):
    import torch
    from torch import nn
    torch.set_num_threads(4)
    torch.manual_seed(261007)
    if name == 'imports':
        root = Path(os.environ.get('CLASHER_ROOT', BASE / 'repos/clasher'))
        sys.path[:0] = [str(root / 'src'), str(root / 'scripts')]
        modules = ['cv2', 'numpy', 'yaml', 'torchvision', 'ultralytics',
                   'train_l1_stream_v3', 'train_l1_events_v2', 'train_l1_perception']
        for module in modules:
            importlib.import_module(module)
        return {'modules': modules, 'repo': str(root)}
    assert torch.cuda.is_available(), 'CUDA unavailable'
    torch.cuda.set_device(0)
    torch.cuda.reset_peak_memory_stats()
    if name == 'cuda':
        import torchvision
        boxes = torch.tensor([[0., 0., 10., 10.], [1., 1., 9., 9.]], device='cuda')
        assert torchvision.ops.nms(boxes, torch.tensor([.9, .8], device='cuda'), .5).tolist() == [0]
        return {'is_available': True, 'device': torch.cuda.get_device_name(),
                'capability': list(torch.cuda.get_device_capability()),
                'bf16_supported_reported': torch.cuda.is_bf16_supported(),
                'cudnn': torch.backends.cudnn.version(), 'torchvision_cuda_nms': True}
    if name in ('fp32', 'tf32', 'bf16'):
        n, steps = 8192, 10
        torch.backends.cuda.matmul.allow_tf32 = name == 'tf32'
        a, b = (torch.randn(n, n, device='cuda') for _ in range(2))
        def multiply():
            with torch.autocast('cuda', dtype=torch.bfloat16, enabled=name == 'bf16'):
                return a @ b
        for _ in range(3):
            c = multiply()
        torch.cuda.synchronize()
        start, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
        start.record()
        for _ in range(steps):
            c = multiply()
        end.record()
        end.synchronize()
        seconds = start.elapsed_time(end) / 1000
        reference = a[:8].cpu().double() @ b[:, :8].cpu().double()
        sample = c[:8, :8].double().cpu()
        relative = ((sample - reference).norm() / reference.norm()).item()
        assert math.isfinite(relative) and relative < {'fp32': 1e-4, 'tf32': .005, 'bf16': .03}[name]
        return {'n': n, 'steps': steps, 'seconds': seconds, 'tflops': 2 * n**3 * steps / seconds / 1e12,
                'output_dtype': str(c.dtype), 'relative_l2_error': relative}
    if name in ('conv', 'transformer'):
        if name == 'conv':
            from torchvision.models import resnet18
            model = resnet18(num_classes=10).cuda().train()
            x = torch.randn(16, 3, 128, 128, device='cuda')
            target = torch.randint(10, (16,), device='cuda')
        else:
            model = nn.TransformerEncoder(nn.TransformerEncoderLayer(
                512, 8, dim_feedforward=2048, dropout=0., batch_first=True), 6).cuda().train()
            x = torch.randn(8, 128, 512, device='cuda')
            target = torch.randn_like(x)
        opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
        scaler = torch.amp.GradScaler('cuda', enabled=name == 'transformer')
        first = next(model.parameters())
        before = first.detach().clone()
        def step():
            opt.zero_grad(set_to_none=True)
            with torch.autocast('cuda', dtype=torch.float16, enabled=name == 'transformer'):
                pred = model(x)
                loss = nn.functional.cross_entropy(pred, target) if name == 'conv' else nn.functional.mse_loss(pred, target)
            assert torch.isfinite(loss).item(), 'nonfinite loss'
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            return loss.item()
        for _ in range(3):
            step()
        torch.cuda.synchronize()
        started = time.perf_counter()
        losses = [step() for _ in range(10)]
        torch.cuda.synchronize()
        seconds = time.perf_counter() - started
        assert not torch.equal(first, before), 'parameters did not update'
        return {'steps': 10, 'seconds': seconds, 'ms_per_step': seconds * 100,
                'loss_first': losses[0], 'loss_last': losses[-1], 'amp': name == 'transformer',
                'parameters': sum(p.numel() for p in model.parameters()),
                'input_shape': list(x.shape), 'layers': 6 if name == 'transformer' else None}
    if name == 'dataloader':
        class Images(torch.utils.data.Dataset):
            def __len__(self):
                return 32 * 72
            def __getitem__(self, index):
                return torch.randint(256, (3, 224, 224), dtype=torch.uint8), index
        loader = torch.utils.data.DataLoader(Images(), batch_size=32, num_workers=16,
            pin_memory=True, prefetch_factor=2, multiprocessing_context='fork')
        started = time.perf_counter()
        iterator = iter(loader)
        for _ in range(8):
            images, _ = next(iterator)
            images.to('cuda', non_blocking=True)
        torch.cuda.synchronize()
        startup = time.perf_counter() - started
        started = time.perf_counter()
        for images, _ in iterator:
            transferred = images.to('cuda', non_blocking=True)
        torch.cuda.synchronize()
        seconds = time.perf_counter() - started
        assert transferred.is_cuda
        return {'workers': 16, 'batch_size': 32, 'shape': [3, 224, 224], 'dtype': 'uint8',
                'startup_and_8_warmup_batches_seconds': startup, 'measured_batches': 64,
                'seconds': seconds, 'images_per_second': 2048 / seconds,
                'includes_pinned_host_to_device': True, 'synthetic_not_disk_io': True}
    if name == 'compile':
        def pointwise(x):
            return (x.sin() + x.cos()).square()
        x = torch.randn(1024, 1024, device='cuda', requires_grad=True)
        compiled = torch.compile(pointwise, backend='inductor', fullgraph=True)
        started = time.perf_counter()
        actual = compiled(x)
        torch.testing.assert_close(actual, pointwise(x))
        actual.mean().backward()
        assert torch.isfinite(x.grad).all().item()
        torch.cuda.synchronize()
        return {'backend': 'inductor', 'forward_and_backward': True,
                'first_compile_seconds': time.perf_counter() - started}
    if name == 'yolo':
        import numpy as np
        from PIL import Image, ImageDraw
        import yaml
        # No pretrained weights, AMP auto-check model, telemetry or external downloads.
        original_connect = socket.socket.connect
        def offline_connect(sock, address):
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                import ipaddress
                if not ipaddress.ip_address(address[0]).is_loopback:
                    raise OSError('synthetic GPU check forbids external network connections')
            return original_connect(sock, address)
        socket.socket.connect = offline_connect
        from ultralytics import YOLO
        from ultralytics.utils import SETTINGS
        SETTINGS.update({k: False for k in ('sync', 'wandb', 'comet', 'mlflow', 'clearml',
                                           'neptune', 'hub', 'dvc', 'tensorboard')})
        work = Path(tempfile.mkdtemp(prefix='clasher-gpu-yolo-', dir=BASE / 'tmp'))
        rng = np.random.default_rng(261007)
        for split, count in [('train', 24), ('val', 8)]:
            for kind in ('images', 'labels'):
                (work / kind / split).mkdir(parents=True)
            for i in range(count):
                image = Image.fromarray(rng.integers(0, 35, (320, 320, 3), dtype=np.uint8))
                x, y = rng.integers(32, 208, 2).tolist()
                ImageDraw.Draw(image).rectangle((x, y, x+64, y+64), fill=(220, 80, 50))
                image.save(work / 'images' / split / f'{i:03}.jpg')
                (work / 'labels' / split / f'{i:03}.txt').write_text(
                    f'0 {(x+32)/320} {(y+32)/320} 0.2 0.2\n')
        data = work / 'data.yaml'
        data.write_text(yaml.safe_dump({'path': str(work), 'train': 'images/train',
                                       'val': 'images/val', 'names': {0: 'rectangle'}}))
        model = YOLO('yolov8s.yaml')
        epoch = {}
        def epoch_start(trainer):
            torch.cuda.synchronize()
            epoch['start'] = time.perf_counter()
        def epoch_end(trainer):
            torch.cuda.synchronize()
            epoch['train_epoch_seconds'] = time.perf_counter() - epoch.pop('start')
            assert torch.isfinite(trainer.tloss).all().item()
            epoch['train_loss'] = trainer.tloss.tolist()
        model.add_callback('on_train_epoch_start', epoch_start)
        model.add_callback('on_train_epoch_end', epoch_end)
        started = time.perf_counter()
        model.train(data=str(data), epochs=1, imgsz=320, batch=4, device=0, workers=2,
                    pretrained=False, amp=False, plots=False, save=True, cache=False,
                    project=str(work), name='run', exist_ok=False, optimizer='AdamW',
                    mosaic=0., deterministic=True, seed=261007, verbose=False)
        torch.cuda.synchronize()
        assert (work / 'run/weights/last.pt').is_file()
        assert (work / 'run/results.csv').is_file()
        return {**epoch, 'train_validate_save_seconds': time.perf_counter() - started,
                'train_images': 24, 'val_images': 8, 'batch_size': 4, 'image_size': 320,
                'amp': False, 'pretrained': False, 'model': 'YOLOv8s', 'artifacts': str(work)}
    raise ValueError(name)


def worker(name):
    started = time.perf_counter()
    result = {'status': 'fail'}
    with contextlib.redirect_stdout(sys.stderr):
        try:
            result = {'status': 'pass', **probe(name)}
        except Exception as exc:
            result.update(error=f'{type(exc).__name__}: {exc}', traceback=traceback.format_exc())
        finally:
            torch = sys.modules.get('torch')
            if torch is not None and torch.cuda.is_initialized():
                result['peak_allocated_mib'] = torch.cuda.max_memory_allocated() / 1024**2
                result['peak_reserved_mib'] = torch.cuda.max_memory_reserved() / 1024**2
            result['process_seconds'] = time.perf_counter() - started
    print(json.dumps(result, allow_nan=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--only', nargs='+', choices=PROBES, default=list(PROBES))
    parser.add_argument('--probe', choices=PROBES, help=argparse.SUPPRESS)
    parser.add_argument('--timeout', type=int, default=120, help='per-probe timeout in seconds')
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    if args.output and not args.output.resolve().is_relative_to(BASE / 'tmp'):
        parser.error('--output must live under /mpac/sdicks02/tmp')
    if socket.gethostname().split('.')[0] not in ('127x01', '127x04', '127x07', '127x08'):
        parser.error('GPU jobs are restricted to 127x01/04/07/08')
    configure()
    if args.probe:
        worker(args.probe)
        return
    receipt = {'host': socket.gethostname(), 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'python': sys.version, 'executable': sys.executable, 'nice': os.getpriority(os.PRIO_PROCESS, 0),
               'versions': {p: importlib.metadata.version(p) for p in
                            ('torch', 'torchvision', 'ultralytics', 'numpy', 'opencv-python', 'triton')},
               'gpu_before': smi(), 'checks': {}}
    for name in args.only:
        users = subprocess.check_output(['who'], text=True).strip()
        if users:
            receipt['checks'][name] = {'status': 'skip', 'reason': 'occupied host; keep lab responsive', 'who': users}
            continue
        print(f'[{receipt["host"]}] {name}', file=sys.stderr, flush=True)
        process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--probe', name],
                                   stdout=subprocess.PIPE, stderr=sys.stderr, text=True, start_new_session=True)
        try:
            output, _ = process.communicate(timeout=args.timeout)
            result = json.loads(output)
            if process.returncode:
                result.update(status='fail', returncode=process.returncode)
        except subprocess.TimeoutExpired:
            # This process group belongs solely to the subprocess just launched above.
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
            result = {'status': 'fail', 'error': f'timeout after {args.timeout}s'}
        except ValueError as exc:
            result = {'status': 'fail', 'error': str(exc), 'returncode': process.returncode,
                      'stdout_tail': output[-2000:]}
        receipt['checks'][name] = result
    receipt['gpu_after'] = smi()
    receipt['all_requested_required_passed'] = all(
        receipt['checks'][p]['status'] == 'pass' for p in args.only if p in REQUIRED)
    receipt['full_required_suite_passed'] = REQUIRED <= receipt['checks'].keys() and all(
        receipt['checks'][p]['status'] == 'pass' for p in REQUIRED)
    encoded = json.dumps(receipt, indent=2, allow_nan=False) + '\n'
    if args.output:
        output = args.output.resolve()
        if not output.is_relative_to(BASE / 'tmp'):
            parser.error('--output must live under /mpac/sdicks02/tmp')
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(encoded)
        temporary.replace(output)
    print(encoded, end='')
    sys.exit(0 if receipt['all_requested_required_passed'] else 1)


if __name__ == '__main__':
    main()

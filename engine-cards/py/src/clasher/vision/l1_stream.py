"""Bounded, latest-frame H.264 capture. Decode timestamps are not render ticks."""
from __future__ import annotations

import os
import subprocess
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

from clasher.vision.l1 import public_pixels


@dataclass(frozen=True)
class ScreenFrame:
    sequence: int
    decoded_at: float
    pixels: np.ndarray
    produced_at: float | None = None


class ScreenStream:
    """One adb child, no saved raw media, and one buffered sanitized frame.

    Consumers can miss frames; sequence gaps make this visible. A timestamp
    barrier rejects old decoded frames but cannot prove compositor freshness.
    Android's bounded screenrecord sessions restart without retaining video.
    """

    def __init__(self, adb, serial, *, session_seconds=120):
        self.command = [str(adb), '-s', serial, 'exec-out', 'screenrecord',
                        '--output-format=h264', '--size', '540x1140',
                        '--bit-rate', '4000000', '--time-limit', str(session_seconds), '-']
        self.condition = threading.Condition()
        self.stop = threading.Event()
        self.latest = None
        self.error = None
        self.process = None
        self.sequence = 0
        self.restarts = 0
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        import av
        try:
            while not self.stop.is_set():
                decoder = av.CodecContext.create('h264', 'r')
                decoder.thread_count = 1
                with self.condition:
                    if self.stop.is_set():
                        return
                    self.process = subprocess.Popen(self.command, stdout=subprocess.PIPE,
                                                    stderr=subprocess.DEVNULL, bufsize=0)
                    process = self.process
                try:
                    while not self.stop.is_set():
                        raw = os.read(process.stdout.fileno(), 65536)
                        if not raw:
                            break
                        for packet in decoder.parse(raw):
                            for frame in decoder.decode(packet):
                                decoded_at = time.perf_counter()
                                image = frame.to_ndarray(format='bgr24')
                                if image.shape != (1140, 540, 3):
                                    raise ValueError(f'Unexpected stream dimensions: {image.shape}')
                                # Reuse the audited source-resolution sanitizer.
                                pixels = public_pixels(cv2.resize(image, (1080, 2280),
                                                                  interpolation=cv2.INTER_NEAREST))
                                with self.condition:
                                    self.sequence += 1
                                    self.latest = ScreenFrame(self.sequence, decoded_at, pixels)
                                    self.condition.notify_all()
                finally:
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    process.stdout.close()
                if not self.stop.is_set():
                    if process.returncode != 0:
                        raise RuntimeError(f'screenrecord exited {process.returncode}')
                    self.restarts += 1
        except BaseException as exc:
            with self.condition:
                self.error = exc
                self.condition.notify_all()

    def read(self, *, after_sequence=0, after_time=0.0, timeout=15):
        deadline = time.perf_counter() + timeout
        with self.condition:
            while True:
                if self.error is not None:
                    raise RuntimeError('Screen stream failed') from self.error
                if (self.latest is not None and self.latest.sequence > after_sequence
                        and self.latest.decoded_at >= after_time):
                    return self.latest
                remaining = deadline - time.perf_counter()
                if remaining <= 0 or self.stop.is_set():
                    raise TimeoutError('No fresh decoded screen frame')
                self.condition.wait(remaining)

    def close(self):
        with self.condition:
            self.stop.set()
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
            self.condition.notify_all()
        self.thread.join(timeout=8)
        if self.thread.is_alive():
            raise RuntimeError('Owned screen stream did not stop')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class GrpcScreenStream(ScreenStream):
    """RGB screenshot stream with the emulator's frame-generation timestamp.

    Generated protobuf bindings must come from the installed emulator SDK.
    Its timestamp describes screenshot production, not a native game tick.
    """

    def __init__(self, port, proto_dir, discovery):
        import importlib.util
        from pathlib import Path
        import grpc
        path = Path(proto_dir)/'emulator_controller_pb2.py'
        spec = importlib.util.spec_from_file_location('l1_emulator_pb2', path)
        pb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pb)
        settings = dict(line.strip().split('=', 1) for line in Path(discovery).read_text().splitlines()
                        if '=' in line and not line.lstrip().startswith('#'))
        token = settings.get('grpc.token')
        if not token:
            raise ValueError('Owned emulator gRPC token missing')
        if int(settings['grpc.port']) != int(port):
            raise ValueError('Owned emulator gRPC port mismatch')
        self.channel = grpc.insecure_channel(f'127.0.0.1:{int(port)}', options=[
            ('grpc.max_receive_message_length', 16*1024*1024)])
        method = self.channel.unary_stream('/android.emulation.control.EmulatorController/streamScreenshot',
            request_serializer=pb.ImageFormat.SerializeToString, response_deserializer=pb.Image.FromString)
        self.rpc = method(pb.ImageFormat(format=pb.ImageFormat.RGB888, width=1080, height=2280),
                          metadata=(('authorization', 'Bearer '+token),))
        self.condition = threading.Condition()
        self.stop = threading.Event()
        self.latest = self.error = None
        self.sequence = self.restarts = 0
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            for frame in self.rpc:
                if self.stop.is_set():
                    break
                if not frame.image:
                    continue
                if (frame.format.width, frame.format.height) != (1080, 2280):
                    raise ValueError('Unexpected gRPC image dimensions')
                rgb = np.frombuffer(frame.image, np.uint8).reshape(2280, 1080, 3)
                bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                safe = public_pixels(bgr)
                with self.condition:
                    self.sequence += 1
                    self.latest = ScreenFrame(self.sequence, time.perf_counter(), safe,
                                              frame.timestampUs / 1e6)
                    self.condition.notify_all()
        except BaseException as exc:
            if not self.stop.is_set():
                with self.condition:
                    self.error = exc
                    self.condition.notify_all()

    def close(self):
        self.stop.set()
        self.rpc.cancel()
        self.channel.close()
        with self.condition:
            self.condition.notify_all()
        self.thread.join(timeout=8)
        if self.thread.is_alive():
            raise RuntimeError('Owned gRPC stream did not stop')

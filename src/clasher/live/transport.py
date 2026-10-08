"""One producer/consumer raw-pixel ring and bounded latest-value queues."""
from queue import Empty, Full
import time


class ObservationWindow:
    """Latest public frame plus bounded, unacknowledged one-shot events."""
    def __init__(self, capacity=4096):
        self.capacity = capacity
        self.pending = []

    def message(self, observation, acknowledged):
        from dataclasses import replace
        self.pending = [(seq, event) for seq, event in self.pending if seq > acknowledged]
        self.pending.extend((observation.frame.sequence, event) for event in observation.events)
        if len(self.pending) > self.capacity:
            raise RuntimeError('Unacknowledged perception events exceeded bound')
        return replace(observation, frame=replace(observation.frame, pixels=None),
                       events=tuple(event for _, event in self.pending))


class FrameRing:
    """64 public frames. Writer never waits on the reader or a full queue.

    Slots are sequence-checked under short locks. Overflow evicts the oldest;
    a concurrent reader causes that incoming frame to be dropped instead.
    Consumer owns a pixel copy, so an overwrite cannot tear an inference input.
    """
    def __init__(self, ctx, capacity=64, shape=(1140, 540, 3)):
        import math
        self.capacity, self.shape = capacity, shape
        self.size = math.prod(shape)
        self.pixels = ctx.RawArray('B', capacity*self.size)
        self.sequences = ctx.RawArray('q', [-1]*capacity)
        self.stamps = ctx.RawArray('d', capacity*3)
        self.locks = [ctx.Lock() for _ in range(capacity)]
        self.latest = ctx.RawValue('q', -1)
        self.contention_drops = ctx.RawValue('q', 0)

    def write(self, frame):
        import numpy as np
        if frame.pixels.shape != self.shape or frame.pixels.dtype != np.uint8:
            raise ValueError('Ring requires sanitized uint8 BGR pixels')
        seq = frame.sequence
        slot = seq % self.capacity
        if not self.locks[slot].acquire(False):
            self.contention_drops.value += 1
            self.latest.value = seq
            return False
        try:
            np.frombuffer(self.pixels, np.uint8).reshape(self.capacity, *self.shape)[slot] = frame.pixels
            self.stamps[slot*3:slot*3+3] = (frame.produced_at, frame.received_at, frame.timestamp_ms)
            self.sequences[slot] = seq
            self.latest.value = seq
        finally:
            self.locks[slot].release()
        return True

    def read(self, after, episode):
        import numpy as np
        from .contracts import Frame
        newest = self.latest.value
        if newest <= after:
            return None, after, 0
        seq = max(after+1, newest-self.capacity+1)
        missed = seq-after-1
        slot = seq % self.capacity
        if not self.locks[slot].acquire(False):
            return None, after, 0
        try:
            if self.sequences[slot] != seq:
                return None, seq, missed+1
            produced, received, media = self.stamps[slot*3:slot*3+3]
            pixels = np.frombuffer(self.pixels, np.uint8).reshape(self.capacity, *self.shape)[slot].copy()
        finally:
            self.locks[slot].release()
        return Frame(episode, seq, produced, received, media, pixels), seq, missed


def put_latest(queue, value):
    """Drop oldest under backpressure; never block a producing stage."""
    for _ in range(3):
        try:
            queue.put_nowait(value)
            return True
        except Full:
            try:
                queue.get_nowait()
            except Empty:
                # multiprocessing feeder may not yet have exposed the old item.
                time.sleep(0)
    return False


def drain_latest(queue, previous=None):
    while True:
        try:
            previous = queue.get_nowait()
        except Empty:
            return previous


def should_drop(sequence, age_seconds):
    # Irregular steps retain original timestamps; never reset temporal history.
    return age_seconds >= .4 or (age_seconds >= .150 and sequence % 2 == 1)

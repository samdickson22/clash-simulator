from __future__ import annotations

import queue
import threading
import time
from typing import Dict, List, Optional

import numpy as np
import torch

from .model import MaskedPolicyValueNet


class InferenceServer:
    """Batched policy inference server for actor requests."""

    def __init__(
        self,
        *,
        model: MaskedPolicyValueNet,
        device: torch.device,
        request_queue,
        response_queues: Dict[int, object],
        max_batch: int,
        max_wait_ms: float,
    ) -> None:
        self.model = model
        self.device = device
        self.request_queue = request_queue
        self.response_queues = response_queues
        self.max_batch = max(1, int(max_batch))
        self.max_wait_s = max(0.0, float(max_wait_ms) / 1000.0)
        self.stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="inference-server", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def sync_weights_from(self, source_model: MaskedPolicyValueNet) -> None:
        with self._lock:
            self.model.load_state_dict(source_model.state_dict())
            self.model.eval()

    def _run(self) -> None:
        self.model.eval()
        while not self.stop_event.is_set():
            try:
                first = self.request_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            except Exception:
                break

            pending: List[dict] = [first]
            start = time.perf_counter()
            while len(pending) < self.max_batch:
                remaining = self.max_wait_s - (time.perf_counter() - start)
                if remaining <= 0.0:
                    break
                try:
                    pending.append(self.request_queue.get(timeout=remaining))
                except queue.Empty:
                    break
                except Exception:
                    break

            boards = np.concatenate([req["boards"] for req in pending], axis=0)
            huds = np.concatenate([req["huds"] for req in pending], axis=0)
            masks = np.concatenate([req["masks"] for req in pending], axis=0)

            with self._lock, torch.no_grad():
                board_t = torch.as_tensor(boards, dtype=torch.float32, device=self.device)
                hud_t = torch.as_tensor(huds, dtype=torch.float32, device=self.device)
                mask_t = torch.as_tensor(masks, dtype=torch.bool, device=self.device)
                action_t, log_prob_t, value_t, _ = self.model.act(
                    board=board_t,
                    hud=hud_t,
                    action_mask=mask_t,
                    deterministic=False,
                )

            actions = action_t.detach().cpu().numpy().astype(np.int64)
            log_probs = log_prob_t.detach().cpu().numpy().astype(np.float32)
            values = value_t.detach().cpu().numpy().astype(np.float32)

            offset = 0
            for req in pending:
                n = int(req["boards"].shape[0])
                actor_id = int(req["actor_id"])
                response = {
                    "request_id": int(req["request_id"]),
                    "actions": actions[offset : offset + n],
                    "log_probs": log_probs[offset : offset + n],
                    "values": values[offset : offset + n],
                }
                offset += n
                try:
                    self.response_queues[actor_id].put(response)
                except Exception:
                    # Actor may have terminated; ignore.
                    pass

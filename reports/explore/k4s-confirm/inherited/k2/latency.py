"""Honest full-decision latency on the engine's real 20Hz clock."""
from dataclasses import replace
import math

def apply_lateness(channel, waits, available_at, actor, tick, elapsed, deadline):
    overrun = max(0., elapsed-deadline)
    delayed_ticks = math.ceil(overrun*20)
    if delayed_ticks:
        # The selected slot is reserved at the observation tick; delay execution.
        channel.pending[:] = [replace(c, due=c.due+delayed_ticks)
                              if c.submitted == tick else c for c in channel.pending]
        if waits[actor] > tick:
            waits[actor] += delayed_ticks
        available_at[actor] = max(available_at[actor], tick+delayed_ticks)
    return overrun, delayed_ticks

"""Offline timestamp calibration. Native timing never enters perception."""
from __future__ import annotations

import numpy as np


def fit_timing(requests, frames):
    start = next(i for i, r in enumerate(requests) if r['command']=='resume')
    observations = [r for r in requests[start+1:] if r['command']=='observe']
    if len(observations)<40 or len(frames)<40:
        raise ValueError('Insufficient continuous timing samples')
    t = np.array([(r['start_ns']+r['end_ns'])/2e9 for r in observations])
    ticks = np.array([r['result']['tick'] for r in observations], dtype=float)
    if np.any(np.diff(t)<=0) or np.any(np.diff(ticks)<0):
        raise ValueError('Native time is not monotone')
    origin = float(t[0])
    # Alternate blocks of one second, so validation contains whole unseen spans.
    train = ((t-origin).astype(int)%2)==0
    slope, offset = np.polyfit(t[train]-origin, ticks[train], 1)
    residual = (ticks[~train]-(offset+slope*(t[~train]-origin)))*50
    local_train = np.arange(len(t))%2==0
    local_test = ~local_train
    local_test[np.flatnonzero(local_train)[-1]:] = False
    local_residual = (ticks[local_test]-np.interp(t[local_test],t[local_train],ticks[local_train]))*50
    production = np.array([r['produced_epoch_s']+(
        (r['mono_before_ns']+r['mono_after_ns'])/2-r['wall_ns'])/1e9 for r in frames])
    # Every clock edge is interval censored by its two adjacent frames.
    edges = []
    clock_base = 180 if ticks[0]<=3600 else 300
    last_visible_clock=frames[0]['clock']
    for i in range(1, len(frames)):
        a, b = frames[i-1], frames[i]
        if b.get('clock_phase')=='overtime':clock_base=300
        if last_visible_clock is not None and b['clock'] is not None and b['clock']>last_visible_clock+60:
            clock_base=300
        if b['clock'] is not None:last_visible_clock=b['clock']
        if (a['clock'] is None or b['clock'] is None or
            b['clock']!=a['clock']-1 or min(a['clock_confidence'], b['clock_confidence'])<.95):
            continue
        tick = (clock_base-b['clock'])*20+1
        if not ticks[0]<tick<ticks[-1]:
            continue
        # First observation at/above the edge and last below bracket its crossing.
        j = int(np.searchsorted(ticks, tick))
        native_lo = observations[j-1]['start_ns']/1e9
        native_hi = observations[j]['end_ns']/1e9
        edges.append(dict(index=i, tick=tick,
            lag_low_ms=(production[i-1]-native_hi)*1000,
            lag_high_ms=(production[i]-native_lo)*1000))
    if len(edges)<4:
        raise ValueError('Insufficient independently visible clock transitions')
    fit_edges = edges[::2]
    check_edges = edges[1::2]
    lag = float(np.median([(e['lag_low_ms']+e['lag_high_ms'])/2 for e in fit_edges]))
    edge_residual = np.array([max(e['lag_low_ms']-lag, lag-e['lag_high_ms'], 0.) for e in check_edges])
    midpoint_residual = np.array([(e['lag_low_ms']+e['lag_high_ms'])/2-lag for e in check_edges])
    widths = np.array([e['lag_high_ms']-e['lag_low_ms'] for e in check_edges])
    # This measures interval-compatible residual, not hidden compositor ticks.
    bound = float(max(max(abs(residual)), max(edge_residual+widths/2)))
    return dict(schema='clasher.l1.timing.v3', origin_mono_s=origin,
        offset_ticks=float(offset), ticks_per_second=float(slope),
        drift_ppm=float((slope/20-1)*1e6), observations=len(observations), frames=len(frames),
        native_validation_residual_p95_ms=float(np.quantile(abs(residual),.95)),
        native_validation_residual_max_ms=float(max(abs(residual))),
        native_validation_residual_p95_ticks=float(np.quantile(abs(residual),.95)/50),
        native_local_validation_p95_ms=float(np.quantile(abs(local_residual),.95)),
        native_local_validation_max_ms=float(max(abs(local_residual))),
        clock_lag_ms=lag, clock_validation_edges=len(check_edges),
        clock_interval_residual_p95_ms=float(np.quantile(edge_residual,.95)),
        clock_interval_residual_max_ms=float(max(edge_residual)),
        clock_midpoint_residual_p95_ms=float(np.quantile(abs(midpoint_residual),.95)),
        clock_interval_width_p95_ms=float(np.quantile(widths,.95)),
        empirical_bound_ms=bound, empirical_bound_ticks=bound/50,
        fps=float((len(frames)-1)/(production[-1]-production[0])),
        screenshot_transport_p95_ms=float(np.quantile([
            (r['received_mono_s']-p)*1000 for r,p in zip(frames,production)],.95)),
        clock_edges=edges, exact_render_tick_certified=False,
        limitation='Clock edges constrain whole seconds. The residual is a cross-validated empirical timing estimate, not a per-frame compositor fence.')

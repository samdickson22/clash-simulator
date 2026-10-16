"""Own-HUD action permission, separate from identity and model features (s40 API v1).

No engine, model, clocks or capture APIs. The producer attests current frame/UI
freshness; consumers compare its opaque capture ID and exact current poll tick.
"""
from dataclasses import dataclass, replace
import numpy as np

WAIT = 2304


@dataclass(frozen=True)
class SlotPermission:
    allowed: tuple[bool, bool, bool, bool]
    capture_id: str
    poll_tick: int
    reasons: tuple[str, str, str, str]


def check_mode(mode):
    if type(mode) is not str or mode not in ('legacy', 'required'):
        raise ValueError('slot_permission_mode must be legacy or required')
    return mode


def permission_state(source):
    """None permission means unrestricted ONLY in legacy mode; errors deny all."""
    try:
        mode = getattr(source, 'slot_permission_mode', 'legacy')
        p = getattr(source, 'slot_permission', None)
        if type(mode) is str and mode == 'metadata_exception':
            return (False,) * 4, dict(status='metadata_exception')
        if type(mode) is not str or mode not in ('legacy', 'required'):
            return (False,) * 4, dict(status='invalid_mode')
        if p is None:
            return (None, None) if mode == 'legacy' else ((False,) * 4, dict(status='missing'))
        if type(p) is not SlotPermission:
            return (False,) * 4, dict(status='malformed')
        if (type(p.allowed) is not tuple or len(p.allowed) != 4
                or any(type(v) is not bool for v in p.allowed)
                or type(p.reasons) is not tuple or len(p.reasons) != 4
                or any(type(v) is not str or not 0 < len(v) <= 128 for v in p.reasons)
                or type(p.capture_id) is not str or not 0 < len(p.capture_id) <= 256
                or type(p.poll_tick) is not int or p.poll_tick < 0):
            return (False,) * 4, dict(status='malformed')
        expected_id = getattr(source, 'slot_permission_capture_id', None)
        expected_tick = getattr(source, 'slot_permission_poll_tick', None)
        if (type(expected_id) is not str or not 0 < len(expected_id) <= 256
                or type(expected_tick) is not int or expected_tick < 0):
            return (False,) * 4, dict(status='missing_current_capture')
        if p.capture_id != expected_id or p.poll_tick != expected_tick:
            return (False,) * 4, dict(status='stale')
        return p.allowed, dict(status='current', allowed=p.allowed, capture_id=p.capture_id,
                               poll_tick=p.poll_tick, reasons=p.reasons)
    except Exception:
        return (False,) * 4, dict(status='metadata_exception')


def native_request(request):
    """Strip only control metadata for the unchanged model-feature legality mask."""
    return replace(request, slot_permission=None, slot_permission_mode='legacy',
                   slot_permission_capture_id=None, slot_permission_poll_tick=None)


def eligibility_mask(packet):
    """Policy dictionary carries native model mask plus optional choice-only mask."""
    native = np.asarray(packet['action_mask'], dtype=np.bool_)
    candidate = packet.get('eligibility_mask')
    if candidate is None:
        return native
    candidate = np.asarray(candidate)
    if candidate.dtype != np.bool_ or candidate.shape != native.shape:
        out = np.zeros_like(native); out[WAIT] = bool(native[WAIT]); return out
    return native & candidate


def bind_view(view, mode):
    """Pin session mode and actual poll tick on a private metadata-only packet."""
    check_mode(mode)
    source = view.reserved.packet
    fields = metadata_fields(source)
    source_mode = fields['slot_permission_mode']
    valid_mode = type(source_mode) is str and source_mode in ('legacy', 'required')
    # LL0/old callers retain the identical view object and packet when absent.
    if mode == 'legacy' and fields['slot_permission'] is None and valid_mode and source_mode == 'legacy':
        return view
    effective = mode if valid_mode and source_mode == 'legacy' else (source_mode if valid_mode else 'metadata_exception')
    packet = replace(source, slot_permission_mode=effective, slot_permission_poll_tick=view.tick)
    return replace(view, reserved=replace(view.reserved, packet=packet))


def choice_or_wait(action, packet):
    """Built-in fallback safeguard; final loop guard remains independent."""
    action = int(action)
    allowed, status = permission_state(packet)
    if allowed is None:
        return action
    if action == WAIT:
        return action
    if 0 <= action < WAIT and allowed[action // 576]:
        return action
    return WAIT


def metadata_fields(source):
    try:
        return {key: getattr(source, key, default) for key, default in (
            ('slot_permission', None), ('slot_permission_capture_id', None),
            ('slot_permission_poll_tick', None), ('slot_permission_mode', 'legacy'))}
    except Exception:
        return dict(slot_permission=None, slot_permission_capture_id=None,
                    slot_permission_poll_tick=None, slot_permission_mode='metadata_exception')

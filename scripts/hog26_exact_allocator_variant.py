"""Build an explicitly isolated allocator variant for native differential probes."""

import hashlib
import inspect

from clasher.torch_sim.simple_attack_effects import allocate_fast_attack_effects_
from scripts.hog26_integer_muzzle_probe import integer_muzzle_offsets


def exact_allocator_variant():
    source = inspect.getsource(allocate_fast_attack_effects_)
    old = '''    muzzle_x = source_x + torch.trunc(aim_dx * muzzle_distance / aim_denominator).to(
        torch.int32
    )
    muzzle_y = source_y + torch.trunc(aim_dy * muzzle_distance / aim_denominator).to(
        torch.int32
    )'''
    new = '''    offset_x, offset_y = integer_muzzle_offsets(
        aim_dx.to(torch.int64), aim_dy.to(torch.int64), projectile_start_radius
    )
    muzzle_x = source_x + offset_x.to(torch.int32)
    muzzle_y = source_y + offset_y.to(torch.int32)'''
    if source.count(old) != 1:
        raise ValueError("allocator source drifted; review the isolated patch")
    variant = source.replace(old, new)
    namespace = dict(allocate_fast_attack_effects_.__globals__)
    namespace["integer_muzzle_offsets"] = integer_muzzle_offsets
    # Compile only the inspected local function with the literal patch above.
    exec(compile(variant, "<diagnostic-exact-muzzle-allocator>", "exec"), namespace)  # noqa: S102
    return namespace["allocate_fast_attack_effects_"], hashlib.sha256(variant.encode()).hexdigest()

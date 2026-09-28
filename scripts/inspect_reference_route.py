"""Read bounded movement-route arrays from a paused, task-owned Android battle."""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
from pathlib import Path

from smoke_reference_battle import request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--serial", default="emulator-5580")
    parser.add_argument("--port", type=int, default=26789)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--card-id", type=int, default=26000021)
    args = parser.parse_args()
    pid = int(
        subprocess.check_output(
            [str(args.adb), "-s", args.serial, "shell", "pidof", "nullsroyale.rel.free"]
        )
    )
    status = request(args.port, "status")
    assert status["paused"] and status["mode"] == "headless"
    capture = request(args.port, "observe-atomic")
    assert capture["atomic"] and not capture["rich"]["truncated"]
    before = capture["ordinary"]

    def memory(address, size):
        if not 0 < address < 1 << 56 or not 0 < size <= 4096:
            raise ValueError("out-of-bounds diagnostic memory request")
        command = f"dd if=/proc/{pid}/mem bs=1 skip={address} count={size} 2>/dev/null"
        data = subprocess.check_output(
            [str(args.adb), "-s", args.serial, "exec-out", command]
        )
        if len(data) != size:
            raise ValueError("short diagnostic memory read")
        return data

    def pointer(address):
        return struct.unpack("<Q", memory(address, 8))[0]

    manager = int(status["manager"], 16)
    world = pointer(manager + 0xA8)
    king = pointer(world + 0xE0)
    objects_manager = pointer(king + 0x10)
    vector = pointer(objects_manager + 8)
    capacity, count = struct.unpack("<ii", memory(objects_manager + 0x10, 8))
    assert 0 <= count <= capacity <= 100000 and count <= 128
    objects = struct.unpack(f"<{count}Q", memory(vector, count * 8))
    tilemap = pointer(pointer(objects_manager + 0x98) + 0xC0)
    tile_values = pointer(tilemap + 0x98)
    width, height = struct.unpack("<ii", memory(tilemap + 0xA8, 8))
    assert (width, height) == (36, 64)
    tile_bytes = b"".join(
        memory(tile_values + offset, min(4096, width * height * 4 - offset))
        for offset in range(0, width * height * 4, 4096)
    )
    tile_flags = struct.unpack(f"<{width * height}i", tile_bytes)
    river_rows = [list(tile_flags[y * width : (y + 1) * width]) for y in range(28, 35)]
    bit6_cells = [
        [i % width, i // width] for i, flags in enumerate(tile_flags) if flags & 64
    ]
    path_grid = pointer(pointer(objects_manager + 0x98) + 0x10)
    path_grid_header = list(struct.unpack("<10i", memory(path_grid, 40)))
    assert path_grid_header[:2] == [36, 64]
    path_overlay_enabled = bool(memory(path_grid + 0x71, 1)[0])
    overlay_buffers = {}
    for offset in (0x28, 0x30):
        overlay = pointer(path_grid + offset)
        overlay_values = pointer(overlay) if overlay else 0
        cells = []
        if overlay_values:
            capacity, count = struct.unpack("<ii", memory(overlay + 8, 8))
            assert width * height == count <= capacity <= 100000
            overlay_bytes = b"".join(
                memory(overlay_values + start, min(4096, count * 4 - start))
                for start in range(0, count * 4, 4096)
            )
            costs = struct.unpack(f"<{count}i", overlay_bytes)
            cells = [
                [i % width, i // width, cost] for i, cost in enumerate(costs) if cost
            ]
        overlay_buffers[hex(offset)] = cells
    pathfinder = pointer(path_grid + 0x40)
    pathfinder_flags = list(memory(pathfinder + 0x74, 4))
    heuristic_mode = struct.unpack("<i", memory(pathfinder + 0x18, 4))[0]
    records = []
    for obj in objects:
        if not obj:
            continue
        card = struct.unpack("<i", memory(obj + 0xAC, 4))[0]
        if card != args.card_id:
            continue
        identity = struct.unpack("<I", memory(obj + 8, 4))[0]
        assert any(
            o["nativeObjectId"] == identity and o["cardId"] == card
            for o in before["objects"]
        )
        # objectIndex is an object-list index, not a character type. Filter
        # projectile records by their absent HP before reading components.
        observation = next(
            o for o in before["objects"] if o["nativeObjectId"] == identity
        )
        if observation["hp"] is None:
            continue
        component_vector = pointer(obj + 0x18)
        component_mask = memory(obj + 0x30, 1)[0]
        capacity, count = struct.unpack("<ii", memory(obj + 0x20, 8))
        assert 2 <= count <= capacity <= 16
        rich_object = next(
            o for o in capture["rich"]["objects"] if o["nativeObjectId"] == identity
        )
        assert rich_object["components"]["valid"]
        slot = next(c for c in rich_object["components"]["slots"] if c["slot"] == 1)
        assert (
            slot["ownerBacklinkValid"] and slot["typeValid"] and slot["engineType"] == 1
        )
        assert slot["vtableLibgOffset"] == 0x18A1F38
        movement = pointer(component_vector + 8)
        assert pointer(movement + 8) == obj
        attack = pointer(component_vector)
        assert pointer(attack + 8) == obj
        record = {"nativeObjectId": identity, "tick": before["tick"], "cardId": card}
        record["component_mask"] = component_mask
        record["movement_getter_present"] = bool(component_mask & 2 and count >= 2)
        count = struct.unpack("<i", memory(movement + 0x38, 4))[0]
        assert 0 <= count <= 100
        codes = (
            list(struct.unpack(f"<{count}i", memory(movement + 0x3C, count * 4)))
            if count
            else []
        )
        assert all(0 <= code < 36 * 64 for code in codes)
        record["route_codes_reverse_order"] = codes
        record["route_direction_vector"] = list(
            struct.unpack("<ii", memory(movement + 0x30, 8))
        )
        record["route_cells_next_first"] = [
            [code % 36, code // 36] for code in reversed(codes)
        ]
        record["attack_finish_elapsed_ms"] = struct.unpack(
            "<i", memory(attack + 0x48, 4)
        )[0]
        record["attack_timeline_ms"] = struct.unpack("<i", memory(attack + 0x24, 4))[0]
        record["attack_load_ms"] = struct.unpack("<i", memory(attack + 0x28, 4))[0]
        record["retains_pending_lethal_target"] = bool(memory(attack + 0x18, 1)[0])
        record["has_attacked_current_target"] = bool(memory(attack + 0x19, 1)[0])
        record["character_state"] = struct.unpack("<i", memory(obj + 0x11C, 4))[0]
        record["avoidance"] = struct.unpack("<i", memory(movement + 0x1F4, 4))[0]
        record["facing_vector"] = list(struct.unpack("<ii", memory(obj + 0xF8, 8)))
        record["movement_accumulator_x_y_count"] = list(
            struct.unpack("<iii", memory(movement + 0x1D4, 12))
        )
        base = pointer(movement) - 0x18A1F38
        avoidance_static_mask = pointer(base + 0x19CA090)
        record["avoidance_static_flag"] = bool(pointer(obj + 0xB0) & avoidance_static_mask)
        record["avoidance_static_mask"] = hex(avoidance_static_mask)
        record["range_getter_libg_offset"] = pointer(pointer(obj) + 0x128) - base
        record["character_vtable_libg_offset"] = pointer(obj) - base
        character_data = pointer(obj + 0x48)
        record["base_sight_logic_units"] = struct.unpack(
            "<i", memory(character_data + 0x434, 4)
        )[0]
        record["attacker_radius_logic_units"] = struct.unpack(
            "<i", memory(character_data + 0x4E4, 4)
        )[0]
        record["native_lane_id"] = struct.unpack("<i", memory(obj + 0x158, 4))[0]
        records.append(record)
    after = request(args.port, "observe")
    assert records, "no matching character movement components"
    assert after == before, "native state changed during read-only route inspection"
    result = {
        "status": "paused_native_route_arrays",
        "records": records,
        "path_grid_header_i32": path_grid_header,
        "path_overlay_enabled": path_overlay_enabled,
        "overlay_buffers_nonzero_cells": overlay_buffers,
        "pathfinder_flags_0x74": pathfinder_flags,
        "pathfinder_heuristic_mode": heuristic_mode,
        "runtime_river_rows_y28_34": river_rows,
        "runtime_bit6_cells": bit6_cells,
        "scope": "Debug reference only; raw reverse-ordered path arrays are not actor features.",
    }
    with args.output.open("x") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

"""Fail closed when native scheduling no longer matches the declared tick boundary."""


def validate_command_step(before: dict, after: dict, receipts: list[dict]) -> None:
    tick = before.get("tick")
    if (
        type(tick) is not int
        or type(after.get("tick")) is not int
        or after["tick"] != tick + 1
    ):
        raise ValueError("native execution must advance exactly one tick")
    for key in ("generation", "stateEpoch"):
        if type(before.get(key)) is not int or after.get(key) != before[key]:
            raise ValueError("native epoch changed during command execution")
    sequences = set()
    for receipt in receipts:
        if receipt.get("ok") is not True or receipt.get("kind") != "card":
            raise ValueError("native scheduler did not acknowledge a card command")
        if (
            type(receipt.get("registeredAtTick")) is not int
            or type(receipt.get("executeTick")) is not int
            or receipt["registeredAtTick"] != tick
            or receipt["executeTick"] != after["tick"]
        ):
            raise ValueError("schedule receipt disagrees with observed command ticks")
        for key in ("generation", "stateEpoch"):
            if type(receipt.get(key)) is not int or receipt[key] != before[key]:
                raise ValueError("schedule receipt belongs to another native epoch")
        sequence = receipt.get("sequence")
        if type(sequence) is not int or sequence < 0 or sequence in sequences:
            raise ValueError("invalid or duplicate native schedule receipt")
        sequences.add(sequence)

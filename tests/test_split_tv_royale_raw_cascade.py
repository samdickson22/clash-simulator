from scripts.split_tv_royale_raw_cascade import resolve_held_out_archetypes


def test_resolve_held_out_archetypes_can_explicitly_disable_holdouts() -> None:
    assert resolve_held_out_archetypes([], disabled=True) == frozenset()


def test_resolve_held_out_archetypes_preserves_default_and_explicit_modes() -> None:
    assert resolve_held_out_archetypes([], disabled=False)
    assert resolve_held_out_archetypes(
        ["graveyard", "x-bow"], disabled=False
    ) == frozenset({"graveyard", "x-bow"})

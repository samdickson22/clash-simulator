from clasher.torch_sim.manifest_audit import audit_enabled_one_vs_one


def test_exhaustive_enabled_one_vs_one_capability_matrix_is_exactly_accounted() -> None:
    audit = audit_enabled_one_vs_one()
    summary = audit.summary()

    assert summary["deck_count"] == 33
    assert summary["card_slots"] == 264
    assert summary["enabled_card_count"] == 66
    assert summary["ordered_pair_count"] == 66 * 66
    assert summary["ticks_per_pair"] == 1
    assert summary["scope"] == "post-deployment tick window"
    assert summary["decks_sha256"] == (
        "39fd5d5fe36cc7cfa69cf049de3ea2e7e00bc143ec71b14f33ead300fb4b2944"
    )
    assert summary["matrix_sha256"] == (
        "2f12247533d21f4927757f46b47b2a3b1a0abd82113831f2e82af58639283db6"
    )
    assert summary["oracle_mismatches"] == 0
    assert summary["execution_error_pairs"] == 0
    assert summary["split_execution_pairs"] == 0
    assert (
        summary["tensor_executed_exact_pairs"] + summary["counted_fallback_pairs"]
        == summary["ordered_pair_count"]
    )
    assert summary["tensor_executed_exact_pairs"] == 400
    assert summary["counted_fallback_pairs"] == 3_956
    assert summary["fallback_is_tensor_parity"] is False

    for row in audit.rows:
        assert row.parity_passed
        assert row.tensor_parity_passed is (row.execution == "tensor")
        if row.execution == "fallback":
            assert row.tensor_ticks == 0
            assert row.python_ticks == row.advanced_ticks
            assert row.unsupported_fallbacks == 1

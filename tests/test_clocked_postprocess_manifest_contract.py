from pathlib import Path


def test_postprocess_consumes_authoritative_clocked_neutral_artifact() -> None:
    script = Path("scripts/postprocess_tv_royale_persistent_batch.sh").read_text(
        encoding="utf-8"
    )
    assert "neutral=$(jq -r '.artifacts.neutral_sequence.path'" in script
    assert 'semantic/neutral_sequence.jsonl.gz' not in script
    assert script.count('--neutral "$neutral"') == 3

import json
import subprocess
import sys


def test_gym_smoke_debug_dump_jsonl(tmp_path):
    dump_path = tmp_path / "gym_debug.jsonl"
    cmd = [
        sys.executable,
        "-m",
        "clasher.rl.gym_env",
        "--episodes",
        "1",
        "--max-steps",
        "8",
        "--action-mode",
        "flat",
        "--quiet-engine",
        "--debug-dump",
        str(dump_path),
        "--dump-max-legal",
        "32",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    assert dump_path.exists()
    lines = dump_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["episode"] == 1
    assert isinstance(payload["records"], list)
    assert payload["records"]
    first = payload["records"][0]
    assert "agent_action_flat" in first
    assert "legal_action_count" in first
    assert "mask_sha256" in first

"""Shared evaluation runner, isolated iteration-2 outputs and pilot guards."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluate as base
import kit
import json
if __name__ == '__main__':
    pins = json.loads((kit.HERE/'preflight.json').read_text())
    kit.check_data_pins(pins)
    assert kit.sources_match(pins['sources'])
    base.module.OUT = Path(__file__).resolve().parent
    base.module.main()

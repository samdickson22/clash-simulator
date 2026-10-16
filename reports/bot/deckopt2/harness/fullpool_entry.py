"""Verify the truth-simulator identity before loading either runtime."""
import json
from bot.levels.placement_probe import installed_identity
import fullpool_eval as fp
from fullpool_worker import main

if __name__ == '__main__':
    expected=json.loads((fp.JOB/'manifest.json').read_text())['simulator']
    actual=installed_identity()
    assert actual==expected,('truth simulator identity differs',actual,expected)
    print('TRUTH_SIMULATOR_PIN_VERIFIED',json.dumps(actual,sort_keys=True),flush=True)
    main()

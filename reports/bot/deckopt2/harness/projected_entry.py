"""Select the registered LD implementation only after the requested parity check."""
import json
from pathlib import Path
from bot.deckopt2.run import sha
J=Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2');R=J/'final-validation'
if __name__=='__main__':
    config=json.loads((R/'implementation.json').read_text())
    assert config['bank_sha256']==sha(R/'validation/bank.json')
    assert config['parity_receipt_sha256']==sha(J/'projected-parity/receipt.json')
    receipt=json.loads((J/'projected-parity/receipt.json').read_text())
    if config['mode']=='fc-c4':
        assert receipt['passed'] and receipt['reserve_fired']
        assert config['factory_sha256']==sha(J/'projected_fast.py')
        from projected_fast import install
        install()
    else:assert config['mode']=='LD' and not receipt['passed']
    from pool import main
    main()

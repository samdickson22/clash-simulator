"""Run reports/bot/learned-opponent/native-total-tools/totality.py unchanged except for two text substitutions:
the bot import path is this tree's (so CLASHER_BOT_RUNTIME_PINS=live16402 resolves), and with --runtime-config the
probe's base state uses the runtime's own R.config (the live16402 stats; json.dumps(R.config) is what the search
ships to the native, bot/search/lopp_fast.py) instead of the recorded root's config.

    CLASHER_BOT_RUNTIME=<root> CLASHER_BOT_RUNTIME_PINS=live16402 python -B totality_live.py [--runtime-config] \
        --roots DIR --out OUT.json [--scrub]
"""
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[4]
SRC = TREE / 'reports/bot/learned-opponent/native-total-tools/totality.py'
PATH_LINE = "sys.path.insert(0, '/mpac/sdicks02/repos/clasher-bot')"
CFG_LINE = """cfg_text = (d / f"config-{r0['config'][:16]}.json").read_text()"""

text = SRC.read_text()
assert text.count(PATH_LINE) == 1 and text.count(CFG_LINE) == 1, 'totality.py changed: update the substitutions'
text = text.replace(PATH_LINE, f'sys.path.insert(0, {str(TREE)!r})')
if '--runtime-config' in sys.argv:
    sys.argv.remove('--runtime-config')
    text = text.replace(CFG_LINE, 'cfg_text = json.dumps(R.config)')
sys.argv[0] = str(SRC)
exec(compile(text, str(SRC), 'exec'), {'__name__': '__main__', '__file__': str(SRC)})

"""Dump R.meta (sorted JSON) to argv[1] (hash-seed dependence check)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from bot.players.runtime import Runtime
rt = Runtime()
Path(sys.argv[1]).write_text(json.dumps(rt.R.meta, sort_keys=True, indent=0))

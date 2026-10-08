"""20 FPS offline collection with exact scheduled boundaries and verified shipping.

Run --prepare, then --smoke. Phase A refuses to run without smoke admission.
All video and large labels live in the capped cache, outside tracked paths.
"""
from pathlib import Path
import sys
V4=Path(__file__).resolve().parents[1]/'reports/strategy_council_20260928/live-loop/v4'
sys.path.insert(0,str(V4))
from collector import main
if __name__=='__main__':main()

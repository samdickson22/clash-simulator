#!/bin/sh
# fake bsbounds (CoreGraphics window bounds): FAKE_BOUNDS_FILE "w,h" (default 540,980), like fake_bsgrab.py info
if [ -n "$FAKE_BOUNDS_FILE" ]; then wh=$(cat "$FAKE_BOUNDS_FILE"); else wh=540,980; fi
echo "{\"window_id\":1,\"pid\":2,\"bounds\":[100,50,${wh}],\"onscreen\":true}"

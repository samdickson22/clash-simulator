"""Dump differential.config() for the C56 card set (one process per Python arm). Usage: cfg_dump.py OUT.json"""
import json, sys
import differential as D
from c56_controller import CARDS
cfg = D.config(tuple(CARDS))
json.dump(cfg, open(sys.argv[1], 'w'), sort_keys=True, default=str)
print(len(cfg['cards']), 'cards')

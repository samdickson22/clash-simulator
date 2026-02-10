from .hog_rider import HogRiderJump
from .sparky import SparkyChargeUp
from .bandit import BanditDash
from .fisherman import FishermanHook
from .miner import MinerTunnel

CARD_MECHANICS = {
    'HogRider': [HogRiderJump],
    'Sparky': [SparkyChargeUp],
    'Bandit': [BanditDash],
    'Assassin': [BanditDash],      # Internal name for Bandit
    'Fisherman': [FishermanHook],
    'Miner': [MinerTunnel],
}

__all__ = [
    'HogRiderJump', 'SparkyChargeUp', 'BanditDash', 'FishermanHook', 'MinerTunnel',
    'CARD_MECHANICS'
]
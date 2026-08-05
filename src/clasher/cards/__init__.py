from .archer_queen import ArcherQueenCloak
from .bandit import BanditDash
from .battle_ram import BattleRamCharge
from .electro_dragon import ElectroDragonChainLightning
from .electro_spirit import ElectroSpiritChain
from .electro_wizard import ElectroWizardSpawnZap
from .firecracker import AttackRecoil, FirecrackerRecoil
from .fisherman import FishermanHook
from .hog_rider import HogRiderJump
from .ice_golem import IceGolemChill
from .ice_spirit import IceSpiritFreeze
from .lumberjack import LumberjackRage
from .magic_archer import MagicArcherPierce
from .mega_knight import MegaKnightSlam
from .miner import UndergroundDeployment
from .royal_ghost import InvisibilityWhenNotAttacking, RoyalGhostFade
from .sparky import SparkyChargeUp
from .tesla import HideWhenIdle
from .valkyrie import ValkyrieSpin
from .wallbreakers import WallBreakersDemolition

CARD_MECHANICS = {
    'Fisherman': [FishermanHook],
    'Sparky': [SparkyChargeUp],
}

__all__ = [
    'ArcherQueenCloak', 'BanditDash', 'BattleRamCharge', 'ElectroDragonChainLightning',
    'ElectroSpiritChain', 'ElectroWizardSpawnZap', 'AttackRecoil',
    'FirecrackerRecoil', 'FishermanHook',
    'HogRiderJump', 'IceGolemChill', 'IceSpiritFreeze', 'LumberjackRage',
    'MagicArcherPierce', 'MegaKnightSlam', 'UndergroundDeployment',
    'InvisibilityWhenNotAttacking', 'RoyalGhostFade',
    'SparkyChargeUp', 'HideWhenIdle', 'ValkyrieSpin', 'WallBreakersDemolition', 'CARD_MECHANICS'
]

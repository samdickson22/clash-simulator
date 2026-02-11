from .archer_queen import ArcherQueenCloak
from .bandit import BanditDash
from .battle_ram import BattleRamCharge
from .electro_dragon import ElectroDragonChainLightning
from .electro_spirit import ElectroSpiritChain
from .electro_wizard import ElectroWizardSpawnZap, ElectroWizardStunAttack
from .firecracker import FirecrackerRecoil
from .fisherman import FishermanHook
from .hog_rider import HogRiderJump
from .ice_golem import IceGolemChill
from .ice_spirit import IceSpiritFreeze
from .lumberjack import LumberjackRage
from .magic_archer import MagicArcherPierce
from .mega_knight import MegaKnightSlam
from .royal_ghost import RoyalGhostFade
from .sparky import SparkyChargeUp
from .valkyrie import ValkyrieSpin
from .wallbreakers import WallBreakersDemolition

CARD_MECHANICS = {
    'ArcherQueen': [ArcherQueenCloak],
    'Bandit': [BanditDash],
    'Assassin': [BanditDash],
    'BattleRam': [BattleRamCharge],
    'ElectroDragon': [ElectroDragonChainLightning],
    'ElectroSpirit': [ElectroSpiritChain],
    'ElectroWizard': [ElectroWizardSpawnZap, ElectroWizardStunAttack],
    'Firecracker': [FirecrackerRecoil],
    'Fisherman': [FishermanHook],
    'HogRider': [HogRiderJump],
    'IceGolemite': [IceGolemChill],
    'IceSpirits': [IceSpiritFreeze],
    'AxeMan': [LumberjackRage],
    'EliteArcher': [MagicArcherPierce],
    'MegaKnight': [MegaKnightSlam],
    'Ghost': [RoyalGhostFade],
    'Sparky': [SparkyChargeUp],
    'Valkyrie': [ValkyrieSpin],
    'Wallbreakers': [WallBreakersDemolition],
}

__all__ = [
    'ArcherQueenCloak', 'BanditDash', 'BattleRamCharge', 'ElectroDragonChainLightning',
    'ElectroSpiritChain', 'ElectroWizardSpawnZap', 'ElectroWizardStunAttack', 'FirecrackerRecoil', 'FishermanHook',
    'HogRiderJump', 'IceGolemChill', 'IceSpiritFreeze', 'LumberjackRage',
    'MagicArcherPierce', 'MegaKnightSlam', 'RoyalGhostFade',
    'SparkyChargeUp', 'ValkyrieSpin', 'WallBreakersDemolition', 'CARD_MECHANICS'
]

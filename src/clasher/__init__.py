from gymnasium.envs.registration import register

register(
    id="ClashRoyale-v0",
    entry_point="clasher.gym_env:ClashRoyaleEnv",
)

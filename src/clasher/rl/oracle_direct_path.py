"""Executable exact candidate for allocation-lean oracle backup paths."""

from __future__ import annotations

from clasher.battle import BattleState

from .oracle_planner import FixedDepthThompsonOracle, _PlannerNode
from .reward_model import reward_win_prob_p0


class DirectPathFixedDepthThompsonOracle(FixedDepthThompsonOracle):
    """Planner variant storing nodes and scalar actions directly in its path."""

    def select_actions(self, battle: BattleState) -> dict[int, int]:
        tree: dict[tuple, _PlannerNode] = {}
        root_tensor_fork = self._capture_tensor_fork(battle)
        root_key = self._state_key(battle)
        root_legal = {
            player_id: self._legal_actions(battle, player_id)
            for player_id in (0, 1)
        }
        root_candidates = (
            {
                player_id: self._sample_actions(root_legal[player_id])
                for player_id in (0, 1)
            }
            if self.stable_root_candidates
            else None
        )
        for _ in range(self.num_simulations):
            sim = self._clone_for_search(battle, root_tensor_fork)
            path: list[tuple[_PlannerNode, int, int]] = []
            for depth in range(self.plan_depth):
                key = root_key if depth == 0 else self._state_key(sim)
                node = tree.get(key)
                if node is None:
                    node = _PlannerNode()
                    tree[key] = node

                if depth == 0 and root_candidates is not None:
                    legal0 = root_candidates[0]
                elif depth == 0:
                    legal0 = self._sample_actions(root_legal[0])
                else:
                    legal0 = self._sample_actions(self._legal_actions(sim, 0))
                action0 = node.by_player[0].sample_action(legal0, self.rng)

                if depth == 0 and root_candidates is not None:
                    legal1 = root_candidates[1]
                elif depth == 0:
                    legal1 = self._sample_actions(root_legal[1])
                else:
                    legal1 = self._sample_actions(self._legal_actions(sim, 1))
                action1 = node.by_player[1].sample_action(legal1, self.rng)

                path.append((node, action0, action1))
                self._apply_joint_action_direct(sim, action0, action1)
                if sim.game_over:
                    break

            value_prob_p0 = self._evaluate_state_prob_p0(sim)
            for node, action0, action1 in path:
                node.by_player[0].update(action0, value_prob_p0)
                node.by_player[1].update(action1, 1.0 - value_prob_p0)

        root = tree.get(root_key)
        out: dict[int, int] = {}
        for player_id in (0, 1):
            legal = (
                root_candidates[player_id]
                if root_candidates is not None
                else self._sample_actions(root_legal[player_id])
            )
            if root is None:
                out[player_id] = int(self.rng.choice(legal))
            elif root_candidates is not None:
                visited = root.by_player[player_id].greedy_visited_action(legal)
                out[player_id] = (
                    visited if visited is not None else int(self.rng.choice(legal))
                )
            else:
                out[player_id] = root.by_player[player_id].greedy_action(legal)
        return out

    def _evaluate_state_prob_p0(self, battle: BattleState) -> float:
        """Return the scalar leaf value used internally during backup."""
        return reward_win_prob_p0(battle, self.reward_profile)

    def _apply_joint_action_direct(
        self,
        battle: BattleState,
        action0: int,
        action1: int,
    ) -> None:
        order = [0, 1]
        self.rng.shuffle(order)
        for player_id in order:
            action = action0 if player_id == 0 else action1
            self.action_space.apply_action(battle, player_id, int(action))
        self._advance_simulation(battle)

"""
Multi-Tiered AI Opponent Hierarchy for Pokémon TCG (Standard Format)
Provides 3 distinct AI difficulty personas:
1. Tier 1 - Casual (Heuristic Greedy AI)
2. Tier 2 - Competitor (Tactical MCTS AI - 100 Iterations)
3. Tier 3 - Championship Master (Deep ISMCTS with Prize-Mapping & Disruption - 300+ Iterations)
"""

from typing import Dict, Any, Optional

# Import live game engine
game_engine = __import__("Game Engine")
TurnBasedGreedyAI = game_engine.TurnBasedGreedyAI
MCTSController = game_engine.MCTSController


class CasualAI(TurnBasedGreedyAI):
    """
    Tier 1 - Casual AI.
    Plays immediate available moves with basic energy attachments and attacks.
    """
    pass


class CompetitorAI(MCTSController):
    """
    Tier 2 - Competitor AI.
    Tactical Information-Set MCTS with moderate lookahead (80-120 iterations).
    Prioritizes evolution lines and attacking highest prize threats.
    """
    def __init__(self, iteration_limit: int = 100, simulation_depth: int = 10, exploration_constant: float = 1.414):
        super().__init__(
            iteration_limit=iteration_limit,
            simulation_depth=simulation_depth,
            exploration_constant=exploration_constant
        )


class ChampionshipMasterAI(MCTSController):
    """
    Tier 3 - Championship Master AI.
    Deep Information-Set MCTS (300+ iterations) with prize-map optimization,
    hand disruption timing (Iono / Unfair Stamp), and bench management.
    """
    def __init__(self, iteration_limit: int = 300, simulation_depth: int = 16, exploration_constant: float = 1.25):
        super().__init__(
            iteration_limit=iteration_limit,
            simulation_depth=simulation_depth,
            exploration_constant=exploration_constant
        )


class AIOpponentFactory:
    """Factory to instantiate AI opponents across all 3 tiers."""

    @staticmethod
    def create_opponent(tier: str = "Competitor", **kwargs) -> Any:
        tier_lower = tier.lower()
        if "casual" in tier_lower or "tier 1" in tier_lower or "greedy" in tier_lower:
            return CasualAI()
        elif "master" in tier_lower or "championship" in tier_lower or "tier 3" in tier_lower:
            return ChampionshipMasterAI(**kwargs)
        else:
            return CompetitorAI(**kwargs)

"""
Pokémon TCG Meta Gauntlet & Tournament Testing Engine (Standard Format)
Evaluates any custom or synthesized decklist against all premier Standard Format meta decks.
Computes:
1. Matchup win rates, records, and tier ratings (Favorable, Even, Unfavorable).
2. Opening setup consistency (Mulligan rate, T1 Basic setup rate).
3. Prize trade velocity and average prize differentials.
4. Comprehensive Meta Viability Rating (Tier S, Tier 1, Tier 2, Rogue).
"""

import time
from typing import List, Dict, Tuple, Optional

# Import live game engine and deck validator
game_engine = __import__("Game Engine")
CardFactory = game_engine.CardFactory
Player = game_engine.Player
GameState = game_engine.GameState
TurnBasedGreedyAI = game_engine.TurnBasedGreedyAI
MCTSController = game_engine.MCTSController
STANDARD_ARCHETYPES = game_engine.STANDARD_ARCHETYPES
from deck_builder import DeckValidator, DeckBuilder


class MetaGauntlet:
    """
    Automated Testing Suite: Pits a candidate deck against the full Standard Format Meta Gauntlet.
    """
    def __init__(
        self,
        card_factory: Optional[CardFactory] = None,
        archetypes: Optional[Dict[str, List[str]]] = None
    ):
        self.factory = card_factory or CardFactory('cards.json')
        self.archetypes = archetypes or STANDARD_ARCHETYPES

    def run_gauntlet(
        self,
        custom_deck: List[str],
        custom_deck_name: str = "Candidate Deck",
        games_per_matchup: int = 4,
        mcts_iterations: int = 80,
        mcts_depth: int = 8,
        verbose: bool = False
    ) -> Dict:
        """
        Runs a comprehensive gauntlet across all Standard Format archetypes.
        """
        is_valid, errors = DeckValidator.validate_deck(custom_deck, self.factory)
        if not is_valid:
            raise ValueError(f"Cannot run Gauntlet on invalid deck: {errors}")

        matchup_results = {}
        total_wins = 0
        total_losses = 0
        total_draws = 0
        total_prizes_taken = 0
        total_prizes_lost = 0
        total_turns_in_wins = []
        total_turns_in_losses = []
        mulligan_count = 0
        total_games_played = 0

        target_names = list(self.archetypes.keys())
        print(f"\n{'='*85}")
        print(f"  RUNNING META GAUNTLET: '{custom_deck_name}' vs {len(target_names)} Standard Archetypes")
        print(f"  ({games_per_matchup} Games/Matchup, Total: {len(target_names) * games_per_matchup} Games)")
        print(f"{'='*85}\n")

        start_time = time.time()

        for idx, meta_name in enumerate(target_names, 1):
            print(f"[{idx}/{len(target_names)}] Gauntlet Matchup: {custom_deck_name} vs {meta_name}...")
            meta_deck = self.archetypes[meta_name]

            m_wins = 0
            m_losses = 0
            m_draws = 0
            m_prizes_taken = 0
            m_prizes_lost = 0

            for g in range(games_per_matchup):
                total_games_played += 1
                c1 = MCTSController(iteration_limit=mcts_iterations, simulation_depth=mcts_depth)
                c2 = TurnBasedGreedyAI()

                if g % 2 == 0:
                    p1 = Player(custom_deck_name, custom_deck, self.factory, controller=c1)
                    p2 = Player(meta_name, meta_deck, self.factory, controller=c2)
                    game = GameState(p1, p2)
                    
                    # Track mulligans on candidate
                    p1_hand_basics = sum(1 for c in p1.hand if getattr(c, 'stage', '') == 'Basic')
                    if p1_hand_basics == 0:
                        mulligan_count += 1

                    winner, reason = game.run_game(verbose=verbose)

                    p1_prizes = 6 - len(p1.prize_cards)
                    p2_prizes = 6 - len(p2.prize_cards)
                    m_prizes_taken += p1_prizes
                    m_prizes_lost += p2_prizes
                    total_prizes_taken += p1_prizes
                    total_prizes_lost += p2_prizes

                    if winner is p1:
                        m_wins += 1
                        total_wins += 1
                        total_turns_in_wins.append(game.turn_number)
                    elif winner is p2:
                        m_losses += 1
                        total_losses += 1
                        total_turns_in_losses.append(game.turn_number)
                    else:
                        m_draws += 1
                        total_draws += 1
                else:
                    p2 = Player(meta_name, meta_deck, self.factory, controller=c1)
                    p1 = Player(custom_deck_name, custom_deck, self.factory, controller=c2)
                    game = GameState(p2, p1)

                    p1_hand_basics = sum(1 for c in p1.hand if getattr(c, 'stage', '') == 'Basic')
                    if p1_hand_basics == 0:
                        mulligan_count += 1

                    winner, reason = game.run_game(verbose=verbose)

                    p1_prizes = 6 - len(p1.prize_cards)
                    p2_prizes = 6 - len(p2.prize_cards)
                    m_prizes_taken += p1_prizes
                    m_prizes_lost += p2_prizes
                    total_prizes_taken += p1_prizes
                    total_prizes_lost += p2_prizes

                    if winner is p1:
                        m_wins += 1
                        total_wins += 1
                        total_turns_in_wins.append(game.turn_number)
                    elif winner is p2:
                        m_losses += 1
                        total_losses += 1
                        total_turns_in_losses.append(game.turn_number)
                    else:
                        m_draws += 1
                        total_draws += 1

            m_total = games_per_matchup
            m_wr = (m_wins / m_total) * 100
            diff = m_prizes_taken - m_prizes_lost

            if m_wr >= 55.0:
                classification = "Favorable"
            elif m_wr >= 45.0:
                classification = "Even"
            else:
                classification = "Unfavorable"

            matchup_results[meta_name] = {
                "record": f"{m_wins}-{m_losses}-{m_draws}",
                "win_rate": m_wr,
                "classification": classification,
                "prizes_taken": m_prizes_taken,
                "prizes_lost": m_prizes_lost,
                "prize_diff": diff
            }

        elapsed = time.time() - start_time
        overall_wr = (total_wins / total_games_played) * 100
        net_prize_diff = total_prizes_taken - total_prizes_lost
        mulligan_rate = (mulligan_count / total_games_played) * 100
        avg_turn_win = (sum(total_turns_in_wins) / len(total_turns_in_wins)) if total_turns_in_wins else 0.0
        avg_turn_loss = (sum(total_turns_in_losses) / len(total_turns_in_losses)) if total_turns_in_losses else 0.0

        if overall_wr >= 65.0:
            meta_tier = "Tier S (Dominant Meta Choice)"
        elif overall_wr >= 50.0:
            meta_tier = "Tier 1 (Competitive Tournament Pick)"
        elif overall_wr >= 35.0:
            meta_tier = "Tier 2 (Viable Rogue / Pocket Pick)"
        else:
            meta_tier = "Tier 3 / Casual (Needs Refinement)"

        # Formatted Output
        print(f"\n{'='*85}")
        print(f"  META GAUNTLET REPORT: {custom_deck_name}")
        print(f"{'='*85}")
        print(f"Overall Record: {total_wins}-{total_losses}-{total_draws} ({overall_wr:.1f}% Win Rate) | Tier: {meta_tier}")
        print(f"Total Prizes: Taken {total_prizes_taken} vs Lost {total_prizes_lost} (Net {net_prize_diff:+d})")
        print(f"Consistency: {mulligan_rate:.1f}% Mulligan Rate | Avg Turn to Win: {avg_turn_win:.1f} | Avg Turn to Loss: {avg_turn_loss:.1f}")
        print(f"Evaluation Completed in {elapsed:.2f}s ({elapsed/total_games_played:.2f}s/game)\n")

        print(f"{'Opponent Archetype':<20} | {'Classification':<13} | {'Record':<10} | {'Win Rate':<10} | {'Prize Diff'}")
        print(f"{'-'*20}-+-{'-'*13}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}")
        for opp_name, data in matchup_results.items():
            print(f"{opp_name:<20} | {data['classification']:<13} | {data['record']:<10} | {data['win_rate']:>6.1f}%    | {data['prize_diff']:+d}")

        print(f"{'='*85}\n")

        return {
            "custom_deck_name": custom_deck_name,
            "overall_record": f"{total_wins}-{total_losses}-{total_draws}",
            "overall_win_rate": overall_wr,
            "meta_tier": meta_tier,
            "net_prize_diff": net_prize_diff,
            "mulligan_rate": mulligan_rate,
            "avg_turn_to_win": avg_turn_win,
            "avg_turn_to_loss": avg_turn_loss,
            "matchup_breakdown": matchup_results,
            "elapsed_seconds": elapsed
        }


if __name__ == '__main__':
    factory = CardFactory('cards.json')
    builder = DeckBuilder(factory)
    deck = builder.generate_deck_from_scratch("Ceruledge ex", preferred_ace_spec="Grand Tree")
    gauntlet = MetaGauntlet(factory)
    gauntlet.run_gauntlet(deck, custom_deck_name="Ceruledge ex (Grand Tree)", games_per_matchup=2)

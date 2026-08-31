"""
Master Test Suite for Project Vulpix Suite:
- DeckBuilder & Scratch Generator
- MetaGauntlet Engine
- Multi-Tiered AI Opponents
- AICoach & Blunder Analysis Engine
- StrategyPlanner & Prize-Map Generator
"""

import unittest

game_engine = __import__("Game Engine")
CardFactory = game_engine.CardFactory
STANDARD_ARCHETYPES = game_engine.STANDARD_ARCHETYPES

from deck_builder import DeckBuilder, DeckValidator, AntiMetaOptimizer
from meta_gauntlet import MetaGauntlet
from ai_opponents import CasualAI, CompetitorAI, ChampionshipMasterAI, AIOpponentFactory
from ai_coach import AICoach
from strategy_planner import StrategyPlanner


class TestVulpixMasterSuite(unittest.TestCase):
    def setUp(self):
        self.factory = CardFactory('cards.json')
        self.builder = DeckBuilder(self.factory)
        self.gauntlet = MetaGauntlet(self.factory)
        self.coach = AICoach(self.factory, coach_iterations=30, coach_depth=5)
        self.planner = StrategyPlanner(self.factory)

    def test_deck_builder_scratch_generation(self):
        """Test scratch generator produces valid 60-card decks for all archetypes."""
        for attacker in ["Ceruledge ex", "Gardevoir ex", "Charizard ex", "Terapagos ex"]:
            deck = self.builder.generate_deck_from_scratch(attacker)
            self.assertEqual(len(deck), 60)
            is_valid, errors = DeckValidator.validate_deck(deck, self.factory)
            self.assertTrue(is_valid, f"Failed for {attacker}: {errors}")

    def test_ai_opponent_factory_tiers(self):
        """Test AI Opponent factory instantiates correct personas."""
        casual = AIOpponentFactory.create_opponent("Casual")
        self.assertIsInstance(casual, CasualAI)

        comp = AIOpponentFactory.create_opponent("Competitor")
        self.assertIsInstance(comp, CompetitorAI)

        master = AIOpponentFactory.create_opponent("Championship Master")
        self.assertIsInstance(master, ChampionshipMasterAI)

    def test_ai_coach_move_recommendations_and_blunder_analysis(self):
        """Test AI Coach evaluates board, ranks moves, and detects blunders."""
        # Create a live test board state
        game = self.coach.ingest_live_board_state(
            p1_active_name="Gardevoir ex",
            p1_active_hp=310,
            p1_active_energy=["Psychic Energy", "Psychic Energy", "Psychic Energy"],
            p1_bench_names=["Ralts"],
            p1_hand_names=["Professor's Research", "Psychic Energy"],
            p1_prizes_remaining=4,
            p2_active_name="Charmander",
            p2_active_hp=70,
            p2_bench_names=["Charizard ex"],
            p2_prizes_remaining=6
        )
        game.turn_number = 2
        game.players[0].turns_taken = 1
        game.players[0].active_pokemon.turn_played = 0

        eval_result = self.coach.evaluate_turn(game)
        self.assertIn("recommended_moves", eval_result)
        self.assertGreater(len(eval_result["recommended_moves"]), 0)

        # Top move should be attack (190 dmg KOs 70 HP Charmander)
        best_rec = eval_result["recommended_moves"][0]
        self.assertEqual(best_rec["action"][0], 'attack')

        # Check blunder analysis on sub-optimal pass vs optimal attack
        pass_action = ('pass',)
        blunder_analysis = self.coach.analyze_player_move(game, pass_action)
        self.assertIn(blunder_analysis["grade"], ("Blunder", "Inaccuracy"))

        best_analysis = self.coach.analyze_player_move(game, best_rec["action"])
        self.assertEqual(best_analysis["grade"], "Best Move")

    def test_strategy_planner_gameplan_synthesis(self):
        """Test StrategyPlanner creates comprehensive prize-map and matchup guide."""
        my_deck = STANDARD_ARCHETYPES["Ceruledge ex"]
        opp_deck = STANDARD_ARCHETYPES["Charizard ex"]

        plan = self.planner.generate_gameplan(
            my_deck=my_deck,
            my_deck_name="Ceruledge ex",
            opp_deck=opp_deck,
            opp_deck_name="Charizard ex"
        )
        self.assertIn("prize_map_plan", plan)
        self.assertIn("threat_warnings", plan)
        self.assertIn("dos", plan)
        self.assertIn("donts", plan)
        self.assertGreater(len(plan["dos"]), 0)


if __name__ == '__main__':
    unittest.main()

"""
Unit tests for DeckBuilder, DeckValidator, PTCGL Import/Export, and AntiMetaOptimizer.
"""

import unittest
from deck_builder import DeckBuilder, DeckValidator, AntiMetaOptimizer
game_engine = __import__("Game Engine")
CardFactory = game_engine.CardFactory


class TestDeckBuilder(unittest.TestCase):
    def setUp(self):
        self.factory = CardFactory('cards.json')
        self.builder = DeckBuilder(self.factory)
        self.optimizer = AntiMetaOptimizer(self.factory)

    def test_deck_validator_valid_deck(self):
        """Test validator on a legal 60-card deck."""
        legal_deck = (
            ["Ralts"] * 4 +
            ["Kirlia"] * 4 +
            ["Gardevoir ex"] * 2 +
            ["Hero's Cape"] * 1 +
            ["Buddy-Buddy Poffin"] * 4 +
            ["Ultra Ball"] * 4 +
            ["Super Rod"] * 2 +
            ["Professor's Research"] * 4 +
            ["Iono"] * 3 +
            ["Boss's Orders"] * 2 +
            ["Psychic Energy"] * 30
        )
        is_valid, errors = DeckValidator.validate_deck(legal_deck, self.factory)
        self.assertTrue(is_valid, f"Validation failed with errors: {errors}")
        self.assertEqual(len(errors), 0)

    def test_deck_validator_invalid_card_count(self):
        """Test validator catches 59-card or 61-card decks."""
        short_deck = ["Pikachu"] * 59
        is_valid, errors = DeckValidator.validate_deck(short_deck, self.factory)
        self.assertFalse(is_valid)
        self.assertTrue(any("exactly 60 cards" in e for e in errors))

    def test_deck_validator_four_copy_limit(self):
        """Test validator catches >4 copies of non-basic energy cards."""
        illegal_deck = ["Professor's Research"] * 5 + ["Pikachu"] * 55
        is_valid, errors = DeckValidator.validate_deck(illegal_deck, self.factory)
        self.assertFalse(is_valid)
        self.assertTrue(any("maximum allowed is 4" in e for e in errors))

    def test_deck_validator_ace_spec_limit(self):
        """Test validator catches >1 ACE SPEC card."""
        illegal_deck = ["Hero's Cape"] * 1 + ["Prime Catcher"] * 1 + ["Pikachu"] * 58
        is_valid, errors = DeckValidator.validate_deck(illegal_deck, self.factory)
        self.assertFalse(is_valid)
        self.assertTrue(any("ACE SPEC" in e for e in errors))

    def test_deck_validator_no_basic_pokemon(self):
        """Test validator catches decks with no Basic Pokémon."""
        illegal_deck = ["Kirlia"] * 4 + ["Psychic Energy"] * 56
        is_valid, errors = DeckValidator.validate_deck(illegal_deck, self.factory)
        self.assertFalse(is_valid)
        self.assertTrue(any("at least 1 Basic Pokémon" in e for e in errors))

    def test_generate_deck_from_scratch_stage2_charizard(self):
        """Test scratch generator generates a legal 60-card Charizard ex Stage 2 deck with Rare Candy."""
        deck = self.builder.generate_deck_from_scratch(
            primary_attacker="Charizard ex",
            preferred_ace_spec="Unfair Stamp"
        )
        self.assertEqual(len(deck), 60)
        is_valid, errors = DeckValidator.validate_deck(deck, self.factory)
        self.assertTrue(is_valid, f"Generated Charizard deck is invalid: {errors}")
        self.assertIn("Charmander", deck)
        self.assertIn("Charizard ex", deck)
        self.assertIn("Rare Candy", deck)
        self.assertIn("Unfair Stamp", deck)

    def test_generate_deck_from_scratch_stage1_ceruledge(self):
        """Test scratch generator generates a legal 60-card Ceruledge ex Stage 1 deck."""
        deck = self.builder.generate_deck_from_scratch(
            primary_attacker="Ceruledge ex",
            preferred_ace_spec="Grand Tree"
        )
        self.assertEqual(len(deck), 60)
        is_valid, errors = DeckValidator.validate_deck(deck, self.factory)
        self.assertTrue(is_valid, f"Generated Ceruledge deck is invalid: {errors}")
        self.assertIn("Charcadet", deck)
        self.assertIn("Ceruledge ex", deck)
        self.assertIn("Grand Tree", deck)

    def test_generate_deck_from_scratch_basic_terapagos(self):
        """Test scratch generator generates a legal 60-card Terapagos ex Basic Tera deck with Area Zero."""
        deck = self.builder.generate_deck_from_scratch(
            primary_attacker="Terapagos ex",
            preferred_ace_spec="Prime Catcher",
            support_engine="tera_support"
        )
        self.assertEqual(len(deck), 60)
        is_valid, errors = DeckValidator.validate_deck(deck, self.factory)
        self.assertTrue(is_valid, f"Generated Terapagos deck is invalid: {errors}")
        self.assertIn("Terapagos ex", deck)
        self.assertIn("Area Zero Underdepths", deck)
        self.assertIn("Prime Catcher", deck)

    def test_ptcgl_import_and_export_roundtrip(self):
        """Test exporting a deck to PTCGL format and importing it back retains card integrity."""
        deck = self.builder.generate_deck_from_scratch("Gardevoir ex", preferred_ace_spec="Hero's Cape")
        ptcgl_text = self.builder.export_to_ptcgl(deck)
        
        self.assertIn("Pokémon:", ptcgl_text)
        self.assertIn("Trainer:", ptcgl_text)
        self.assertIn("Energy:", ptcgl_text)
        self.assertIn("Gardevoir ex", ptcgl_text)
        self.assertIn("Hero's Cape", ptcgl_text)

        imported_deck = self.builder.import_from_ptcgl(ptcgl_text)
        self.assertEqual(len(imported_deck), 60)
        self.assertEqual(sorted(deck), sorted(imported_deck))

    def test_anti_meta_optimizer_tournament_evaluation(self):
        """Test AntiMetaOptimizer evaluates field share and selects highest EV deck."""
        target_meta = {
            "Charizard ex": 0.50,
            "Gardevoir ex": 0.50
        }
        res = self.optimizer.optimize_anti_meta_deck(
            target_meta,
            candidate_archetypes=[
                ("Ceruledge ex", "Fire", ["Grand Tree"]),
                ("Terapagos ex", "Colorless", ["Prime Catcher"])
            ],
            sample_games_per_eval=1,
            mcts_iterations=5
        )
        self.assertIn("best_deck_name", res)
        self.assertIn("best_decklist", res)
        self.assertEqual(len(res["best_decklist"]), 60)
        self.assertIn("expected_winrate", res)


if __name__ == '__main__':
    unittest.main()


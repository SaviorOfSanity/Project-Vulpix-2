"""
Comprehensive test suite for Pokemon TCG Game Engine, Rule Mechanics, AI Controllers, and MCTS.
"""

import unittest
import copy
import sys
import os

# Import from Game Engine.py
game_engine_module = __import__("Game Engine")
CardType = game_engine_module.CardType
TrainerType = game_engine_module.TrainerType
EnergyType = game_engine_module.EnergyType
Card = game_engine_module.Card
PokemonCard = game_engine_module.PokemonCard
TrainerCard = game_engine_module.TrainerCard
EnergyCard = game_engine_module.EnergyCard
CardFactory = game_engine_module.CardFactory
Player = game_engine_module.Player
GameState = game_engine_module.GameState
TurnBasedGreedyAI = game_engine_module.TurnBasedGreedyAI
MCTSNode = game_engine_module.MCTSNode
MCTSController = game_engine_module.MCTSController


class TestEngineMechanics(unittest.TestCase):
    def setUp(self):
        self.factory = CardFactory('cards.json')

    def test_player_equality_and_deepcopy(self):
        """Player class MUST implement __eq__ comparing by self.name to ensure .index() lookups work across deepcopies."""
        p1 = Player("P1", ["Pikachu"] * 10, self.factory)
        p2 = Player("P2", ["Charmander"] * 10, self.factory)
        game = GameState(p1, p2)

        cloned_game = copy.deepcopy(game)
        # Verify .index() works with the deepcopied players
        self.assertEqual(cloned_game.players.index(p1), 0)
        self.assertEqual(cloned_game.players.index(p2), 1)

        # Custom .clone() should also work
        fast_cloned_game = game.clone()
        self.assertEqual(fast_cloned_game.players.index(p1), 0)
        self.assertEqual(fast_cloned_game.players.index(p2), 1)

    def test_energy_cost_affordability(self):
        """Test exact energy requirement satisfaction and Colorless cost padding."""
        pikachu = self.factory.create_card("Pikachu")
        # Gnaw: 1 Colorless, Thunder Jolt: 1 Lightning + 1 Colorless
        l_energy = self.factory.create_card("Lightning Energy")
        f_energy = self.factory.create_card("Fire Energy")

        # 0 Energy
        self.assertFalse(pikachu.can_afford([EnergyType.COLORLESS]))
        self.assertFalse(pikachu.can_afford([EnergyType.LIGHTNING, EnergyType.COLORLESS]))

        # Attach 1 Fire Energy -> Can afford Gnaw (Colorless), but NOT Thunder Jolt (Lightning + Colorless)
        pikachu.attached_energy.append(f_energy)
        self.assertTrue(pikachu.can_afford([EnergyType.COLORLESS]))
        self.assertFalse(pikachu.can_afford([EnergyType.LIGHTNING, EnergyType.COLORLESS]))

        # Attach 1 Lightning Energy -> Now has [Fire, Lightning] -> Can afford Thunder Jolt
        pikachu.attached_energy.append(l_energy)
        self.assertTrue(pikachu.can_afford([EnergyType.LIGHTNING, EnergyType.COLORLESS]))

    def test_card_execution_order_professors_research(self):
        """
        Verify card resolution order for Professor's Research:
        1. Pop supporter card from hand first
        2. Execute card effect (discard remainder of hand, draw 7)
        3. Move played supporter to discard pile
        4. Set supporter_played_this_turn = True
        """
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        # On Turn 2+ (or P2 Turn 1), supporters are legal
        game.turn_number = 2
        p1.turns_taken = 1

        supporter = self.factory.create_card("Professor's Research")
        other_card = self.factory.create_card("Lightning Energy")
        p1.hand = [other_card, supporter]

        # Legal moves should include play_supporter
        legal_moves = game.get_legal_moves()
        supporter_move = ('play_supporter', 1)
        self.assertIn(supporter_move, legal_moves)

        turn_ended = game.handle_action(supporter_move, verbose=False)
        self.assertFalse(turn_ended)  # Supporter does not end the turn
        self.assertTrue(game.supporter_played_this_turn)
        self.assertEqual(len(p1.hand), 7)
        # Discard pile must contain the discarded other_card AND the played supporter
        self.assertIn(other_card, p1.discard_pile)
        self.assertIn(supporter, p1.discard_pile)
        self.assertEqual(p1.discard_pile[-1], supporter)

    def test_action_limitations(self):
        """Test energy attachment max 1, supporter max 1, retreat max 1, bench max 5."""
        p1 = Player("P1", ["Pikachu"] * 15, self.factory)
        p2 = Player("P2", ["Charmander"] * 15, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        # 1. Bench max 5
        p1.bench = [self.factory.create_card("Pikachu") for _ in range(5)]
        p1.hand = [self.factory.create_card("Pikachu")]
        moves = game.get_legal_moves()
        self.assertNotIn(('play_pokemon', 0), moves)

        # 2. Energy attachment max 1
        p1.hand = [self.factory.create_card("Lightning Energy")]
        game.energy_attached_this_turn = True
        moves = game.get_legal_moves()
        self.assertNotIn(('attach_energy', 0, 0), moves)

        # 3. Supporter max 1
        p1.hand = [self.factory.create_card("Professor's Research")]
        game.supporter_played_this_turn = True
        moves = game.get_legal_moves()
        self.assertNotIn(('play_supporter', 0), moves)

    def test_knockout_and_win_conditions(self):
        """
        Test knockout handling:
        1. Discard active Pokémon
        2. prize_taker = self.players[1 - self.players.index(defeated_player)]
        3. Strict win check order: Prizes -> Bench wipe -> Promote bench
        """
        p1 = Player("P1", ["Pikachu"] * 15, self.factory)
        p2 = Player("P2", ["Charmander"] * 15, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        # Scenario A: Bench wipe win condition
        p2.active_pokemon.damage_counters = 50  # Max HP 70
        p2.bench = []
        p1.prize_cards = [self.factory.create_card("Lightning Energy") for _ in range(3)]

        # Apply 30 damage to KO Charmander
        p1.active_pokemon.attached_energy = [self.factory.create_card("Lightning Energy"), self.factory.create_card("Lightning Energy")]
        game.handle_action(('attack', 1), verbose=False)  # Thunder Jolt 30 dmg

        self.assertTrue(game.game_over)
        self.assertEqual(game.winner, p1)
        self.assertIn("bench wipe", game.win_reason.lower())

        # Scenario B: Prize win condition
        game2 = GameState(p1, p2)
        game2.setup_game(verbose=False)
        p2.bench = [self.factory.create_card("Charmander")]
        p1.prize_cards = [self.factory.create_card("Lightning Energy")]  # Only 1 prize left
        p2.active_pokemon.damage_counters = 50

        p1.active_pokemon.attached_energy = [self.factory.create_card("Lightning Energy"), self.factory.create_card("Lightning Energy")]
        game2.handle_action(('attack', 1), verbose=False)

        self.assertTrue(game2.game_over)
        self.assertEqual(game2.winner, p1)
        self.assertIn("taking all prize cards", game2.win_reason.lower())

    def test_deck_out_win_condition(self):
        """If a player cannot draw a card at turn start, opponent wins by deck out."""
        p1 = Player("P1", ["Pikachu"] * 10, self.factory)
        p2 = Player("P2", ["Charmander"] * 10, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        # Empty P2's deck
        p2.deck = []
        # End P1's turn
        game.switch_turns(verbose=False)

        self.assertTrue(game.game_over)
        self.assertEqual(game.winner, p1)
        self.assertIn("deck out", game.win_reason.lower())


    def test_evolution_mechanics(self):
        """Test evolving basic Pokémon on turn 2+ preserves damage counters, energy, and sets base_card."""
        p1 = Player("P1", ["Charmander"] * 30, self.factory)
        p2 = Player("P2", ["Pikachu"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        # Advance to P1 Turn 2 (p1.turns_taken >= 1)
        p1.turns_taken = 1
        game.turn_number = 2

        charmander = p1.active_pokemon
        charmander.turn_played = -1  # In play from setup
        charmander.damage_counters = 20
        f_energy = self.factory.create_card("Fire Energy")
        charmander.attached_energy.append(f_energy)

        charmeleon = self.factory.create_card("Charmeleon")
        p1.hand = [charmeleon]

        moves = game.get_legal_moves()
        self.assertIn(('evolve', 0, 0), moves)

        game.handle_action(('evolve', 0, 0), verbose=False)
        self.assertEqual(p1.active_pokemon.name, "Charmeleon")
        self.assertEqual(p1.active_pokemon.damage_counters, 20)
        self.assertEqual(p1.active_pokemon.attached_energy, [f_energy])
        self.assertEqual(p1.active_pokemon.base_card.name, "Charmander")
        self.assertEqual(p1.active_pokemon.turn_played, 2)

    def test_evolution_timing_restrictions(self):
        """
        Official Pokémon TCG Rules:
        1. Cannot evolve on a player's first turn of the game (turns_taken == 0).
        2. Cannot evolve on the same turn a Pokémon was placed down.
        """
        p1 = Player("P1", ["Charmander"] * 30, self.factory)
        p2 = Player("P2", ["Pikachu"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        charmeleon = self.factory.create_card("Charmeleon")
        p1.hand = [charmeleon]

        # Case 1: P1 Turn 1 (turns_taken == 0) -> CANNOT evolve
        moves = game.get_legal_moves()
        self.assertNotIn(('evolve', 0, 0), moves)

        # Case 2: P1 Turn 2 (turns_taken == 1, turn_number = 2)
        p1.turns_taken = 1
        game.turn_number = 2

        # Active Charmander from setup (turn_played = -1) -> CAN evolve
        moves = game.get_legal_moves()
        self.assertIn(('evolve', 0, 0), moves)

        # Case 3: Place a new Charmander on bench during Turn 2 -> CANNOT evolve on same turn
        p1.bench = []
        new_charmander = self.factory.create_card("Charmander")
        p1.hand = [new_charmander, charmeleon]
        game.handle_action(('play_pokemon', 0), verbose=False)  # target bench 0
        self.assertEqual(p1.bench[0].turn_played, 2)

        # Active (setup) can evolve, but newly placed bench Charmander (target_idx 1) CANNOT evolve
        moves = game.get_legal_moves()
        self.assertIn(('evolve', 0, 0), moves)  # Active target 0 can evolve
        self.assertNotIn(('evolve', 0, 1), moves)  # Bench target 1 CANNOT evolve on turn played

    def test_retreat_mechanics(self):
        """Test retreating active Pokémon discards retreat cost and swaps with bench."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        benched_pika = self.factory.create_card("Pikachu")
        p1.bench = [benched_pika]
        active_pika = p1.active_pokemon
        l_energy = self.factory.create_card("Lightning Energy")
        active_pika.attached_energy = [l_energy]  # Pikachu retreat cost is 1

        moves = game.get_legal_moves()
        self.assertIn(('retreat', 0), moves)

        game.handle_action(('retreat', 0), verbose=False)
        self.assertEqual(p1.active_pokemon, benched_pika)
        self.assertEqual(p1.bench[0], active_pika)
        self.assertEqual(len(active_pika.attached_energy), 0)
        self.assertIn(l_energy, p1.discard_pile)
        self.assertTrue(game.retreated_this_turn)


    def test_p1_turn_1_restrictions(self):
        """Official Tournament Rules: Player 1 going first on Turn 1 cannot attack and cannot play Supporters."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        # Attach 2 Lightning energy to active Pikachu and give a Supporter
        p1.active_pokemon.attached_energy = [
            self.factory.create_card("Lightning Energy"),
            self.factory.create_card("Lightning Energy")
        ]
        p1.hand = [self.factory.create_card("Professor's Research")]

        # On Turn 1 (game.turn_number == 0): Neither attack nor supporter is legal
        moves = game.get_legal_moves()
        self.assertNotIn(('attack', 0), moves)
        self.assertNotIn(('attack', 1), moves)
        self.assertNotIn(('play_supporter', 0), moves)

        # Switch to P2 (Turn 2, game.turn_number == 1)
        game.switch_turns(verbose=False)
        p2.active_pokemon.attached_energy = [
            self.factory.create_card("Fire Energy"),
            self.factory.create_card("Fire Energy")
        ]
        p2.hand = [self.factory.create_card("Professor's Research")]

        # P2 going second CAN attack and CAN play Supporters on their first turn
        moves_p2 = game.get_legal_moves()
        self.assertIn(('attack', 0), moves_p2)
        self.assertIn(('play_supporter', 0), moves_p2)

    def test_weakness_and_resistance_calculation(self):
        """Test 2x damage for weakness and -30 damage for resistance."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        # Give Defender a Water weakness (like Charmander) and Attacker Water element
        defender = p2.active_pokemon
        defender.weakness = EnergyType.WATER
        defender.resistance = None

        attacker = p1.active_pokemon
        attacker.element = EnergyType.WATER

        # Attack with 10 base damage -> Weakness doubles to 20
        game.turn_number = 2  # P1 Turn 2
        p1.turns_taken = 1
        attacker.attached_energy = [self.factory.create_card("Lightning Energy")]
        game._handle_attack(0, verbose=False)  # Gnaw 10 base dmg
        self.assertEqual(defender.damage_counters, 20)

        # Now test resistance: Defender resists Water
        defender.damage_counters = 0
        defender.weakness = None
        defender.resistance = EnergyType.WATER
        game._handle_attack(0, verbose=False)  # 10 base dmg - 30 resistance = 0
        self.assertEqual(defender.damage_counters, 0)

    def test_multi_prize_knockout_ex(self):
        """Test that knocking out a Pokémon ex (prize_yield=2) awards 2 prize cards."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Pikachu ex"] * 10 + ["Charmander"] * 20, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        # Setup P2 active as Pikachu ex (200 HP, 2 Prizes)
        p2_ex = self.factory.create_card("Pikachu ex")
        p2.active_pokemon = p2_ex
        self.assertEqual(p2_ex.prize_yield, 2)
        self.assertTrue(p2_ex.is_rule_box)

        # P1 starts with 6 prizes
        self.assertEqual(len(p1.prize_cards), 6)

        # Knock out Pikachu ex
        p2_ex.apply_damage(200, verbose=False)
        game._handle_knockout(p2, verbose=False)

        # P1 should have taken 2 prize cards -> 4 remaining
        self.assertEqual(len(p1.prize_cards), 4)

    def test_pokemon_tool_attachment_and_hp_boost(self):
        """Test Bravery Charm provides +50 HP to Basic Pokémon and enforces 1 tool per Pokémon."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        active_pika = p1.active_pokemon
        self.assertEqual(active_pika.get_effective_max_hp(), 60)

        # Give P1 Bravery Charm
        charm = self.factory.create_card("Bravery Charm")
        p1.hand = [charm]

        moves = game.get_legal_moves()
        self.assertIn(('attach_tool', 0, 0), moves)

        # Attach tool to active Pikachu
        game.handle_action(('attach_tool', 0, 0), verbose=False)
        self.assertEqual(active_pika.attached_tool, charm)
        self.assertEqual(active_pika.get_effective_max_hp(), 110)

        # Give P1 another Bravery Charm -> Cannot attach to active Pikachu because it already has a tool
        charm2 = self.factory.create_card("Bravery Charm")
        p1.hand = [charm2]
        moves_after = game.get_legal_moves()
        self.assertNotIn(('attach_tool', 0, 0), moves_after)

    def test_pokemon_tool_damage_boost_maximum_belt(self):
        """Test Maximum Belt deals +50 extra damage against Pokémon ex."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Pikachu ex"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        game.turn_number = 2
        p1.turns_taken = 1

        p2.active_pokemon = self.factory.create_card("Pikachu ex")
        belt = self.factory.create_card("Maximum Belt")
        p1.active_pokemon.attached_tool = belt
        p1.active_pokemon.attached_energy = [self.factory.create_card("Lightning Energy")]

        # Gnaw base damage is 10 + 50 Belt boost vs ex = 60 total damage
        game._handle_attack(0, verbose=False)
        self.assertEqual(p2.active_pokemon.damage_counters, 60)

    def test_stadium_rules_and_replacement(self):
        """Test Stadium placement, once per turn limit, and replacement."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        stadium1 = self.factory.create_card("Artazon")
        stadium2 = self.factory.create_card("Artazon")
        p1.hand = [stadium1, stadium2]

        # Play first stadium
        moves = game.get_legal_moves()
        self.assertIn(('play_stadium', 0), moves)
        game.handle_action(('play_stadium', 0), verbose=False)

        self.assertEqual(game.active_stadium, stadium1)
        self.assertTrue(game.stadium_played_this_turn)

        # Cannot play another stadium in the same turn
        moves2 = game.get_legal_moves()
        self.assertNotIn(('play_stadium', 0), moves2)

    def test_item_cards_unlimited_plays(self):
        """Test Item cards can be played multiple times per turn."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        nest_ball_1 = self.factory.create_card("Nest Ball")
        nest_ball_2 = self.factory.create_card("Nest Ball")
        p1.hand = [nest_ball_1, nest_ball_2]
        p1.deck = [self.factory.create_card("Pikachu"), self.factory.create_card("Pikachu")]
        p1.bench = []

        # Play first Nest Ball
        game.handle_action(('play_item', 0), verbose=False)
        self.assertEqual(len(p1.bench), 1)

        # Play second Nest Ball in same turn -> Still legal
        moves = game.get_legal_moves()
        self.assertIn(('play_item', 0), moves)
        game.handle_action(('play_item', 0), verbose=False)
        self.assertEqual(len(p1.bench), 2)

    def test_rare_candy_evolution(self):
        """Test Rare Candy evolves Basic directly into Stage 2."""
        p1 = Player("P1", ["Charmander"] * 30, self.factory)
        p2 = Player("P2", ["Pikachu"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        game.turn_number = 2
        p1.turns_taken = 1

        active_charmander = p1.active_pokemon
        active_charmander.turn_played = 0

        charizard_ex = self.factory.create_card("Charizard ex")
        rare_candy = self.factory.create_card("Rare Candy")
        p1.hand = [rare_candy, charizard_ex]

        # Play Rare Candy
        game.handle_action(('play_item', 0), verbose=False)
        self.assertEqual(p1.active_pokemon.name, "Charizard ex")
        self.assertEqual(p1.active_pokemon.base_card, active_charmander)


class TestAIControllers(unittest.TestCase):
    def setUp(self):
        self.factory = CardFactory('cards.json')

    def test_turn_based_greedy_ai(self):
        """Verify TurnBasedGreedyAI prioritization on turn 2+: Bench/Evolve -> Attach Energy -> Supporter -> Attack -> Pass."""
        ai = TurnBasedGreedyAI()
        p1 = Player("P1", ["Pikachu"] * 30, self.factory, controller=ai)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        # Set to Turn 2+ (turn_number = 2, turns_taken = 1) so Supporters and Attacks are legal
        game.turn_number = 2
        p1.turns_taken = 1
        p1.bench = []

        p1.hand = [
            self.factory.create_card("Pikachu"),
            self.factory.create_card("Lightning Energy"),
            self.factory.create_card("Professor's Research")
        ]

        # Step 1: Should choose play_pokemon
        moves = game.get_legal_moves()
        action1 = ai.choose_action(game, moves)
        self.assertEqual(action1[0], 'play_pokemon')
        game.handle_action(action1, verbose=False)

        # Step 2: Should choose attach_energy to active
        moves = game.get_legal_moves()
        action2 = ai.choose_action(game, moves)
        self.assertEqual(action2[0], 'attach_energy')
        self.assertEqual(action2[2], 0)  # Target active
        game.handle_action(action2, verbose=False)

        # Step 3: Now has 1 energy on Pikachu -> Gnaw (10 dmg) is affordable!
        # According to priorities: Supporter before Attack
        moves = game.get_legal_moves()
        action3 = ai.choose_action(game, moves)
        self.assertEqual(action3[0], 'play_supporter')

    def test_mcts_controller_evaluation_and_search(self):
        """Verify MCTS composite heuristic evaluation and UCB1 search."""
        mcts = MCTSController(iteration_limit=50, simulation_depth=4)
        p1 = Player("P1", ["Pikachu"] * 15, self.factory, controller=mcts)
        p2 = Player("P2", ["Charmander"] * 15, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        # Test composite heuristic evaluation bounds
        eval_score = mcts._evaluate_state(game, p1)
        self.assertTrue(-1.0 <= eval_score <= 1.0)

        # Test MCTS move selection returns a legal move
        moves = game.get_legal_moves()
        chosen = mcts.choose_action(game, moves)
        self.assertIn(chosen, moves)


if __name__ == '__main__':
    unittest.main()

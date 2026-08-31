"""
Comprehensive test suite for Pokemon TCG Game Engine, Rule Mechanics, AI Controllers, and MCTS (Standard Format Phase 2).
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
        self.assertEqual(cloned_game.players.index(p1), 0)
        self.assertEqual(cloned_game.players.index(p2), 1)

        fast_cloned_game = game.clone()
        self.assertEqual(fast_cloned_game.players.index(p1), 0)
        self.assertEqual(fast_cloned_game.players.index(p2), 1)

    def test_energy_cost_affordability(self):
        """Test exact energy requirement satisfaction and Colorless cost padding."""
        pikachu = self.factory.create_card("Pikachu")
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
        """Verify card resolution order for Professor's Research."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        game.turn_number = 2
        p1.turns_taken = 1

        supporter = self.factory.create_card("Professor's Research")
        other_card = self.factory.create_card("Lightning Energy")
        p1.hand = [other_card, supporter]

        legal_moves = game.get_legal_moves()
        supporter_move = ('play_supporter', 1)
        self.assertIn(supporter_move, legal_moves)

        turn_ended = game.handle_action(supporter_move, verbose=False)
        self.assertFalse(turn_ended)
        self.assertTrue(game.supporter_played_this_turn)
        self.assertEqual(len(p1.hand), 7)
        self.assertIn(other_card, p1.discard_pile)
        self.assertIn(supporter, p1.discard_pile)
        self.assertEqual(p1.discard_pile[-1], supporter)

    def test_retreat_mechanics(self):
        """Test energy discard cost on retreat, state tracking, and bench promotion."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        game.turn_number = 2
        p1.turns_taken = 1

        p1.active_pokemon = self.factory.create_card("Pikachu")
        p1.bench = [self.factory.create_card("Charmander")]
        p1.active_pokemon.attached_energy = [self.factory.create_card("Lightning Energy")]

        # Retreat Pikachu (cost 1) -> Charmander becomes Active
        moves = game.get_legal_moves()
        self.assertIn(('retreat', 0), moves)

        turn_ended = game.handle_action(('retreat', 0), verbose=False)
        self.assertFalse(turn_ended)
        self.assertTrue(game.retreated_this_turn)
        self.assertEqual(p1.active_pokemon.name, "Charmander")
        self.assertEqual(p1.bench[0].name, "Pikachu")
        self.assertEqual(len(p1.discard_pile), 1)

    def test_multi_prize_knockout_ex(self):
        """Test Rule Box Pokémon ex awards 2 Prize Cards upon knockout."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        p2.active_pokemon = self.factory.create_card("Pikachu ex")  # 200 HP
        p2.bench = [self.factory.create_card("Charmander")]

        # Charizard ex with Maximum Belt (+50 vs ex): 180 + 50 = 230 damage (KOs 200 HP Pikachu ex)
        p1.active_pokemon = self.factory.create_card("Charizard ex")
        p1.active_pokemon.attached_energy = [self.factory.create_card("Fire Energy")] * 2
        p1.active_pokemon.attached_tool = self.factory.create_card("Maximum Belt")

        p1_initial_prizes = len(p1.prize_cards)  # 6
        game._handle_attack(0, verbose=False)

        self.assertEqual(p2.active_pokemon.name, "Charmander")
        self.assertEqual(len(p1.prize_cards), p1_initial_prizes - 2)

    def test_pokemon_tool_attachment_and_hp_boost(self):
        """Test Bravery Charm adds 50 HP only to Basic Pokémon."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        charm = self.factory.create_card("Bravery Charm")
        p1.active_pokemon = self.factory.create_card("Pikachu")  # Basic, 60 HP
        p1.active_pokemon.attached_tool = charm

        self.assertEqual(p1.active_pokemon.get_effective_max_hp(), 110)

        # Knockout threshold should be 110 HP
        p1.active_pokemon.apply_damage(60, verbose=False)
        self.assertFalse(p1.active_pokemon.is_knocked_out())

        p1.active_pokemon.apply_damage(50, verbose=False)
        self.assertTrue(p1.active_pokemon.is_knocked_out())

    def test_stadium_rules_and_replacement(self):
        """Test Stadium placement, once per turn limit, and replacement."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        stadium1 = self.factory.create_card("Artazon")
        stadium2 = self.factory.create_card("Artazon")
        p1.hand = [stadium1, stadium2]

        moves = game.get_legal_moves()
        self.assertIn(('play_stadium', 0), moves)
        game.handle_action(('play_stadium', 0), verbose=False)

        self.assertEqual(game.active_stadium, stadium1)
        self.assertTrue(game.stadium_played_this_turn)

        moves2 = game.get_legal_moves()
        self.assertNotIn(('play_stadium', 0), moves2)

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

        game.handle_action(('play_item', 0), verbose=False)
        self.assertEqual(p1.active_pokemon.name, "Charizard ex")
        self.assertEqual(p1.active_pokemon.base_card, active_charmander)

    # --- PHASE 2 META & MECHANIC TESTS ---

    def test_pidgeot_ex_quick_search_ability(self):
        """Test Pidgeot ex Quick Search ability searches deck for any card into hand."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        pidgeot = self.factory.create_card("Pidgeot ex")
        p1.bench = [pidgeot]
        p1.deck = [self.factory.create_card("Boss's Orders")] + p1.deck
        p1_hand_count = len(p1.hand)

        moves = game.get_legal_moves()
        ability_move = ('use_pokemon_ability', 1, 'Quick Search')
        self.assertIn(ability_move, moves)

        game.handle_action(ability_move, verbose=False)
        self.assertEqual(len(p1.hand), p1_hand_count + 1)
        self.assertEqual(p1.hand[-1].name, "Boss's Orders")
        self.assertTrue(pidgeot.ability_used_this_turn)

        # Cannot be used twice in same turn
        moves2 = game.get_legal_moves()
        self.assertNotIn(ability_move, moves2)

    def test_charizard_ex_infernal_reign_ability(self):
        """Test Charizard ex Infernal Reign attaches up to 3 Basic Fire Energy on evolve."""
        p1 = Player("P1", ["Fire Energy"] * 20 + ["Charmander"] * 10, self.factory)
        p2 = Player("P2", ["Pikachu"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        game.turn_number = 2
        p1.turns_taken = 1
        p1.bench = []

        active = p1.active_pokemon
        active.turn_played = 0

        zard = self.factory.create_card("Charizard ex")
        candy = self.factory.create_card("Rare Candy")
        p1.hand = [candy, zard]
        p1.deck = [self.factory.create_card("Fire Energy") for _ in range(5)]

        game.handle_action(('play_item', 0), verbose=False)
        self.assertEqual(p1.active_pokemon.name, "Charizard ex")
        # Should have attached 3 Fire Energy from deck to active
        self.assertEqual(len(p1.active_pokemon.attached_energy), 3)

    def test_teal_mask_ogerpon_teal_dance_ability(self):
        """Test Teal Mask Ogerpon ex attaches Grass energy from hand and draws 1 card."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        ogerpon = self.factory.create_card("Teal Mask Ogerpon ex")
        p1.active_pokemon = ogerpon
        grass = self.factory.create_card("Grass Energy")
        p1.hand = [grass]

        moves = game.get_legal_moves()
        ab_move = ('use_pokemon_ability', 0, 'Teal Dance')
        self.assertIn(ab_move, moves)

        game.handle_action(ab_move, verbose=False)
        self.assertIn(grass, ogerpon.attached_energy)
        self.assertEqual(len(p1.hand), 1)

    def test_miraidon_ex_tandem_unit_ability(self):
        """Test Miraidon ex Tandem Unit searches up to 2 Basic Lightning Pokemon to bench."""
        p1 = Player("P1", ["Lightning Energy"] * 10 + ["Pikachu"] * 10, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        miraidon = self.factory.create_card("Miraidon ex")
        p1.active_pokemon = miraidon
        p1.bench = []
        p1.deck = [self.factory.create_card("Pikachu"), self.factory.create_card("Pikachu ex")] + p1.deck

        moves = game.get_legal_moves()
        ab_move = ('use_pokemon_ability', 0, 'Tandem Unit')
        self.assertIn(ab_move, moves)

        game.handle_action(ab_move, verbose=False)
        self.assertEqual(len(p1.bench), 2)
        self.assertEqual(p1.bench[0].element, EnergyType.LIGHTNING)

    def test_dragapult_ex_phantom_dive_bench_damage(self):
        """Test Dragapult ex Phantom Dive deals 200 Active + 60 Bench spread damage."""
        p1 = Player("P1", ["Dreepy"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        dragapult = self.factory.create_card("Dragapult ex")
        dragapult.attached_energy = [self.factory.create_card("Fire Energy"), self.factory.create_card("Psychic Energy")]
        p1.active_pokemon = dragapult

        p2.active_pokemon = self.factory.create_card("Charizard ex")  # 330 HP
        p2_bench_charmander = self.factory.create_card("Charmander")  # 70 HP
        p2.bench = [p2_bench_charmander]

        game._handle_attack(0, verbose=False)
        self.assertEqual(p2.active_pokemon.damage_counters, 200)
        self.assertEqual(p2_bench_charmander.damage_counters, 60)

    def test_iron_hands_ex_amp_you_very_much_extra_prize(self):
        """Test Iron Hands ex Amp You Very Much takes 1 additional prize card on KO."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        iron_hands = self.factory.create_card("Iron Hands ex")
        iron_hands.attached_energy = [
            self.factory.create_card("Lightning Energy"),
            self.factory.create_card("Double Turbo Energy"),
            self.factory.create_card("Double Turbo Energy")
        ]
        p1.active_pokemon = iron_hands

        # Defending single-prize Charmander (70 HP)
        p2.active_pokemon = self.factory.create_card("Charmander")
        p2.bench = [self.factory.create_card("Charmander")]

        # Amp You Very Much: 120 base - 40 (2x DTE) = 80 dmg (KOs 70 HP Charmander)
        p1_prizes_start = len(p1.prize_cards)  # 6
        game._handle_attack(1, verbose=False)

        # Should take 1 (base) + 1 (extra_prizes) = 2 prize cards for a single prize KO!
        self.assertEqual(len(p1.prize_cards), p1_prizes_start - 2)

    def test_raging_bolt_ex_bellowing_thunder_energy_discard(self):
        """Test Raging Bolt ex Bellowing Thunder discards basic energies for 70x damage."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        bolt = self.factory.create_card("Raging Bolt ex")
        bolt.attached_energy = [
            self.factory.create_card("Lightning Energy"),
            self.factory.create_card("Fighting Energy"),
            self.factory.create_card("Grass Energy")
        ]
        p1.active_pokemon = bolt

        p2.active_pokemon = self.factory.create_card("Charizard ex")  # 330 HP
        p2.bench = [self.factory.create_card("Charmander")]

        # 3 Basic Energies discarded * 70 = 210 damage
        game._handle_attack(1, verbose=False)
        self.assertEqual(p2.active_pokemon.damage_counters, 210)
        self.assertEqual(len(bolt.attached_energy), 0)

    def test_jet_energy_auto_switch(self):
        """Test Jet Energy attached to Benched Pokemon automatically switches to Active."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        active = self.factory.create_card("Pikachu")
        benched = self.factory.create_card("Charmander")
        p1.active_pokemon = active
        p1.bench = [benched]

        jet = self.factory.create_card("Jet Energy")
        p1.hand = [jet]

        # Attach Jet Energy to Benched Charmander (target_idx 1)
        game.handle_action(('attach_energy', 0, 1), verbose=False)
        self.assertEqual(p1.active_pokemon, benched)
        self.assertEqual(p1.bench[0], active)

    def test_double_turbo_energy_damage_reduction_and_cost(self):
        """Test Double Turbo Energy provides 2 Colorless and reduces attack damage by 20."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        dte = self.factory.create_card("Double Turbo Energy")
        pidgeot = self.factory.create_card("Pidgeot ex")
        # Blistering Wind cost: [Colorless, Colorless], base 120 dmg
        pidgeot.attached_energy = [dte]
        self.assertTrue(pidgeot.can_afford([EnergyType.COLORLESS, EnergyType.COLORLESS]))

        p1.active_pokemon = pidgeot
        p2.active_pokemon = self.factory.create_card("Charizard ex")
        p2.bench = [self.factory.create_card("Charmander")]

        # 120 - 20 (DTE) = 100 damage
        game._handle_attack(0, verbose=False)
        self.assertEqual(p2.active_pokemon.damage_counters, 100)

    def test_buddy_buddy_poffin_and_counter_catcher(self):
        """Test Buddy-Buddy Poffin benches up to 2 <=70 HP Basic Pokemon and Counter Catcher gusts when behind on prizes."""
        p1 = Player("P1", ["Charmander"] * 4 + ["Pikachu"] * 26, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        p1.bench = []
        poffin = self.factory.create_card("Buddy-Buddy Poffin")
        p1.hand = [poffin]

        game.handle_action(('play_item', 0), verbose=False)
        self.assertEqual(len(p1.bench), 2)
        for b in p1.bench:
            self.assertTrue(b.max_hp <= 70)

        # Counter Catcher: only legal when behind in prizes
        cc = self.factory.create_card("Counter Catcher")
        p1.hand = [cc]
        p2.active_pokemon = self.factory.create_card("Pikachu")
        p2_bench_target = self.factory.create_card("Charizard ex")
        p2.bench = [p2_bench_target]

        # Equal prizes (6 vs 6) -> Not legal
        self.assertNotIn(('play_item', 0), game.get_legal_moves())

        # P2 takes 1 prize (P1 has 6, P2 has 5 -> P1 is behind)
        p2.prize_cards.pop()
        self.assertIn(('play_item', 0), game.get_legal_moves())

        game.handle_action(('play_item', 0), verbose=False)
        self.assertEqual(p2.active_pokemon, p2_bench_target)

    def test_electric_generator_and_professor_sada(self):
        """Test Electric Generator attaches Lightning energy to benched Lightning Pokemon and Sada attaches from discard to Ancient."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        # 1. Electric Generator test
        gen = self.factory.create_card("Electric Generator")
        p1.hand = [gen]
        p1.bench = [self.factory.create_card("Pikachu")]
        p1.deck = [self.factory.create_card("Lightning Energy"), self.factory.create_card("Lightning Energy")] + p1.deck

        game.handle_action(('play_item', 0), verbose=False)
        self.assertEqual(len(p1.bench[0].attached_energy), 2)

        # 2. Professor Sada's Vitality test
        game.turn_number = 2
        p1.turns_taken = 1
        sada = self.factory.create_card("Professor Sada's Vitality")
        p1.hand = [sada]
        bolt = self.factory.create_card("Raging Bolt ex")
        p1.active_pokemon = bolt
        p1.discard_pile = [self.factory.create_card("Fighting Energy")]

        game.handle_action(('play_supporter', 0), verbose=False)
        self.assertEqual(len(bolt.attached_energy), 1)
        self.assertEqual(len(p1.hand), 3)  # Drew 3 cards


class TestAIControllers(unittest.TestCase):
    def setUp(self):
        self.factory = CardFactory('cards.json')

    def test_turn_based_greedy_ai(self):
        """Verify TurnBasedGreedyAI prioritization: Abilities -> Bench/Evolve -> Attach Energy -> Supporter -> Attack -> Pass."""
        ai = TurnBasedGreedyAI()
        p1 = Player("P1", ["Pikachu"] * 30, self.factory, controller=ai)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        game.turn_number = 2
        p1.turns_taken = 1
        p1.bench = []

        miraidon = self.factory.create_card("Miraidon ex")
        p1.active_pokemon = miraidon

        p1.hand = [
            self.factory.create_card("Pikachu"),
            self.factory.create_card("Lightning Energy"),
            self.factory.create_card("Professor's Research")
        ]

        # Step 1: Should choose ability Tandem Unit
        moves = game.get_legal_moves()
        action1 = ai.choose_action(game, moves)
        self.assertEqual(action1[0], 'use_pokemon_ability')
        game.handle_action(action1, verbose=False)

        # Step 2: Should choose play_pokemon
        moves = game.get_legal_moves()
        action2 = ai.choose_action(game, moves)
        self.assertEqual(action2[0], 'play_pokemon')
        game.handle_action(action2, verbose=False)

    def test_mcts_controller_evaluation_and_search(self):
        """Verify MCTS composite heuristic evaluation and UCB1 search."""
        mcts = MCTSController(iteration_limit=50, simulation_depth=4)
        p1 = Player("P1", ["Pikachu"] * 15, self.factory, controller=mcts)
        p2 = Player("P2", ["Charmander"] * 15, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        eval_score = mcts._evaluate_state(game, p1)
        self.assertTrue(-1.0 <= eval_score <= 1.0)

        moves = game.get_legal_moves()
        chosen = mcts.choose_action(game, moves)
        self.assertIn(chosen, moves)


if __name__ == '__main__':
    unittest.main()

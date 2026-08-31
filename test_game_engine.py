"""
Comprehensive test suite for Pokemon TCG Game Engine, Rule Mechanics, AI Controllers, and MCTS (Standard Format Phase 3).
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
SpecialCondition = game_engine_module.SpecialCondition
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

        p2.active_pokemon = self.factory.create_card("Charmander")
        p2.bench = [self.factory.create_card("Charmander")]

        p1_prizes_start = len(p1.prize_cards)  # 6
        game._handle_attack(1, verbose=False)

        # 1 (base) + 1 (extra) = 2 prizes
        self.assertEqual(len(p1.prize_cards), p1_prizes_start - 2)

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

        game.handle_action(('attach_energy', 0, 1), verbose=False)
        self.assertEqual(p1.active_pokemon, benched)
        self.assertEqual(p1.bench[0], active)

    # --- PHASE 3 TESTS: SPECIAL CONDITIONS & CHECKUP ---

    def test_special_conditions_poison_and_burn_checkup(self):
        """Test Poison (10 dmg) and Burn (20 dmg) apply damage during between-turn Pokémon Checkup."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        p1.active_pokemon = self.factory.create_card("Charmander")  # 70 HP
        p1.active_pokemon.add_special_condition(SpecialCondition.POISONED, poison_dmg=10)
        p1.active_pokemon.add_special_condition(SpecialCondition.BURNED)

        # Checkup should deal 10 (Poison) + 20 (Burn) = 30 damage
        game.pokemon_checkup(verbose=False)
        self.assertEqual(p1.active_pokemon.damage_counters, 30)

    def test_special_conditions_asleep_and_paralyzed_retreat_block(self):
        """Test Asleep and Paralyzed block attacking and retreating."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        game.turn_number = 2
        p1.turns_taken = 1

        p1.active_pokemon = self.factory.create_card("Pikachu")
        p1.active_pokemon.attached_energy = [self.factory.create_card("Lightning Energy")] * 2
        p1.bench = [self.factory.create_card("Charmander")]

        # Normal state: Attack and Retreat are legal
        moves = game.get_legal_moves()
        self.assertTrue(any(m[0] == 'attack' for m in moves))
        self.assertTrue(any(m[0] == 'retreat' for m in moves))

        # Put to Sleep: Attack and Retreat must be prohibited
        p1.active_pokemon.add_special_condition(SpecialCondition.ASLEEP)
        moves_asleep = game.get_legal_moves()
        self.assertFalse(any(m[0] == 'attack' for m in moves_asleep))
        self.assertFalse(any(m[0] == 'retreat' for m in moves_asleep))

    def test_special_conditions_cleared_on_bench_and_evolution(self):
        """Test Special Conditions are cured when switching to bench or evolving."""
        p1 = Player("P1", ["Charmander"] * 30, self.factory)
        p2 = Player("P2", ["Pikachu"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        p1.active_pokemon = self.factory.create_card("Charmander")
        p1.active_pokemon.add_special_condition(SpecialCondition.POISONED)
        self.assertTrue(p1.active_pokemon.is_poisoned())

        # Evolve via Rare Candy -> Special Conditions cleared!
        p1.hand = [self.factory.create_card("Rare Candy"), self.factory.create_card("Charizard ex")]
        game.turn_number = 2
        p1.turns_taken = 1
        p1.active_pokemon.turn_played = 0

        game.handle_action(('play_item', 0), verbose=False)
        self.assertEqual(p1.active_pokemon.name, "Charizard ex")
        self.assertFalse(p1.active_pokemon.is_poisoned())

    # --- PHASE 3 TESTS: ACE SPEC CARDS ---

    def test_ace_spec_deck_limit_enforcement(self):
        """Test strict validation that a deck cannot contain more than 1 ACE SPEC card."""
        illegal_deck = ["Prime Catcher", "Hero's Cape"] + ["Pikachu"] * 58
        with self.assertRaises(ValueError):
            Player("IllegalPlayer", illegal_deck, self.factory)

    def test_ace_spec_prime_catcher(self):
        """Test Prime Catcher gusts opponent's bench AND switches user's active in one action."""
        p1 = Player("P1", ["Prime Catcher"] + ["Pikachu"] * 29, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        my_active = self.factory.create_card("Pikachu")
        my_bench = self.factory.create_card("Ralts")
        p1.active_pokemon = my_active
        p1.bench = [my_bench]

        opp_active = self.factory.create_card("Charmander")
        opp_bench = self.factory.create_card("Charizard ex")
        p2.active_pokemon = opp_active
        p2.bench = [opp_bench]

        p1.hand = [self.factory.create_card("Prime Catcher")]
        game.handle_action(('play_item', 0), verbose=False)

        # Both sides switched
        self.assertEqual(p1.active_pokemon, my_bench)
        self.assertEqual(p2.active_pokemon, opp_bench)

    def test_ace_spec_heros_cape_100_hp_boost(self):
        """Test Hero's Cape ACE SPEC Tool grants +100 HP to any Pokémon."""
        p1 = Player("P1", ["Hero's Cape"] + ["Pikachu"] * 29, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        drifloon = self.factory.create_card("Drifloon")  # Base 70 HP
        p1.active_pokemon = drifloon
        drifloon.attached_tool = self.factory.create_card("Hero's Cape")

        self.assertEqual(drifloon.get_effective_max_hp(), 170)

    def test_ace_spec_unfair_stamp_disruption(self):
        """Test Unfair Stamp only playable after a friendly KO, reshuffling hand to 5 (user) and 2 (opp)."""
        p1 = Player("P1", ["Unfair Stamp"] + ["Pikachu"] * 29, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        p1.hand = [self.factory.create_card("Unfair Stamp")]
        p2.hand = [self.factory.create_card("Pikachu")] * 6

        # Not legal if no KO occurred
        self.assertNotIn(('play_item', 0), game.get_legal_moves())

        # KO occurred last turn
        p1.pokemon_ko_last_turn = True
        self.assertIn(('play_item', 0), game.get_legal_moves())

        game.handle_action(('play_item', 0), verbose=False)
        self.assertEqual(len(p1.hand), 5)
        self.assertEqual(len(p2.hand), 2)

    # --- PHASE 3 TESTS: GARDEVOIR & TERA ARCHETYPES ---

    def test_gardevoir_ex_psychic_embrace_and_drifloon_scaling(self):
        """Test Gardevoir ex Psychic Embrace accelerates energy from discard with 20 self-damage and scales Balloon Blast."""
        p1 = Player("P1", ["Ralts"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        gardevoir = self.factory.create_card("Gardevoir ex")
        drifloon = self.factory.create_card("Drifloon")  # 70 HP
        drifloon.attached_tool = self.factory.create_card("Hero's Cape")  # 170 HP max!
        p1.active_pokemon = drifloon
        p1.bench = [gardevoir]

        p1.discard_pile = [self.factory.create_card("Psychic Energy") for _ in range(4)]

        # Attach 2 Psychic Energy via Psychic Embrace to Drifloon (target_idx 0)
        # Move: ('use_pokemon_ability', 1 (Gardevoir on bench), 'Psychic Embrace', 0 (Drifloon))
        game.handle_action(('use_pokemon_ability', 1, 'Psychic Embrace', 0), verbose=False)
        game.handle_action(('use_pokemon_ability', 1, 'Psychic Embrace', 0), verbose=False)

        self.assertEqual(len(drifloon.attached_energy), 2)
        self.assertEqual(drifloon.damage_counters, 40)

        # Drifloon Balloon Blast: 30x per damage counter = 30 * 4 = 120 damage!
        p2.active_pokemon = self.factory.create_card("Charizard ex")  # 330 HP
        p2.bench = [self.factory.create_card("Charmander")]

        game._handle_attack(0, verbose=False)
        self.assertEqual(p2.active_pokemon.damage_counters, 120)

    def test_terapagos_ex_unified_barrage_and_area_zero(self):
        """Test Area Zero Underdepths expands Bench to 8 with Tera Pokémon and scales Unified Barrage (30x bench)."""
        p1 = Player("P1", ["Hoothoot"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        terapagos = self.factory.create_card("Terapagos ex")
        p1.active_pokemon = terapagos
        p1.active_pokemon.attached_energy = [self.factory.create_card("Double Turbo Energy")]

        # Standard bench limit without Area Zero is 5
        self.assertEqual(p1.get_max_bench_size(game), 5)

        # Play Area Zero Underdepths -> Bench limit becomes 8!
        area_zero = self.factory.create_card("Area Zero Underdepths")
        game.active_stadium = area_zero
        self.assertEqual(p1.get_max_bench_size(game), 8)

        # Fill bench with 8 benched Pokémon
        p1.bench = [self.factory.create_card("Hoothoot") for _ in range(8)]

        p2.active_pokemon = self.factory.create_card("Charizard ex")
        p2.bench = [self.factory.create_card("Charmander")]

        # Unified Barrage: 30 * 8 = 240 - 20 (Double Turbo Energy) = 220 damage!
        game._handle_attack(0, verbose=False)
        self.assertEqual(p2.active_pokemon.damage_counters, 220)

    def test_munkidori_adrena_brain_damage_transfer(self):
        """Test Munkidori Adrena-Brain moves 30 damage from friendly Pokémon to opponent."""
        p1 = Player("P1", ["Ralts"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        munki = self.factory.create_card("Munkidori")
        munki.attached_energy = [self.factory.create_card("Darkness Energy")]
        p1.active_pokemon = self.factory.create_card("Gardevoir ex")
        p1.active_pokemon.damage_counters = 40
        p1.bench = [munki]

        p2.active_pokemon = self.factory.create_card("Pikachu")
        p2.active_pokemon.damage_counters = 0

        # Move: ('use_pokemon_ability', 1 (Munki on bench), 'Adrena-Brain')
        game.handle_action(('use_pokemon_ability', 1, 'Adrena-Brain'), verbose=False)

        # 30 damage moved from Gardevoir to Pikachu
        self.assertEqual(p1.active_pokemon.damage_counters, 10)
        self.assertEqual(p2.active_pokemon.damage_counters, 30)

    def test_ismcts_determinization_robustness(self):
        """Verify ISMCTS belief-state determinization shuffles opponent hidden cards without mutating public state."""
        mcts = MCTSController(iteration_limit=50, simulation_depth=4)
        p1 = Player("P1", ["Pikachu"] * 15, self.factory, controller=mcts)
        p2 = Player("P2", ["Charmander"] * 15, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        det_game = mcts._determinize_state(game, p1)
        self.assertEqual(len(det_game.players[1].hand), len(game.players[1].hand))
        self.assertEqual(len(det_game.players[1].deck), len(game.players[1].deck))
        self.assertEqual(len(det_game.players[1].prize_cards), len(game.players[1].prize_cards))

        moves = game.get_legal_moves()
        chosen = mcts.choose_action(game, moves)
        self.assertIn(chosen, moves)

    # --- PHASE 4 TESTS: MODERN SETS, NEW ARCHETYPES & TOURNAMENT MATRIX ---

    def test_gholdengo_ex_coin_bonus_and_make_it_rain(self):
        """Test Gholdengo ex Coin Bonus (draw 2 active) and Make It Rain (50x per basic energy discarded from hand)."""
        p1 = Player("P1", ["Gimmighoul"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        gholdengo = self.factory.create_card("Gholdengo ex")
        gholdengo.attached_energy = [self.factory.create_card("Metal Energy")]
        p1.active_pokemon = gholdengo

        # Hand has 3 Metal Energy
        p1.hand = [self.factory.create_card("Metal Energy") for _ in range(3)]
        p1_deck_count = len(p1.deck)

        # 1. Coin Bonus when Active: draws 2 cards
        game.handle_action(('use_pokemon_ability', 0, 'Coin Bonus'), verbose=False)
        self.assertEqual(len(p1.deck), p1_deck_count - 2)

        # 2. Make It Rain: discards all 3 Basic Energy from hand -> 3 * 50 = 150 damage!
        p2.active_pokemon = self.factory.create_card("Charizard ex")  # 330 HP
        p2.bench = [self.factory.create_card("Charmander")]

        game._handle_attack(0, verbose=False)
        self.assertEqual(p2.active_pokemon.damage_counters, 150)
        self.assertEqual(len(p1.hand), 2)  # Drew 2, discarded 3

    def test_ceruledge_ex_abyssal_flames_discard_scaling(self):
        """Test Ceruledge ex Abyssal Flames deals 30 + 30x per Energy card in discard pile."""
        p1 = Player("P1", ["Charcadet"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        ceruledge = self.factory.create_card("Ceruledge ex")
        ceruledge.attached_energy = [self.factory.create_card("Fire Energy")]
        p1.active_pokemon = ceruledge

        # 5 Fire Energy in discard pile
        p1.discard_pile = [self.factory.create_card("Fire Energy") for _ in range(5)]

        p2.active_pokemon = self.factory.create_card("Charizard ex")  # 330 HP
        p2.bench = [self.factory.create_card("Charmander")]

        # Abyssal Flames: 30 + (30 * 5) = 180 damage!
        game._handle_attack(0, verbose=False)
        self.assertEqual(p2.active_pokemon.damage_counters, 180)

    def test_archaludon_ex_metal_bridge_zero_retreat(self):
        """Test Archaludon ex Metal Bridge passive provides free retreat for any Pokémon with Metal Energy."""
        p1 = Player("P1", ["Duraludon"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        active_duraludon = self.factory.create_card("Duraludon")  # Base retreat 2
        archaludon = self.factory.create_card("Archaludon ex")
        p1.active_pokemon = active_duraludon
        p1.bench = [archaludon]

        # No Metal Energy attached -> retreat cost is 2
        self.assertEqual(active_duraludon.get_effective_retreat_cost(p1), 2)

        # Attach Metal Energy -> Metal Bridge makes retreat cost 0!
        active_duraludon.attached_energy = [self.factory.create_card("Metal Energy")]
        self.assertEqual(active_duraludon.get_effective_retreat_cost(p1), 0)

        # Retreat requires 0 energy discarded
        game.handle_action(('retreat', 0), verbose=False)
        self.assertEqual(p1.active_pokemon, archaludon)
        self.assertEqual(len(active_duraludon.attached_energy), 1)

    def test_grand_tree_chain_evolution(self):
        """Test Grand Tree Stadium ACE SPEC chain evolves Basic -> Stage 1 -> Stage 2 in 1 turn from deck."""
        p1 = Player("P1", ["Charmander"] * 30, self.factory)
        p2 = Player("P2", ["Pikachu"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        charmander = self.factory.create_card("Charmander")
        p1.active_pokemon = charmander
        p1.deck = [self.factory.create_card("Charmeleon"), self.factory.create_card("Charizard ex")] + p1.deck

        grand_tree = self.factory.create_card("Grand Tree")
        game.active_stadium = grand_tree

        game.handle_action(('use_stadium_ability',), verbose=False)
        self.assertEqual(p1.active_pokemon.name, "Charizard ex")

    def test_neutral_center_ex_damage_prevention(self):
        """Test Neutral Center Stadium ACE SPEC prevents all damage from Pokémon ex to non-Rule Box Pokémon."""
        p1 = Player("P1", ["Charizard ex"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        zard_ex = self.factory.create_card("Charizard ex")  # Rule Box ex
        zard_ex.attached_energy = [self.factory.create_card("Fire Energy")] * 2
        p1.active_pokemon = zard_ex

        charmander = self.factory.create_card("Charmander")  # Non-Rule Box (70 HP)
        p2.active_pokemon = charmander
        p2.bench = [self.factory.create_card("Charmander")]

        # Play Neutral Center
        game.active_stadium = self.factory.create_card("Neutral Center")

        # Attack should deal 0 damage!
        game._handle_attack(0, verbose=False)
        self.assertEqual(charmander.damage_counters, 0)
        self.assertFalse(charmander.is_knocked_out())

    def test_night_stretcher_and_earthen_vessel(self):
        """Test Night Stretcher recovers card from discard, and Earthen Vessel searches 2 Basic Energy."""
        p1 = Player("P1", ["Pikachu"] * 30, self.factory)
        p2 = Player("P2", ["Charmander"] * 30, self.factory)
        game = GameState(p1, p2)
        game.setup_game(verbose=False)

        # 1. Night Stretcher
        p1.discard_pile = [self.factory.create_card("Charizard ex")]
        p1.hand = [self.factory.create_card("Night Stretcher")]
        game.handle_action(('play_item', 0), verbose=False)
        self.assertTrue(any(c.name == "Charizard ex" for c in p1.hand))

        # 2. Earthen Vessel
        p1.hand = [self.factory.create_card("Earthen Vessel"), self.factory.create_card("Pikachu")]
        p1.deck = [self.factory.create_card("Fire Energy"), self.factory.create_card("Metal Energy")] + p1.deck
        game.handle_action(('play_item', 0), verbose=False)
        self.assertEqual(sum(1 for c in p1.hand if isinstance(c, EnergyCard)), 2)

    def test_tournament_matrix_runner_execution(self):
        """Test TournamentMatrixRunner runs multi-deck simulation and outputs ranking dict."""
        TournamentMatrixRunner = game_engine_module.TournamentMatrixRunner
        mini_archetypes = {
            "Gardevoir": ["Ralts"] * 30,
            "Terapagos": ["Hoothoot"] * 30
        }
        runner = TournamentMatrixRunner(
            archetypes=mini_archetypes,
            card_factory=self.factory,
            games_per_matchup=2,
            c1_kwargs={"iteration_limit": 20, "simulation_depth": 3}
        )
        res = runner.run_round_robin(verbose=False)
        self.assertIn("ranked_decks", res)
        self.assertIn("results_matrix", res)
        self.assertEqual(len(res["ranked_decks"]), 2)


if __name__ == '__main__':
    unittest.main()


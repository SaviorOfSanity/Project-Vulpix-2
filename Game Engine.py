"""
Complete Turn-Based Pokémon TCG Simulator & AI Controllers
Includes:
- Full rule engine (GameState, Player, Card hierarchy, Turn lifecycle, Knockouts)
- Baseline AI (TurnBasedGreedyAI)
- Advanced Heuristic MCTS Controller (MCTSNode, MCTSController)
- Batch simulation and post-game analytics harness (run_simulation)
"""

import os
import json
import math
import time
import random
import copy
from enum import Enum, auto


# ============================================================================
# 1. Enums
# ============================================================================

class CardType(Enum):
    POKEMON = auto()
    TRAINER = auto()
    ENERGY = auto()


class TrainerType(Enum):
    ITEM = auto()
    SUPPORTER = auto()
    STADIUM = auto()


class EnergyType(Enum):
    GRASS = 0
    FIRE = 1
    WATER = 2
    LIGHTNING = 3
    PSYCHIC = 4
    FIGHTING = 5
    DARKNESS = 6
    METAL = 7
    FAIRY = 8
    DRAGON = 9
    COLORLESS = 10


# ============================================================================
# 2. Card Hierarchy
# ============================================================================

class Card:
    def __init__(self, name: str, card_type: CardType):
        self.name = name
        self.card_type = card_type

    def clone(self):
        return Card(self.name, self.card_type)

    def __repr__(self):
        return f"{self.name} ({self.card_type.name})"


class PokemonCard(Card):
    def __init__(
        self,
        name: str,
        hp: int,
        attacks: list,
        stage: str = "Basic",
        evolves_from: str = None,
        element: EnergyType = EnergyType.COLORLESS,
        weakness: EnergyType = None,
        resistance: EnergyType = None,
        retreat_cost: int = 0
    ):
        super().__init__(name, CardType.POKEMON)
        self.stage = stage
        self.evolves_from = evolves_from
        self.element = element
        self.weakness = weakness
        self.resistance = resistance
        self.hp = hp
        self.max_hp = hp
        self.attacks = attacks
        self.retreat_cost = retreat_cost

        # Dynamic in-game state
        self.damage_counters = 0
        self.attached_energy = []
        self.special_conditions = {}
        self.base_card = None  # Underlying card when evolved
        self.turn_played = -1  # Turn number when card was put into play (-1 for setup)

    def is_knocked_out(self) -> bool:
        return self.damage_counters >= self.max_hp

    def apply_damage(self, amount: int, verbose: bool = True) -> bool:
        self.damage_counters += amount
        if verbose:
            print(f"{self.name} took {amount} damage. Total damage: {self.damage_counters}/{self.max_hp}")
            if self.is_knocked_out():
                print(f"{self.name} has been knocked out!")
        return self.is_knocked_out()

    def can_afford(self, cost: list) -> bool:
        """Checks if the Pokémon has sufficient attached energy to pay an attack or retreat cost."""
        attached_types = [e.energy_type for e in self.attached_energy]
        cost_copy = list(cost)

        # 1. Satisfy specific colored energy costs first
        for energy_type in cost_copy[:]:
            if energy_type != EnergyType.COLORLESS:
                if energy_type in attached_types:
                    attached_types.remove(energy_type)
                    cost_copy.remove(energy_type)
                else:
                    return False  # Missing required colored energy

        # 2. Satisfy remaining Colorless costs with any remaining energy
        colorless_needed = cost_copy.count(EnergyType.COLORLESS)
        return len(attached_types) >= colorless_needed

    def clone(self):
        cloned = PokemonCard(
            name=self.name,
            hp=self.max_hp,
            attacks=self.attacks,
            stage=self.stage,
            evolves_from=self.evolves_from,
            element=self.element,
            weakness=self.weakness,
            resistance=self.resistance,
            retreat_cost=self.retreat_cost
        )
        cloned.damage_counters = self.damage_counters
        cloned.attached_energy = [e.clone() for e in self.attached_energy]
        cloned.special_conditions = dict(self.special_conditions)
        cloned.turn_played = self.turn_played
        if self.base_card:
            cloned.base_card = self.base_card.clone()
        return cloned


class TrainerCard(Card):
    def __init__(self, name: str, trainer_type: TrainerType, effect_description: str):
        super().__init__(name, CardType.TRAINER)
        self.trainer_type = trainer_type
        self.effect_description = effect_description

    def use_effect(self, game_state, player, verbose: bool = True):
        """Executes the specific trainer card effect."""
        if verbose:
            print(f"Using {self.name}: {self.effect_description}")

        if self.name == "Professor's Research":
            # 1. Discard remaining hand
            player.discard_pile.extend(player.hand)
            player.hand = []
            # 2. Draw 7 cards
            player.draw_cards(7)
            if verbose:
                print(f"{player.name} discarded their hand and drew 7 new cards.")

    def clone(self):
        return TrainerCard(self.name, self.trainer_type, self.effect_description)


class EnergyCard(Card):
    def __init__(self, name: str, energy_type: EnergyType):
        super().__init__(name, CardType.ENERGY)
        self.energy_type = energy_type

    def clone(self):
        return EnergyCard(self.name, self.energy_type)


# ============================================================================
# 3. Card Factory
# ============================================================================

DEFAULT_CARDS_DATA = [
    {
        "name": "Pikachu",
        "card_type": "Pokemon",
        "stage": "Basic",
        "evolves_from": None,
        "element": "Lightning",
        "weakness": "Fighting",
        "resistance": "Metal",
        "hp": 60,
        "attacks": [
            {"name": "Gnaw", "cost": ["Colorless"], "damage": 10},
            {"name": "Thunder Jolt", "cost": ["Lightning", "Colorless"], "damage": 30}
        ],
        "retreat_cost": 1
    },
    {
        "name": "Charmander",
        "card_type": "Pokemon",
        "stage": "Basic",
        "evolves_from": None,
        "element": "Fire",
        "weakness": "Water",
        "resistance": None,
        "hp": 70,
        "attacks": [
            {"name": "Scratch", "cost": ["Colorless"], "damage": 10},
            {"name": "Ember", "cost": ["Fire", "Colorless"], "damage": 30}
        ],
        "retreat_cost": 1
    },
    {
        "name": "Charmeleon",
        "card_type": "Pokemon",
        "stage": "Stage 1",
        "evolves_from": "Charmander",
        "element": "Fire",
        "weakness": "Water",
        "resistance": None,
        "hp": 90,
        "attacks": [
            {"name": "Slash", "cost": ["Colorless", "Colorless"], "damage": 40}
        ],
        "retreat_cost": 2
    },
    {
        "name": "Professor's Research",
        "card_type": "Trainer",
        "trainer_type": "Supporter",
        "effect_description": "Discard your hand and draw 7 cards."
    },
    {
        "name": "Lightning Energy",
        "card_type": "Energy",
        "energy_type": "Lightning"
    },
    {
        "name": "Fire Energy",
        "card_type": "Energy",
        "energy_type": "Fire"
    }
]


class CardFactory:
    def __init__(self, json_path: str = "cards.json"):
        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                card_data_list = json.load(f)
        else:
            card_data_list = DEFAULT_CARDS_DATA

        self.card_database = {c["name"]: c for c in card_data_list}

    def create_card(self, card_name: str) -> Card:
        card_data = self.card_database.get(card_name)
        if not card_data:
            raise ValueError(f"Card '{card_name}' not found in database.")

        card_type = card_data["card_type"]
        if card_type == "Pokemon":
            attacks = []
            for atk in card_data["attacks"]:
                attacks.append({
                    "name": atk["name"],
                    "cost": [EnergyType[e.upper()] for e in atk["cost"]],
                    "damage": atk["damage"]
                })

            element_str = card_data.get("element")
            if not element_str:
                # Infer element from attacks or default to Colorless
                for a in attacks:
                    colored = [c for c in a["cost"] if c != EnergyType.COLORLESS]
                    if colored:
                        element_str = colored[0].name
                        break
            element = EnergyType[element_str.upper()] if element_str else EnergyType.COLORLESS

            weakness_str = card_data.get("weakness")
            weakness = EnergyType[weakness_str.upper()] if weakness_str else None

            resistance_str = card_data.get("resistance")
            resistance = EnergyType[resistance_str.upper()] if resistance_str else None

            return PokemonCard(
                name=card_data["name"],
                hp=card_data["hp"],
                attacks=attacks,
                stage=card_data.get("stage", "Basic"),
                evolves_from=card_data.get("evolves_from"),
                element=element,
                weakness=weakness,
                resistance=resistance,
                retreat_cost=card_data.get("retreat_cost", 0)
            )
        elif card_type == "Trainer":
            return TrainerCard(
                name=card_data["name"],
                trainer_type=TrainerType[card_data["trainer_type"].upper()],
                effect_description=card_data["effect_description"]
            )
        elif card_type == "Energy":
            return EnergyCard(
                name=card_data["name"],
                energy_type=EnergyType[card_data["energy_type"].upper()]
            )
        else:
            raise ValueError(f"Unknown card type: {card_type}")


# ============================================================================
# 4. Player & GameState
# ============================================================================

class Player:
    def __init__(self, name: str, deck_list_names: list, card_factory: CardFactory, controller=None):
        self.name = name
        self.controller = controller
        self.deck = [card_factory.create_card(n) for n in deck_list_names]
        self.hand = []
        self.discard_pile = []
        self.prize_cards = []
        self.active_pokemon = None
        self.bench = []
        self.turns_taken = 0  # Number of turns completed by this player

    def __eq__(self, other):
        if not isinstance(other, Player):
            return False
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return self.name

    def shuffle_deck(self):
        random.shuffle(self.deck)

    def draw_cards(self, num: int = 1) -> list:
        drawn = []
        for _ in range(num):
            if self.deck:
                card = self.deck.pop(0)
                self.hand.append(card)
                drawn.append(card)
            else:
                break
        return drawn

    def setup_board(self, verbose: bool = True):
        """Finds the first Basic Pokémon in hand to set as Active Pokémon."""
        for i, card in enumerate(self.hand):
            if isinstance(card, PokemonCard) and card.stage == "Basic":
                self.active_pokemon = self.hand.pop(i)
                self.active_pokemon.turn_played = -1  # In play before turn 1 starts
                if verbose:
                    print(f"{self.name} set {self.active_pokemon.name} as their Active Pokémon.")
                break

    def clone(self):
        p = Player.__new__(Player)
        p.name = self.name
        p.controller = self.controller
        p.deck = [c.clone() for c in self.deck]
        p.hand = [c.clone() for c in self.hand]
        p.discard_pile = [c.clone() for c in self.discard_pile]
        p.prize_cards = [c.clone() for c in self.prize_cards]
        p.active_pokemon = self.active_pokemon.clone() if self.active_pokemon else None
        p.bench = [c.clone() for c in self.bench]
        p.turns_taken = self.turns_taken
        return p


class GameState:
    def __init__(self, player1: Player, player2: Player):
        self.players = [player1, player2]
        self.turn_number = 0
        self.active_player_index = 0
        self.game_over = False
        self.win_reason = ""
        self.winner = None

        # Turn action limitations
        self.supporter_played_this_turn = False
        self.energy_attached_this_turn = False
        self.retreated_this_turn = False

    def get_active_player(self) -> Player:
        return self.players[self.active_player_index]

    def get_opponent_player(self) -> Player:
        return self.players[1 - self.active_player_index]

    def setup_game(self, verbose: bool = True):
        """
        Official Pokémon TCG Setup & Mulligan Rules:
        1. Both players draw 7 cards.
        2. Players check for Basic Pokémon. If none, player reveals hand, shuffles, and redraws (Mulligan).
        3. Opponent draws 1 extra card per opponent mulligan.
        4. Setup Active Pokémon and optional Bench.
        5. Set aside 6 Prize cards from the remaining deck.
        """
        if verbose:
            print("--- Setting up the game (Official Tournament Rules) ---")

        mulligans = [0, 0]
        # Step 1: Draw opening hand of 7 cards, mulligan until a Basic Pokemon is found
        for idx, player in enumerate(self.players):
            for _ in range(100):  # Safety bound against infinite loops
                player.shuffle_deck()
                # Return current hand to deck if mulliganing
                if player.hand:
                    player.deck.extend(player.hand)
                    player.hand = []
                    mulligans[idx] += 1
                player.hand = player.draw_cards(7)
                has_basic = any(isinstance(c, PokemonCard) and c.stage == "Basic" for c in player.hand)
                if has_basic:
                    break
                if verbose:
                    print(f"{player.name} has no Basic Pokémon in hand. Taking a Mulligan ({mulligans[idx] + 1}).")

            if not any(isinstance(c, PokemonCard) and c.stage == "Basic" for c in player.hand):
                opponent = self.players[1 - idx]
                self.winner = opponent
                self.win_reason = f"{opponent.name} won because {player.name} had no Basic Pokémon in deck."
                self.game_over = True
                return

        # Step 2: Opponents can draw 1 extra card for each mulligan taken by their opponent
        for idx, player in enumerate(self.players):
            opp_mulligans = mulligans[1 - idx]
            if opp_mulligans > 0:
                bonus = player.draw_cards(opp_mulligans)
                if verbose:
                    print(f"{player.name} drew {len(bonus)} extra card(s) due to opponent's mulligan(s).")

        # Step 3: Setup Active Pokémon (and bench)
        for player in self.players:
            player.setup_board(verbose)

        # Step 4: Set aside 6 Prize cards from the remaining deck
        for player in self.players:
            player.prize_cards = player.draw_cards(6)

        if verbose:
            print("-------------------------------------------------------")

    def switch_turns(self, verbose: bool = True):
        # Current player completes their turn
        self.get_active_player().turns_taken += 1

        self.active_player_index = 1 - self.active_player_index
        self.turn_number += 1
        self.supporter_played_this_turn = False
        self.energy_attached_this_turn = False
        self.retreated_this_turn = False

        active_player = self.get_active_player()
        if verbose:
            print(f"\n--- Turn {self.turn_number + 1}: It is now {active_player.name}'s turn ---")

        # Mandatory draw phase at turn start
        drawn_cards = active_player.draw_cards(1)
        if not drawn_cards:
            opponent = self.get_opponent_player()
            self.winner = opponent
            self.win_reason = f"{opponent.name} won because {active_player.name} could not draw a card (deck out)."
            self.game_over = True
            if verbose:
                print(self.win_reason)
            return

        if verbose:
            print(f"{active_player.name} drew a card.")

    def get_legal_moves(self) -> list:
        if self.game_over:
            return []

        moves = []
        player = self.get_active_player()
        is_p1_turn_1 = (self.turn_number == 0)

        # --- Hand Actions ---
        for i, card in enumerate(player.hand):
            if isinstance(card, PokemonCard):
                if card.stage == "Basic" and len(player.bench) < 5:
                    moves.append(('play_pokemon', i))
                elif card.stage == "Stage 1":
                    # Pokémon TCG Rule: Cannot evolve on a player's first turn of the game,
                    # and cannot evolve on the turn a Pokémon was put into play.
                    if player.turns_taken >= 1:
                        targets = [player.active_pokemon] + player.bench
                        for target_idx, p in enumerate(targets):
                            if p and p.name == card.evolves_from and p.turn_played < self.turn_number:
                                moves.append(('evolve', i, target_idx))

            elif isinstance(card, TrainerCard):
                # Pokémon TCG Rule (Sword & Shield / Scarlet & Violet):
                # The player going first cannot play a Supporter card on their first turn (Turn 1).
                if card.trainer_type == TrainerType.SUPPORTER and not self.supporter_played_this_turn and not is_p1_turn_1:
                    moves.append(('play_supporter', i))

            elif isinstance(card, EnergyCard):
                if not self.energy_attached_this_turn:
                    targets = [player.active_pokemon] + player.bench
                    for target_idx, p in enumerate(targets):
                        if p:
                            moves.append(('attach_energy', i, target_idx))

        # --- Active Pokémon Actions ---
        if player.active_pokemon:
            # Attacks (Pokémon TCG Rule: Player going first cannot attack on Turn 1)
            if not is_p1_turn_1:
                for i, attack in enumerate(player.active_pokemon.attacks):
                    if player.active_pokemon.can_afford(attack['cost']):
                        moves.append(('attack', i))

            # Retreat (requires bench presence and retreat energy cost)
            retreat_cost = [EnergyType.COLORLESS] * player.active_pokemon.retreat_cost
            if len(player.bench) > 0 and not self.retreated_this_turn and player.active_pokemon.can_afford(retreat_cost):
                for bench_idx in range(len(player.bench)):
                    moves.append(('retreat', bench_idx))

        # Pass is always legal to end the turn if no attack or further actions desired
        moves.append(('pass',))
        return moves

    def handle_action(self, move: tuple, verbose: bool = True) -> bool:
        """
        Executes a move.
        Returns True if the turn ends (attack or pass), False otherwise.
        """
        action_type = move[0]
        player = self.get_active_player()

        if action_type == 'play_pokemon':
            card_idx = move[1]
            pokemon_card = player.hand.pop(card_idx)
            pokemon_card.turn_played = self.turn_number  # Track turn played for evolution rule
            player.bench.append(pokemon_card)
            if verbose:
                print(f"{player.name} played {pokemon_card.name} to the bench.")
            return False

        elif action_type == 'play_supporter':
            # 1. Remove card from hand
            card_to_play = player.hand.pop(move[1])
            # 2. Execute card effect
            card_to_play.use_effect(self, player, verbose)
            # 3. Move to discard pile
            player.discard_pile.append(card_to_play)
            # 4. Set turn limitation flag
            self.supporter_played_this_turn = True
            return False

        elif action_type == 'evolve':
            card_idx, target_idx = move[1], move[2]
            evolution_card = player.hand.pop(card_idx)

            if target_idx == 0:  # Active Pokémon
                base_pokemon = player.active_pokemon
                player.active_pokemon = evolution_card
            else:  # Benched Pokémon (target_idx 1 maps to bench[0])
                base_pokemon = player.bench[target_idx - 1]
                player.bench[target_idx - 1] = evolution_card

            # Retain damage counters, attached energy, and underlying card
            evolution_card.damage_counters = base_pokemon.damage_counters
            evolution_card.attached_energy = base_pokemon.attached_energy
            evolution_card.base_card = base_pokemon
            evolution_card.turn_played = self.turn_number  # Evolved card cannot evolve again this turn
            if verbose:
                print(f"{player.name} evolved {base_pokemon.name} into {evolution_card.name}!")
            return False

        elif action_type == 'attach_energy':
            card_idx, target_idx = move[1], move[2]
            energy_card = player.hand.pop(card_idx)

            if target_idx == 0:
                player.active_pokemon.attached_energy.append(energy_card)
                target_name = player.active_pokemon.name
            else:
                player.bench[target_idx - 1].attached_energy.append(energy_card)
                target_name = player.bench[target_idx - 1].name

            self.energy_attached_this_turn = True
            if verbose:
                print(f"{player.name} attached {energy_card.name} to {target_name}.")
            return False

        elif action_type == 'retreat':
            bench_idx_to_promote = move[1]
            cost = player.active_pokemon.retreat_cost
            if verbose:
                print(f"{player.name} discards {cost} energy to retreat {player.active_pokemon.name}.")

            # Discard retreat cost
            player.discard_pile.extend(player.active_pokemon.attached_energy[:cost])
            del player.active_pokemon.attached_energy[:cost]

            promoted_pokemon = player.bench[bench_idx_to_promote]
            player.bench[bench_idx_to_promote] = player.active_pokemon
            player.active_pokemon = promoted_pokemon
            self.retreated_this_turn = True
            if verbose:
                print(f"{promoted_pokemon.name} is now Active.")
            return False

        elif action_type == 'attack':
            self._handle_attack(move[1], verbose)
            return True

        elif action_type == 'pass':
            if verbose:
                print(f"{player.name} passes the turn.")
            return True

        return False

    def _handle_attack(self, attack_idx: int, verbose: bool = True):
        player = self.get_active_player()
        opponent = self.get_opponent_player()
        attacker = player.active_pokemon
        defender = opponent.active_pokemon

        if not attacker or not defender:
            return

        chosen_attack = attacker.attacks[attack_idx]
        base_damage = chosen_attack['damage']
        damage = base_damage

        # Pokémon TCG Official Weakness & Resistance Calculation
        # 1. Weakness: 2x damage if defender weakness matches attacker element
        if defender.weakness and defender.weakness == attacker.element:
            damage *= 2
            if verbose:
                print(f"  Weakness applied ({attacker.element.name} vs {defender.weakness.name}): {base_damage} -> {damage} DMG!")

        # 2. Resistance: -30 damage if defender resistance matches attacker element
        if defender.resistance and defender.resistance == attacker.element:
            damage = max(0, damage - 30)
            if verbose:
                print(f"  Resistance applied ({attacker.element.name} vs {defender.resistance.name}): -> {damage} DMG!")

        if verbose:
            print(f"{attacker.name} uses {chosen_attack['name']} for {damage} total damage!")

        is_knockout = defender.apply_damage(damage, verbose)
        if is_knockout:
            self._handle_knockout(opponent, verbose)

    def _handle_knockout(self, defeated_player: Player, verbose: bool = True):
        if verbose:
            print(f"{defeated_player.active_pokemon.name} was knocked out and moved to discard pile.")
        defeated_player.discard_pile.append(defeated_player.active_pokemon)
        defeated_player.active_pokemon = None

        # Award prize card to prize taker
        prize_taker = self.players[1 - self.players.index(defeated_player)]
        if verbose:
            print(f"{prize_taker.name} takes a prize card.")
        if prize_taker.prize_cards:
            prize_taker.hand.append(prize_taker.prize_cards.pop())

        # Check win conditions in strict order:
        # 1. Prize taker has taken all prize cards
        if len(prize_taker.prize_cards) == 0:
            self.winner = prize_taker
            self.win_reason = f"{prize_taker.name} won by taking all prize cards."
            self.game_over = True
            if verbose:
                print(self.win_reason)
            return

        # 2. Defeated player has no bench Pokémon left
        if len(defeated_player.bench) == 0:
            self.winner = prize_taker
            self.win_reason = f"{prize_taker.name} won as {defeated_player.name} has no Pokémon left on bench (bench wipe)."
            self.game_over = True
            if verbose:
                print(self.win_reason)
            return

        # 3. Defeated player promotes first benched Pokémon
        defeated_player.active_pokemon = defeated_player.bench.pop(0)
        if verbose:
            print(f"{defeated_player.name} promoted {defeated_player.active_pokemon.name} to Active.")

    def run_game(self, verbose: bool = True, max_turns: int = 100):
        """Main game loop supporting multi-action turns and turn limits."""
        self.setup_game(verbose)
        if self.game_over:
            return self.winner, self.win_reason

        if verbose:
            print(f"\n--- Turn 1: It is now {self.get_active_player().name}'s turn (No Turn 1 Draw for Player 1) ---")

        while not self.game_over and self.turn_number < max_turns:
            active_player = self.get_active_player()

            # Multi-action turn loop
            while True:
                if verbose:
                    self.display_board_state(verbose)

                legal_moves = self.get_legal_moves()
                if not legal_moves:
                    break

                chosen_move = active_player.controller.choose_action(self, legal_moves)

                if not verbose:
                    controller_name = type(active_player.controller).__name__
                    move_details = " ".join(map(str, chosen_move))
                    player_id = "P1" if active_player == self.players[0] else "P2"
                    print(f"({player_id} - {controller_name}) chose: {move_details}")

                if verbose:
                    move_details = " ".join(map(str, chosen_move))
                    print(f"{active_player.name} chooses: {move_details}")

                turn_ended = self.handle_action(chosen_move, verbose)
                if turn_ended or self.game_over:
                    break

            if self.game_over:
                break

            self.switch_turns(verbose)

        # Timeout resolution if max_turns reached without definitive win
        if not self.game_over:
            self.game_over = True
            p1_prizes = len(self.players[0].prize_cards)
            p2_prizes = len(self.players[1].prize_cards)
            if p1_prizes < p2_prizes:
                self.winner = self.players[0]
                self.win_reason = f"{self.players[0].name} won on turn limit with fewer prize cards remaining ({p1_prizes} vs {p2_prizes})."
            elif p2_prizes < p1_prizes:
                self.winner = self.players[1]
                self.win_reason = f"{self.players[1].name} won on turn limit with fewer prize cards remaining ({p2_prizes} vs {p1_prizes})."
            else:
                self.winner = None
                self.win_reason = "Game ended in a draw (turn limit reached with equal prize cards)."

        return self.winner, self.win_reason

    def display_board_state(self, verbose: bool = True):
        if not verbose:
            return
        player = self.get_active_player()
        opponent = self.get_opponent_player()
        print("\n" + "=" * 40)
        print(f"ACTIVE: {player.name} | Hand: {len(player.hand)} | Deck: {len(player.deck)} | Prizes: {len(player.prize_cards)}")
        if player.active_pokemon:
            e_count = len(player.active_pokemon.attached_energy)
            print(f"  Active: {player.active_pokemon.name} [{player.active_pokemon.damage_counters}/{player.active_pokemon.max_hp} HP, Energy: {e_count}]")
        else:
            print("  Active: (None)")
        bench_str = ", ".join([f"{p.name} ({len(p.attached_energy)}E)" for p in player.bench]) or "(Empty)"
        print(f"  Bench: {bench_str}")

        print("-" * 40)
        print(f"OPPONENT: {opponent.name} | Hand: {len(opponent.hand)} | Deck: {len(opponent.deck)} | Prizes: {len(opponent.prize_cards)}")
        if opponent.active_pokemon:
            e_count = len(opponent.active_pokemon.attached_energy)
            print(f"  Active: {opponent.active_pokemon.name} [{opponent.active_pokemon.damage_counters}/{opponent.active_pokemon.max_hp} HP, Energy: {e_count}]")
        else:
            print("  Active: (None)")
        bench_str = ", ".join([f"{p.name} ({len(p.attached_energy)}E)" for p in opponent.bench]) or "(Empty)"
        print(f"  Bench: {bench_str}")
        print("=" * 40 + "\n")

    def clone(self):
        """Optimized fast deep-cloning of the GameState for MCTS rollouts."""
        g = GameState.__new__(GameState)
        g.players = [self.players[0].clone(), self.players[1].clone()]
        g.turn_number = self.turn_number
        g.active_player_index = self.active_player_index
        g.game_over = self.game_over
        g.win_reason = self.win_reason
        g.winner = g.players[self.players.index(self.winner)] if self.winner else None
        g.supporter_played_this_turn = self.supporter_played_this_turn
        g.energy_attached_this_turn = self.energy_attached_this_turn
        g.retreated_this_turn = self.retreated_this_turn
        return g


# ============================================================================
# 5. AI Controllers
# ============================================================================

class HumanController:
    """Handles interactive input for a human player."""
    def choose_action(self, game_state: GameState, legal_moves: list) -> tuple:
        active_player = game_state.get_active_player()
        print(f"It's {active_player.name}'s turn. Choose an action:")
        for i, move in enumerate(legal_moves):
            print(f"[{i}] {move[0].replace('_', ' ').title()}: {move[1:]}")

        while True:
            try:
                choice = int(input("> "))
                if 0 <= choice < len(legal_moves):
                    return legal_moves[choice]
            except (ValueError, IndexError):
                pass
            print("Invalid choice. Please enter a valid number.")


class TurnBasedGreedyAI:
    """
    A sequential heuristic AI that performs a full turn progression:
    1. Bench available Basic Pokémon and evolve Pokémon.
    2. Attach Energy (prioritizing Active Pokémon, then Bench).
    3. Play available Supporter cards.
    4. Select highest-damage affordable attack.
    5. If no attack is available, pass.
    """
    def choose_action(self, game_state: GameState, legal_moves: list) -> tuple:
        # 1. Bench Basic Pokémon and evolve
        for move in legal_moves:
            if move[0] in ('play_pokemon', 'evolve'):
                return move

        # 2. Attach energy (Active first, then bench)
        for move in legal_moves:
            if move[0] == 'attach_energy' and move[2] == 0:  # target Active
                return move
        for move in legal_moves:
            if move[0] == 'attach_energy':
                return move

        # 3. Play supporter
        for move in legal_moves:
            if move[0] == 'play_supporter':
                return move

        # 4. Highest-damage affordable attack
        best_attack = None
        highest_damage = -1
        attacker = game_state.get_active_player().active_pokemon
        if attacker:
            for move in legal_moves:
                if move[0] == 'attack':
                    attack_details = attacker.attacks[move[1]]
                    if attack_details['damage'] > highest_damage:
                        highest_damage = attack_details['damage']
                        best_attack = move

        if best_attack:
            return best_attack

        # 5. Pass
        return ('pass',)


class MCTSNode:
    """Monte Carlo Tree Search Node with UCB1 and perspective handling."""
    def __init__(self, game_state: GameState, parent=None, move=None):
        self.game_state = game_state
        self.parent = parent
        self.move = move
        self.children = []
        self.visits = 0
        self.total_score = 0.0  # Sum of scores from perspective of game_state's active player
        self.untried_moves = game_state.get_legal_moves()

    def select_child(self, exploration_constant: float = 1.414):
        """
        Selects child using UCB1.
        Properly handles two-player zero-sum perspective inversion:
        Parent maximizes expected value for its acting player.
        """
        best_score = -float('inf')
        best_child = None
        current_player = self.game_state.get_active_player()

        for child in self.children:
            if child.visits == 0:
                return child

            # Exploit value from current node's player perspective
            child_player = child.game_state.get_active_player()
            child_avg = child.total_score / child.visits
            if child_player == current_player:
                exploit = child_avg
            else:
                exploit = -child_avg

            explore = exploration_constant * math.sqrt(math.log(self.visits) / child.visits)
            ucb_score = exploit + explore

            if ucb_score > best_score:
                best_score = ucb_score
                best_child = child

        return best_child

    def expand(self):
        """Expands tree with an untried move."""
        move = self.untried_moves.pop()
        new_state = self.game_state.clone()
        turn_ended = new_state.handle_action(move, verbose=False)
        if turn_ended and not new_state.game_over:
            new_state.switch_turns(verbose=False)

        child = MCTSNode(new_state, parent=self, move=move)
        self.children.append(child)
        return child

    def backpropagate(self, score: float, perspective_player: Player):
        """
        Backpropagates rollout evaluation up the tree.
        Stores score at each node from the perspective of that node's active player.
        """
        node = self
        while node is not None:
            node.visits += 1
            node_player = node.game_state.get_active_player()
            if node_player == perspective_player:
                node.total_score += score
            else:
                node.total_score -= score
            node = node.parent


class MCTSController:
    """
    Advanced Heuristic Monte Carlo Tree Search Controller.
    - UCB1 selection with two-player zero-sum inversion.
    - Fast greedy rollout playout policy with horizon limit.
    - Composite heuristic evaluation normalized to [-1.0, 1.0].
    """
    def __init__(self, iteration_limit: int = 1000, simulation_depth: int = 8, exploration_constant: float = 1.414):
        self.iteration_limit = iteration_limit
        self.simulation_depth = simulation_depth
        self.exploration_constant = exploration_constant

    def _evaluate_state(self, game_state: GameState, perspective_player: Player) -> float:
        """
        Composite heuristic evaluation function normalized to approximately [-1.0, 1.0].
        Weights:
        - Prize Difference: 1.0
        - Board Presence: 0.25
        - Active Damage Inflicted: 0.25
        - Energy & Attack Potential: 0.25
        """
        # Terminal state handling
        if game_state.game_over:
            if game_state.winner == perspective_player:
                return 1.0
            elif game_state.winner is not None:
                return -1.0
            return 0.0

        p_idx = game_state.players.index(perspective_player)
        my_player = game_state.players[p_idx]
        opp_player = game_state.players[1 - p_idx]

        # 1. Prize Difference (Range: [-6, 6] -> normalized to [-1.0, 1.0])
        prize_diff = (len(opp_player.prize_cards) - len(my_player.prize_cards)) / 6.0

        # 2. Board Presence (Range: [-6, 6] -> normalized)
        my_board = (1 if my_player.active_pokemon else 0) + len(my_player.bench)
        opp_board = (1 if opp_player.active_pokemon else 0) + len(opp_player.bench)
        board_diff = (my_board - opp_board) / 6.0

        # 3. Active Damage Inflicted (Ratio of opponent Active HP dealt)
        active_damage_score = 0.0
        if opp_player.active_pokemon and opp_player.active_pokemon.max_hp > 0:
            active_damage_score = opp_player.active_pokemon.damage_counters / opp_player.active_pokemon.max_hp

        # 4. Energy & Attack Potential
        my_energy = sum(len(p.attached_energy) for p in ([my_player.active_pokemon] + my_player.bench) if p)
        opp_energy = sum(len(p.attached_energy) for p in ([opp_player.active_pokemon] + opp_player.bench) if p)
        energy_diff = (my_energy - opp_energy) / 6.0

        affordable_ratio = 0.0
        if my_player.active_pokemon and my_player.active_pokemon.attacks:
            affordable_attacks = sum(1 for atk in my_player.active_pokemon.attacks if my_player.active_pokemon.can_afford(atk['cost']))
            affordable_ratio = affordable_attacks / len(my_player.active_pokemon.attacks)

        potential_score = (energy_diff * 0.5) + (affordable_ratio * 0.5)

        # Composite weighted sum
        raw_score = (
            (prize_diff * 1.0) +
            (board_diff * 0.25) +
            (active_damage_score * 0.25) +
            (potential_score * 0.25)
        )

        # Normalization to [-1.0, 1.0]
        return max(-1.0, min(1.0, raw_score / 1.75))

    def _run_simulation_with_greedy_policy(self, game_state: GameState, perspective_player: Player) -> float:
        """Fast, greedy rollout simulation over a bounded horizon."""
        sim_game = game_state.clone()

        for _ in range(self.simulation_depth):
            if sim_game.game_over:
                break

            legal_moves = sim_game.get_legal_moves()
            if not legal_moves:
                break

            # Greedy move selection in rollout
            best_move = ('pass',)
            best_attack = None
            highest_damage = -1
            active_p = sim_game.get_active_player().active_pokemon

            if active_p:
                for m in legal_moves:
                    if m[0] == 'attack':
                        dmg = active_p.attacks[m[1]]['damage']
                        if dmg > highest_damage:
                            highest_damage = dmg
                            best_attack = m

            if best_attack:
                best_move = best_attack
            else:
                # Prioritize setup / building moves over pass
                build_moves = [m for m in legal_moves if m[0] in ('play_pokemon', 'evolve', 'attach_energy', 'play_supporter')]
                if build_moves:
                    best_move = random.choice(build_moves)
                else:
                    best_move = legal_moves[0]

            turn_ended = sim_game.handle_action(best_move, verbose=False)
            if turn_ended and not sim_game.game_over:
                sim_game.switch_turns(verbose=False)

        return self._evaluate_state(sim_game, perspective_player)

    def choose_action(self, game_state: GameState, legal_moves: list) -> tuple:
        if len(legal_moves) == 1:
            return legal_moves[0]

        root = MCTSNode(game_state=game_state)
        root_player = game_state.get_active_player()

        for _ in range(self.iteration_limit):
            node = root
            # 1. Selection
            while not node.untried_moves and node.children:
                node = node.select_child(self.exploration_constant)

            # 2. Expansion
            if node.untried_moves:
                node = node.expand()

            # 3. Rollout Simulation
            score = self._run_simulation_with_greedy_policy(node.game_state, root_player)

            # 4. Backpropagation
            node.backpropagate(score, root_player)

        if not root.children:
            return random.choice(legal_moves)

        # Select child with highest visit count or best score from root perspective
        best_child = max(root.children, key=lambda c: c.visits)

        if best_child.visits > 0:
            child_player = best_child.game_state.get_active_player()
            avg_score = (best_child.total_score / best_child.visits) if child_player == root_player else -(best_child.total_score / best_child.visits)
            print(f"    L [MCTS Stats] Visits: {best_child.visits}/{root.visits} | Win/Advantage Estimate: {avg_score:+.3f}")

        return best_child.move


# ============================================================================
# 6. Simulation & Logging Harness
# ============================================================================

def run_simulation(
    controller1_type,
    controller2_type,
    num_games: int,
    card_factory: CardFactory,
    deck1_names: list,
    deck2_names: list,
    c1_kwargs: dict = None,
    c2_kwargs: dict = None,
    verbose_moves: bool = False
):
    c1_kwargs = c1_kwargs or {}
    c2_kwargs = c2_kwargs or {}
    c1_name = controller1_type.__name__
    c2_name = controller2_type.__name__

    print(f"\n================================================================================")
    print(f"  RUNNING BATCH SIMULATION: {c1_name} vs {c2_name} ({num_games} Games)")
    print(f"================================================================================\n")

    wins = {c1_name: 0, c2_name: 0, "Draw": 0}
    win_reasons = {c1_name: {}, c2_name: {}, "Draw": {}}
    start_time = time.time()

    for i in range(num_games):
        c1 = controller1_type(**c1_kwargs)
        c2 = controller2_type(**c2_kwargs)

        p1 = Player("P1", deck1_names, card_factory, controller=c1)
        p2 = Player("P2", deck2_names, card_factory, controller=c2)

        # Alternate starting player for fairness
        if i % 2 == 0:
            game = GameState(p1, p2)
        else:
            game = GameState(p2, p1)

        print(f"\n--- Starting Game {i + 1}/{num_games} (P1: {type(game.players[0].controller).__name__}, P2: {type(game.players[1].controller).__name__}) ---")
        winner, reason = game.run_game(verbose=verbose_moves)

        # Categorize win reason
        reason_cat = "Other"
        if "all prize cards" in reason:
            reason_cat = "All Prizes Taken"
        elif "bench wipe" in reason or "no Pokémon left" in reason:
            reason_cat = "Bench Wipe"
        elif "deck out" in reason:
            reason_cat = "Deck Out"
        elif "turn limit" in reason or "timed out" in reason:
            reason_cat = "Turn Limit / Prize Advantage"

        if winner and winner.controller is c1:
            wins[c1_name] += 1
            win_reasons[c1_name][reason_cat] = win_reasons[c1_name].get(reason_cat, 0) + 1
            outcome_str = f"Winner: {c1_name} ({p1.name})"
        elif winner and winner.controller is c2:
            wins[c2_name] += 1
            win_reasons[c2_name][reason_cat] = win_reasons[c2_name].get(reason_cat, 0) + 1
            outcome_str = f"Winner: {c2_name} ({p2.name})"
        else:
            wins["Draw"] += 1
            win_reasons["Draw"][reason_cat] = win_reasons["Draw"].get(reason_cat, 0) + 1
            outcome_str = "Draw"

        print(f"Game {i + 1}/{num_games} Result: {outcome_str} | Reason: {reason}")

    elapsed = time.time() - start_time
    print(f"\n================================================================================")
    print(f"  SIMULATION SUMMARY ({num_games} Games in {elapsed:.2f}s, {elapsed/num_games:.2f}s/game)")
    print(f"================================================================================")

    for name in [c1_name, c2_name, "Draw"]:
        count = wins[name]
        pct = (count / num_games) * 100
        print(f"\n* {name}: {count} wins ({pct:.1f}%)")
        if count > 0:
            for reason_name, r_count in win_reasons[name].items():
                print(f"    - {reason_name}: {r_count} ({r_count/count * 100:.1f}%)")

    print(f"\n================================================================================\n")
    return wins, win_reasons


# ============================================================================
# 7. Main Execution Block
# ============================================================================

if __name__ == '__main__':
    factory = CardFactory('cards.json')

    # Decks
    deck_pikachu = ["Pikachu"] * 10 + ["Professor's Research"] * 4 + ["Lightning Energy"] * 10
    deck_charizard = ["Charmander"] * 10 + ["Charmeleon"] * 5 + ["Professor's Research"] * 4 + ["Fire Energy"] * 10

    # 1. Run 10 games of MCTSController vs TurnBasedGreedyAI
    run_simulation(
        controller1_type=MCTSController,
        controller2_type=TurnBasedGreedyAI,
        num_games=10,
        card_factory=factory,
        deck1_names=deck_pikachu,
        deck2_names=deck_charizard,
        c1_kwargs={"iteration_limit": 200, "simulation_depth": 8},
        verbose_moves=False
    )
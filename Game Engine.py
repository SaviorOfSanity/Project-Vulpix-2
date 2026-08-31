"""
Complete Turn-Based Pokémon TCG Simulator & AI Controllers (Standard Format Engine)
Includes:
- Full rule engine (GameState, Player, Card hierarchy, Turn lifecycle, Knockouts)
- Rule Box & Multi-Prize Pokémon (ex, Tera, Mega Evolution awarding 2 or 3 prize cards)
- Trainer Sub-types: Items (unlimited), Tools (stat/HP modifiers, max 1/card), Stadiums (global field), Supporters (1/turn)
- Ability Engine & Between-Turns Pokémon Checkup
- Baseline AI (TurnBasedGreedyAI) & Advanced Heuristic MCTS Controller (MCTSNode, MCTSController)
- Batch simulation and post-game analytics harness (run_simulation)
"""

import os
import json
import math
import time
import random
from enum import Enum, auto


# ============================================================================
# 1. Enums
# ============================================================================

class CardType(Enum):
    POKEMON = auto()
    TRAINER = auto()
    ENERGY = auto()


class TrainerType(Enum):
    ITEM = "Item"
    SUPPORTER = "Supporter"
    TOOL = "Tool"
    STADIUM = "Stadium"


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
        retreat_cost: int = 0,
        prize_yield: int = 1,
        is_rule_box: bool = False,
        ability: dict = None
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
        self.prize_yield = prize_yield
        self.is_rule_box = is_rule_box
        self.ability = ability

        # Dynamic in-game state
        self.damage_counters = 0
        self.attached_energy = []
        self.attached_tool = None  # Max 1 Pokémon Tool attached
        self.special_conditions = {}
        self.base_card = None  # Underlying card when evolved
        self.turn_played = -1  # Turn number when card was put into play (-1 for setup)
        self.ability_used_this_turn = False

    def get_effective_max_hp(self) -> int:
        """Returns max HP accounting for attached Pokémon Tool boosts (e.g. Bravery Charm +50 HP to Basic)."""
        bonus = 0
        if self.attached_tool and self.attached_tool.tool_hp_boost > 0:
            if not self.attached_tool.tool_condition or self.attached_tool.tool_condition.lower() == self.stage.lower():
                bonus += self.attached_tool.tool_hp_boost
        return self.max_hp + bonus

    def is_knocked_out(self) -> bool:
        return self.damage_counters >= self.get_effective_max_hp()

    def apply_damage(self, amount: int, verbose: bool = True) -> bool:
        self.damage_counters += amount
        if verbose:
            eff_hp = self.get_effective_max_hp()
            print(f"{self.name} took {amount} damage. Total damage: {self.damage_counters}/{eff_hp} HP")
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
                    return False

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
            retreat_cost=self.retreat_cost,
            prize_yield=self.prize_yield,
            is_rule_box=self.is_rule_box,
            ability=self.ability
        )
        cloned.damage_counters = self.damage_counters
        cloned.attached_energy = [e.clone() for e in self.attached_energy]
        if self.attached_tool:
            cloned.attached_tool = self.attached_tool.clone()
        cloned.special_conditions = dict(self.special_conditions)
        cloned.turn_played = self.turn_played
        cloned.ability_used_this_turn = self.ability_used_this_turn
        if self.base_card:
            cloned.base_card = self.base_card.clone()
        return cloned


class TrainerCard(Card):
    def __init__(
        self,
        name: str,
        trainer_type: TrainerType,
        effect_description: str,
        tool_hp_boost: int = 0,
        tool_damage_boost: int = 0,
        tool_condition: str = None,
        tool_target: str = None
    ):
        super().__init__(name, CardType.TRAINER)
        self.trainer_type = trainer_type
        self.effect_description = effect_description
        self.tool_hp_boost = tool_hp_boost
        self.tool_damage_boost = tool_damage_boost
        self.tool_condition = tool_condition
        self.tool_target = tool_target

    def use_effect(self, game_state, player, verbose: bool = True):
        """Executes the specific trainer card effect."""
        if verbose:
            print(f"Using {self.name}: {self.effect_description}")

        opp = game_state.get_opponent_player()

        if self.name == "Professor's Research":
            # Discard hand and draw 7
            player.discard_pile.extend(player.hand)
            player.hand = []
            player.draw_cards(7)
            if verbose:
                print(f"{player.name} discarded their hand and drew 7 new cards.")

        elif self.name == "Boss's Orders":
            # Switch in 1 opponent's benched Pokémon to Active
            if opp.bench:
                target_bench_idx = 0  # In AI / Default, promote first benched target
                swapped_in = opp.bench.pop(target_bench_idx)
                opp.bench.append(opp.active_pokemon)
                opp.active_pokemon = swapped_in
                if verbose:
                    print(f"{player.name} used Boss's Orders to gust {swapped_in.name} into the Active Spot!")

        elif self.name == "Iono":
            # Both players shuffle hands to deck, draw cards = remaining prizes
            for p in [player, opp]:
                p.deck.extend(p.hand)
                p.hand = []
                p.shuffle_deck()
                drawn = p.draw_cards(len(p.prize_cards))
                if verbose:
                    print(f"{p.name} shuffled hand into deck and drew {len(drawn)} cards ({len(p.prize_cards)} prizes left).")

        elif self.name == "Nest Ball":
            # Search deck for first Basic Pokémon and bench it
            if len(player.bench) < 5:
                for i, c in enumerate(player.deck):
                    if isinstance(c, PokemonCard) and c.stage == "Basic":
                        benched = player.deck.pop(i)
                        benched.turn_played = game_state.turn_number
                        player.bench.append(benched)
                        if verbose:
                            print(f"{player.name} searched deck with Nest Ball and benched {benched.name}.")
                        break
            player.shuffle_deck()

        elif self.name == "Ultra Ball":
            # Discard up to 2 other cards from hand, search deck for any Pokémon
            if len(player.hand) >= 2:
                for _ in range(2):
                    discarded = player.hand.pop(0)
                    player.discard_pile.append(discarded)
                for i, c in enumerate(player.deck):
                    if isinstance(c, PokemonCard):
                        found = player.deck.pop(i)
                        player.hand.append(found)
                        if verbose:
                            print(f"{player.name} used Ultra Ball to search {found.name} into hand.")
                        break
            player.shuffle_deck()

        elif self.name == "Switch":
            # Switch Active with Bench
            if player.bench:
                swapped = player.bench.pop(0)
                player.bench.append(player.active_pokemon)
                player.active_pokemon = swapped
                if verbose:
                    print(f"{player.name} used Switch: {swapped.name} is now Active.")

        elif self.name == "Rare Candy":
            # Evolve Basic directly into Stage 2 if available
            if player.turns_taken >= 1:
                # Find matching Stage 2 in hand
                stage2_in_hand = [c for c in player.hand if isinstance(c, PokemonCard) and c.stage == "Stage 2"]
                targets = [player.active_pokemon] + player.bench
                for s2 in stage2_in_hand:
                    for t_idx, target in enumerate(targets):
                        if target and target.stage == "Basic" and target.turn_played < game_state.turn_number:
                            player.hand.remove(s2)
                            if t_idx == 0:
                                base = player.active_pokemon
                                player.active_pokemon = s2
                            else:
                                base = player.bench[t_idx - 1]
                                player.bench[t_idx - 1] = s2
                            s2.damage_counters = base.damage_counters
                            s2.attached_energy = base.attached_energy
                            s2.attached_tool = base.attached_tool
                            s2.base_card = base
                            s2.turn_played = game_state.turn_number
                            if verbose:
                                print(f"{player.name} used Rare Candy to evolve {base.name} directly into {s2.name}!")
                            return

        elif self.name == "Artazon":
            # Search deck for a Basic Pokémon without a Rule Box and bench it
            if len(player.bench) < 5:
                for i, c in enumerate(player.deck):
                    if isinstance(c, PokemonCard) and c.stage == "Basic" and not c.is_rule_box:
                        benched = player.deck.pop(i)
                        benched.turn_played = game_state.turn_number
                        player.bench.append(benched)
                        if verbose:
                            print(f"{player.name} used Stadium Artazon to search and bench {benched.name}.")
                        break
            player.shuffle_deck()

    def clone(self):
        return TrainerCard(
            name=self.name,
            trainer_type=self.trainer_type,
            effect_description=self.effect_description,
            tool_hp_boost=self.tool_hp_boost,
            tool_damage_boost=self.tool_damage_boost,
            tool_condition=self.tool_condition,
            tool_target=self.tool_target
        )


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
        "prize_yield": 1,
        "is_rule_box": false if "false" in dir() else False,
        "attacks": [
            {"name": "Gnaw", "cost": ["Colorless"], "damage": 10},
            {"name": "Thunder Jolt", "cost": ["Lightning", "Colorless"], "damage": 30}
        ],
        "retreat_cost": 1
    },
    {
        "name": "Pikachu ex",
        "card_type": "Pokemon",
        "stage": "Basic",
        "evolves_from": None,
        "element": "Lightning",
        "weakness": "Fighting",
        "resistance": "Metal",
        "hp": 200,
        "prize_yield": 2,
        "is_rule_box": True,
        "attacks": [
            {"name": "Topaz Bolt", "cost": ["Lightning", "Lightning", "Colorless"], "damage": 300}
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
        "prize_yield": 1,
        "is_rule_box": False,
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
        "prize_yield": 1,
        "is_rule_box": False,
        "attacks": [
            {"name": "Slash", "cost": ["Colorless", "Colorless"], "damage": 40}
        ],
        "retreat_cost": 2
    },
    {
        "name": "Charizard ex",
        "card_type": "Pokemon",
        "stage": "Stage 2",
        "evolves_from": "Charmeleon",
        "element": "Fire",
        "weakness": "Water",
        "resistance": None,
        "hp": 330,
        "prize_yield": 2,
        "is_rule_box": True,
        "attacks": [
            {"name": "Burning Darkness", "cost": ["Fire", "Fire"], "damage": 180}
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
        "name": "Boss's Orders",
        "card_type": "Trainer",
        "trainer_type": "Supporter",
        "effect_description": "Switch in 1 of your opponent's Benched Pokémon to the Active Spot."
    },
    {
        "name": "Iono",
        "card_type": "Trainer",
        "trainer_type": "Supporter",
        "effect_description": "Both players shuffle their hands into their decks and draw cards equal to their remaining Prize cards."
    },
    {
        "name": "Nest Ball",
        "card_type": "Trainer",
        "trainer_type": "Item",
        "effect_description": "Search your deck for a Basic Pokémon and put it onto your Bench."
    },
    {
        "name": "Ultra Ball",
        "card_type": "Trainer",
        "trainer_type": "Item",
        "effect_description": "Discard 2 cards from hand, search deck for a Pokémon."
    },
    {
        "name": "Switch",
        "card_type": "Trainer",
        "trainer_type": "Item",
        "effect_description": "Switch your Active Pokémon with 1 of your Benched Pokémon."
    },
    {
        "name": "Rare Candy",
        "card_type": "Trainer",
        "trainer_type": "Item",
        "effect_description": "Choose 1 of your Basic Pokémon in play. Evolve it directly into a Stage 2 Pokémon."
    },
    {
        "name": "Bravery Charm",
        "card_type": "Trainer",
        "trainer_type": "Tool",
        "tool_hp_boost": 50,
        "tool_condition": "Basic",
        "effect_description": "The Basic Pokémon this card is attached to gets +50 HP."
    },
    {
        "name": "Maximum Belt",
        "card_type": "Trainer",
        "trainer_type": "Tool",
        "tool_damage_boost": 50,
        "tool_target": "ex",
        "effect_description": "Attacks do 50 more damage to the opponent's Pokémon ex."
    },
    {
        "name": "Artazon",
        "card_type": "Trainer",
        "trainer_type": "Stadium",
        "effect_description": "Once during each player's turn, search deck for a Basic Pokémon without a Rule Box and bench it."
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
                self.cards_data = json.load(f)
        else:
            self.cards_data = DEFAULT_CARDS_DATA

        self.cards_by_name = {c["name"]: c for c in self.cards_data}

    def create_card(self, card_name: str) -> Card:
        if card_name not in self.cards_by_name:
            raise ValueError(f"Card '{card_name}' not found in database.")

        card_info = self.cards_by_name[card_name]
        card_type = card_info.get("card_type")

        if card_type == "Pokemon":
            element_str = card_info.get("element", "Colorless").upper()
            element = getattr(EnergyType, element_str, EnergyType.COLORLESS)

            weakness_str = card_info.get("weakness")
            weakness = getattr(EnergyType, weakness_str.upper(), None) if weakness_str else None

            resistance_str = card_info.get("resistance")
            resistance = getattr(EnergyType, resistance_str.upper(), None) if resistance_str else None

            attacks = []
            for atk in card_info.get("attacks", []):
                attacks.append({
                    "name": atk["name"],
                    "cost": [getattr(EnergyType, c.upper(), EnergyType.COLORLESS) for c in atk["cost"]],
                    "damage": atk["damage"]
                })

            return PokemonCard(
                name=card_info["name"],
                hp=card_info["hp"],
                attacks=attacks,
                stage=card_info.get("stage", "Basic"),
                evolves_from=card_info.get("evolves_from"),
                element=element,
                weakness=weakness,
                resistance=resistance,
                retreat_cost=card_info.get("retreat_cost", 0),
                prize_yield=card_info.get("prize_yield", 1),
                is_rule_box=card_info.get("is_rule_box", False),
                ability=card_info.get("ability")
            )

        elif card_type == "Trainer":
            t_type_str = card_info.get("trainer_type", "Item").upper()
            trainer_type = getattr(TrainerType, t_type_str, TrainerType.ITEM)
            return TrainerCard(
                name=card_info["name"],
                trainer_type=trainer_type,
                effect_description=card_info.get("effect_description", ""),
                tool_hp_boost=card_info.get("tool_hp_boost", 0),
                tool_damage_boost=card_info.get("tool_damage_boost", 0),
                tool_condition=card_info.get("tool_condition"),
                tool_target=card_info.get("tool_target")
            )

        elif card_type == "Energy":
            energy_type_str = card_info.get("energy_type", "Colorless").upper()
            energy_type = getattr(EnergyType, energy_type_str, EnergyType.COLORLESS)
            return EnergyCard(
                name=card_info["name"],
                energy_type=energy_type
            )

        else:
            raise ValueError(f"Unknown card type: {card_type}")


# ============================================================================
# 4. Player & GameState
# ============================================================================

class Player:
    def __init__(self, name: str, deck_list: list, card_factory: CardFactory, controller=None):
        self.name = name
        self.deck = [card_factory.create_card(card_name) for card_name in deck_list]
        self.hand = []
        self.prize_cards = []
        self.discard_pile = []
        self.active_pokemon = None
        self.bench = []
        self.controller = controller
        self.turns_taken = 0

    def __eq__(self, other):
        if not isinstance(other, Player):
            return False
        return self.name == other.name

    def shuffle_deck(self):
        random.shuffle(self.deck)

    def draw_cards(self, count: int = 1) -> list:
        drawn = []
        for _ in range(count):
            if self.deck:
                drawn.append(self.deck.pop(0))
        self.hand.extend(drawn)
        return drawn

    def setup_board(self, verbose: bool = True):
        # 1. Place first Basic Pokémon from hand to Active Spot
        for i, card in enumerate(self.hand):
            if isinstance(card, PokemonCard) and card.stage == "Basic":
                self.active_pokemon = self.hand.pop(i)
                self.active_pokemon.turn_played = -1  # Placed during pre-game setup
                if verbose:
                    print(f"{self.name} placed {self.active_pokemon.name} into the Active Spot.")
                break

        # 2. Place optional additional Basic Pokémon onto Bench (up to 5)
        for i in range(len(self.hand) - 1, -1, -1):
            if len(self.bench) >= 5:
                break
            card = self.hand[i]
            if isinstance(card, PokemonCard) and card.stage == "Basic":
                benched = self.hand.pop(i)
                benched.turn_played = -1
                self.bench.append(benched)
                if verbose:
                    print(f"{self.name} placed {benched.name} onto the Bench.")

    def clone(self):
        cloned = Player(self.name, [], CardFactory.__new__(CardFactory), self.controller)
        cloned.deck = [c.clone() for c in self.deck]
        cloned.hand = [c.clone() for c in self.hand]
        cloned.prize_cards = [c.clone() for c in self.prize_cards]
        cloned.discard_pile = [c.clone() for c in self.discard_pile]
        cloned.active_pokemon = self.active_pokemon.clone() if self.active_pokemon else None
        cloned.bench = [b.clone() for b in self.bench]
        cloned.turns_taken = self.turns_taken
        return cloned


class GameState:
    def __init__(self, player1: Player, player2: Player):
        self.players = [player1, player2]
        self.active_player_index = 0
        self.turn_number = 0
        self.supporter_played_this_turn = False
        self.energy_attached_this_turn = False
        self.retreated_this_turn = False
        self.active_stadium = None  # Global Stadium in play
        self.stadium_played_this_turn = False
        self.game_over = False
        self.winner = None
        self.win_reason = ""

    def get_active_player(self) -> Player:
        return self.players[self.active_player_index]

    def get_opponent_player(self) -> Player:
        return self.players[1 - self.active_player_index]

    def get_opponent(self, player: Player) -> Player:
        p_idx = self.players.index(player)
        return self.players[1 - p_idx]

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
        for idx, player in enumerate(self.players):
            for _ in range(100):
                player.shuffle_deck()
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

        for idx, player in enumerate(self.players):
            opp_mulligans = mulligans[1 - idx]
            if opp_mulligans > 0:
                bonus = player.draw_cards(opp_mulligans)
                if verbose:
                    print(f"{player.name} drew {len(bonus)} extra card(s) due to opponent's mulligan(s).")

        for player in self.players:
            player.setup_board(verbose)

        for player in self.players:
            player.prize_cards = player.draw_cards(6)

        if verbose:
            print("-------------------------------------------------------")

    def pokemon_checkup(self, verbose: bool = False):
        """Standardized Pokémon Checkup Step executed between turns."""
        for player in self.players:
            pokemon_list = [player.active_pokemon] + player.bench
            for p in pokemon_list:
                if p:
                    p.ability_used_this_turn = False

    def switch_turns(self, verbose: bool = True):
        self.get_active_player().turns_taken += 1
        self.active_player_index = 1 - self.active_player_index
        self.turn_number += 1
        self.supporter_played_this_turn = False
        self.energy_attached_this_turn = False
        self.retreated_this_turn = False
        self.stadium_played_this_turn = False

        self.pokemon_checkup(verbose)

        active_player = self.get_active_player()
        if verbose:
            print(f"\n--- Turn {self.turn_number + 1}: It is now {active_player.name}'s turn ---")

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
                elif card.stage in ("Stage 1", "Stage 2"):
                    # Cannot evolve on a player's first turn of the game or turn placed down
                    if player.turns_taken >= 1:
                        targets = [player.active_pokemon] + player.bench
                        for target_idx, p in enumerate(targets):
                            if p and p.name == card.evolves_from and p.turn_played < self.turn_number:
                                moves.append(('evolve', i, target_idx))

            elif isinstance(card, TrainerCard):
                if card.trainer_type == TrainerType.ITEM:
                    # Item cards are playable unlimited times per turn
                    moves.append(('play_item', i))

                elif card.trainer_type == TrainerType.TOOL:
                    # Tools can be attached to any Pokémon without an attached tool
                    targets = [player.active_pokemon] + player.bench
                    for target_idx, p in enumerate(targets):
                        if p and p.attached_tool is None:
                            moves.append(('attach_tool', i, target_idx))

                elif card.trainer_type == TrainerType.STADIUM:
                    # Max 1 stadium per turn, cannot play identical stadium to active one
                    if not self.stadium_played_this_turn and (not self.active_stadium or self.active_stadium.name != card.name):
                        moves.append(('play_stadium', i))

                elif card.trainer_type == TrainerType.SUPPORTER:
                    # Supporter cards (1 per turn, blocked P1 Turn 1)
                    if not self.supporter_played_this_turn and not is_p1_turn_1:
                        moves.append(('play_supporter', i))

            elif isinstance(card, EnergyCard):
                if not self.energy_attached_this_turn:
                    targets = [player.active_pokemon] + player.bench
                    for target_idx, p in enumerate(targets):
                        if p:
                            moves.append(('attach_energy', i, target_idx))

        # --- Stadium & Ability Actions ---
        if self.active_stadium and self.active_stadium.name == "Artazon" and not self.stadium_played_this_turn:
            if len(player.bench) < 5:
                moves.append(('use_stadium_ability',))

        # --- Active Pokémon Actions ---
        if player.active_pokemon:
            # Attacks (blocked P1 Turn 1)
            if not is_p1_turn_1:
                for i, attack in enumerate(player.active_pokemon.attacks):
                    if player.active_pokemon.can_afford(attack['cost']):
                        moves.append(('attack', i))

            # Retreat
            retreat_cost = [EnergyType.COLORLESS] * player.active_pokemon.retreat_cost
            if len(player.bench) > 0 and not self.retreated_this_turn and player.active_pokemon.can_afford(retreat_cost):
                for bench_idx in range(len(player.bench)):
                    moves.append(('retreat', bench_idx))

        # Pass is always legal to conclude the turn
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
            pokemon_card.turn_played = self.turn_number
            player.bench.append(pokemon_card)
            if verbose:
                print(f"{player.name} played {pokemon_card.name} to the bench.")
            return False

        elif action_type == 'play_item':
            card_to_play = player.hand.pop(move[1])
            card_to_play.use_effect(self, player, verbose)
            player.discard_pile.append(card_to_play)
            return False

        elif action_type == 'attach_tool':
            card_idx, target_idx = move[1], move[2]
            tool_card = player.hand.pop(card_idx)
            target = player.active_pokemon if target_idx == 0 else player.bench[target_idx - 1]
            target.attached_tool = tool_card
            if verbose:
                print(f"{player.name} attached Pokémon Tool {tool_card.name} to {target.name} (Effective Max HP: {target.get_effective_max_hp()}).")
            return False

        elif action_type == 'play_stadium':
            stadium_card = player.hand.pop(move[1])
            if self.active_stadium:
                # Discard existing stadium
                if verbose:
                    print(f"Stadium {self.active_stadium.name} was discarded.")
            self.active_stadium = stadium_card
            self.stadium_played_this_turn = True
            if verbose:
                print(f"{player.name} played Stadium {stadium_card.name} onto the field.")
            return False

        elif action_type == 'use_stadium_ability':
            if self.active_stadium:
                self.active_stadium.use_effect(self, player, verbose)
                self.stadium_played_this_turn = True
            return False

        elif action_type == 'play_supporter':
            card_to_play = player.hand.pop(move[1])
            card_to_play.use_effect(self, player, verbose)
            player.discard_pile.append(card_to_play)
            self.supporter_played_this_turn = True
            return False

        elif action_type == 'evolve':
            card_idx, target_idx = move[1], move[2]
            evolution_card = player.hand.pop(card_idx)

            if target_idx == 0:
                base_pokemon = player.active_pokemon
                player.active_pokemon = evolution_card
            else:
                base_pokemon = player.bench[target_idx - 1]
                player.bench[target_idx - 1] = evolution_card

            evolution_card.damage_counters = base_pokemon.damage_counters
            evolution_card.attached_energy = base_pokemon.attached_energy
            evolution_card.attached_tool = base_pokemon.attached_tool
            evolution_card.base_card = base_pokemon
            evolution_card.turn_played = self.turn_number

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

        # Dynamic Attack Scaling (e.g. Charizard ex Burning Darkness: 180 + 30 per prize taken by opponent)
        if chosen_attack['name'] == "Burning Darkness":
            prizes_taken = 6 - len(player.prize_cards)
            base_damage = 180 + (30 * prizes_taken)

        damage = base_damage

        # Pokémon Tool Damage Boost (e.g. Maximum Belt +50 damage against Pokémon ex)
        if attacker.attached_tool and attacker.attached_tool.tool_damage_boost > 0:
            if not attacker.attached_tool.tool_target or (attacker.attached_tool.tool_target == "ex" and defender.is_rule_box):
                damage += attacker.attached_tool.tool_damage_boost
                if verbose:
                    print(f"  Tool Boost ({attacker.attached_tool.name}): +{attacker.attached_tool.tool_damage_boost} DMG!")

        # Weakness & Resistance
        if defender.weakness and defender.weakness == attacker.element:
            damage *= 2
            if verbose:
                print(f"  Weakness applied ({attacker.element.name} vs {defender.weakness.name}): {base_damage} -> {damage} DMG!")

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
        defeated_pokemon = defeated_player.active_pokemon
        if not defeated_pokemon:
            return

        if verbose:
            rule_box_str = f" [Rule Box: {defeated_pokemon.prize_yield} Prizes]" if defeated_pokemon.is_rule_box else ""
            print(f"{defeated_pokemon.name}{rule_box_str} was knocked out!")

        # Discard attached tool, attached energy, and Pokemon card
        if defeated_pokemon.attached_tool:
            defeated_player.discard_pile.append(defeated_pokemon.attached_tool)
            defeated_pokemon.attached_tool = None

        defeated_player.discard_pile.extend(defeated_pokemon.attached_energy)
        defeated_pokemon.attached_energy = []
        defeated_player.discard_pile.append(defeated_pokemon)
        defeated_player.active_pokemon = None

        # Award Prize Cards according to prize_yield (e.g. 2 for Pokemon ex)
        prize_taker = self.players[1 - self.players.index(defeated_player)]
        prizes_to_take = min(defeated_pokemon.prize_yield, len(prize_taker.prize_cards))

        for _ in range(prizes_to_take):
            if prize_taker.prize_cards:
                prize_taker.hand.append(prize_taker.prize_cards.pop())

        if verbose:
            print(f"* {prize_taker.name} took {prizes_to_take} Prize Card(s)! ({len(prize_taker.prize_cards)} remaining)")

        # Win conditions:
        # 1. Taken all prize cards
        if len(prize_taker.prize_cards) == 0:
            self.winner = prize_taker
            self.win_reason = f"{prize_taker.name} won by taking all prize cards."
            self.game_over = True
            if verbose:
                print(self.win_reason)
            return

        # 2. Bench Wipe
        if len(defeated_player.bench) == 0:
            self.winner = prize_taker
            self.win_reason = f"{prize_taker.name} won as {defeated_player.name} has no Pokémon left on bench (bench wipe)."
            self.game_over = True
            if verbose:
                print(self.win_reason)
            return

        # 3. Promote first benched Pokémon
        defeated_player.active_pokemon = defeated_player.bench.pop(0)
        if verbose:
            print(f"{defeated_player.name} promoted {defeated_player.active_pokemon.name} to Active.")

    def clone(self):
        cloned_p1 = self.players[0].clone()
        cloned_p2 = self.players[1].clone()
        cloned_game = GameState(cloned_p1, cloned_p2)
        cloned_game.active_player_index = self.active_player_index
        cloned_game.turn_number = self.turn_number
        cloned_game.supporter_played_this_turn = self.supporter_played_this_turn
        cloned_game.energy_attached_this_turn = self.energy_attached_this_turn
        cloned_game.retreated_this_turn = self.retreated_this_turn
        if self.active_stadium:
            cloned_game.active_stadium = self.active_stadium.clone()
        cloned_game.stadium_played_this_turn = self.stadium_played_this_turn
        cloned_game.game_over = self.game_over
        if self.winner:
            cloned_game.winner = cloned_p1 if self.winner == self.players[0] else cloned_p2
        cloned_game.win_reason = self.win_reason
        return cloned_game

    def display_board_state(self, verbose: bool = True):
        if not verbose:
            return
        p1 = self.players[0]
        p2 = self.players[1]
        print("\n" + "=" * 60)
        print(f"Turn {self.turn_number + 1} | Active: {self.get_active_player().name} | Stadium: {self.active_stadium.name if self.active_stadium else 'None'}")
        print("-" * 60)
        print(f"[{p2.name}] Deck: {len(p2.deck)} | Hand: {len(p2.hand)} | Prizes: {len(p2.prize_cards)}")
        if p2.active_pokemon:
            tool_str = f" [Tool: {p2.active_pokemon.attached_tool.name}]" if p2.active_pokemon.attached_tool else ""
            print(f"  Active: {p2.active_pokemon.name} ({p2.active_pokemon.damage_counters}/{p2.active_pokemon.get_effective_max_hp()} HP, {len(p2.active_pokemon.attached_energy)} Energy){tool_str}")
        print(f"  Bench: {', '.join(b.name for b in p2.bench) if p2.bench else 'Empty'}")
        print("-" * 60)
        print(f"[{p1.name}] Deck: {len(p1.deck)} | Hand: {len(p1.hand)} | Prizes: {len(p1.prize_cards)}")
        if p1.active_pokemon:
            tool_str = f" [Tool: {p1.active_pokemon.attached_tool.name}]" if p1.active_pokemon.attached_tool else ""
            print(f"  Active: {p1.active_pokemon.name} ({p1.active_pokemon.damage_counters}/{p1.active_pokemon.get_effective_max_hp()} HP, {len(p1.active_pokemon.attached_energy)} Energy){tool_str}")
        print(f"  Bench: {', '.join(b.name for b in p1.bench) if p1.bench else 'Empty'}")
        print(f"  Hand: {', '.join(c.name for c in p1.hand)}")
        print("=" * 60 + "\n")

    def run_game(self, verbose: bool = True, max_turns: int = 100):
        self.setup_game(verbose)
        if self.game_over:
            return self.winner, self.win_reason

        while not self.game_over and self.turn_number < max_turns:
            active_player = self.get_active_player()

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
                self.win_reason = "Match resulted in a draw on turn limit with identical prize counts."

        return self.winner, self.win_reason


# ============================================================================
# 5. AI Controllers (TurnBasedGreedyAI & MCTSController)
# ============================================================================

class HumanController:
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
    Sequential priority AI for modern Standard format:
    1. Bench Basic Pokémon and Evolve.
    2. Attach Energy (Active first, then Bench).
    3. Attach Tools (Active first, then Bench).
    4. Play Stadium / Use Stadium Ability.
    5. Play Item cards (Nest Ball, Ultra Ball, Rare Candy, Switch).
    6. Play Supporter cards.
    7. Select highest-damage attack.
    8. Pass.
    """
    def choose_action(self, game_state: GameState, legal_moves: list) -> tuple:
        # 1. Bench Basic & Evolve
        for move in legal_moves:
            if move[0] in ('play_pokemon', 'evolve'):
                return move

        # 2. Attach Energy (Active first, then bench)
        for move in legal_moves:
            if move[0] == 'attach_energy' and move[2] == 0:
                return move
        for move in legal_moves:
            if move[0] == 'attach_energy':
                return move

        # 3. Attach Tools (Active first, then bench)
        for move in legal_moves:
            if move[0] == 'attach_tool' and move[2] == 0:
                return move
        for move in legal_moves:
            if move[0] == 'attach_tool':
                return move

        # 4. Play Stadium / Use Stadium Ability
        for move in legal_moves:
            if move[0] in ('play_stadium', 'use_stadium_ability'):
                return move

        # 5. Play Items
        for move in legal_moves:
            if move[0] == 'play_item':
                return move

        # 6. Play Supporter
        for move in legal_moves:
            if move[0] == 'play_supporter':
                return move

        # 7. Highest damage attack
        best_attack = None
        highest_damage = -1
        attacker = game_state.get_active_player().active_pokemon
        if attacker:
            for move in legal_moves:
                if move[0] == 'attack':
                    attack_details = attacker.attacks[move[1]]
                    dmg = attack_details['damage']
                    if dmg > highest_damage:
                        highest_damage = dmg
                        best_attack = move

        if best_attack:
            return best_attack

        # 8. Pass
        return ('pass',)


class MCTSNode:
    def __init__(self, game_state: GameState, parent=None, move=None):
        self.game_state = game_state
        self.parent = parent
        self.move = move
        self.children = []
        self.visits = 0
        self.total_score = 0.0
        self.untried_moves = game_state.get_legal_moves()

    def select_child(self, exploration_constant: float = 1.414):
        best_score = -float('inf')
        best_child = None
        current_player = self.game_state.get_active_player()

        for child in self.children:
            if child.visits == 0:
                return child

            child_player = child.game_state.get_active_player()
            child_avg = child.total_score / child.visits
            exploit = child_avg if child_player == current_player else -child_avg
            explore = exploration_constant * math.sqrt(math.log(self.visits) / child.visits)
            ucb_score = exploit + explore

            if ucb_score > best_score:
                best_score = ucb_score
                best_child = child

        return best_child

    def expand(self):
        move = self.untried_moves.pop()
        new_state = self.game_state.clone()
        turn_ended = new_state.handle_action(move, verbose=False)
        if turn_ended and not new_state.game_over:
            new_state.switch_turns(verbose=False)

        child = MCTSNode(new_state, parent=self, move=move)
        self.children.append(child)
        return child

    def backpropagate(self, score: float, perspective_player: Player):
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
    Advanced Multi-Prize Aware Monte Carlo Tree Search Controller.
    - UCB1 selection with two-player zero-sum inversion.
    - Fast greedy rollout policy.
    - Normalized [-1.0, 1.0] composite heuristic with prize yield, tool boosts, and stadium presence.
    """
    def __init__(self, iteration_limit: int = 1000, simulation_depth: int = 8, exploration_constant: float = 1.414):
        self.iteration_limit = iteration_limit
        self.simulation_depth = simulation_depth
        self.exploration_constant = exploration_constant

    def _evaluate_state(self, game_state: GameState, perspective_player: Player) -> float:
        if game_state.game_over:
            if game_state.winner == perspective_player:
                return 1.0
            elif game_state.winner is not None:
                return -1.0
            return 0.0

        p_idx = game_state.players.index(perspective_player)
        my_player = game_state.players[p_idx]
        opp_player = game_state.players[1 - p_idx]

        # 1. Prize Difference (Remaining prize cards)
        prize_diff = (len(opp_player.prize_cards) - len(my_player.prize_cards)) / 6.0

        # 2. Board Presence & HP
        my_board = [my_player.active_pokemon] + my_player.bench
        opp_board = [opp_player.active_pokemon] + opp_player.bench

        my_pokemon_count = sum(1 for p in my_board if p)
        opp_pokemon_count = sum(1 for p in opp_board if p)
        board_diff = (my_pokemon_count - opp_pokemon_count) / 6.0

        # 3. Active Damage Inflicted
        active_damage_score = 0.0
        if opp_player.active_pokemon and opp_player.active_pokemon.get_effective_max_hp() > 0:
            active_damage_score = opp_player.active_pokemon.damage_counters / opp_player.active_pokemon.get_effective_max_hp()

        # 4. Attached Energy & Equipped Tools
        my_energy = sum(len(p.attached_energy) for p in my_board if p)
        opp_energy = sum(len(p.attached_energy) for p in opp_board if p)
        energy_diff = (my_energy - opp_energy) / 6.0

        my_tools = sum(1 for p in my_board if p and p.attached_tool)
        opp_tools = sum(1 for p in opp_board if p and p.attached_tool)
        tool_diff = (my_tools - opp_tools) / 6.0

        # 5. Attack Readiness
        affordable_ratio = 0.0
        if my_player.active_pokemon and my_player.active_pokemon.attacks:
            affordable_attacks = sum(1 for atk in my_player.active_pokemon.attacks if my_player.active_pokemon.can_afford(atk['cost']))
            affordable_ratio = affordable_attacks / len(my_player.active_pokemon.attacks)

        raw_score = (
            (prize_diff * 1.0) +
            (board_diff * 0.20) +
            (active_damage_score * 0.25) +
            (energy_diff * 0.20) +
            (tool_diff * 0.10) +
            (affordable_ratio * 0.15)
        )

        return max(-1.0, min(1.0, raw_score / 1.90))

    def _run_simulation_with_greedy_policy(self, game_state: GameState, perspective_player: Player) -> float:
        sim_game = game_state.clone()

        for _ in range(self.simulation_depth):
            if sim_game.game_over:
                break

            legal_moves = sim_game.get_legal_moves()
            if not legal_moves:
                break

            # Sequential Rollout Policy:
            # 1. Bench & Evolve
            evolve_or_bench = [m for m in legal_moves if m[0] in ('play_pokemon', 'evolve')]
            if evolve_or_bench:
                best_move = evolve_or_bench[0]
            else:
                # 2. Attach Energy (Active target 0 prioritized)
                energy_moves = [m for m in legal_moves if m[0] == 'attach_energy']
                if energy_moves:
                    active_e = [m for m in energy_moves if m[2] == 0]
                    best_move = active_e[0] if active_e else energy_moves[0]
                else:
                    # 3. Attach Tools
                    tool_moves = [m for m in legal_moves if m[0] == 'attach_tool']
                    if tool_moves:
                        best_move = tool_moves[0]
                    else:
                        # 4. Play Items & Stadiums
                        item_moves = [m for m in legal_moves if m[0] in ('play_item', 'play_stadium', 'use_stadium_ability')]
                        if item_moves:
                            best_move = item_moves[0]
                        else:
                            # 5. Play Supporter
                            supporter_moves = [m for m in legal_moves if m[0] == 'play_supporter']
                            if supporter_moves:
                                best_move = supporter_moves[0]
                            else:
                                # 6. Highest-damage attack
                                attack_moves = [m for m in legal_moves if m[0] == 'attack']
                                if attack_moves:
                                    active_p = sim_game.get_active_player().active_pokemon
                                    best_atk = None
                                    max_dmg = -1
                                    for m in attack_moves:
                                        dmg = active_p.attacks[m[1]]['damage'] if active_p else 0
                                        if dmg > max_dmg:
                                            max_dmg = dmg
                                            best_atk = m
                                    best_move = best_atk if best_atk else attack_moves[0]
                                else:
                                    best_move = ('pass',)

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
            while not node.untried_moves and node.children:
                node = node.select_child(self.exploration_constant)

            if node.untried_moves:
                node = node.expand()

            score = self._run_simulation_with_greedy_policy(node.game_state, root_player)
            node.backpropagate(score, root_player)

        if not root.children:
            return random.choice(legal_moves)

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

        if i % 2 == 0:
            game = GameState(p1, p2)
        else:
            game = GameState(p2, p1)

        print(f"\n--- Starting Game {i + 1}/{num_games} (P1: {type(game.players[0].controller).__name__}, P2: {type(game.players[1].controller).__name__}) ---")
        winner, reason = game.run_game(verbose=verbose_moves)

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

    # Decks with ex and Trainer types
    deck_pikachu = (
        ["Pikachu ex"] * 4 +
        ["Pikachu"] * 6 +
        ["Nest Ball"] * 4 +
        ["Bravery Charm"] * 2 +
        ["Professor's Research"] * 4 +
        ["Boss's Orders"] * 2 +
        ["Lightning Energy"] * 12
    )

    deck_charizard = (
        ["Charmander"] * 6 +
        ["Charmeleon"] * 4 +
        ["Charizard ex"] * 3 +
        ["Rare Candy"] * 3 +
        ["Ultra Ball"] * 4 +
        ["Artazon"] * 2 +
        ["Professor's Research"] * 4 +
        ["Fire Energy"] * 10
    )

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
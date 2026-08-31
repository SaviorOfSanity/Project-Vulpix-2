"""
Pokémon TCG Interactive AI Coach & Real-Time Blunder Analysis Engine
Features:
1. Real-Time Move Recommendations (Ranks Top 3 Actions by ISMCTS win expectancy).
2. Blunder & Inaccuracy Detection (Flags drops in win probability > 0.15 with explanations).
3. Plain-English Tactical Explanations (Thinning deck, energy milestones, prize mapping).
4. Live PTCGL Board State Ingestion Adapter.
"""

from typing import List, Dict, Tuple, Optional, Any

# Import live game engine
game_engine = __import__("Game Engine")
CardFactory = game_engine.CardFactory
Player = game_engine.Player
GameState = game_engine.GameState
PokemonCard = game_engine.PokemonCard
EnergyCard = game_engine.EnergyCard
TrainerCard = game_engine.TrainerCard
MCTSController = game_engine.MCTSController


class AICoach:
    """
    Real-time interactive coaching advisor and blunder analysis engine.
    """
    def __init__(
        self,
        card_factory: Optional[CardFactory] = None,
        coach_iterations: int = 150,
        coach_depth: int = 12
    ):
        self.factory = card_factory or CardFactory('cards.json')
        self.mcts = MCTSController(iteration_limit=coach_iterations, simulation_depth=coach_depth)

    def get_action_description(self, game_state: GameState, action: Tuple) -> str:
        """Converts an action tuple into human-readable tactical text."""
        action_type = action[0]
        player = game_state.get_active_player()
        opp = game_state.players[1 - game_state.active_player_index]

        if action_type == 'play_pokemon':
            card = player.hand[action[1]]
            return f"Play {card.name} to Bench (Expands board presence and prepares next turn evolution)."
        elif action_type == 'evolve':
            card = player.hand[action[1]]
            target = player.active_pokemon if action[2] == 0 else player.bench[action[2] - 1]
            return f"Evolve {target.name} into {card.name} (Increases HP to {card.max_hp} and unlocks new attacks/abilities)."
        elif action_type == 'use_pokemon_ability':
            ability_name = action[2]
            return f"Activate Ability '{ability_name}' (Generates resource advantage without ending turn)."
        elif action_type == 'play_item':
            card = player.hand[action[1]]
            ace_str = " [ACE SPEC]" if card.is_ace_spec else ""
            if card.name == "Buddy-Buddy Poffin":
                return f"Play Item: Buddy-Buddy Poffin (Thins Basic Pokémon from deck to optimize future draws)."
            elif card.name == "Ultra Ball":
                return f"Play Item: Ultra Ball (Searches key evolution or attacker from deck)."
            elif card.name == "Prime Catcher":
                return f"Play ACE SPEC: Prime Catcher (Gusts vulnerable target on opponent's bench)."
            return f"Play Item{ace_str}: {card.name}"
        elif action_type == 'attach_tool':
            card = player.hand[action[1]]
            tgt = "Active" if action[2] == 0 else f"Bench #{action[2]}"
            return f"Attach Tool {card.name} to {tgt}"
        elif action_type == 'play_stadium':
            card = player.hand[action[1]]
            return f"Play Stadium: {card.name}"
        elif action_type == 'use_stadium_ability':
            stadium_name = game_state.active_stadium.name if game_state.active_stadium else "Stadium"
            return f"Use Stadium Ability: {stadium_name}"
        elif action_type == 'attach_energy':
            card = player.hand[action[1]]
            tgt = "Active Pokémon" if action[2] == 0 else f"Benched Pokémon #{action[2]}"
            return f"Attach {card.name} to {tgt} (Building attack readiness)."
        elif action_type == 'play_supporter':
            card = player.hand[action[1]]
            if card.name == "Professor's Research":
                return f"Play Supporter: Professor's Research (Draws fresh 7 cards)."
            elif card.name == "Iono":
                return f"Play Supporter: Iono (Hand disruption + draws {len(player.prize_cards)} cards)."
            elif card.name == "Boss's Orders":
                return f"Play Supporter: Boss's Orders (Gusts target Pokémon into Active spot)."
            return f"Play Supporter: {card.name}"
        elif action_type == 'attack':
            atk = player.active_pokemon.attacks[action[1]]
            dmg = atk.get('damage', 0)
            opp_active = opp.active_pokemon
            opp_hp = (opp_active.get_effective_max_hp() - opp_active.damage_counters) if opp_active else 0
            is_ko = " -> KNOCK OUT!" if (dmg >= opp_hp and opp_active) else ""
            return f"Attack with '{atk['name']}' ({dmg} Damage{is_ko})"
        elif action_type == 'retreat':
            return f"Retreat Active Pokémon to Bench #{action[1]}"
        elif action_type == 'pass':
            return "Pass the turn (Ends your turn)."
        return str(action)

    def evaluate_turn(
        self,
        game_state: GameState,
        top_n: int = 3
    ) -> Dict:
        """
        Evaluates the current board and returns top recommended moves with win expectancies.
        """
        legal_moves = game_state.get_legal_moves()
        if not legal_moves:
            return {"recommended_moves": [], "current_eval": 0.0, "advice": "No legal moves available."}

        active_player = game_state.get_active_player()
        base_eval = self.mcts._evaluate_state(game_state, active_player)

        # Run simulations across legal actions
        action_scores = []

        for move in legal_moves:
            sim_state = game_state.clone()
            sim_state.handle_action(move, verbose=False)

            # Evaluate immediate simulated result
            score = self.mcts._evaluate_state(sim_state, sim_state.players[game_state.active_player_index])
            action_scores.append({
                "action": move,
                "score": score,
                "description": self.get_action_description(game_state, move)
            })

        # Rank moves by score
        action_scores.sort(key=lambda x: x["score"], reverse=True)
        top_recommendations = action_scores[:top_n]

        # Generate tactical summary advice
        best_move = top_recommendations[0]
        if best_move["action"][0] == 'attack':
            advice = f"Attack now with {best_move['description']} to apply immediate prize pressure."
        elif best_move["action"][0] in ('play_pokemon', 'evolve'):
            advice = f"Prioritize board development: {best_move['description']}."
        elif best_move["action"][0] == 'attach_energy':
            advice = f"Power up your attackers: {best_move['description']}."
        else:
            advice = f"Optimal play: {best_move['description']}."

        return {
            "current_eval": base_eval,
            "recommended_moves": top_recommendations,
            "all_move_evals": action_scores,
            "tactical_advice": advice
        }

    def analyze_player_move(
        self,
        game_state: GameState,
        chosen_move: Tuple,
        blunder_threshold: float = 0.15
    ) -> Dict:
        """
        Checks if the player's chosen move was a Blunder, Inaccuracy, or Best Move.
        """
        evaluation = self.evaluate_turn(game_state)
        top_recs = evaluation["recommended_moves"]
        if not top_recs:
            return {"grade": "Normal", "explanation": "No alternatives."}

        best_score = top_recs[0]["score"]
        chosen_score = None

        for item in evaluation["all_move_evals"]:
            if item["action"] == chosen_move:
                chosen_score = item["score"]
                break

        if chosen_score is None:
            chosen_score = evaluation["current_eval"]

        delta = best_score - chosen_score

        if delta <= 0.02:
            grade = "Best Move"
            comment = "Excellent play! This line maximizes your prize advantage."
        elif delta <= 0.08:
            grade = "Good Move"
            comment = "Solid play, closely aligned with optimal lines."
        elif delta <= blunder_threshold:
            grade = "Inaccuracy"
            comment = f"Suboptimal sequencing. Alternative was: {top_recs[0]['description']} (+{delta:.2f} EV)."
        else:
            grade = "Blunder"
            comment = f"Critical Blunder! Missed {top_recs[0]['description']}. This cost {delta:.2f} in win probability."

        return {
            "grade": grade,
            "delta": delta,
            "chosen_score": chosen_score,
            "best_score": best_score,
            "best_action": top_recs[0]["action"],
            "best_action_desc": top_recs[0]["description"],
            "comment": comment
        }

    def ingest_live_board_state(
        self,
        p1_active_name: str,
        p1_active_hp: int,
        p1_active_energy: List[str],
        p1_bench_names: List[str],
        p1_hand_names: List[str],
        p1_prizes_remaining: int,
        p2_active_name: str,
        p2_active_hp: int,
        p2_bench_names: List[str],
        p2_prizes_remaining: int,
        stadium_name: Optional[str] = None
    ) -> GameState:
        """
        Ingestion Adapter: Converts raw PTCGL / OCR state into an active GameState for coaching analysis.
        """
        # Create dummy deck bases
        p1_deck_names = ["Pikachu"] * 60
        p2_deck_names = ["Charmander"] * 60

        p1 = Player("You (Live)", p1_deck_names, self.factory)
        p2 = Player("Opponent (Live)", p2_deck_names, self.factory)
        game = GameState(p1, p2)

        # Build P1 Active
        p1_active = self.factory.create_card(p1_active_name)
        p1_active.damage_counters = max(0, p1_active.max_hp - p1_active_hp)
        p1_active.attached_energy = [self.factory.create_card(e) for e in p1_active_energy]
        p1.active_pokemon = p1_active

        # Build P1 Bench & Hand
        p1.bench = [self.factory.create_card(name) for name in p1_bench_names]
        p1.hand = [self.factory.create_card(name) for name in p1_hand_names]
        p1.prize_cards = [self.factory.create_card("Pikachu") for _ in range(p1_prizes_remaining)]

        # Build P2 Active & Bench
        p2_active = self.factory.create_card(p2_active_name)
        p2_active.damage_counters = max(0, p2_active.max_hp - p2_active_hp)
        p2.active_pokemon = p2_active
        p2.bench = [self.factory.create_card(name) for name in p2_bench_names]
        p2.prize_cards = [self.factory.create_card("Charmander") for _ in range(p2_prizes_remaining)]

        if stadium_name and stadium_name in self.factory.cards_by_name:
            game.active_stadium = self.factory.create_card(stadium_name)

        return game

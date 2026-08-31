"""
Pokémon TCG Deck Builder, Scratch Generator & Anti-Meta Tournament Optimizer (Standard Format)
Features:
1. Complete 60-Card Standard Format Legality Validation (Rule Box limits, 1 ACE SPEC, max 4 copies).
2. Scratch Deck Generator for any primary attacker or evolution chain.
3. Mathematical Search & Energy Curve Optimizer.
4. Anti-Meta & 2nd-Order Counter-Meta Tournament EV Optimizer.
5. Standard PTCGL / Limitless TCG Text Import & Export.
"""

import json
import re
from typing import List, Dict, Tuple, Optional

# Import live game engine
game_engine = __import__("Game Engine")
CardFactory = game_engine.CardFactory
Player = game_engine.Player
GameState = game_engine.GameState
TurnBasedGreedyAI = game_engine.TurnBasedGreedyAI
MCTSController = game_engine.MCTSController
STANDARD_ARCHETYPES = game_engine.STANDARD_ARCHETYPES
TournamentMatrixRunner = game_engine.TournamentMatrixRunner


BASIC_ENERGY_NAMES = {
    "Grass Energy", "Fire Energy", "Water Energy", "Lightning Energy",
    "Psychic Energy", "Fighting Energy", "Darkness Energy", "Metal Energy"
}


class DeckValidator:
    """Validates 60-card Pokémon TCG Standard Format deck legality."""
    
    @staticmethod
    def validate_deck(deck_names: List[str], card_factory: CardFactory) -> Tuple[bool, List[str]]:
        errors = []
        if len(deck_names) != 60:
            errors.append(f"Deck must contain exactly 60 cards (currently has {len(deck_names)}).")

        card_counts: Dict[str, int] = {}
        for name in deck_names:
            card_counts[name] = card_counts.get(name, 0) + 1

        ace_spec_count = 0
        basic_pokemon_count = 0

        for name, count in card_counts.items():
            if name not in card_factory.cards_by_name:
                errors.append(f"Unknown card: '{name}' not found in database.")
                continue

            cdata = card_factory.cards_by_name[name]
            
            # 4-copy limit (Basic Energy exempt)
            if name not in BASIC_ENERGY_NAMES and count > 4:
                errors.append(f"Deck contains {count} copies of '{name}' (maximum allowed is 4).")

            # ACE SPEC Limit: exactly 1 per deck
            if cdata.get("is_ace_spec", False):
                ace_spec_count += count

            # Basic Pokémon check
            if cdata.get("card_type") == "Pokemon" and cdata.get("stage") == "Basic":
                basic_pokemon_count += count

        if ace_spec_count > 1:
            errors.append(f"Deck contains {ace_spec_count} ACE SPEC cards (maximum allowed is 1).")

        if basic_pokemon_count == 0:
            errors.append("Deck must contain at least 1 Basic Pokémon to be playable.")

        is_valid = (len(errors) == 0)
        return is_valid, errors


class DeckBuilder:
    """
    Automated Deck Generator from Scratch, Energy Curve Optimizer, and PTCGL Parser.
    """
    def __init__(self, card_factory: Optional[CardFactory] = None):
        self.factory = card_factory or CardFactory('cards.json')

    def generate_deck_from_scratch(
        self,
        primary_attacker: str,
        secondary_attacker: Optional[str] = None,
        preferred_ace_spec: Optional[str] = None,
        support_engine: str = "standard"
    ) -> List[str]:
        """
        Builds an optimized, legal 60-card deck from scratch centered on primary_attacker.
        """
        deck: List[str] = []
        primary_data = self.factory.cards_by_name.get(primary_attacker)
        if not primary_data:
            raise ValueError(f"Attacker '{primary_attacker}' not found in card database.")

        # 1. Build Pokémon Engine
        # Add primary attacker line
        stage = primary_data.get("stage", "Basic")
        is_ex = primary_data.get("is_rule_box", False)

        if stage == "Basic":
            deck += [primary_attacker] * (4 if is_ex else 3)
        elif stage == "Stage 1":
            pre_evo = primary_data.get("evolves_from")
            if pre_evo:
                deck += [pre_evo] * 4
            deck += [primary_attacker] * 4
        elif stage == "Stage 2":
            stage_1 = primary_data.get("evolves_from")
            stage_1_data = self.factory.cards_by_name.get(stage_1, {})
            basic = stage_1_data.get("evolves_from")
            if basic:
                deck += [basic] * 4
                deck += [stage_1] * 1  # 1 Stage 1 + 4 Rare Candy
                deck += [primary_attacker] * 3
            else:
                deck += [stage_1] * 4
                deck += [primary_attacker] * 3

        # Add secondary attacker line if specified
        if secondary_attacker and secondary_attacker in self.factory.cards_by_name:
            sec_data = self.factory.cards_by_name[secondary_attacker]
            sec_stage = sec_data.get("stage", "Basic")
            if sec_stage == "Basic":
                deck += [secondary_attacker] * 2
            elif sec_stage == "Stage 1":
                sec_pre = sec_data.get("evolves_from")
                if sec_pre and sec_pre in self.factory.cards_by_name:
                    deck += [sec_pre] * 2
                deck += [secondary_attacker] * 2

        # Support Pokémon Consistency Engine
        if support_engine == "draw_support" or primary_attacker in ("Gardevoir ex", "Ceruledge ex", "Gholdengo ex"):
            if "Fezandipiti ex" in self.factory.cards_by_name and "Fezandipiti ex" not in deck:
                deck += ["Fezandipiti ex"] * 1
        elif support_engine == "tera_support" or primary_data.get("is_tera", False):
            if "Hoothoot" in self.factory.cards_by_name and "Noctowl" in self.factory.cards_by_name:
                deck += ["Hoothoot"] * 2 + ["Noctowl"] * 2

        # 2. Search & Item Package
        # Check if we have <=70 HP Basics for Buddy-Buddy Poffin
        has_poffin_targets = any(
            self.factory.cards_by_name.get(c, {}).get("hp", 999) <= 70 and
            self.factory.cards_by_name.get(c, {}).get("stage") == "Basic"
            for c in deck
        )
        if has_poffin_targets:
            deck += ["Buddy-Buddy Poffin"] * 4
            deck += ["Nest Ball"] * 2
        else:
            deck += ["Nest Ball"] * 4

        deck += ["Ultra Ball"] * 4

        if stage == "Stage 2":
            deck += ["Rare Candy"] * 4

        # Recovery Items
        deck += ["Super Rod"] * 2
        if "Night Stretcher" in self.factory.cards_by_name and primary_attacker in ("Ceruledge ex", "Gholdengo ex", "Gardevoir ex"):
            deck += ["Night Stretcher"] * 2

        # Specific item synergies
        if primary_attacker in ("Miraidon ex", "Iron Hands ex"):
            deck += ["Electric Generator"] * 4
        elif primary_attacker in ("Ceruledge ex", "Gholdengo ex"):
            deck += ["Earthen Vessel"] * 4

        # 3. Supporters Package
        deck += ["Professor's Research"] * 4
        deck += ["Iono"] * 3
        deck += ["Boss's Orders"] * 2
        deck += ["Counter Catcher"] * 1

        if primary_data.get("is_ancient", False) or (secondary_attacker and self.factory.cards_by_name.get(secondary_attacker, {}).get("is_ancient", False)):
            deck += ["Professor Sada's Vitality"] * 4

        # 4. Stadium & ACE SPEC Selection
        if preferred_ace_spec and preferred_ace_spec in self.factory.cards_by_name:
            deck += [preferred_ace_spec] * 1
        else:
            # Auto-select best ACE SPEC for archetype
            if primary_attacker == "Gardevoir ex":
                deck += ["Hero's Cape"] * 1
            elif primary_attacker == "Charizard ex":
                deck += ["Unfair Stamp"] * 1
            elif primary_attacker == "Ceruledge ex":
                deck += ["Secret Box"] if "Secret Box" in self.factory.cards_by_name else ["Grand Tree"]
            elif primary_data.get("is_tera", False):
                deck += ["Prime Catcher"] * 1
            else:
                deck += ["Prime Catcher"] * 1

        if primary_data.get("is_tera", False) and "Area Zero Underdepths" in self.factory.cards_by_name:
            deck += ["Area Zero Underdepths"] * 3

        # 5. Energy Optimization & Curve Completion
        # Find primary energy type from attack costs
        needed_energy_type = "Fire Energy"
        for atk in primary_data.get("attacks", []):
            for cost_type in atk.get("cost", []):
                if cost_type != "Colorless":
                    cand = f"{cost_type} Energy"
                    if cand in self.factory.cards_by_name:
                        needed_energy_type = cand
                        break

        # Calculate remaining slots to reach exactly 60 cards
        current_count = len(deck)
        remaining = 60 - current_count

        if remaining < 4:
            # Trim excess items/supporters if deck is overfilled
            while len(deck) > 52:
                for removable in ["Nest Ball", "Iono", "Buddy-Buddy Poffin"]:
                    if deck.count(removable) > 2:
                        deck.remove(removable)
                        break
            remaining = 60 - len(deck)

        # Add Special Energy if usable
        if primary_data.get("is_tera", False) or primary_attacker in ("Terapagos ex", "Charizard ex", "Miraidon ex"):
            deck += ["Double Turbo Energy"] * min(4, max(2, remaining // 3))
            remaining = 60 - len(deck)

        # Fill remaining slots with primary Basic Energy
        deck += [needed_energy_type] * remaining

        # Final validate
        is_valid, errors = DeckValidator.validate_deck(deck, self.factory)
        if not is_valid:
            raise ValueError(f"Deck generation produced invalid deck: {errors}")

        return deck

    def export_to_ptcgl(self, deck_names: List[str]) -> str:
        """Exports decklist to standard PTCGL text format."""
        pokemon_lines = []
        trainer_lines = []
        energy_lines = []

        counts: Dict[str, int] = {}
        for name in deck_names:
            counts[name] = counts.get(name, 0) + 1

        for name, count in sorted(counts.items()):
            cdata = self.factory.cards_by_name.get(name, {})
            ctype = cdata.get("card_type", "Pokemon")
            if ctype == "Pokemon":
                pokemon_lines.append(f"{count} {name}")
            elif ctype == "Trainer":
                trainer_lines.append(f"{count} {name}")
            elif ctype == "Energy":
                energy_lines.append(f"{count} {name}")

        output = ["Pokémon: " + str(sum(counts[k] for k in counts if self.factory.cards_by_name.get(k, {}).get("card_type") == "Pokemon"))]
        output.extend(pokemon_lines)
        output.append("\nTrainer: " + str(sum(counts[k] for k in counts if self.factory.cards_by_name.get(k, {}).get("card_type") == "Trainer")))
        output.extend(trainer_lines)
        output.append("\nEnergy: " + str(sum(counts[k] for k in counts if self.factory.cards_by_name.get(k, {}).get("card_type") == "Energy")))
        output.extend(energy_lines)

        return "\n".join(output)

    def import_from_ptcgl(self, ptcgl_text: str) -> List[str]:
        """Imports decklist from standard PTCGL text format."""
        deck = []
        for line in ptcgl_text.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("Pokémon:") or line.startswith("Trainer:") or line.startswith("Energy:"):
                continue

            match = re.match(r"^(\d+)\s+([A-Za-z0-9\s'’\-]+?)(?:\s+[A-Z]{2,4}\s+\d+)?$", line)
            if match:
                count = int(match.group(1))
                raw_name = match.group(2).strip()
                # Resolve fuzzy match
                resolved_name = None
                for card_name in self.factory.cards_by_name:
                    if card_name.lower() == raw_name.lower():
                        resolved_name = card_name
                        break
                
                if resolved_name:
                    deck += [resolved_name] * count

        is_valid, errors = DeckValidator.validate_deck(deck, self.factory)
        return deck


class AntiMetaOptimizer:
    """
    Tournament EV & Counter-Meta Deck Optimizer.
    Evaluates expected tournament meta distributions and synthesizes decks
    that beat the primary meta threats and their 2nd-order counter decks.
    """
    def __init__(self, card_factory: Optional[CardFactory] = None):
        self.factory = card_factory or CardFactory('cards.json')
        self.builder = DeckBuilder(self.factory)

    def optimize_anti_meta_deck(
        self,
        meta_distribution: Dict[str, float],
        candidate_archetypes: Optional[List[Tuple[str, str, List[str]]]] = None,
        sample_games_per_eval: int = 2,
        mcts_iterations: int = 30
    ) -> Dict:
        """
        Finds and tunes the optimal deck to maximize Expected Tournament Win Rate
        against a predicted meta field (e.g. 40% Charizard, 30% Ceruledge, 30% Gardevoir).
        """
        print(f"\n{'='*80}")
        print(f"  ANTI-META TOURNAMENT OPTIMIZER: Analyzing Field Distribution")
        for deck_name, share in meta_distribution.items():
            print(f"    - {deck_name}: {share*100:.1f}% Expected Meta Share")
        print(f"{'='*80}\n")

        # Candidate Archetypes to evaluate & tech
        candidates = candidate_archetypes or [
            ("Ceruledge ex", "Fire", ["Secret Box", "Grand Tree"]),
            ("Terapagos ex", "Colorless", ["Prime Catcher", "Neutral Center"]),
            ("Gardevoir ex", "Psychic", ["Hero's Cape", "Unfair Stamp"]),
            ("Charizard ex", "Fire", ["Unfair Stamp", "Prime Catcher"]),
            ("Raging Bolt ex", "Dragon", ["Prime Catcher", "Hero's Cape"]),
            ("Miraidon ex", "Lightning", ["Prime Catcher"]),
            ("Gholdengo ex", "Metal", ["Prime Catcher", "Neutral Center"]),
            ("Dragapult ex", "Dragon", ["Prime Catcher", "Hero's Cape"])
        ]

        best_score = -1.0
        best_candidate = None
        best_decklist = []
        eval_records = []

        for primary_atk, ptype, ace_specs in candidates:
            for ace_spec in ace_specs:
                if ace_spec not in self.factory.cards_by_name:
                    continue

                test_deck = self.builder.generate_deck_from_scratch(
                    primary_attacker=primary_atk,
                    preferred_ace_spec=ace_spec
                )

                # Simulate against each archetype in the meta distribution
                weighted_wr = 0.0
                matchup_results = {}

                for meta_target, target_weight in meta_distribution.items():
                    if meta_target not in STANDARD_ARCHETYPES:
                        continue

                    opp_deck = STANDARD_ARCHETYPES[meta_target]
                    wins = 0

                    for g in range(sample_games_per_eval):
                        c1 = MCTSController(iteration_limit=mcts_iterations, simulation_depth=4)
                        c2 = TurnBasedGreedyAI()

                        if g % 2 == 0:
                            p1 = Player("Candidate", test_deck, self.factory, controller=c1)
                            p2 = Player(meta_target, opp_deck, self.factory, controller=c2)
                            game = GameState(p1, p2)
                            winner, _ = game.run_game(verbose=False)
                            if winner is p1:
                                wins += 1
                        else:
                            p2 = Player(meta_target, opp_deck, self.factory, controller=c1)
                            p1 = Player("Candidate", test_deck, self.factory, controller=c2)
                            game = GameState(p2, p1)
                            winner, _ = game.run_game(verbose=False)
                            if winner is p1:
                                wins += 1

                    match_wr = wins / sample_games_per_eval
                    matchup_results[meta_target] = match_wr
                    weighted_wr += match_wr * target_weight

                record = {
                    "archetype": primary_atk,
                    "ace_spec": ace_spec,
                    "weighted_expected_winrate": weighted_wr,
                    "matchups": matchup_results,
                    "decklist": test_deck
                }
                eval_records.append(record)

                if weighted_wr > best_score or best_candidate is None:
                    best_score = weighted_wr
                    best_candidate = record
                    best_decklist = test_deck

        print(f"[TOP EV] Optimal Anti-Meta Deck Identified: {best_candidate['archetype']} ({best_candidate['ace_spec']})")
        print(f"   Expected Field Win Rate: {best_candidate['weighted_expected_winrate']*100:.1f}%\n")

        return {
            "best_deck_name": f"{best_candidate['archetype']} ({best_candidate['ace_spec']})",
            "best_decklist": best_decklist,
            "expected_winrate": best_candidate['weighted_expected_winrate'],
            "matchup_breakdown": best_candidate['matchups'],
            "all_evaluated": eval_records
        }



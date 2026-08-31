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
from typing import List, Dict, Tuple, Optional, Any

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
        if support_engine == "draw_support" or primary_attacker in ("Gardevoir ex", "Ceruledge ex", "Gholdengo ex", "Lillie's Clefairy ex"):
            if "Fezandipiti ex" in self.factory.cards_by_name and "Fezandipiti ex" not in deck:
                deck += ["Fezandipiti ex"] * 1
        elif support_engine == "tera_support" or primary_data.get("is_tera", False):
            if "Hoothoot" in self.factory.cards_by_name and "Noctowl" in self.factory.cards_by_name:
                deck += ["Hoothoot"] * 2 + ["Noctowl"] * 2

        if primary_attacker == "Lillie's Clefairy ex" or secondary_attacker == "Mega Kangaskhan ex":
            if "Latias ex" in self.factory.cards_by_name:
                deck += ["Latias ex"] * 2
            if "Wellspring Mask Ogerpon ex" in self.factory.cards_by_name:
                deck += ["Wellspring Mask Ogerpon ex"] * 1
            if "Koraidon ex" in self.factory.cards_by_name:
                deck += ["Koraidon ex"] * 1

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
        elif primary_attacker == "Lillie's Clefairy ex":
            deck += ["Wondrous Patch"] * 3
            if "Lillie's Pearl" in self.factory.cards_by_name:
                deck += ["Lillie's Pearl"] * 2

        # 3. Supporters Package
        if primary_attacker == "Lillie's Clefairy ex":
            deck += ["Crispin"] * 4
            deck += ["Boss's Orders"] * 2
            deck += ["Ciphermaniac's Codebreaking"] * 2
        else:
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

        if (primary_data.get("is_tera", False) or primary_attacker == "Lillie's Clefairy ex" or "Wellspring Mask Ogerpon ex" in deck) and "Area Zero Underdepths" in self.factory.cards_by_name:
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

    def build_targeted_counter_deck(
        self,
        target_name_or_deck: Any,
        preferred_style: str = "Hard Counter"
    ) -> Dict:
        """
        Builds a dedicated, customized deck designed specifically to beat a single target archetype.
        Analyzes the target's type weakness, HP milestones, ability reliance, and prize structure.
        """
        target_name = target_name_or_deck if isinstance(target_name_or_deck, str) else "Custom Opponent"
        target_cards = STANDARD_ARCHETYPES.get(target_name, []) if isinstance(target_name_or_deck, str) else target_name_or_deck

        # Determine target's primary element & structure
        target_primary_type = "Colorless"
        target_has_ex = False
        target_has_stage2 = False

        for cname in target_cards:
            cdata = self.factory.cards_by_name.get(cname, {})
            if cdata.get("is_rule_box", False):
                target_has_ex = True
            if cdata.get("stage") == "Stage 2":
                target_has_stage2 = True
            if cdata.get("attacks"):
                for atk in cdata.get("attacks", []):
                    for cost in atk.get("cost", []):
                        if cost in ("Fire", "Psychic", "Lightning", "Water", "Grass", "Metal", "Darkness", "Dragon"):
                            target_primary_type = cost
                            break

        # Select the ultimate counter archetype based on matchup mechanics
        if "Dragapult" in target_name:
            counter_atk = "Cornerstone Mask Ogerpon ex"
            ace_spec = "Hero's Cape"
            strategy_note = (
                "Dragapult ex World Championship Counter Strategy:\n"
                "• Cornerstone Stance completely blocks damage from Pokémon with Abilities.\n"
                "• Hero's Cape pushes your attacker out of Phantom Dive (200 + 60 bench) range, turning the 2-prize trade decisively in your favor."
            )
        elif "Teal Mask" in target_name or "Clefairy" in target_name:
            counter_atk = "Ceruledge ex"
            ace_spec = "Prime Catcher"
            strategy_note = (
                "Teal Mask / Lillie's Clefairy Rainbow Swarm Counter Strategy:\n"
                "• Exploits Fire Weakness on Teal Mask Ogerpon ex for easy 2-prize KOs.\n"
                "• Prime Catcher gusts Lillie's Clefairy ex off the 8-Pokémon bench to collapse their energy discount engine."
            )
        elif "Zoroark" in target_name:
            counter_atk = "Crustle"
            ace_spec = "Hero's Cape"
            strategy_note = (
                "N's Zoroark ex Championship Counter Strategy:\n"
                "• Exploits Grass Weakness on N's Zorua and N's Zoroark ex for 260+ damage Crabhammer 1HKOs.\n"
                "• Crustle's Solid Rock ability (-30 damage) and 1-prize status creates an impossible prize race for Zoroark."
            )
        elif "Alakazam" in target_name or "Slowking" in target_name:
            counter_atk = "N's Zoroark ex"
            ace_spec = "Unfair Stamp"
            strategy_note = (
                "Alakazam / Slowking Bench-Attack Counter Strategy:\n"
                "• Exploits Darkness Weakness on Abra, Kadabra, Alakazam, and Slowking for instant 1HKOs.\n"
                "• Unfair Stamp reduces opponent's hand to 2 cards, shutting down Dudunsparce and Seek Inspiration draw engines."
            )
        elif "Excadrill" in target_name or "Metang" in target_name:
            counter_atk = "Ceruledge ex"
            ace_spec = "Grand Tree"
            strategy_note = (
                "Mega Excadrill / Metang Metal Acceleration Counter Strategy:\n"
                "• Exploits Fire Weakness across the entire Drilbur, Excadrill, Beldum, and Metang line for doubled damage.\n"
                "• Grand Tree enables instant Turn 1 evolution to KO opposing Beldums before Metal Maker can accelerate."
            )
        elif "Crustle" in target_name:
            counter_atk = "Ceruledge ex"
            ace_spec = "Secret Box"
            strategy_note = (
                "Crustle Solid Rock Counter Strategy:\n"
                "• Overwhelms Crustle's -30 damage reduction by exploiting Fire Weakness for 500+ damage Abyssal Flames."
            )
        elif target_primary_type == "Fire" or "Charizard" in target_name:
            counter_atk = "Terapagos ex"
            ace_spec = "Neutral Center"
            strategy_note = (
                "Fire Matchup Counter Strategy:\n"
                "• Uses Neutral Center Stadium to completely prevent all attack damage from Pokémon ex.\n"
                "• Deploys Terapagos ex Crown Opal (180 dmg) to lock out Basic attackers while denying Charizard KO prizes."
            )
        elif target_primary_type == "Psychic" or "Gardevoir" in target_name:
            counter_atk = "Ceruledge ex"
            ace_spec = "Grand Tree"
            strategy_note = (
                "Gardevoir Matchup Counter Strategy:\n"
                "• Employs high damage speed via Abyssal Flames (300+ damage with discarded energies) to 1HKO Gardevoir ex (310 HP).\n"
                "• Grand Tree accelerates Charcadet directly to Ceruledge ex by Turn 1-2 to outpace Gardevoir's setup."
            )
        else:
            counter_atk = "Ceruledge ex"
            ace_spec = "Prime Catcher"
            strategy_note = (
                "Universal Tempo Counter Strategy:\n"
                "• Exploits Prime Catcher gusting to eliminate support engines before attackers power up."
            )

        counter_deck = self.generate_deck_from_scratch(
            primary_attacker=counter_atk,
            preferred_ace_spec=ace_spec
        )
        ptcgl_text = self.export_to_ptcgl(counter_deck)

        return {
            "target_deck": target_name,
            "counter_deck_name": f"{counter_atk} ({ace_spec})",
            "primary_attacker": counter_atk,
            "ace_spec": ace_spec,
            "counter_decklist": counter_deck,
            "ptcgl_text": ptcgl_text,
            "strategy_rationale": strategy_note
        }

    def innovate_rogue_anti_meta_deck(self) -> Dict:
        """
        Synthesizes an unexpected, rogue/underground deck designed to catch
        the top meta decks off guard through prize denial, lockdown, or speed.
        """
        import random
        rogue_concepts = [
            {
                "name": "Cornerstone Safeguard Anti-Ability Lock",
                "attacker": "Cornerstone Mask Ogerpon ex",
                "ace_spec": "Neutral Center",
                "concept": "Total Immunity Against Pokémon with Abilities",
                "why_it_wins": "Meta titans like Charizard ex, Gardevoir ex, Pidgeot ex, Gholdengo ex, and Archaludon ex rely on abilities. Cornerstone Stance completely blocks 100% of damage from any Pokémon with an ability!"
            },
            {
                "name": "Applin & Dipplin Festival Lead Double-Attack",
                "attacker": "Dipplin",
                "ace_spec": "Secret Box",
                "concept": "Single-Prize Double Striker Swarm",
                "why_it_wins": "With Festival Grounds, Dipplin attacks twice per turn for just 1 Grass Energy (100 + 100 dmg). Giving up only 1 prize card crushes the prize exchange against multi-prize ex decks."
            },
            {
                "name": "Dusknoir Cursed Blast + Drifloon 360 Nuke",
                "attacker": "Drifloon",
                "secondary": "Dusknoir",
                "ace_spec": "Hero's Cape",
                "concept": "Ghost Catapult 1-Prize Knock Out Engine",
                "why_it_wins": "Dusknoir detonates Cursed Blast to place 130 damage counters anywhere on the opponent's bench (wiping out support engines). Drifloon with Hero's Cape hits 360+ damage to 1HKO 330 HP Stage 2 ex Pokémon!"
            },
            {
                "name": "Milotic ex Anti-Tera Lockdown",
                "attacker": "Milotic ex",
                "ace_spec": "Prime Catcher",
                "concept": "Complete Immunity to Tera Pokémon",
                "why_it_wins": "Sparkling Scales prevents all damage and effects from Tera Pokémon (Terapagos ex, Dragapult ex, Charizard ex). Tera decks cannot damage Milotic ex."
            },
            {
                "name": "Bloodmoon Ursaluna Endgame Sweeper",
                "attacker": "Bloodmoon Ursaluna ex",
                "ace_spec": "Hero's Cape",
                "concept": "Zero-Energy 240 Damage Finisher",
                "why_it_wins": "As opponent takes prize cards, Blood Moon drops to 0-1 energy cost, creating a 360 HP endgame juggernaut that 1HKOs active attackers for free."
            },
            {
                "name": "Bouffalant + Terapagos Colorless Bunker",
                "attacker": "Terapagos ex",
                "secondary": "Bouffalant",
                "ace_spec": "Neutral Center",
                "concept": "Impenetrable -60 Damage Reduction Fortress",
                "why_it_wins": "Bouffalant's Curly Wall reduces damage taken by Colorless Basics by 60. Combined with Crown Opal (180 dmg) and Neutral Center, meta decks cannot break through."
            },
            {
                "name": "Pecharunt ex + Brute Bonnet Toxic Melter",
                "attacker": "Pecharunt ex",
                "secondary": "Brute Bonnet",
                "ace_spec": "Dangerous Laser",
                "concept": "Triple Special Condition Passive Burn",
                "why_it_wins": "Dangerous Laser + Toxic Boost inflicts Poison, Burn, and Confusion. Munkidori's Adrena-Brain moves damage counters, dealing 90+ passive damage between turns without even attacking."
            },
            {
                "name": "Archaludon ex Heavy Metal Bridge",
                "attacker": "Archaludon ex",
                "ace_spec": "Grand Tree",
                "concept": "300 HP Metal Energy Recycler",
                "why_it_wins": "300 HP Metal powerhouse accelerates discarded Metal Energy directly onto attackers while Metal Defender provides passive damage reduction."
            },
            {
                "name": "Iron Hands ex Prize Accelerator",
                "attacker": "Iron Hands ex",
                "ace_spec": "Prime Catcher",
                "concept": "3-Prize Multiplier Blitz",
                "why_it_wins": "Amp You Very Much takes 3 Prize cards per ex Knock Out. Taking 2 KOs on opposing 2-prize ex Pokémon wins the match in just 2 turns."
            },
            {
                "name": "Pikachu ex Topaz Bolt Burst",
                "attacker": "Pikachu ex",
                "ace_spec": "Sparkling Crystal",
                "concept": "300 Damage Turn-2 Lightning Cannon",
                "why_it_wins": "Sparkling Crystal reduces Topaz Bolt's cost, firing 300 damage by Turn 2 to 1HKO almost every target in the Standard Format."
            },
            {
                "name": "Froslass Freezing Shroud Ability-Punisher",
                "attacker": "Froslass",
                "secondary": "Munkidori",
                "ace_spec": "Neutral Center",
                "concept": "Passive Board-Wide Freeze",
                "why_it_wins": "Freezing Shroud passively damages all Pokémon with abilities during Pokémon Checkup. Ability-dependent decks (Pidgeot, Fezandipiti, Kirlia) collapse without attacking."
            },
            {
                "name": "Latias ex + Raging Bolt Speed Turbo",
                "attacker": "Raging Bolt ex",
                "secondary": "Latias ex",
                "ace_spec": "Prime Catcher",
                "concept": "Zero-Retreat Unlimited Energy Cannon",
                "why_it_wins": "Latias ex gives free retreat to all Basic Pokémon. Discards unlimited energies from anywhere on your board to hit 280-420+ damage on Turn 1-2."
            },
            {
                "name": "Lillie's Clefairy Rainbow Swarm Toolbox",
                "attacker": "Lillie's Clefairy ex",
                "secondary": "Mega Kangaskhan ex",
                "ace_spec": "Prime Catcher",
                "concept": "Area Zero 8-Bench Multi-Type Toolbox",
                "why_it_wins": "Expands bench to 8 slots with Area Zero Underdepths. Uses Lillie's Clefairy Fairy Chorus to reduce energy costs by 1 across the board and accelerates multi-color energy with Crispin, Wondrous Patch, and Latias ex free retreat."
            }
        ]

        if not hasattr(self, '_rogue_cycle') or not self._rogue_cycle:
            self._rogue_cycle = list(rogue_concepts)
            random.shuffle(self._rogue_cycle)

        chosen = self._rogue_cycle.pop(0)

        deck = self.generate_deck_from_scratch(
            primary_attacker=chosen["attacker"],
            secondary_attacker=chosen.get("secondary"),
            preferred_ace_spec=chosen["ace_spec"]
        )
        ptcgl_text = self.export_to_ptcgl(deck)

        return {
            "rogue_name": chosen["name"],
            "primary_attacker": chosen["attacker"],
            "ace_spec": chosen["ace_spec"],
            "archetype_concept": chosen["concept"],
            "why_it_wins": chosen["why_it_wins"],
            "decklist": deck,
            "ptcgl_text": ptcgl_text
        }





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
            ("Dragapult ex", "Dragon", ["Prime Catcher", "Hero's Cape"]),
            ("Teal Mask Ogerpon ex", "Grass", ["Prime Catcher", "Secret Box"]),
            ("N's Zoroark ex", "Darkness", ["Unfair Stamp", "Prime Catcher"]),
            ("Alakazam", "Psychic", ["Hero's Cape", "Secret Box"]),
            ("Slowking", "Psychic", ["Secret Box", "Hero's Cape"]),
            ("Mega Excadrill ex", "Metal", ["Prime Catcher", "Grand Tree"]),
            ("Crustle", "Grass", ["Hero's Cape", "Neutral Center"]),
            ("Cornerstone Mask Ogerpon ex", "Fighting", ["Hero's Cape", "Neutral Center"])
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



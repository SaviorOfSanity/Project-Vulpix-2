"""
Pokémon TCG Matchup Gameplan & Strategic Prize-Map Planner (Standard Format)
Generates customized, in-depth tournament strategy guides for any Deck A vs Deck B matchup.
Pillars:
1. Optimal 2-2-2 Prize-Map Roadmap.
2. Turn 1-2 Setup Priorities (Search targets, bench limits).
3. Primary Attackers & Damage Milestones.
4. Opponent Threat Warnings & Counterplays (ACE SPECs, Gusts, Disruption).
5. Matchup Dos and Don'ts.
"""

from typing import List, Dict, Tuple, Optional, Any

# Import live game engine
game_engine = __import__("Game Engine")
CardFactory = game_engine.CardFactory
STANDARD_ARCHETYPES = game_engine.STANDARD_ARCHETYPES


class StrategyPlanner:
    """
    Automated Strategic Matchup Guide & Prize-Mapping Engine.
    """
    def __init__(self, card_factory: Optional[CardFactory] = None):
        self.factory = card_factory or CardFactory('cards.json')

    def analyze_deck_composition(self, deck_names: List[str]) -> Dict:
        """Extracts key strategic metrics from a 60-card decklist."""
        pokemon_cards = []
        ace_specs = []
        draw_supporters = []
        gust_cards = []
        rule_box_attackers = []
        single_prize_attackers = []

        counts = {}
        for name in deck_names:
            counts[name] = counts.get(name, 0) + 1

        for name in set(deck_names):
            cdata = self.factory.cards_by_name.get(name, {})
            ctype = cdata.get("card_type")

            if ctype == "Pokemon":
                pokemon_cards.append((name, counts[name], cdata))
                if cdata.get("is_rule_box", False):
                    rule_box_attackers.append((name, cdata))
                else:
                    if cdata.get("attacks"):
                        single_prize_attackers.append((name, cdata))
            elif cdata.get("is_ace_spec", False):
                ace_specs.append(name)
            elif name in ("Professor's Research", "Iono", "Professor Sada's Vitality"):
                draw_supporters.append(name)
            elif name in ("Boss's Orders", "Counter Catcher", "Prime Catcher"):
                gust_cards.append(name)

        return {
            "pokemon": pokemon_cards,
            "rule_box_ex": rule_box_attackers,
            "single_prizers": single_prize_attackers,
            "ace_specs": ace_specs,
            "draw_supporters": draw_supporters,
            "gust_cards": gust_cards
        }

    def generate_gameplan(
        self,
        my_deck: List[str],
        my_deck_name: str,
        opp_deck: List[str],
        opp_deck_name: str
    ) -> Dict:
        """
        Synthesizes a deep strategic gameplan for my_deck against opp_deck.
        """
        my_comp = self.analyze_deck_composition(my_deck)
        opp_comp = self.analyze_deck_composition(opp_deck)

        # 1. Prize Map Roadmap
        # Check opponent's 2-prize liabilities
        opp_ex_names = [name for name, _ in opp_comp["rule_box_ex"]]
        my_ex_names = [name for name, _ in my_comp["rule_box_ex"]]

        if len(opp_ex_names) >= 2:
            prize_plan = (
                f"Execute a 2-2-2 Prize Route:\n"
                f"  1. Take first 2 prizes on opponent's starting active or benched {opp_ex_names[0]}.\n"
                f"  2. Use gust ({', '.join(my_comp['gust_cards']) or 'Boss / Prime Catcher'}) to KO a 2nd Rule Box Pokémon ({opp_ex_names[1] if len(opp_ex_names) > 1 else opp_ex_names[0]}).\n"
                f"  3. Close the game with a final 2-prize Knock Out on the remaining Rule Box Pokémon for all 6 prizes."
            )
        else:
            prize_plan = (
                f"Execute an Adaptive 1-2-1-2 / 2-2-2 Prize Route:\n"
                f"  1. Take early single prizes on non-evolved support Basics.\n"
                f"  2. Save gust cards ({', '.join(my_comp['gust_cards']) or 'Boss'}) to eliminate their main attacker for 2 prizes once committed.\n"
                f"  3. Maintain prize trade advantage by denying them multi-prize turns."
            )

        # 2. Turn 1-2 Setup Priorities
        setup_basics = [name for name, count, cdata in my_comp["pokemon"] if cdata.get("stage") == "Basic" and not cdata.get("is_rule_box", False)]
        bench_priorities = f"Bench {', '.join(setup_basics[:3]) or 'primary Basic attackers'} on Turn 1 via Buddy-Buddy Poffin or Nest Ball."

        # 3. Key Matchup Interactions & Warnings
        warnings = []
        if opp_comp["ace_specs"]:
            warnings.append(f"Watch out for Opponent's ACE SPEC: {', '.join(opp_comp['ace_specs'])}.")
        if "Neutral Center" in opp_deck:
            warnings.append("Opponent runs Neutral Center: Do not attack non-Rule Box Pokémon with Pokémon ex while stadium is in play.")
        if "Hero's Cape" in opp_deck:
            warnings.append("Opponent runs Hero's Cape (+100 HP): Account for higher KO damage thresholds.")
        if "Unfair Stamp" in opp_deck:
            warnings.append("Opponent runs Unfair Stamp: Taking early prize lead will trigger hand reduction to 2 cards.")

        # 4. Dos and Don'ts
        dos = [
            f"Establish your main attacker ({', '.join(my_ex_names[:2]) or 'Primary Attacker'}) by Turn 2.",
            f"Conserve gust cards ({', '.join(my_comp['gust_cards']) or 'Boss'}) for high-value 2-prize KOs.",
            "Thin Basic Pokémon from deck before playing Professor's Research or Iono."
        ]
        donts = [
            "Do not over-bench 2-prize liabilities if you cannot power them up this turn.",
            "Do not play your ACE SPEC carelessly before baiting opponent's Stadium/Item removals.",
            "Do not attach energy to an inactive attacker when your active is 1 energy away from taking prizes."
        ]

        report = {
            "matchup_title": f"{my_deck_name} vs {opp_deck_name}",
            "prize_map_plan": prize_plan,
            "turn_1_2_setup": bench_priorities,
            "threat_warnings": warnings,
            "dos": dos,
            "donts": donts,
            "my_ace_spec": my_comp["ace_specs"],
            "opp_ace_spec": opp_comp["ace_specs"]
        }

        # Formatted Output
        print(f"\n{'='*85}")
        print(f"  STRATEGIC MATCHUP GUIDE: {my_deck_name} vs {opp_deck_name}")
        print(f"{'='*85}\n")
        print("[PRIZE MAP ROADMAP]")
        print(prize_plan + "\n")
        print("[TURN 1-2 SETUP PRIORITIES]")
        print(f"  - {bench_priorities}\n")
        print("[THREAT WARNINGS & COUNTERS]")
        for w in warnings:
            print(f"  - {w}")
        print("\n[DOS]")
        for d in dos:
            print(f"  - {d}")
        print("\n[DONTS]")
        for d in donts:
            print(f"  - {d}")
        print(f"\n{'='*85}\n")

        return report


if __name__ == '__main__':
    factory = CardFactory('cards.json')
    planner = StrategyPlanner(factory)
    planner.generate_gameplan(
        my_deck=STANDARD_ARCHETYPES["Gardevoir ex"],
        my_deck_name="Gardevoir ex",
        opp_deck=STANDARD_ARCHETYPES["Charizard ex"],
        opp_deck_name="Charizard ex"
    )

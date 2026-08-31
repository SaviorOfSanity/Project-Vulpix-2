"""
Utility script to generate verification logs for Phase 3 Standard format meta matchups:
1. Verbose match log: Gardevoir ex / Drifloon vs Terapagos ex / Noctowl
2. Batch simulation log with Information-Set MCTS (ISMCTS), Special Conditions, and ACE SPECs.
"""

import sys
import io

game_engine = __import__("Game Engine")
CardFactory = game_engine.CardFactory
Player = game_engine.Player
GameState = game_engine.GameState
TurnBasedGreedyAI = game_engine.TurnBasedGreedyAI
MCTSController = game_engine.MCTSController
run_simulation = game_engine.run_simulation

def generate_logs():
    factory = CardFactory('cards.json')

    deck_gardevoir = (
        ["Ralts"] * 4 +
        ["Kirlia"] * 4 +
        ["Gardevoir ex"] * 2 +
        ["Drifloon"] * 2 +
        ["Scream Tail"] * 2 +
        ["Munkidori"] * 2 +
        ["Fezandipiti ex"] * 1 +
        ["Hero's Cape"] * 1 +
        ["Buddy-Buddy Poffin"] * 4 +
        ["Ultra Ball"] * 4 +
        ["Super Rod"] * 2 +
        ["Counter Catcher"] * 1 +
        ["Professor's Research"] * 4 +
        ["Boss's Orders"] * 2 +
        ["Iono"] * 3 +
        ["Psychic Energy"] * 18 +
        ["Darkness Energy"] * 4
    )

    deck_terapagos = (
        ["Terapagos ex"] * 3 +
        ["Hoothoot"] * 3 +
        ["Noctowl"] * 3 +
        ["Fezandipiti ex"] * 1 +
        ["Prime Catcher"] * 1 +
        ["Area Zero Underdepths"] * 3 +
        ["Buddy-Buddy Poffin"] * 4 +
        ["Ultra Ball"] * 4 +
        ["Nest Ball"] * 4 +
        ["Super Rod"] * 2 +
        ["Double Turbo Energy"] * 4 +
        ["Professor's Research"] * 4 +
        ["Boss's Orders"] * 2 +
        ["Iono"] * 3 +
        ["Grass Energy"] * 6 +
        ["Lightning Energy"] * 6 +
        ["Fighting Energy"] * 7
    )

    # 1. Generate Verbose Game Log
    print("\n" + "="*80)
    print("  LOG 1: VERBOSE MATCH (Gardevoir ex / Drifloon vs Terapagos ex / Noctowl)")
    print("="*80 + "\n")

    c1 = MCTSController(iteration_limit=200, simulation_depth=12)
    c2 = TurnBasedGreedyAI()
    p1 = Player("Red (ISMCTS - Gardevoir ex)", deck_gardevoir, factory, controller=c1)
    p2 = Player("Blue (GreedyAI - Terapagos ex)", deck_terapagos, factory, controller=c2)

    game = GameState(p1, p2)
    winner, reason = game.run_game(verbose=True, max_turns=30)
    print(f"\n[FINAL RESULT] Winner: {winner.name if winner else 'None'} | Reason: {reason}\n")

    # 2. Generate Batch Simulation Telemetry Log
    print("\n" + "="*80)
    print("  LOG 2: BATCH META SIMULATION (5 Games)")
    print("="*80 + "\n")

    run_simulation(
        controller1_type=MCTSController,
        controller2_type=TurnBasedGreedyAI,
        num_games=5,
        card_factory=factory,
        deck1_names=deck_gardevoir,
        deck2_names=deck_terapagos,
        c1_kwargs={"iteration_limit": 250, "simulation_depth": 14},
        verbose_moves=False
    )

if __name__ == '__main__':
    generate_logs()

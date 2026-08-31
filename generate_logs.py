"""
Utility script to generate verification logs for Phase 2 Standard format meta matchups:
1. Verbose single match log (Charizard ex / Pidgeot ex vs Dragapult ex)
2. Batch simulation log (MCTS search telemetry, abilities, special energy, and summary statistics)
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

    deck_charizard_pidgeot = (
        ["Charmander"] * 4 +
        ["Charmeleon"] * 1 +
        ["Charizard ex"] * 3 +
        ["Pidgey"] * 3 +
        ["Pidgeot ex"] * 2 +
        ["Rare Candy"] * 4 +
        ["Buddy-Buddy Poffin"] * 4 +
        ["Ultra Ball"] * 4 +
        ["Nest Ball"] * 2 +
        ["Super Rod"] * 2 +
        ["Counter Catcher"] * 1 +
        ["Professor's Research"] * 4 +
        ["Boss's Orders"] * 2 +
        ["Iono"] * 3 +
        ["Artazon"] * 1 +
        ["Fire Energy"] * 16 +
        ["Double Turbo Energy"] * 4
    )

    deck_dragapult = (
        ["Dreepy"] * 4 +
        ["Drakloak"] * 4 +
        ["Dragapult ex"] * 3 +
        ["Buddy-Buddy Poffin"] * 4 +
        ["Rare Candy"] * 3 +
        ["Ultra Ball"] * 4 +
        ["Super Rod"] * 2 +
        ["Counter Catcher"] * 1 +
        ["Professor's Research"] * 4 +
        ["Boss's Orders"] * 2 +
        ["Iono"] * 3 +
        ["Fire Energy"] * 8 +
        ["Psychic Energy"] * 8 +
        ["Jet Energy"] * 4 +
        ["Mist Energy"] * 6
    )

    # 1. Generate Verbose Game Log
    print("\n" + "="*80)
    print("  LOG 1: VERBOSE MATCH (Charizard ex/Pidgeot ex vs Dragapult ex)")
    print("="*80 + "\n")

    c1 = MCTSController(iteration_limit=200, simulation_depth=12)
    c2 = TurnBasedGreedyAI()
    p1 = Player("Red (MCTS - Charizard/Pidgeot)", deck_charizard_pidgeot, factory, controller=c1)
    p2 = Player("Blue (GreedyAI - Dragapult)", deck_dragapult, factory, controller=c2)

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
        deck1_names=deck_charizard_pidgeot,
        deck2_names=deck_dragapult,
        c1_kwargs={"iteration_limit": 250, "simulation_depth": 14},
        verbose_moves=False
    )

if __name__ == '__main__':
    generate_logs()

"""
Utility script to generate sample verification logs:
1. Verbose single game log (Full board states, actions, card plays, attacks, knockouts)
2. Batch simulation log (MCTS search telemetry, per-move logs, summary statistics)
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
    deck1 = ["Pikachu"] * 10 + ["Professor's Research"] * 4 + ["Lightning Energy"] * 10
    deck2 = ["Charmander"] * 10 + ["Charmeleon"] * 5 + ["Professor's Research"] * 4 + ["Fire Energy"] * 10

    # 1. Generate Verbose Game Log
    print("\n" + "="*80)
    print("  LOG 1: FULL VERBOSE MATCH (MCTSController vs TurnBasedGreedyAI)")
    print("="*80 + "\n")

    c1 = MCTSController(iteration_limit=100, simulation_depth=6)
    c2 = TurnBasedGreedyAI()
    p1 = Player("Ash (MCTS)", deck1, factory, controller=c1)
    p2 = Player("Gary (GreedyAI)", deck2, factory, controller=c2)

    game = GameState(p1, p2)
    winner, reason = game.run_game(verbose=True, max_turns=30)
    print(f"\n[FINAL RESULT] Winner: {winner.name if winner else 'None'} | Reason: {reason}\n")

    # 2. Generate Batch Simulation Telemetry Log
    print("\n" + "="*80)
    print("  LOG 2: BATCH SIMULATION WITH MCTS TELEMETRY (5 Games)")
    print("="*80 + "\n")

    run_simulation(
        controller1_type=MCTSController,
        controller2_type=TurnBasedGreedyAI,
        num_games=5,
        card_factory=factory,
        deck1_names=deck1,
        deck2_names=deck2,
        c1_kwargs={"iteration_limit": 150, "simulation_depth": 6},
        verbose_moves=False
    )

if __name__ == '__main__':
    generate_logs()

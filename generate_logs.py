"""
Utility script to run Phase 4 Tournament Matrix simulations and generate comprehensive meta reports.
"""

import sys
import io

game_engine = __import__("Game Engine")
CardFactory = game_engine.CardFactory
TournamentMatrixRunner = game_engine.TournamentMatrixRunner
STANDARD_ARCHETYPES = game_engine.STANDARD_ARCHETYPES

def generate_logs():
    factory = CardFactory('cards.json')

    print("\n" + "="*85)
    print("  PHASE 4: STANDARD FORMAT META TOURNAMENT MATRIX (8 ARCHETYPES)")
    print("="*85 + "\n")

    runner = TournamentMatrixRunner(
        archetypes=STANDARD_ARCHETYPES,
        card_factory=factory,
        games_per_matchup=2,
        c1_kwargs={"iteration_limit": 80, "simulation_depth": 6}
    )

    results = runner.run_round_robin(verbose=False)
    print(f"\n[PHASE 4 COMPLETE] Evaluated {len(results['ranked_decks'])} archetypes across {results['elapsed_seconds']:.2f} seconds.\n")

if __name__ == '__main__':
    generate_logs()

"""
Project Vulpix 2.0 - High-Performance HTTP & JSON REST API Server
Zero external dependencies (uses Python standard library http.server).
Exposes endpoints for:
- /api/archetypes (GET)
- /api/parse_deck (POST)
- /api/build_scratch_deck (POST)
- /api/run_gauntlet (POST)
- /api/optimize_anti_meta (POST)
- /api/generate_gameplan (POST)
- /api/coach_eval (POST)
Serves static frontend assets from ./web directory.
"""

import os
import sys
import json
import mimetypes
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from typing import Dict, Any

# Import live game modules
game_engine = __import__("Game Engine")
CardFactory = game_engine.CardFactory
STANDARD_ARCHETYPES = game_engine.STANDARD_ARCHETYPES

from deck_builder import DeckBuilder, DeckValidator, AntiMetaOptimizer
from meta_gauntlet import MetaGauntlet
from ai_coach import AICoach
from strategy_planner import StrategyPlanner

PORT = 8080
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

# Shared Engine Instances
FACTORY = CardFactory('cards.json')
BUILDER = DeckBuilder(FACTORY)
GAUNTLET = MetaGauntlet(FACTORY)
COACH = AICoach(FACTORY, coach_iterations=80, coach_depth=6)
PLANNER = StrategyPlanner(FACTORY)
OPTIMIZER = AntiMetaOptimizer(FACTORY)


class VulpixAPIHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def _send_json_response(self, data: Any, status_code: int = 200):
        response_bytes = json.dumps(data).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response_bytes)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(response_bytes)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        if self.path == '/api/archetypes':
            summary = {}
            for name, dlist in STANDARD_ARCHETYPES.items():
                summary[name] = {
                    "card_count": len(dlist),
                    "ptcgl_text": BUILDER.export_to_ptcgl(dlist)
                }
            self._send_json_response({"status": "success", "archetypes": summary})
            return

        # Fallback to serving static files from ./web
        if self.path == '/' or not os.path.exists(os.path.join(WEB_DIR, self.path.lstrip('/'))):
            self.path = '/index.html'
        super().do_GET()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        try:
            if self.path == '/api/parse_deck':
                self.handle_parse_deck(payload)
            elif self.path == '/api/build_scratch_deck':
                self.handle_build_scratch_deck(payload)
            elif self.path == '/api/target_counter_deck':
                self.handle_target_counter_deck(payload)
            elif self.path == '/api/generate_rogue_deck':
                self.handle_generate_rogue_deck(payload)
            elif self.path == '/api/run_gauntlet':
                self.handle_run_gauntlet(payload)
            elif self.path == '/api/optimize_anti_meta':
                self.handle_optimize_anti_meta(payload)
            elif self.path == '/api/generate_gameplan':
                self.handle_generate_gameplan(payload)
            elif self.path == '/api/coach_eval':
                self.handle_coach_eval(payload)
            else:
                self._send_json_response({"error": f"Unknown endpoint: {self.path}"}, 404)
        except Exception as e:
            self._send_json_response({"error": str(e)}, 500)

    def handle_parse_deck(self, payload: Dict):
        deck_text = payload.get("deck_text", "")
        try:
            decklist = BUILDER.import_from_ptcgl(deck_text)
        except Exception as e:
            self._send_json_response({"success": False, "error": f"Parse error: {str(e)}"}, 400)
            return

        is_valid, errors = DeckValidator.validate_deck(decklist, FACTORY)
        comp = PLANNER.analyze_deck_composition(decklist)

        # Categorize cards
        pokemon_count = sum(count for _, count, _ in comp["pokemon"])
        trainer_count = len(decklist) - pokemon_count - sum(1 for c in decklist if FACTORY.cards_by_name.get(c, {}).get("card_type") == "Energy")
        energy_count = sum(1 for c in decklist if FACTORY.cards_by_name.get(c, {}).get("card_type") == "Energy")

        self._send_json_response({
            "success": True,
            "is_valid": is_valid,
            "errors": errors,
            "total_cards": len(decklist),
            "decklist": decklist,
            "composition": {
                "pokemon": pokemon_count,
                "trainers": trainer_count,
                "energy": energy_count,
                "ace_specs": comp["ace_specs"],
                "pokemon_details": [(name, count) for name, count, _ in comp["pokemon"]],
                "draw_supporters": comp["draw_supporters"],
                "gust_cards": comp["gust_cards"]
            }
        })

    def handle_build_scratch_deck(self, payload: Dict):
        attacker = payload.get("attacker", "Ceruledge ex")
        ace_spec = payload.get("ace_spec", None)

        deck = BUILDER.generate_deck_from_scratch(attacker, preferred_ace_spec=ace_spec)
        ptcgl_text = BUILDER.export_to_ptcgl(deck)
        comp = PLANNER.analyze_deck_composition(deck)

        pokemon_count = sum(count for _, count, _ in comp["pokemon"])
        energy_count = sum(1 for c in deck if FACTORY.cards_by_name.get(c, {}).get("card_type") == "Energy")
        trainer_count = 60 - pokemon_count - energy_count

        self._send_json_response({
            "success": True,
            "attacker": attacker,
            "ace_spec": ace_spec or (comp["ace_specs"][0] if comp["ace_specs"] else "None"),
            "ptcgl_text": ptcgl_text,
            "decklist": deck,
            "composition": {
                "pokemon": pokemon_count,
                "trainers": trainer_count,
                "energy": energy_count,
                "ace_specs": comp["ace_specs"]
            }
        })

    def handle_target_counter_deck(self, payload: Dict):
        target_name = payload.get("target_name", "Charizard ex")
        target_text = payload.get("target_deck_text", "")

        if target_text.strip():
            try:
                target_deck = BUILDER.import_from_ptcgl(target_text)
                res = BUILDER.build_targeted_counter_deck(target_deck)
            except Exception:
                res = BUILDER.build_targeted_counter_deck(target_name)
        else:
            res = BUILDER.build_targeted_counter_deck(target_name)

        comp = PLANNER.analyze_deck_composition(res["counter_decklist"])
        pokemon_count = sum(count for _, count, _ in comp["pokemon"])
        energy_count = sum(1 for c in res["counter_decklist"] if FACTORY.cards_by_name.get(c, {}).get("card_type") == "Energy")
        trainer_count = 60 - pokemon_count - energy_count

        self._send_json_response({
            "success": True,
            "target_deck": target_name,
            "counter_deck_name": res["counter_deck_name"],
            "primary_attacker": res["primary_attacker"],
            "ace_spec": res["ace_spec"],
            "strategy_rationale": res["strategy_rationale"],
            "ptcgl_text": res["ptcgl_text"],
            "decklist": res["counter_decklist"],
            "composition": {
                "pokemon": pokemon_count,
                "trainers": trainer_count,
                "energy": energy_count,
                "ace_specs": comp["ace_specs"]
            }
        })

    def handle_generate_rogue_deck(self, payload: Dict):
        res = BUILDER.innovate_rogue_anti_meta_deck()
        comp = PLANNER.analyze_deck_composition(res["decklist"])

        pokemon_count = sum(count for _, count, _ in comp["pokemon"])
        energy_count = sum(1 for c in res["decklist"] if FACTORY.cards_by_name.get(c, {}).get("card_type") == "Energy")
        trainer_count = 60 - pokemon_count - energy_count

        self._send_json_response({
            "success": True,
            "rogue_name": res["rogue_name"],
            "primary_attacker": res["primary_attacker"],
            "ace_spec": res["ace_spec"],
            "archetype_concept": res["archetype_concept"],
            "why_it_wins": res["why_it_wins"],
            "ptcgl_text": res["ptcgl_text"],
            "decklist": res["decklist"],
            "composition": {
                "pokemon": pokemon_count,
                "trainers": trainer_count,
                "energy": energy_count,
                "ace_specs": comp["ace_specs"]
            }
        })

    def handle_run_gauntlet(self, payload: Dict):
        deck_text = payload.get("deck_text", "")
        archetype_name = payload.get("archetype_name", None)
        games_per_matchup = int(payload.get("games_per_matchup", 2))
        mcts_iterations = int(payload.get("mcts_iterations", 50))

        if deck_text.strip():
            deck = BUILDER.import_from_ptcgl(deck_text)
            deck_name = payload.get("deck_name", "Custom Deck")
        elif archetype_name and archetype_name in STANDARD_ARCHETYPES:
            deck = STANDARD_ARCHETYPES[archetype_name]
            deck_name = archetype_name
        else:
            deck = STANDARD_ARCHETYPES["Ceruledge ex"]
            deck_name = "Ceruledge ex"

        res = GAUNTLET.run_gauntlet(
            custom_deck=deck,
            custom_deck_name=deck_name,
            games_per_matchup=games_per_matchup,
            mcts_iterations=mcts_iterations,
            mcts_depth=5
        )

        # Build chart data series
        labels = list(res["matchup_breakdown"].keys())
        win_rates = [res["matchup_breakdown"][k]["win_rate"] for k in labels]
        prize_diffs = [res["matchup_breakdown"][k]["prize_diff"] for k in labels]
        classifications = [res["matchup_breakdown"][k]["classification"] for k in labels]

        self._send_json_response({
            "success": True,
            "report": res,
            "chart_data": {
                "labels": labels,
                "win_rates": win_rates,
                "prize_diffs": prize_diffs,
                "classifications": classifications
            }
        })

    def handle_optimize_anti_meta(self, payload: Dict):
        meta_dist = payload.get("meta_distribution", {
            "Charizard ex": 0.40,
            "Gardevoir ex": 0.30,
            "Ceruledge ex": 0.30
        })
        mcts_iterations = int(payload.get("mcts_iterations", 30))

        res = OPTIMIZER.optimize_anti_meta_deck(
            meta_distribution=meta_dist,
            sample_games_per_eval=2,
            mcts_iterations=mcts_iterations
        )
        ptcgl_text = BUILDER.export_to_ptcgl(res["best_decklist"])

        # Format candidate comparisons
        candidate_labels = [f"{c['archetype']} ({c['ace_spec']})" for c in res["all_evaluated"]]
        candidate_wrs = [round(c['weighted_expected_winrate'] * 100, 1) for c in res["all_evaluated"]]

        self._send_json_response({
            "success": True,
            "best_deck_name": res["best_deck_name"],
            "expected_winrate": res["expected_winrate"],
            "ptcgl_text": ptcgl_text,
            "decklist": res["best_decklist"],
            "matchup_breakdown": res["matchup_breakdown"],
            "candidates_chart": {
                "labels": candidate_labels,
                "win_rates": candidate_wrs
            }
        })

    def handle_generate_gameplan(self, payload: Dict):
        my_deck_text = payload.get("my_deck_text", "")
        my_deck_name = payload.get("my_deck_name", "My Deck")
        opp_archetype = payload.get("opp_archetype", "Charizard ex")

        if my_deck_text.strip():
            my_deck = BUILDER.import_from_ptcgl(my_deck_text)
        elif my_deck_name in STANDARD_ARCHETYPES:
            my_deck = STANDARD_ARCHETYPES[my_deck_name]
        else:
            my_deck = STANDARD_ARCHETYPES["Gardevoir ex"]
            my_deck_name = "Gardevoir ex"

        opp_deck = STANDARD_ARCHETYPES.get(opp_archetype, STANDARD_ARCHETYPES["Charizard ex"])

        plan = PLANNER.generate_gameplan(
            my_deck=my_deck,
            my_deck_name=my_deck_name,
            opp_deck=opp_deck,
            opp_deck_name=opp_archetype
        )

        self._send_json_response({
            "success": True,
            "gameplan": plan
        })

    def handle_coach_eval(self, payload: Dict):
        game = COACH.ingest_live_board_state(
            p1_active_name=payload.get("p1_active_name", "Gardevoir ex"),
            p1_active_hp=int(payload.get("p1_active_hp", 310)),
            p1_active_energy=payload.get("p1_active_energy", ["Psychic Energy", "Psychic Energy", "Psychic Energy"]),
            p1_bench_names=payload.get("p1_bench_names", ["Ralts"]),
            p1_hand_names=payload.get("p1_hand_names", ["Professor's Research", "Psychic Energy"]),
            p1_prizes_remaining=int(payload.get("p1_prizes_remaining", 4)),
            p2_active_name=payload.get("p2_active_name", "Charmander"),
            p2_active_hp=int(payload.get("p2_active_hp", 70)),
            p2_bench_names=payload.get("p2_bench_names", ["Charizard ex"]),
            p2_prizes_remaining=int(payload.get("p2_prizes_remaining", 6)),
            stadium_name=payload.get("stadium_name", None)
        )
        game.turn_number = int(payload.get("turn_number", 2))
        game.players[0].turns_taken = 1
        if game.players[0].active_pokemon:
            game.players[0].active_pokemon.turn_played = 0

        eval_res = COACH.evaluate_turn(game, top_n=3)

        self._send_json_response({
            "success": True,
            "current_eval": eval_res["current_eval"],
            "recommended_moves": eval_res["recommended_moves"],
            "tactical_advice": eval_res["tactical_advice"]
        })


def run_server(port: int = PORT):
    server_address = ('', port)
    httpd = ThreadingHTTPServer(server_address, VulpixAPIHandler)
    print(f"\n{'='*75}")
    print(f"  ⚡ VULPIX AI CHAMPIONSHIP SUITE RUNNING AT: http://localhost:{port}")
    print(f"{'='*75}\n")
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()

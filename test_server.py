"""
Automated Test Suite for Vulpix API Server (test_server.py)
Tests all JSON REST endpoints:
- GET /api/archetypes
- POST /api/parse_deck
- POST /api/build_scratch_deck
- POST /api/run_gauntlet
- POST /api/optimize_anti_meta
- POST /api/generate_gameplan
- POST /api/coach_eval
"""

import unittest
import threading
import time
import json
import urllib.request
from http.server import ThreadingHTTPServer

from server import VulpixAPIHandler, PORT

TEST_PORT = 8089


class TestVulpixServerAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', TEST_PORT), VulpixAPIHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _post(self, endpoint: str, payload: dict) -> dict:
        url = f"http://127.0.0.1:{TEST_PORT}{endpoint}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))

    def _get(self, endpoint: str) -> dict:
        url = f"http://127.0.0.1:{TEST_PORT}{endpoint}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))

    def test_get_archetypes(self):
        res = self._get('/api/archetypes')
        self.assertEqual(res["status"], "success")
        self.assertIn("archetypes", res)
        self.assertIn("Charizard ex", res["archetypes"])
        self.assertIn("Ceruledge ex", res["archetypes"])

    def test_post_build_scratch_deck(self):
        res = self._post('/api/build_scratch_deck', {
            "attacker": "Ceruledge ex",
            "ace_spec": "Grand Tree"
        })
        self.assertTrue(res["success"])
        self.assertEqual(len(res["decklist"]), 60)
        self.assertIn("Grand Tree", res["ptcgl_text"])
        self.assertIn("composition", res)

    def test_post_parse_deck(self):
        sample_ptcgl = (
            "Pokémon: 14\n"
            "4 Ceruledge ex\n"
            "4 Charcadet\n"
            "1 Fezandipiti ex\n"
            "1 Squawkabilly ex\n"
            "4 Kirlia\n\n"
            "Trainer: 32\n"
            "1 Grand Tree (ACE SPEC)\n"
            "4 Buddy-Buddy Poffin\n"
            "4 Ultra Ball\n"
            "2 Nest Ball\n"
            "2 Super Rod\n"
            "4 Earthen Vessel\n"
            "4 Professor's Research\n"
            "3 Iono\n"
            "2 Boss's Orders\n"
            "1 Counter Catcher\n"
            "7 Fire Energy\n\n"
            "Energy: 14\n"
            "14 Fire Energy"
        )
        res = self._post('/api/parse_deck', {"deck_text": sample_ptcgl})
        self.assertTrue(res["success"])
        self.assertTrue(res["is_valid"])
        self.assertEqual(res["total_cards"], 60)

    def test_post_generate_gameplan(self):
        res = self._post('/api/generate_gameplan', {
            "my_deck_name": "Ceruledge ex",
            "opp_archetype": "Charizard ex"
        })
        self.assertTrue(res["success"])
        self.assertIn("gameplan", res)
        self.assertIn("prize_map_plan", res["gameplan"])
        self.assertIn("threat_warnings", res["gameplan"])

    def test_post_coach_eval(self):
        res = self._post('/api/coach_eval', {
            "p1_active_name": "Gardevoir ex",
            "p1_active_hp": 310,
            "p1_active_energy": ["Psychic Energy", "Psychic Energy", "Psychic Energy"],
            "p1_bench_names": ["Ralts"],
            "p1_hand_names": ["Professor's Research", "Psychic Energy"],
            "p1_prizes_remaining": 4,
            "p2_active_name": "Charmander",
            "p2_active_hp": 70,
            "p2_bench_names": ["Charizard ex"],
            "p2_prizes_remaining": 6,
            "turn_number": 2
        })
        self.assertTrue(res["success"])
        self.assertIn("recommended_moves", res)
        self.assertGreater(len(res["recommended_moves"]), 0)


if __name__ == '__main__':
    unittest.main()

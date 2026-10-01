"""v4.0 player state, field route, observatory and methodology tests."""
import os
import sys
import tempfile
import threading
import unittest
import json
import struct
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import extract
import journal
import methodology
import observatory
import player_state
import route_planner
import make_db_sample
import woth_scanner


class V4(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_snap = woth_scanner.SNAP_DIR
        self.old_journal = journal.JOURNAL_DIR
        woth_scanner.SNAP_DIR = os.path.join(self.tmp.name, "snapshots")
        journal.JOURNAL_DIR = os.path.join(self.tmp.name, "journal")
        woth_scanner._cache.clear()

    def tearDown(self):
        woth_scanner.SNAP_DIR = self.old_snap
        journal.JOURNAL_DIR = self.old_journal
        woth_scanner._cache.clear()
        self.tmp.cleanup()

    def test_named_player_vector_is_exact(self):
        cfg = extract.load_config()
        props = {"Session": {"PlayerTransform": {"Translation": {
            "X": 100000.0, "Y": 200000.0, "Z": -80000.0}}}}
        got = player_state.inspect(props, b"", 0, "Nez Perce Valley", cfg)
        self.assertTrue(got["available"])
        self.assertEqual(got["confidence"], "exact")
        self.assertEqual(got["position"]["x"], 100000)
        self.assertIn("PlayerTransform/Translation", got["path"])

    def test_unnamed_or_outside_vector_is_not_a_map_pin(self):
        cfg = extract.load_config()
        unnamed = player_state.inspect({"Location": {"X": 1, "Y": 2, "Z": 3}},
                                       b"", 0, "Nez Perce Valley", cfg)
        self.assertFalse(unnamed["available"])
        outside = player_state.inspect(
            {"PlayerLocation": {"X": 9e6, "Y": 9e6, "Z": 0}},
            b"", 0, "Nez Perce Valley", cfg)
        self.assertFalse(outside["available"])
        self.assertEqual(outside["candidates"][0]["confidence"], "candidate")

    def test_database_without_named_transform_is_honestly_unavailable(self):
        p = os.path.join(self.tmp.name, "SaveData.sav")
        with open(p, "wb") as f:
            f.write(make_db_sample.build())
        res = woth_scanner.scan(p, snapshot=False)
        self.assertFalse(res["player_state"]["available"])
        self.assertEqual(res["player_state"]["confidence"], "unavailable")
        self.assertIsNone(res["player_state"]["position"])

    @staticmethod
    def _tail_record(x, y, z, aux=(346.4, -114.1, 0.0)):
        return (player_state._PLAYER_PREFIX + struct.pack("<3f", *aux)
                + struct.pack("<3f", x, y, z) + player_state._PLAYER_SUFFIX)

    def _inspect_tail(self, db_body, reserve="Nez Perce Valley"):
        cfg = extract.load_config()
        raw = bytes(db_body)
        original = player_state.woth_db.read_name_table
        player_state.woth_db.read_name_table = lambda _raw, _end: ({}, len(raw))
        try:
            return player_state.inspect({}, raw, 0, reserve, cfg, is_database=True)
        finally:
            player_state.woth_db.read_name_table = original

    def test_database_player_position_record_is_exact(self):
        body = b"\0" * 500 + self._tail_record(179608.625, -61410.89, -85963.67) + b"\0" * 200
        got = self._inspect_tail(body)
        self.assertTrue(got["available"])
        self.assertEqual(got["confidence"], "exact")
        self.assertAlmostEqual(got["position"]["x"], 179608.625, places=2)
        self.assertAlmostEqual(got["position"]["y"], -61410.89, places=2)
        self.assertIn("moved-save", got["verification"])

    def test_player_position_follows_the_player_not_the_vehicle(self):
        # Real saves: the map-hash trailer (vehicle) stays put while the player moves.
        first = self._inspect_tail(b"\0" * 100 + self._tail_record(202303.6, -29247.3, -79270.5))
        second = self._inspect_tail(b"\0" * 100 + self._tail_record(179608.6, -61410.9, -85963.7))
        self.assertNotEqual(first["position"]["x"], second["position"]["x"])

    def test_player_position_outside_map_or_ambiguous_is_unavailable(self):
        outside = self._inspect_tail(b"\0" * 50 + self._tail_record(9e6, 9e6, 0))
        self.assertFalse(outside["available"])
        ambiguous = self._inspect_tail(self._tail_record(1000, 2000, -80000)
                                       + b"\0" * 30 + self._tail_record(5000, 6000, -80000))
        self.assertFalse(ambiguous["available"])
        missing_suffix = self._inspect_tail(
            player_state._PLAYER_PREFIX + b"\0" * 12 + struct.pack("<3f", 1000, 2000, -80000) + b"\0" * 20)
        self.assertFalse(missing_suffix["available"])

    def test_route_uses_manual_start_and_spreads_herds(self):
        animals = [
            {"id": "a", "species": "Mule Deer", "species_zh": "騾鹿", "gender": "M",
             "fitness": .1, "age": 8, "age_stage": "Mature", "herd_index": 1,
             "herd_id": "h1", "habitat": "Forest", "habitat_zh": "森林",
             "area": "A", "x": 10000, "y": 0, "variant": ""},
            {"id": "b", "species": "Mule Deer", "species_zh": "騾鹿", "gender": "M",
             "fitness": .2, "age": 8, "age_stage": "Mature", "herd_index": 2,
             "herd_id": "h2", "habitat": "Forest", "habitat_zh": "森林",
             "area": "B", "x": 20000, "y": 0, "variant": ""},
            {"id": "c", "species": "Mule Deer", "species_zh": "騾鹿", "gender": "M",
             "fitness": .9, "age": 8, "age_stage": "Mature", "herd_index": 3,
             "herd_id": "h3", "habitat": "Forest", "habitat_zh": "森林",
             "area": "C", "x": 50000, "y": 0, "variant": ""},
        ]
        herds = [
            {"index": 1, "id": "h1", "x": 10000, "y": 0, "territory_id": None},
            {"index": 2, "id": "h2", "x": 20000, "y": 0, "territory_id": None},
            {"index": 3, "id": "h3", "x": 50000, "y": 0, "territory_id": None},
        ]
        got = route_planner.plan(animals, herds, "Nez Perce Valley",
                                 species="Mule Deer", habitat="Forest", limit=5,
                                 start_x=0, start_y=0)
        self.assertEqual([s["id"] for s in got["stops"]], ["a", "b"])
        self.assertEqual(got["start"]["kind"], "user coordinate")
        self.assertAlmostEqual(got["straight_line_km"], .2, places=2)
        self.assertIn("不含道路", got["caveat"])

    @staticmethod
    def _animal(aid, age, fit, habitat="Forest", herd=1):
        return {"key": f"id:{aid}", "id": str(aid), "species": "Mule Deer",
                "species_zh": "騾鹿", "gender": "M", "fitness": fit,
                "habitat": habitat, "herd_index": herd, "herd_id": f"h{herd}",
                "age": age, "age_stage": "Mature", "age_limit_status": None,
                "variant": "", "variant_zh": "", "area": "A",
                "x": herd * 1000.0, "y": 0.0, "z": 0.0, "dead": False}

    def test_observatory_year_turn_scorecard_and_cohort(self):
        old_animals = [self._animal(1, 7, .2, herd=1),
                       self._animal(2, 7, .8, herd=2)]
        new_animals = [self._animal(2, 8, .8, herd=2),
                       self._animal(3, 1, .9, herd=3)]
        states = [
            {"sha1": "a", "mtime": 100, "reserve": "Nez Perce Valley",
             "animals": old_animals},
            {"sha1": "b", "mtime": 200, "reserve": "Nez Perce Valley",
             "animals": new_animals},
        ]
        got = observatory.analyse(states)
        self.assertEqual((got["states"], got["transition_count"], got["year_turns"]), (2, 1, 1))
        self.assertEqual((got["present"], got["gone"]), (2, 1))
        self.assertEqual(got["transitions"][0]["removed"], 1)
        self.assertEqual(got["transitions"][0]["spawned"], 1)
        card = got["scorecards"][0]
        self.assertEqual(card["confidence"], "one-year")
        self.assertEqual(card["removed_below_rate"], 1.0)
        gone = next(x for x in got["cohorts"] if x["id"] == "1")
        self.assertEqual(gone["status"], "gone")

    def test_methodology_declares_limits(self):
        got = methodology.report()
        self.assertIn("cause of disappearance", got["never_infer"])
        self.assertIn("planning-aid", {x["class"] for x in got["metrics"]})

    def test_v4_http_endpoints(self):
        p = os.path.join(self.tmp.name, "SaveData.sav")
        with open(p, "wb") as f:
            f.write(make_db_sample.build())
        server = ThreadingHTTPServer(("127.0.0.1", 0), woth_scanner.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            def get(path):
                with urllib.request.urlopen(base + path, timeout=10) as r:
                    return json.load(r)
            qp = urllib.parse.quote(p)
            self.assertEqual(get("/api/methodology")["version"], 1)
            initial = get(f"/api/scan?path={qp}")
            self.assertFalse(initial["player_state"]["available"])
            obs = get(f"/api/observatory?path={qp}")
            self.assertEqual(obs["states"], 1)
            route = get(f"/api/route?path={qp}&start=manual&x=0&y=0&limit=3")
            self.assertEqual(route["source_sha1"], woth_scanner.scan(p, snapshot=False)["sha1"])
            self.assertIn("caveat", route)
            fixed_mtime = os.path.getmtime(p)
            replacement = make_db_sample.build(year=1)
            self.assertEqual(len(replacement), os.path.getsize(p))
            with open(p, "wb") as f:
                f.write(replacement)
            os.utime(p, (fixed_mtime, fixed_mtime))
            live = get(f"/api/live?path={qp}&since={initial['mtime']}"
                       f"&sha1={initial['sha1']}")
            self.assertTrue(live["changed"])
            self.assertNotEqual(live["sha1"], initial["sha1"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
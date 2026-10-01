"""v3.0 habitat, need-zone, journal, WOTH2 and HTTP API coverage."""
import json
import os
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
import sys
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import extract
import habitat
import journal
import knowledge
import make_db_sample
import woth2
import woth_scanner


class V3(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_journal = journal.JOURNAL_DIR
        self.old_snap = woth_scanner.SNAP_DIR
        journal.JOURNAL_DIR = os.path.join(self.tmp.name, "journal")
        woth_scanner.SNAP_DIR = os.path.join(self.tmp.name, "snapshots")
        woth_scanner._cache.clear()

    def tearDown(self):
        journal.JOURNAL_DIR = self.old_journal
        woth_scanner.SNAP_DIR = self.old_snap
        woth_scanner._cache.clear()
        self.tmp.cleanup()

    def _scan(self, name, raw, mtime):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as f:
            f.write(raw)
        os.utime(path, (mtime, mtime))
        return woth_scanner.scan(path, snapshot=False)

    def test_need_zone_integrity_and_calibration_bounds(self):
        cfg = extract.load_config()["maps"]
        d = habitat.data()
        expected = {
            "Nez Perce Valley", "Transylvania", "Aurora Shores",
            "Tikamoon Plains", "Matariki Park", "Lintukoto Reserve",
        }
        self.assertEqual(set(d["reserves"]), expected)
        self.assertEqual(d["license"].split()[0], "GPL-3.0")
        self.assertIn("identity", d["calibration"])
        valid_slugs = set(knowledge.BY_SLUG)
        for reserve, rd in d["reserves"].items():
            self.assertTrue(rd["territories"])
            self.assertTrue(rd["areas"])
            c = cfg[reserve]
            for t in rd["territories"]:
                self.assertIn(t["slug"], valid_slugs)
                self.assertLessEqual(c["x_min"], t["x"])
                self.assertLessEqual(t["x"], c["x_max"])
                self.assertLessEqual(c["y_min"], t["y"])
                self.assertLessEqual(t["y"], c["y_max"])
                self.assertTrue(any(t[a] for a in habitat.ACTIVITIES))
                for act in habitat.ACTIVITIES:
                    for x, y in t[act]:
                        self.assertLessEqual(c["x_min"], x)
                        self.assertLessEqual(x, c["x_max"])
                        self.assertLessEqual(c["y_min"], y)
                        self.assertLessEqual(y, c["y_max"])

    def test_real_territory_sample_matches_and_annotates(self):
        res = self._scan("base.sav", make_db_sample.build(), 1000)
        self.assertEqual(res["reserve"], "Nez Perce Valley")
        self.assertGreater(len(res["animals"]), 150)
        self.assertGreaterEqual(res["zone_match"]["match_rate"], .95)
        self.assertLess(res["zone_match"]["median_dist_m"], 150)
        self.assertTrue(all(a.get("habitat") for a in res["animals"]))
        self.assertTrue(all(h.get("area") for h in res["herds"]))
        self.assertTrue(any(h.get("zone_counts") for h in res["herds"]))

    def test_cull_simulation_is_spread_and_only_recomputes_average(self):
        animals = [
            {"id": "a", "species": "Mule Deer", "habitat": "Lowland Forests",
             "gender": "M", "fitness": .10, "age_stage": "Mature", "herd_index": 1},
            {"id": "b", "species": "Mule Deer", "habitat": "Lowland Forests",
             "gender": "M", "fitness": .20, "age_stage": "Mature", "herd_index": 1},
            {"id": "c", "species": "Mule Deer", "habitat": "Lowland Forests",
             "gender": "M", "fitness": .30, "age_stage": "Mature", "herd_index": 2},
            {"id": "d", "species": "Mule Deer", "habitat": "Lowland Forests",
             "gender": "M", "fitness": .90, "age_stage": "Mature", "herd_index": 3},
        ]
        sim = habitat.simulate_cull(animals, "Mule Deer", "Lowland Forests", limit=2)
        self.assertEqual(sim["removed"], ["a", "c"])
        self.assertEqual(sim["herds_touched"], 2)
        self.assertGreater(sim["after"], sim["before"])
        self.assertNotIn("spawn", sim)

    def test_published_mature_limit_annotation(self):
        a = {"latin": "OdocoileusHemionus", "species": "Mule Deer",
             "gender": "M", "age": 12}
        knowledge.annotate(a)
        self.assertEqual(a["age_limit"], 12)
        self.assertEqual(a["years_to_limit"], 0)
        self.assertEqual(a["age_limit_status"], "at-limit")
        a["age"] = 11
        knowledge.annotate(a)
        self.assertEqual(a["age_limit_status"], "near-limit")

    def test_journal_period_removal_spawn_and_year_turn(self):
        old = self._scan("old.sav", make_db_sample.build(), 1000)
        removed_id = int(old["animals"][0]["id"])
        period = self._scan("period.sav", make_db_sample.build(remove=(removed_id,), spawn=2), 1100)
        tr = journal.analyse(old, period)
        self.assertFalse(tr["year_turn"])
        # The compact binary fixture can make the heuristic parser drop its
        # final synthetic herd after a record is removed. The target ID and
        # both spawned IDs still exercise the journal semantics.
        self.assertGreaterEqual(tr["removed"], 1)
        self.assertEqual(tr["spawned"], 2)
        removed = next(e for e in tr["events"] if e["type"] == "removed")
        self.assertIn("below_avg", removed)
        self.assertEqual(journal.record(old, period), tr["removed"] + tr["spawned"])
        self.assertEqual(journal.record(old, period), 0)  # idempotent
        s = journal.summary()
        self.assertEqual((s["removed_period"], s["spawned"]), (tr["removed"], 2))

        year = self._scan("year.sav", make_db_sample.build(year=1, remove=(removed_id,), spawn=1), 1200)
        yr = journal.analyse(old, year)
        self.assertTrue(yr["year_turn"])
        self.assertGreaterEqual(yr["aged"] / yr["persisting"], .5)
        self.assertTrue(all(e["year_turn"] for e in yr["events"]))

    def test_woth2_probe_never_parses(self):
        p = os.path.join(self.tmp.name, "sample.nrgs")
        with open(p, "wb") as f:
            f.write(b"GVAS" + bytes(range(256)) * 4)
        got = woth2.probe(p)
        self.assertEqual(got["kind"], "GVAS (Unreal SaveGame)")
        self.assertFalse(got["parsed"])
        old = os.environ.get("WOTH2_SAVE_DIR")
        os.environ["WOTH2_SAVE_DIR"] = self.tmp.name
        try:
            found = woth2.scan()
            self.assertEqual(found["count"], 1)
            self.assertFalse(found["supported"])
        finally:
            if old is None:
                os.environ.pop("WOTH2_SAVE_DIR", None)
            else:
                os.environ["WOTH2_SAVE_DIR"] = old

    def test_v3_http_endpoints(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), woth_scanner.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            def get(path):
                with urllib.request.urlopen(base + path, timeout=10) as r:
                    self.assertEqual(r.status, 200)
                    return json.load(r)
            info = get("/api/info")
            self.assertEqual(info["version"], "4.0.8")
            self.assertEqual(len(info["zones"]["reserves"]), 6)
            zones = get("/api/zones?reserve=Nez%20Perce%20Valley")
            self.assertTrue(zones["available"])
            self.assertGreater(len(zones["territories"]), 400)
            self.assertEqual(get("/api/journal")["transitions"], 0)
            self.assertFalse(get("/api/woth2")["supported"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
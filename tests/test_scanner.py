import hashlib, os, struct, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import make_sample, gvas, extract, journal, woth_scanner, woth_db, knowledge

class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        # Keep snapshots and the journal out of the real snapshots/ and journal/ folders.
        self.old_dirs = (woth_scanner.SNAP_DIR, journal.JOURNAL_DIR)
        woth_scanner.SNAP_DIR = os.path.join(self.d, "snapshots")
        journal.JOURNAL_DIR = os.path.join(self.d, "journal")
        self.raw = make_sample.build()
        self.p = os.path.join(self.d, "SaveData.sav"); open(self.p, "wb").write(self.raw)

    def tearDown(self):
        woth_scanner.SNAP_DIR, journal.JOURNAL_DIR = self.old_dirs

    def test_raw_and_compressed_equal(self):
        a = woth_scanner.scan(self.p, snapshot=False)
        c = os.path.join(self.d, "c.sav"); open(c, "wb").write(make_sample.ue_compress(self.raw))
        b = woth_scanner.scan(c, snapshot=False)
        self.assertEqual(len(a["animals"]), len(b["animals"]))
        self.assertGreater(len(a["animals"]), 50)
        self.assertEqual({s["species"] for s in a["summary"]},
                         {"Red Deer", "Wild Boar", "Roe Deer", "Gray Wolf", "Whitetail Deer"})
        self.assertEqual(b["compression"], "ue-chunks(zlib)")

    def test_embedded_and_maps(self):
        a = woth_scanner.scan(self.p, snapshot=False)
        self.assertIn("Nez Perce Valley", a["maps"]); self.assertIn("Transylvania", a["maps"])
        x = a["animals"][0]
        for k in ("gender", "weight", "score", "fitness", "x", "id"):
            self.assertIsNotNone(x[k])
        self.assertIn(x["knowledge_confidence"], ("verified-table", "proxy", "unknown"))

    def test_unknown_property_skipped(self):
        g = gvas.load(self.p)
        self.assertEqual(g.props["Mystery"]["_raw"], "WeirdUnknownProperty")
        self.assertEqual(g.props["Currency"]["_map"][0]["value"], 12345)

    def test_corrupt_does_not_crash(self):
        bad = bytearray(self.raw); i = bad.find(b"TrophyScore") + 40; bad[i:i + 4] = b"\xff\xff\xff\x7f"
        try:
            gvas.Gvas(bytes(bad))
        except gvas.GvasError:
            pass

    def test_read_only(self):
        h = hashlib.sha1(open(self.p, "rb").read()).hexdigest()
        woth_scanner.scan(self.p)
        self.assertEqual(h, hashlib.sha1(open(self.p, "rb").read()).hexdigest())

    def test_diff_kill_spawn(self):
        a = woth_scanner.scan(self.p, snapshot=False)
        p2 = os.path.join(self.d, "s2.sav"); open(p2, "wb").write(make_sample.build(kill=2, spawn=3))
        b = woth_scanner.scan(p2, snapshot=False)
        d = extract.diff(a["animals"], b["animals"])
        self.assertEqual((len(d["added"]), len(d["removed"])), (3, 2))

    def test_species_normalize(self):
        self.assertEqual(extract.normalize_species("/Game/Animals/BP_RedDeer_C")[0], "Red Deer")
        self.assertEqual(extract.normalize_species("EAnimalSpecies::WhitetailDeer")[1], "白尾鹿")
        self.assertEqual(extract.normalize_species("BlueWildebeest")[0], "Blue Wildebeest")
        self.assertEqual(woth_db.species_of("MeleagrisGallopavoMerriami")[2], "Elkcrest Island")

    def test_offline_knowledge_and_life_stages(self):
        self.assertEqual(len(knowledge.ANIMALS), 60)
        reserves = set()
        for info in knowledge.ANIMALS:
            self.assertEqual(set(info["stages"]), {"Young", "Adult", "Mature"})
            self.assertEqual(len(info["trophy_ranges"]), 5)
            self.assertTrue(info["schedule"])
            self.assertTrue(info["reserves"])
            self.assertTrue(info["name_zh"])
            reserves.update(info["reserves"])
            self.assertTrue({e["activity"] for e in info["schedule"]} <= {"Sleep", "Feed", "Drink"})
            for stage in info["stages"].values():
                for sex in ("M", "F"):
                    self.assertLessEqual(stage[sex]["age"][0], stage[sex]["age"][1])
        a = {"latin": "OdocoileusHemionus", "species": "Mule Deer", "gender": "M", "age": 7}
        knowledge.annotate(a)
        self.assertEqual((a["age_stage"], a["stage_weight_range"], a["knowledge_confidence"]),
                         ("Mature", "140 - 200 kg", "verified-table"))
        turkey = {"latin": "MeleagrisGallopavo", "species": "Eastern Wild Turkey", "gender": "M", "age": 4}
        knowledge.annotate(turkey)
        self.assertEqual((turkey["age_stage"], turkey["knowledge_confidence"]), ("Mature", "proxy"))
        mule, _ = knowledge.lookup("OdocoileusHemionus", "Mule Deer")
        self.assertEqual(knowledge.activity_at(mule, 0)["activity"], "Drink")
        self.assertEqual(knowledge.activity_at(mule, 3)["activity"], "Sleep")
        self.assertEqual(knowledge.activity_at(mule, 8)["activity"], "Feed")
        self.assertEqual(knowledge.next_activity(mule, 3, "Drink"), 8)
        self.assertEqual(knowledge.next_activity(mule, 0, "Drink"), 0)
        self.assertEqual(reserves, {
            "Nez Perce Valley", "Transylvania", "Aurora Shores",
            "Tikamoon Plains", "Matariki Park", "Lintukoto Reserve",
            "Elkcrest Island",
        })
        self.assertEqual(mule["reserves"], ["Nez Perce Valley"])
        pheasant = knowledge.BY_SLUG["pheasant"]
        self.assertIn("Elkcrest Island", pheasant["reserves"])
        self.assertEqual(len(knowledge.catalog()["animals"]), 60)
        self.assertEqual([knowledge.fitness_band(x) for x in
                          (0, .1999, .20, .3999, .40, .5999, .60, .7999, .80, 1)],
                         ["very-low", "very-low", "low", "low", "moderate",
                          "moderate", "high", "high", "very-high", "very-high"])
        self.assertIsNone(knowledge.fitness_band(None))
        self.assertIn("fitness_band", extract.to_csv([a]).splitlines()[0])

    def test_diff_tracks_persistent_animal_changes(self):
        animals = woth_scanner.scan(self.p, snapshot=False)["animals"]
        a = [dict(animals[0]), dict(animals[1])]
        a[0]["age"] = 2
        b = [dict(x) for x in a]
        b[0]["age"] += 1
        b[0]["herd_id"] = "new-herd"
        b[0]["x"] += 20000
        d = extract.diff(a, b)
        self.assertEqual(len(d["changed"]), 1)
        self.assertEqual(d["changed"][0]["age_delta"], 1)
        self.assertTrue(d["changed"][0]["herd_changed"])
        self.assertGreaterEqual(d["changed"][0]["moved_m"], 100)

    def test_all_seven_map_backgrounds(self):
        maps = {k: v for k, v in extract.load_config()["maps"].items() if not k.startswith("_")}
        self.assertEqual(set(maps), {
            "Nez Perce Valley", "Transylvania", "Aurora Shores",
            "Tikamoon Plains", "Matariki Park", "Lintukoto Reserve",
            "Elkcrest Island",
        })
        for cfg in maps.values():
            image = os.path.join(os.path.dirname(HERE), "web", cfg["image"])
            self.assertTrue(os.path.isfile(image))
            # A valid WebP is a RIFF container whose declared size matches the file. (A text
            # round-trip once damaged every map image while this test still passed.)
            with open(image, "rb") as f:
                blob = f.read()
            self.assertEqual((blob[:4], blob[8:12]), (b"RIFF", b"WEBP"), image)
            self.assertEqual(struct.unpack("<I", blob[4:8])[0] + 8, len(blob), image)
            self.assertLess(cfg["x_min"], cfg["x_max"])
            self.assertLess(cfg["y_min"], cfg["y_max"])

    def test_vault_compact_latest_state(self):
        cfg = extract.load_config()
        res = woth_scanner.scan(self.p, snapshot=False)
        res["db_info"] = {"reserve": "Nez Perce Valley"}
        res["mtime"] = 100
        old = woth_scanner.vault_entry(res, "snapshot", "old.sav", cfg)
        self.assertNotIn("animals", old)
        self.assertEqual(old["total"], len(res["animals"]))
        self.assertTrue(old["species"])
        newer = dict(old, time=200, source="current", path="now.sav")
        maps = [k for k in cfg["maps"] if not k.startswith("_")]
        vault = woth_scanner.merge_vault_entries([old, newer], maps)
        self.assertEqual((vault["coverage"], vault["total_reserves"]), (1, 7))
        nez = next(x for x in vault["reserves"] if x["reserve"] == "Nez Perce Valley")
        self.assertEqual((nez["source"], nez["path"]), ("current", "now.sav"))
        self.assertFalse(next(x for x in vault["reserves"] if x["reserve"] == "Transylvania")["available"])

    def test_snapshot_dedup_retention_and_history(self):
        old_dir = woth_scanner.SNAP_DIR
        woth_scanner.SNAP_DIR = os.path.join(self.d, "snapshots")
        try:
            first = woth_scanner.take_snapshot(self.p, self.raw, 1000, 3)
            self.assertRegex(os.path.basename(first), r"^\d{8}-\d{6}-[0-9a-f]{10}\.sav$")
            self.assertEqual(first, woth_scanner.take_snapshot(self.p, self.raw, 1001, 3))
            for i in range(1, 5):
                raw = make_sample.build(spawn=i)
                woth_scanner.take_snapshot(self.p, raw, 1001 + i, 3)
            self.assertEqual(len(woth_scanner.list_snapshots(self.p)), 3)
            h = woth_scanner.history(self.p, extract.load_config())
            self.assertTrue(h["health"]["read_only"])
            self.assertTrue(h["points"])
            self.assertIn(h["health"]["status"], ("ok", "warn", "error"))
            current = woth_scanner.scan(self.p, snapshot=False)
            previous = woth_scanner.history_point(current)
            previous["sha1"] = "different"
            previous["total"] = 1
            for s in previous["species"]:
                s["total"] = 1
            changed = woth_scanner.health_report(current, extract.load_config(), previous)
            self.assertEqual(next(c for c in changed["checks"] if c["key"] == "change")["status"], "warn")
        finally:
            woth_scanner.SNAP_DIR = old_dir

if __name__ == "__main__":
    unittest.main(verbosity=2)

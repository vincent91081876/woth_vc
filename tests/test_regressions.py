"""Regression tests for bugs found while auditing v4.0.6.

Every test states the symptom it guards against. They run against temporary
snapshot/journal folders, so they never touch the user's real data.
"""
import glob
import io
import os
import struct
import sys
import tempfile
import unittest
import warnings
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import gvas
import journal
import make_db_sample
import make_sample
import observatory
import route_planner
import woth_scanner


class Isolated(unittest.TestCase):
    """Fresh temporary snapshots/ + journal/ folders and an empty scan cache for every test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = (woth_scanner.SNAP_DIR, journal.JOURNAL_DIR, os.getcwd())
        woth_scanner.SNAP_DIR = os.path.join(self.tmp.name, "snapshots")
        journal.JOURNAL_DIR = os.path.join(self.tmp.name, "journal")
        woth_scanner._cache.clear()

    def tearDown(self):
        woth_scanner.SNAP_DIR, journal.JOURNAL_DIR, cwd = self.old
        os.chdir(cwd)
        woth_scanner._cache.clear()
        self.tmp.cleanup()

    def write(self, name, raw, mtime=1000):
        path = os.path.join(self.tmp.name, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(raw)
        os.utime(path, (mtime, mtime))
        return path


class BundledBinaryTests(unittest.TestCase):
    def test_vendored_wheel_is_a_valid_zip_archive(self):
        """A text round-trip once corrupted vendor/*.whl, so run_windows.bat could not install pyooz from it."""
        wheels = glob.glob(os.path.join(ROOT, "vendor", "*.whl"))
        self.assertTrue(wheels, "no vendored wheel found")
        for whl in wheels:
            with zipfile.ZipFile(whl) as z:  # BadZipFile if the file is damaged
                self.assertIsNone(z.testzip(), whl)


class SnapshotTests(Isolated):
    def test_snapshot_is_taken_even_if_a_no_snapshot_scan_ran_first(self):
        """The Reserve Vault reads every save with snapshot=False on start-up; the normal scan that
        follows used to get that cached result back and silently skip the automatic backup."""
        p = self.write("SaveData.sav", make_sample.build())
        woth_scanner.scan(p, snapshot=False)
        res = woth_scanner.scan(p)
        self.assertIn("snapshot", res)
        self.assertEqual(len(woth_scanner.list_snapshots(p)), 1)

    def test_journal_is_updated_even_if_a_no_snapshot_scan_ran_first(self):
        p = self.write("SaveData.sav", make_db_sample.build(), mtime=1000)
        woth_scanner.scan(p)                                             # first backup = "before"
        self.write("SaveData.sav", make_db_sample.build(spawn=2), mtime=1100)  # the game saved again
        woth_scanner.scan(p, snapshot=False)                             # Reserve Vault read
        res = woth_scanner.scan(p)
        self.assertGreater(res.get("journal_new_events", 0), 0)
        self.assertEqual(len(woth_scanner.list_snapshots(p)), 2)

    def test_scanning_a_stored_snapshot_by_relative_path_makes_no_new_snapshot(self):
        p = self.write("SaveData.sav", make_sample.build())
        stored = woth_scanner.scan(p)["snapshot"]
        before = sorted(os.listdir(woth_scanner.SNAP_DIR))
        os.chdir(self.tmp.name)
        woth_scanner.scan(os.path.relpath(stored, self.tmp.name))
        self.assertEqual(sorted(os.listdir(woth_scanner.SNAP_DIR)), before)

    def test_save_in_a_sibling_folder_with_a_similar_name_is_still_backed_up(self):
        """'snapshots_old/' merely starts with the text 'snapshots' - it is not the snapshot folder."""
        p = self.write(os.path.join("snapshots_old", "SaveData.sav"), make_sample.build())
        self.assertIn("snapshot", woth_scanner.scan(p))


class SuiteIsolationTests(Isolated):
    def test_other_suites_do_not_write_into_the_apps_data_folders(self):
        """test_scanner / test_v4 used to leave fake snapshots and a fake year-turn in the real
        snapshots/ and journal/ folders. Here those folders are empty stand-ins that must stay empty."""
        import test_scanner
        import test_v4
        suite = unittest.TestSuite([test_scanner.T("test_read_only"),
                                    test_v4.V4("test_v4_http_endpoints")])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)  # those older tests leave file handles to the GC
            result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
        self.assertFalse(os.path.exists(woth_scanner.SNAP_DIR), "a test wrote into the snapshots folder")
        self.assertFalse(os.path.exists(journal.JOURNAL_DIR), "a test wrote into the journal folder")


class WatchlistTests(unittest.TestCase):
    def test_animals_at_their_age_limit_come_before_those_one_year_away(self):
        """years_to_limit == 0.0 ('at-limit') was treated as 'missing' and sorted last (then cut off)."""
        import test_v4
        at = dict(test_v4.V4._animal(1, 9, .5), years_to_limit=0.0, age_limit_status="at-limit")
        near = dict(test_v4.V4._animal(2, 9, .5), years_to_limit=1.0, age_limit_status="near-limit")
        got = observatory.analyse([{"sha1": "a", "mtime": 100, "reserve": "Nez Perce Valley",
                                    "animals": [near, at]}])
        self.assertEqual([a["id"] for a in got["watchlist"]], ["1", "2"])


class RoutePlannerTests(unittest.TestCase):
    def test_explicit_ids_mixing_a_male_and_a_female_do_not_crash(self):
        """A female has fitness None; sorting None against a male's float raised TypeError."""
        male = {"id": "m", "species": "Mule Deer", "species_zh": "騾鹿", "gender": "M",
                "fitness": .3, "age": 8, "age_stage": "Mature", "herd_index": 1, "herd_id": "h1",
                "habitat": "Forest", "habitat_zh": "森林", "area": "A", "x": 1000, "y": 0, "variant": ""}
        female = dict(male, id="f", gender="F", fitness=None, herd_index=2, herd_id="h2", x=2000)
        herds = [{"index": 1, "id": "h1", "x": 1000, "y": 0, "territory_id": None},
                 {"index": 2, "id": "h2", "x": 2000, "y": 0, "territory_id": None}]
        got = route_planner.plan([male, female], herds, "Nez Perce Valley", ids=["m", "f"],
                                 start_x=0, start_y=0)
        self.assertEqual({s["id"] for s in got["stops"]}, {"m", "f"})


class OodleHeaderTests(unittest.TestCase):
    @staticmethod
    def _chunk(comp, uncomp, payload=b"\x8c" * 16):
        """One UE compressed chunk holding a single (fake, non-zlib => Oodle) block."""
        return (struct.pack("<II", gvas.PACKAGE_FILE_TAG, 0x22222222) + struct.pack("<q", 131072)
                + struct.pack("<qq", comp, uncomp) + struct.pack("<qq", comp, uncomp) + payload)

    def test_absurd_block_sizes_are_rejected_before_the_native_decoder_runs(self):
        """A damaged header once made the C++ Oodle decoder try to allocate ~400 GB and kill the whole
        server process (std::bad_alloc -> abort) instead of showing an error for that one file."""
        real, calls = gvas.oodle_decompress, []
        gvas.oodle_decompress = lambda buf, n: calls.append(n) or b""
        try:
            for comp, uncomp in ((16, 2 ** 40), (2 ** 40, 131072)):
                with self.subTest(comp=comp, uncomp=uncomp):
                    with self.assertRaises(gvas.GvasError):
                        gvas._ue_chunks(self._chunk(comp, uncomp))
            self.assertEqual(calls, [], "native decoder was called with a file-controlled size")
        finally:
            gvas.oodle_decompress = real


if __name__ == "__main__":
    unittest.main(verbosity=2)

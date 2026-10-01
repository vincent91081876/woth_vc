"""Tests for web/measure.js (scale bar + distance helpers). Needs `node`; skipped when absent."""
import json, os, shutil, subprocess, unittest

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
NODE = shutil.which("node")


class AnimalListDistanceTests(unittest.TestCase):
    def test_animal_list_has_current_distance_column(self):
        with open(os.path.join(WEB, "index.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertIn("['現在距離我','distance_m'", page)
        self.assertIn("distance_m:me&&Number.isFinite(a.x)&&Number.isFinite(a.y)?WothMeasure.dist(me,a):null", page)
        self.assertIn("table('#lt',LCOLS,rows", page)


def run_js(expr):
    code = f"const M=require({json.dumps(os.path.join(WEB, 'measure.js'))});console.log(JSON.stringify({expr}))"
    return json.loads(subprocess.check_output([NODE, "-e", code], text=True))


@unittest.skipUnless(NODE, "node not installed")
class MeasureTests(unittest.TestCase):
    def test_distance_is_metres_from_centimetres(self):
        self.assertAlmostEqual(run_js("M.dist({x:0,y:0},{x:30000,y:40000})"), 500.0)

    def test_path_length_sums_segments(self):
        self.assertAlmostEqual(run_js("M.pathLength([{x:0,y:0},{x:30000,y:40000},{x:30000,y:0}])"), 900.0)
        self.assertEqual(run_js("M.pathLength([{x:1,y:1}])"), 0)

    def test_format(self):
        self.assertEqual(run_js("[M.fmtDist(3.14),M.fmtDist(250.4),M.fmtDist(1234),M.fmtDist(23456)]"),
                         ["3.1 m", "250 m", "1.23 km", "23.5 km"])

    def test_nice_scale_never_exceeds_max_width_and_is_1_2_5(self):
        for ppm in (0.0005, 0.003, 0.05, 0.4, 1.7, 12):
            ns = run_js(f"M.niceScale({ppm},190)")
            self.assertLessEqual(ns["px"], 190 + 1e-9)
            self.assertAlmostEqual(ns["px"], ns["m"] * ppm, places=6)
            self.assertIn(ns["d"], (1, 2, 5))
            self.assertIn(ns["parts"], (4, 5))
        self.assertIsNone(run_js("M.niceScale(0,190)"))

    def test_screen_direction(self):
        self.assertIn("右上", run_js("M.screenDir(1,-1)"))
        self.assertIn("下", run_js("M.screenDir(0,3)"))
        self.assertEqual(run_js("M.screenDir(0,0)"), "")

    def test_zoom_keeps_the_point_under_the_cursor_fixed(self):
        # The map draws at  screen = pad + u*scale + offset  (pad = fixed 30 px margin). Zooming about the
        # cursor must not fold that margin into the offset, or the map drifts away from the cursor.
        js = ("(()=>{const pad=30,base=0.5,mx=300,my=200;let v={s:1,ox:12,oy:-7};"
              "const ux=(mx-pad-v.ox)/(base*v.s),uy=(my-pad-v.oy)/(base*v.s),out=[];"
              "for(const f of [1.25,1.25,0.8,1.25]){v=M.zoomAt(v,mx,my,f,pad);"
              "out.push([pad+ux*base*v.s+v.ox,pad+uy*base*v.s+v.oy,v.s])}return out})()")
        got = run_js(js)
        for sx, sy, _ in got:
            self.assertAlmostEqual(sx, 300, places=6)
            self.assertAlmostEqual(sy, 200, places=6)
        self.assertAlmostEqual(got[-1][2], 1.25 * 1.25 * 0.8 * 1.25, places=9)


if __name__ == "__main__":
    unittest.main()

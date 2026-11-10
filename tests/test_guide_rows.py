"""One continuous edge loop per authored guide (guide_rows), and the engine control behind it."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
import numpy as np
import trimesh
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'engine/targets/zbrush/clone'), str(ROOT / 'engine/targets/zbrush/experiments/python')]
import guide_rows
from crease_rows import find_row
from measure_geometry import read_obj
FIXTURES = ROOT / 'tests/fixtures'


def quad_grid(n):
    vertices = np.array([[float(x), float(y), 0.] for y in range(n + 1) for x in range(n + 1)])
    faces = np.array([[y * (n + 1) + x, y * (n + 1) + x + 1, (y + 1) * (n + 1) + x + 1, (y + 1) * (n + 1) + x] for y in range(n) for x in range(n)])
    return vertices, faces


class Turns(unittest.TestCase):
    def setUp(self):
        self.v, self.q = quad_grid(6)
        self.owners = guide_rows.edge_faces(self.q)

    def test_straight_loop_has_no_turn(self):
        self.assertEqual(guide_rows.turns([14, 15, 16, 17, 18], self.owners), [])

    def test_stepping_to_the_next_loop_is_a_turn_at_each_step(self):
        self.assertEqual(guide_rows.turns([14, 15, 16, 23, 24, 25], self.owners), [2, 3])

    def test_valence_three_vertex_cannot_be_passed_straight(self):
        # Three quads around vertex 0: every pair of its edges borders one face.
        faces = [[0, 1, 2, 3], [0, 3, 4, 5], [0, 5, 6, 1]]
        owners = guide_rows.edge_faces(faces)
        self.assertEqual(guide_rows.turns([1, 0, 3], owners), [1])
        self.assertEqual(guide_rows.turns([1, 0, 5], owners), [1])

    def test_triangles_count_as_faces(self):
        owners = guide_rows.edge_faces([[0, 1, 2], [0, 2, 3, 4]])
        self.assertEqual(guide_rows.turns([1, 2, 0], owners), [1])
        self.assertEqual(guide_rows.turns([1, 2, 3], owners), [])

    def test_closed_loop_checks_its_seam(self):
        ring = [8, 9, 10, 17, 24, 23, 22, 15, 8]       # a square ring on the grid: four corners turn
        self.assertEqual(guide_rows.turns(ring, self.owners, closed=True), [0, 2, 4, 6])


class Measure(unittest.TestCase):
    def setUp(self):
        self.v, self.q = quad_grid(6)

    def test_guide_on_a_grid_line_passes(self):
        guide = np.array([[.4, 3., 0], [5.6, 3., 0]])
        item = guide_rows.measure(self.v, self.q, [guide], 1.)['guides'][0]
        self.assertTrue(item['passed'], item)
        self.assertEqual(item['values']['turns'], 0)
        self.assertEqual(item['vertices'], [22, 23, 24, 25, 26])   # ends may stop short inside the one-face end allowance
        self.assertTrue(item['continuousLoop'])

    def test_diagonal_guide_has_no_loop_and_reports_the_staircase(self):
        guide = np.array([[1., 1., 0], [5., 5., 0]])
        item = guide_rows.measure(self.v, self.q, [guide], 1.)['guides'][0]
        self.assertFalse(item['passed'])
        self.assertIn('turns', item['failures'])
        self.assertGreaterEqual(item['values']['turns'], 6)
        self.assertFalse(item['continuousLoop'])

    def test_staircase_pulled_onto_the_guide_still_fails(self):
        # The defect of job 483afe83 in miniature: vertices dragged onto the curve do not make a loop.
        guide = np.array([[1., 1., 0], [5., 5., 0]])
        path = find_row(self.v, np.asarray(sorted(guide_rows.edge_faces(self.q))), guide, False, 1.)
        moved = self.v.copy()
        for vertex in path:
            t = (self.v[vertex, 0] + self.v[vertex, 1]) / 2
            moved[vertex] = [t, t, 0]
        item = guide_rows.measure(moved, self.q, [guide], 1.)['guides'][0]
        self.assertEqual(item['failures'], ['turns'])
        self.assertLess(item['valuesInFaces']['rowMax'], .05)

    def test_loop_beside_the_guide_is_charged_its_gap(self):
        guide = np.array([[.4, 3.4, 0], [5.6, 3.4, 0]])
        item = guide_rows.measure(self.v, self.q, [guide], 1.)['guides'][0]
        self.assertEqual(item['values']['turns'], 0)
        self.assertIn('rowP95', item['failures'])
        self.assertAlmostEqual(item['valuesInFaces']['rowP95'], .4, places=6)

    def test_guide_corner_excuses_one_turn_there(self):
        # An L-shaped guide: the loop along it changes family at the corner, as a registered guide does.
        v, q = quad_grid(10)
        guide = np.array([[.4, 2., 0], [8., 2., 0], [8., 9.6, 0]])
        self.assertEqual(len(guide_rows.corners(guide, False, 1.)), 1)
        item = guide_rows.measure(v, q, [guide], 1.)['guides'][0]
        self.assertTrue(item['passed'], item)
        self.assertEqual((item['values']['turns'], item['cornerTurns'], item['guideCorners']), (0, 1, 1))
        self.assertIn(30, item['vertices'])                    # the grid vertex at the corner (8, 2)

    def test_corner_excuses_no_turn_elsewhere(self):
        v, q = quad_grid(10)
        guide = np.array([[.4, 2., 0], [8., 2., 0], [8., 9.6, 0]])
        staircase = [23, 24, 35, 36]                           # (1,2) (2,2) (2,3) (3,3): two turns, far from the corner
        owners = guide_rows.edge_faces(q)
        self.assertEqual(guide_rows.turns(staircase, owners), [1, 2])
        self.assertEqual(guide_rows.excused(staircase, [1, 2], v, guide, False, 1.), [])
        at_corner = [29, 30, 41]                               # (7,2) (8,2) (8,3): the one turn at the corner
        self.assertEqual(guide_rows.excused(at_corner, guide_rows.turns(at_corner, owners), v, guide, False, 1.), [1])

    def test_smooth_arc_has_no_corner(self):
        angles = np.linspace(0, np.pi / 2, 60)
        arc = np.c_[6 * np.cos(angles), 6 * np.sin(angles), np.zeros(60)]     # radius 6 faces
        self.assertEqual(guide_rows.corners(arc, False, 1.), [])
        tight = np.c_[np.cos(angles), np.sin(angles), np.zeros(60)]           # radius 1 face: tighter than a loop can bend
        self.assertEqual(len(guide_rows.corners(np.r_[[[1., -3, 0]], tight, [[-3., 1, 0]]], False, 1.)), 1)

    def test_find_loop_never_turns(self):
        guide = np.array([[1., 1.2, 0], [5., 2.8, 0]])
        path = guide_rows.find_loop(self.v, self.q, guide, 1.)
        self.assertTrue(path)
        self.assertEqual(guide_rows.turns(path, guide_rows.edge_faces(self.q)), [])


class IslandSixGuide(unittest.TestCase):
    """The reported case: island 6, request 200, the guide of job 483afe83 (tests/fixtures/guide_rows/README.md)."""

    @classmethod
    def setUpClass(cls):
        source, triangles = read_obj(FIXTURES / 'crease_rows/island6-source.obj')
        cls.h = float(np.sqrt(trimesh.Trimesh(np.asarray(source, float), np.asarray(triangles, int), process=False).area / 200))
        cls.curves = [np.asarray(c, float) for c in json.loads((FIXTURES / 'island6-guide-483afe83.json').read_text())['curves']]

    def measure(self, name):
        points, faces = read_obj(FIXTURES / 'guide_rows' / name)
        return guide_rows.measure(points, faces, self.curves, self.h)['guides'][0]

    def test_accepted_zigzag_chain_now_fails_on_its_turns_alone(self):
        item = self.measure('island6-200-zigzag-209.obj')
        self.assertFalse(item['passed'])
        self.assertEqual(item['failures'], ['turns'])
        self.assertEqual(item['values']['turns'], 8)
        self.assertEqual(item['pathVertices'], 15)
        self.assertEqual((item['guideCorners'], item['cornerTurns']), (0, 0))   # a smooth arc: nothing is excused

    def test_native_strength_100_loop_passes(self):
        item = self.measure('island6-200-native-guide-532.obj')
        self.assertTrue(item['passed'], item)
        self.assertEqual(item['values']['turns'], 0)
        self.assertLess(item['valuesInFaces']['rowP95'], .2)

    def test_native_mesh_without_the_guide_fails(self):
        points, faces = read_obj(FIXTURES / 'crease_rows/island6-200-native-374.obj')
        self.assertFalse(guide_rows.measure(points, faces, self.curves, self.h)['guides'][0]['passed'])


class EngineRegistration(unittest.TestCase):
    """The packaged layout engine puts one edge loop on a registered guide (flat control, slanted to the boundary)."""

    def test_slanted_guide_on_a_flat_patch_gets_a_loop(self):
        from guided_layout import runtime
        from registered_features import constrained
        from quad_connectivity import dissolve_double_edges
        n = 16
        vertices = np.array([[x / n, y / n, 0.] for y in range(n + 1) for x in range(n + 1)])
        triangles = np.array([t for y in range(n) for x in range(n) for a in [y * (n + 1) + x] for t in ([a, a + 1, a + n + 2], [a, a + n + 2, a + n + 1])])
        guide = np.array([[.08, .31, 0], [.93, .64, 0]])
        executable, environment, engine = runtime()
        self.assertIn('constrained-edges', engine.get('capabilities', []))
        with tempfile.TemporaryDirectory() as folder:
            prepared = constrained(vertices, triangles, [guide], np.empty((0, 2), int), np.empty((0, 2), int), folder)
            layout = Path(folder) / 'layout.obj'
            done = subprocess.run([str(executable), '-i', str(prepared['source']), '-o', str(layout), '-f', '150', '-seed', '0', '-boundary',
                                   '-constrained-edges', str(prepared['edges'])], env=environment, capture_output=True, text=True, timeout=120,
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.assertEqual(done.returncode, 0, done.stdout[-2000:])
            self.assertIn('registered', done.stdout)
            points, quads = read_obj(layout)
            points, quads, _ = dissolve_double_edges(np.asarray(points, float), np.asarray(quads, int))
        item = guide_rows.measure(points, np.asarray(quads, int), [guide], float(np.sqrt(1 / 150)))['guides'][0]
        self.assertTrue(item['passed'], item)
        self.assertEqual(item['values']['turns'], 0)
        self.assertLess(item['valuesInFaces']['rowMax'], .25)   # unfitted layout: the loop is already on the guide


if __name__ == '__main__':
    unittest.main()

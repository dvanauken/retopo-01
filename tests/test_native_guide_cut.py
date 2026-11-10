"""The recovered ZRemesher guide cut (native_guide_cut) and the constrained-edge list built from it."""
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
import trimesh
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'engine/targets/zbrush/clone'), str(ROOT / 'engine/targets/zbrush/experiments/python')]
from native_guide_cut import cut, SNAP_SQUARED, CLASSIFY, _line_edge, _inward
from registered_features import constrained, GUIDE_MODE, CREASE_ROW_MODE, CREASE_DIRECTION_MODE


def grid(n, size=1.):
    vertices = np.array([[size * x / n, size * y / n, 0.] for y in range(n + 1) for x in range(n + 1)])
    faces = []
    for y in range(n):
        for x in range(n):
            a = y * (n + 1) + x
            faces += [[a, a + 1, a + n + 2], [a, a + n + 2, a + n + 1]]
    return vertices, np.array(faces)


def edge_set(faces):
    return {tuple(sorted((int(a), int(b)))) for face in faces for a, b in zip(face, np.roll(face, -1))}


class SquareCut(unittest.TestCase):
    def setUp(self):
        self.v = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float)
        self.f = np.array([[0, 1, 2], [0, 2, 3]])

    def test_two_face_points_cross_the_shared_edge_once(self):
        curve = np.array([[.7, .2, 0], [.3, .6, 0]])
        points, faces, report = cut(self.v, self.f, [curve])
        chain = report['chains']['0']
        self.assertEqual(len(chain), 3)
        np.testing.assert_allclose(points[chain[0]], curve[0], atol=1e-12)
        np.testing.assert_allclose(points[chain[1]], [.45, .45, 0], atol=1e-12)   # on the diagonal, on the straight line between the samples
        np.testing.assert_allclose(points[chain[2]], curve[1], atol=1e-12)
        self.assertTrue(all(tuple(sorted(e)) in edge_set(faces) for e in zip(chain[:-1], chain[1:])))
        self.assertEqual(report['spans'][0]['direct'], 1)
        self.assertEqual(report['relocatedVertices'], [])
        np.testing.assert_allclose(trimesh.Trimesh(points, faces, process=False).area, 1.)

    def test_samples_inside_one_face_are_not_kept(self):
        # 0x10c0a0: a span between two points of one face appends nothing; only the two ends become vertices.
        curve = np.array([[.5, .1, 0], [.6, .2, 0], [.7, .25, 0], [.8, .3, 0]])
        points, faces, report = cut(self.v, self.f, [curve])
        self.assertEqual(len(report['chains']['0']), 2)
        self.assertEqual(len(points), 6)

    def test_crossing_near_a_vertex_moves_that_vertex(self):
        # 0x255b10: a cut point within 5 % of an edge end becomes that source vertex, and the vertex moves to the cut point.
        curve = np.array([[.3, .01, 0], [.01, .3, 0]])      # crosses the diagonal at t = 0.155 from vertex 0: no relocation
        self.assertEqual(cut(self.v, self.f, [curve])[2]['relocatedVertices'], [])
        curve = np.array([[.06, .005, 0], [.005, .06, 0]])  # crosses at (0.0325, 0.0325): t = 0.0325 < 0.05
        points, faces, report = cut(self.v, self.f, [curve])
        self.assertEqual([row['vertex'] for row in report['relocatedVertices']], [0])
        np.testing.assert_allclose(points[0], [.0325, .0325, 0], atol=1e-12)
        self.assertEqual(report['chains']['0'][1], 0)
        self.assertEqual(len(points), 6)                    # two free ends, no new point on the diagonal
        # The moved corner left both free ends outside their triangles; 0x253d80 puts them back just inside.
        self.assertEqual(report['inwardRepairs'], 2)
        result = trimesh.Trimesh(points, faces, process=False)
        self.assertGreater(result.area_faces.min(), 0)
        self.assertTrue(result.is_winding_consistent)

    def test_sample_at_a_vertex_snaps_to_it(self):
        diagonal = np.sqrt(2.)
        near = np.sqrt(SNAP_SQUARED) * diagonal * .5
        curve = np.array([[1 - near, near * .1, 0], [.4, .7, 0]])
        points, faces, report = cut(self.v, self.f, [curve])
        self.assertEqual(report['attachments'][0]['onVertices'], 1)
        self.assertEqual(report['chains']['0'][0], 1)

    def test_sample_on_an_edge_is_classified_to_it(self):
        offset = CLASSIFY * np.sqrt(2.) * .25                # inside the classifier tolerance of the diagonal
        curve = np.array([[.5 + offset, .5 - offset, 0], [.2, .7, 0]])
        points, faces, report = cut(self.v, self.f, [curve])
        self.assertEqual(report['attachments'][0]['onEdges'], 1)
        np.testing.assert_allclose(points[report['chains']['0'][0]], [.5, .5, 0], atol=1e-9)

    def test_crease_identity_survives_a_crossing_guide(self):
        curve = np.array([[.8, .3, 0], [.3, .8, 0]])
        points, faces, report = cut(self.v, self.f, [curve], source_paths=[[0, 2]])
        pieces = np.asarray(report['guideEdges']['1'])
        self.assertEqual(len(pieces), 2)
        crossing = set(pieces[0]) & set(pieces[1])
        self.assertEqual(len(crossing), 1)
        np.testing.assert_allclose(points[next(iter(crossing))], [.55, .55, 0], atol=1e-12)
        self.assertEqual(report['chains']['1'][0] + report['chains']['1'][-1], 2)

    def test_guide_off_the_surface_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'does not lie on the source surface'):
            cut(self.v, self.f, [np.array([[.2, .2, 5.], [.8, .8, 5.]])])

    def test_nonedge_source_path_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'not a source mesh edge'):
            cut(self.v, self.f, [], source_paths=[[1, 3]])


class WalkedCut(unittest.TestCase):
    def test_sparse_samples_are_walked_crossing_by_crossing(self):
        v, f = grid(8)
        curve = np.array([[.07, .13, 0], [.91, .52, 0]])      # two samples, many faces apart: 0x10d2e0
        points, faces, report = cut(v, f, [curve])
        chain = report['chains']['0']
        self.assertEqual(report['spans'][0]['walked'], 1)
        present = edge_set(faces)
        self.assertTrue(all(tuple(sorted(e)) in present for e in zip(chain[:-1], chain[1:])))
        direction = (curve[1] - curve[0]) / np.linalg.norm(curve[1] - curve[0])
        offsets = points[chain] - curve[0]
        along = offsets @ direction
        # Relocated source vertices sit on the line too; nothing strays from it, and the walk only moves forward.
        self.assertLess(np.abs(offsets - along[:, None] * direction).max(), 1e-9)
        self.assertTrue(np.all(np.diff(along) > 0))
        result = trimesh.Trimesh(points, faces, process=False)
        self.assertTrue(result.is_winding_consistent)
        self.assertEqual(result.euler_number, 1)
        self.assertGreater(result.area_faces.min(), 0)

    def test_curved_surface_walk_stays_on_the_surface(self):
        sphere = trimesh.creation.icosphere(subdivisions=3)
        v, f = np.asarray(sphere.vertices), np.asarray(sphere.faces)
        angles = np.linspace(.2, 1.3, 9)
        curve = np.array([[np.cos(a) * np.cos(.3), np.sin(a) * np.cos(.3), np.sin(.3)] for a in angles])
        points, faces, report = cut(v, f, [curve])
        chain = report['chains']['0']
        result = trimesh.Trimesh(points, faces, process=False)
        self.assertTrue(result.is_watertight and result.is_winding_consistent)
        distance = trimesh.proximity.closest_point(sphere, points[chain])[1]
        self.assertLess(distance.max(), 1e-9)
        self.assertLess(report['guideSampleMaxDistance'], .02)
        self.assertEqual(report['spans'][0]['flushed'], 0)

    def test_line_edge_parameters(self):
        distance, s, t, parallel = _line_edge(np.zeros(3), np.array([1., 0, 0]), np.array([2., -1, 0]), np.array([2., 3, 0]))
        self.assertFalse(parallel)
        self.assertAlmostEqual(s, 2.)
        self.assertAlmostEqual(t, .25)
        self.assertTrue(_line_edge(np.zeros(3), np.array([1., 0, 0]), np.array([0., 1, 0]), np.array([5., 1, 0]))[3])


    def test_inward_repair(self):
        triangle = np.array([[0., 0], [1, 0], [0, 1]])
        np.testing.assert_array_equal(_inward([.2, .2], triangle), [.2, .2])
        repaired = _inward([.5, -.3], triangle)                  # below the first edge: projected to (0.5, 0), stepped toward (0, 1)
        np.testing.assert_allclose(repaired, [.5 - .0005, .001])


class ConstrainedList(unittest.TestCase):
    def test_guides_first_then_creases_with_modes(self):
        v, f = grid(4)
        curve = np.array([[.1, .35, 0], [.9, .6, 0]])
        hard, soft = np.array([[0, 6], [6, 12]]), np.array([[3, 4]])   # a diagonal the guide crosses, and a boundary edge
        with tempfile.TemporaryDirectory() as folder:
            prepared = constrained(v, f, [curve], hard, soft, folder)
            lines = Path(prepared['edges']).read_text().split('\n')
            rows = [tuple(map(int, line.split())) for line in lines[1:] if line]
            self.assertEqual(int(lines[0]), len(rows))
            chain = prepared['chains'][0]
            self.assertEqual((GUIDE_MODE, CREASE_ROW_MODE, CREASE_DIRECTION_MODE), (2, 3, 1))
            guide = [(a, b, 2) for a, b in zip(chain[:-1], chain[1:])]
            self.assertEqual(rows[:len(guide)], guide)                 # guide edges first, registered (native mode 2), in path order
            creases = rows[len(guide):]
            self.assertEqual(sorted({mode for *_, mode in creases}), [1, 3])    # creases: direction only, or preserved without the lattice line
            self.assertEqual([row for row in creases if row[2] == 1], [(3, 4, 1)])
            present = edge_set(prepared['faces'])
            self.assertTrue(all(tuple(sorted(row[:2])) in present for row in rows))
            # The cut split one preserved crease edge; both halves are listed with its mode.
            self.assertGreater(len([row for row in creases if row[2] == 3]), 2)
            self.assertEqual(prepared['summary']['guideEdges'], len(guide))

    def test_no_guides_keeps_the_source(self):
        v, f = grid(2)
        with tempfile.TemporaryDirectory() as folder:
            prepared = constrained(v, f, [], np.array([[0, 4]]), np.empty((0, 2), int), folder)
            np.testing.assert_array_equal(prepared['points'], v)
            self.assertEqual(Path(prepared['edges']).read_text(), '1\n0 4 3\n')
            with self.assertRaisesRegex(ValueError, 'No constrained edges'):
                constrained(v, f, [], np.empty((0, 2), int), np.empty((0, 2), int), Path(folder) / 'none')


if __name__ == '__main__':
    unittest.main()

from pathlib import Path
import json
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from feature_rows import graph_paths, prepare, measure, rank_key, _straight_surface_connection


def grid(nx=5, ny=3, z=0.):
    vertices = np.array([[float(x), float(y - 1), z] for y in range(ny) for x in range(nx)])
    quads = np.array([[y * nx + x, y * nx + x + 1, (y + 1) * nx + x + 1, (y + 1) * nx + x]
                      for y in range(ny - 1) for x in range(nx - 1)])
    triangles = np.r_[quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]]
    return vertices, quads, triangles


class FeatureRows(unittest.TestCase):
    def test_paths_split_junctions_preserve_loops_and_ignore_input_order(self):
        edges = np.array([[0, 1], [1, 2], [1, 3], [4, 5], [5, 6], [6, 4]])
        expected = [[0, 1], [1, 2], [1, 3], [4, 5, 6, 4]]
        self.assertEqual(graph_paths(edges), expected)
        self.assertEqual(graph_paths(edges[::-1, ::-1]), expected)

    def test_aligned_row_ranks_above_nearby_zigzag(self):
        v, q, f = grid()
        edges = [[i, i + 1] for i in range(5, 9)]
        context = prepare(v, f, edges, [], 1., max_distance=.5, sample_spacing=.125)
        aligned = measure(context, v, q)
        moved = v.copy()
        moved[5:10, 1] += np.array([0., .2, -.2, .2, 0.])
        zigzag = measure(context, moved, q)
        self.assertEqual(aligned['realizedRows'], 1)
        self.assertEqual(zigzag['realizedRows'], 1, zigzag['paths'])
        self.assertAlmostEqual(aligned['tangentError'], 0.)
        self.assertGreater(zigzag['tangentError'], aligned['tangentError'])
        self.assertLess(rank_key(aligned, target=8, face_count=8),
                        rank_key(zigzag, target=8, face_count=8))
        json.dumps(zigzag, allow_nan=False)

    def test_boundary_degree_three_is_not_an_interior_pole(self):
        v, q, f = grid()
        context = prepare(v, f, [], [], 1., max_distance=.5, sample_spacing=.125)
        report = measure(context, v, q)
        self.assertEqual(report['topology']['interiorPoleCount'], 0)
        self.assertEqual(report['topology']['boundaryValence'], {'2': 4, '3': 8})
        self.assertEqual(report['topology']['interiorAllQuadValence'], {'4': 3})

    def test_nearby_disconnected_edges_do_not_realize_a_loop(self):
        v, q, f = grid(3, 3)
        loop = [0, 1, 2, 5, 8, 7, 6, 3, 0]
        edges = list(zip(loop[:-1], loop[1:]))
        context = prepare(v, f, edges, [], 1., max_distance=.5, sample_spacing=.125)
        exact = measure(context, v, q)
        self.assertEqual(exact['missingLoops'], 0, exact['paths'])
        output, triangles = [], []
        for a, b in edges:
            center = (v[a] + v[b]) / 2
            # Each segment is present geometrically, but the vertex identities
            # belong to eight disconnected triangle components.
            third = center + (np.array([1., 0., 0.]) - center) * .1
            start = len(output)
            output.extend([v[a], v[b], third])
            triangles.append([start, start + 1, start + 2])
        disconnected = measure(context, np.array(output), np.array(triangles))
        self.assertEqual(disconnected['missingLoops'], 1)
        self.assertLess(rank_key(exact), rank_key(disconnected))

    def test_close_opposite_fold_sheet_cannot_supply_the_feature_row(self):
        lower, q, f = grid()
        upper = lower + [0., 0., .05]
        source = np.r_[lower, upper]
        n = len(lower)
        bridge = np.array([[4, 9, 9 + n, 4 + n], [9, 14, 14 + n, 9 + n]])
        triangles = np.r_[f, f + n, bridge[:, [0, 1, 2]], bridge[:, [0, 2, 3]]]
        edges = [[i + n, i + n + 1] for i in range(5, 9)]
        context = prepare(source, triangles, edges, [], 1., max_distance=.5, sample_spacing=.125)
        wrong = measure(context, lower, q)
        right = measure(context, upper, q)
        self.assertEqual(wrong['unrealizedRows'], 1)
        self.assertEqual(right['realizedRows'], 1, right['paths'])

    def test_distinct_parallel_loops_sharing_one_output_cycle_are_reported(self):
        v, q, f = grid(3, 3)
        outer = [0, 1, 2, 5, 8, 7, 6, 3, 0]
        points = v[outer]
        inner = (points - [1., 0., 0.]) * .9 + [1., 0., 0.]
        context = prepare(v, f, [], [], 1., max_distance=.5, sample_spacing=.125,
                          paths=[dict(id='outer', kind='crease', vertices=outer, closed=True),
                                 dict(id='inner', kind='crease', points=inner, closed=True)])
        report = measure(context, v, q, paths=[dict(feature='outer', vertices=outer),
                                              dict(feature='inner', vertices=outer)])
        self.assertEqual(report['collapsedLoopPairs'], 1)
        self.assertEqual(report['collapsedLoops'], [['outer', 'inner']])

    def test_engine_provenance_is_validated_not_trusted_as_a_path(self):
        v, q, f = grid()
        context = prepare(v, f, [[i, i + 1] for i in range(5, 9)], [], 1.,
                          max_distance=.5, sample_spacing=.125)
        report = measure(context, v, q, paths=[dict(feature='crease:0', vertices=[5, 7, 9])])
        self.assertEqual(report['unrealizedRows'], 1)
        self.assertIn('output path is disconnected', report['paths'][0]['errors'])


    def test_tiny_closed_loop_has_a_defined_tangent_window(self):
        v, q, f = grid(3, 3)
        v *= .1
        loop = [0, 1, 2, 5, 8, 7, 6, 3, 0]
        context = prepare(v, f, list(zip(loop[:-1], loop[1:])), [], 1.,
                          max_distance=.5, sample_spacing=.125)
        report = measure(context, v, q)
        self.assertTrue(report['passed'], report['paths'])
        self.assertLess(report['tangentError'], 1.)

    def test_small_cycle_at_one_feature_location_does_not_fake_a_full_loop(self):
        v, q, f = grid(3, 3)
        loop = [0, 1, 2, 5, 8, 7, 6, 3, 0]
        context = prepare(v, f, list(zip(loop[:-1], loop[1:])), [], 10.,
                          max_distance=5., sample_spacing=.125)
        tiny = np.array([[0., -1., 0.], [.01, -.99, 0.], [.01, -1., 0.]])
        report = measure(context, tiny, [[0, 1, 2]],
                         paths=[dict(feature='crease:0', vertices=[0, 1, 2, 0])])
        self.assertFalse(report['passed'])
        self.assertIn('row does not wind once around feature', report['paths'][0]['errors'])


    def test_parallel_open_features_cannot_share_an_output_row(self):
        v, q, f = grid()
        context = prepare(v, f, [], [], 1., max_distance=.5, sample_spacing=.125,
                          paths=[dict(id='first', points=v[5:10] + [0., .1, 0.]),
                                 dict(id='second', points=v[5:10] - [0., .1, 0.])])
        report = measure(context, v, q, paths=[dict(feature='first', vertices=list(range(5, 10))),
                                              dict(feature='second', vertices=list(range(5, 10)))])
        self.assertEqual(report['mergedPathPairs'], 1)
        self.assertEqual(report['sharedRowEdges'], 4)
        self.assertFalse(report['passed'])

    def test_reversed_engine_paths_keep_junction_correspondence(self):
        v, q, f = grid()
        context = prepare(v, f, [], [], 1., max_distance=.5, sample_spacing=.125,
                          paths=[dict(id='left', vertices=[5, 6, 7]),
                                 dict(id='right', vertices=[7, 8, 9])])
        report = measure(context, v, q, paths=[dict(feature='left', vertices=[5, 6, 7]),
                                              dict(feature='right', vertices=[9, 8, 7])])
        self.assertTrue(report['passed'], report)
        self.assertEqual(report['junctionMismatches'], 0)
        self.assertEqual(report['mergedPathPairs'], 0)
        self.assertEqual(report['paths'][1]['vertices'], [7, 8, 9])

    def test_explicit_coincident_source_support_can_share_output_edges(self):
        v, q, f = grid()
        context = prepare(v, f, [], [], 1., max_distance=.5, sample_spacing=.125,
                          paths=[dict(id='crease', vertices=[5, 6, 7]),
                                 dict(id='guide', vertices=[6, 7, 8])])
        report = measure(context, v, q, paths=[dict(feature='crease', vertices=[5, 6, 7]),
                                              dict(feature='guide', vertices=[6, 7, 8])])
        self.assertTrue(report['passed'], report)
        self.assertEqual(report['mergedPathPairs'], 0)


    def test_coarse_planar_source_does_not_require_detour_through_source_vertices(self):
        v, q, f = grid(9, 9)
        v = (v + [0., 1., 0.]) / 8.
        guide = np.array([[0., .5, 0.], [1., .5, 0.]])
        h = np.sqrt(1. / 200.)
        context = prepare(v, f, [], [guide], h, max_distance=.5 * h, sample_spacing=.125 * h)
        output = np.array([[x, y, 0.] for y in (.494, .6) for x in np.linspace(0., 1., 15)])
        faces = np.array([[i, i + 1, i + 16, i + 15] for i in range(14)])
        report = measure(context, output, faces, paths=[dict(feature='guide:0', vertices=list(range(15)))])
        self.assertTrue(report['passed'], report['paths'])
        self.assertLessEqual(report['paths'][0]['sourceSheetDistanceMax'], .5 * h)
        self.assertAlmostEqual(report['paths'][0]['distanceMax'], .006)

    def test_flat_shortcut_does_not_cross_a_hole(self):
        v, q, f = grid(4, 4)
        q = np.delete(q, 4, axis=0)
        f = np.r_[q[:, [0, 1, 2]], q[:, [0, 2, 3]]]
        context = prepare(v, f, [], [], 1., max_distance=1., sample_spacing=.125)
        start = np.array([.5, .5, 0.])
        target = np.array([2.5, .5, 0.])
        owner = int(context['mesh'].nearest.on_surface([start])[2][0])
        self.assertFalse(_straight_surface_connection(context, start, owner, target))
        target = np.array([.5, 1.5, 0.])
        self.assertTrue(_straight_surface_connection(context, start, owner, target))


    def test_rotated_closed_row_preserves_its_exact_shared_junction(self):
        v, q, f = grid(5, 5)
        loop = [6, 7, 8, 13, 18, 17, 16, 11, 6]
        tail = [5, 6]
        context = prepare(v, f, [], [], 1., max_distance=.5, sample_spacing=.125,
                          paths=[dict(id='tail', vertices=tail),
                                 dict(id='loop', vertices=loop, closed=True)])
        report = measure(context, v, q, paths=[
            dict(feature='tail', vertices=tail),
            dict(feature='loop', vertices=[13, 18, 17, 16, 11, 6, 7, 8, 13], closed=True)])
        self.assertTrue(report['passed'], report)
        self.assertEqual(report['junctionMismatches'], 0)
        self.assertEqual(report['junctionMatches'], [dict(sourceVertex=6, outputVertices=[6], status='matched')])
        # Geometrically coincident but different vertex identities do not form
        # a source junction. No proximity tolerance may silently weld them.
        split = np.r_[v, v[[6]]]
        split_faces = q.copy()
        split_faces[(split_faces == 6) & (np.arange(len(q))[:, None] == 0)] = len(v)
        wrong = measure(context, split, split_faces, paths=[
            dict(feature='tail', vertices=[5, len(v)]),
            dict(feature='loop', vertices=[13, 18, 17, 16, 11, 6, 7, 8, 13], closed=True)])
        self.assertEqual(wrong['junctionMismatches'], 1)
        self.assertFalse(wrong['passed'])

    def test_count_only_breaks_an_equal_flow_score(self):
        v, q, f = grid()
        context = prepare(v, f, [], [], 1., max_distance=.5, sample_spacing=.125)
        report = measure(context, v, q)
        self.assertLess(rank_key(report, target=8, face_count=8),
                        rank_key(report, target=8, face_count=9))


if __name__ == '__main__':
    unittest.main()


"""Focused adapter contracts and failure isolation; geometry runs are separate."""
import builtins
import ctypes
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import retopo
import features
import terrain
import mesh_ops
import json

V=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]])
F=np.array([[0,2,1],[0,1,3],[1,2,3],[2,0,3]])

class Contract(unittest.TestCase):
    def test_closed_input_positive_and_negative(self):
        self.assertEqual(retopo.check_inputs(V,F,[V[:2]],400,2)[0].shape,(4,3))
        for bad in [F[:-1],np.vstack([F,F[:1]]),F.copy()[:,::-1]*0]:
            with self.subTest(faces=bad.tolist()),self.assertRaises((ValueError,NotImplementedError)):
                retopo.check_inputs(V,bad,[V[:2]],400,2)

    def test_source_winding_is_not_silently_repaired(self):
        bad=F.copy();bad[0]=bad[0,::-1]
        with self.assertRaisesRegex(ValueError,'winding'):retopo.check_inputs(V,bad,[V[:2]],400,2)

    def test_nonfinite_and_zero_length_guides_rejected(self):
        for curve in [np.array([[0,0,0],[np.nan,0,0]]),np.zeros((2,3)),np.array([[1,2,3]])]:
            with self.subTest(curve=curve.tolist()),self.assertRaises(ValueError):retopo.check_inputs(V,F,[curve],400,2)

    def test_semantic_mode_and_target(self):
        for target,mode in [(0,2),(400,0),(400,True),(400.0,2)]:
            with self.subTest(target=target,mode=mode),self.assertRaises((ValueError,NotImplementedError)):
                retopo.check_inputs(V,F,[V[:2]],target,mode)
        with self.assertRaisesRegex(NotImplementedError,'mode 2'):
            retopo.construct(V,F,[V[:2]],guide_mode=1,feature_policy='preserve-sharp')

    def test_obj_roundtrip_and_attribute_refusal(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.obj';retopo.write_obj(path,V,F.tolist());v,f=retopo.read_obj(path)
            np.testing.assert_array_equal(v,V);np.testing.assert_array_equal(f,F)
            path.write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\ng retained\nf 1 2 3\n')
            with self.assertRaisesRegex(ValueError,'unsupported record'):retopo.read_obj(path)
            path.write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 0 2 3\n')
            with self.assertRaisesRegex(ValueError,'zero'):retopo.read_obj(path)

    def test_io_guard_denies_actual_reads_and_restores_after_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'retained.bin';path.write_bytes(b'original')
            originals=(Path.open,builtins.open,np.fromfile,ctypes.CDLL,subprocess.Popen)
            with self.assertRaisesRegex(RuntimeError,'deliberate'):
                with retopo.no_construction_io():
                    for action in [path.read_bytes,lambda:builtins.open(path,'rb'),lambda:np.fromfile(path,'u1'),lambda:ctypes.CDLL('kernel32'),lambda:subprocess.Popen([sys.executable,'-c','pass'])]:
                        with self.assertRaises(PermissionError):action()
                    raise RuntimeError('deliberate')
            self.assertEqual(originals,(Path.open,builtins.open,np.fromfile,ctypes.CDLL,subprocess.Popen))
            self.assertEqual(path.read_bytes(),b'original')

    def test_graph_decomposition_exhausts_edges_without_inventing_links(self):
        edges=[(0,1),(1,2),(2,0),(1,3),(4,5),(5,6),(6,4)]
        paths=features.paths_from_edges(edges);used=[]
        for ids,vertices in paths:
            self.assertEqual(len(vertices),len(ids)+1)
            for edge,a,b in zip(ids,vertices[:-1],vertices[1:]):
                self.assertEqual(set(edges[edge]),{a,b});used.append(edge)
        self.assertEqual(sorted(used),list(range(len(edges))))

    def test_binary_output_crease_encoding(self):
        v=np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]],dtype=float)
        faces=[[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]]
        result=features.output_creases(v,faces)
        self.assertEqual(len(result['edges']),12);self.assertEqual(result['faceLowSlotBytes'],[85]*6)
        self.assertFalse(result['arbitrarySourceTagsTransferred'])
        self.assertEqual(features.output_creases(v[:4],[[0,1,2,3]])['faceLowSlotBytes'],[0])

    def test_heightfield_contract_and_fold_refusal(self):
        v=np.array([[0,0,0],[1,0,.1],[1,1,.2],[0,1,.1]],dtype=float);f=np.array([[0,1,2],[0,2,3]])
        self.assertEqual(len(terrain._source(v,f)[3]),4)
        with self.assertRaisesRegex(ValueError,'positive'):terrain._source(v,f[:,::-1])
        v[2,:2]=v[0,:2]
        with self.assertRaisesRegex(ValueError,'Single-valued'):terrain._source(v,f)

    def test_positive_fan_does_not_hide_a_self_crossing_boundary(self):
        # Every fan triangle has positive area, yet the star wraps twice.
        angles=np.deg2rad([0,144,288,72,216])
        v=np.vstack([np.column_stack([np.cos(angles),np.sin(angles),np.zeros(5)]),[0,0,0]])
        f=np.array([[5,i,(i+1)%5] for i in range(5)])
        with self.assertRaisesRegex(ValueError,'self-intersection'):terrain._source(v,f)

    def test_fractional_edge_points_split_both_incident_faces(self):
        from recovered_mesh_topology import build
        from measure_geometry import topology
        top=build(len(V),F);edge=next(i for i,e in enumerate(top['edges']) if tuple(e)==(0,1))
        t=np.array([0,.25,.75,1],dtype='<f4')
        path=dict(points=V[0]+t[:,None]*(V[1]-V[0]),edges=np.full(4,edge,dtype='<i4'),parameters=t,faces=np.full(3,-1,dtype='<i4'),attributes=np.array([],dtype='<i4'))
        def prepared(vertices,edges,paths):return vertices.copy(),paths,[],[]
        vertices,faces,maps,_,_=mesh_ops.cut_existing_edges(V,F,[path],prepared)
        stats,_,_=topology(vertices,faces)
        self.assertEqual((len(vertices),len(faces)),(6,8));self.assertEqual(stats['boundaryEdges'],0);self.assertEqual(stats['eulerCharacteristic'],2)
        self.assertEqual(maps[0].tolist(),[0,4,5,1]);self.assertEqual(stats['unusedVertices'],0)

    def test_shared_vertex_holes_cap_by_face_fans(self):
        from measure_geometry import topology
        from recovered_balanced_boundary_cap import cap
        v=np.array([[0,0,1],[0,0,-1],[1,0,0],[0,1,0],[-1,0,0],[0,-1,0]],dtype=float)
        closed=[[0,2,3],[0,3,4],[0,4,5],[0,5,2],[1,3,2],[1,4,3],[1,5,4],[1,2,5]]
        punctured=[r for i,r in enumerate(closed) if i not in (0,2)];protected=np.zeros(6,bool)
        with self.assertRaisesRegex(NotImplementedError,'Shared/branch'):cap(v,punctured,protected)
        filled,loops,_=mesh_ops.cap_face_fans(v,punctured,protected);stats,_,_=topology(v,filled)
        self.assertEqual(sorted(map(len,loops)),[3,3]);self.assertEqual(len(filled),8)
        self.assertEqual(stats['boundaryEdges'],0);self.assertEqual(stats['nonmanifoldEdges'],0);self.assertEqual(stats['eulerCharacteristic'],2)

    def test_positive_and_negative_geometry_reports_serialize(self):
        from mesh_validation import validate_closed
        edges=sorted({tuple(sorted((int(a),int(b)))) for row in F for a,b in zip(row,np.roll(row,-1))})
        good=validate_closed(V,F,V,F.tolist(),target=100,physical_edges=edges)
        self.assertTrue(json.loads(json.dumps(good))['passed'])
        bad=V.copy();bad[0,0]+=.1
        result=validate_closed(V,F,bad,F.tolist(),target=100,physical_edges=edges)
        self.assertFalse(json.loads(json.dumps(result))['passed'])

if __name__=='__main__':unittest.main()

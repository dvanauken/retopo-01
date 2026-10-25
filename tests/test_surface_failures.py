"""Recoverable candidate and Windows progress-publication failures."""
from pathlib import Path
import contextlib
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import curved_quad as cq


class RecoverableFailures(unittest.TestCase):
    def test_transient_progress_sharing_violation_retries(self):
        original=Path.replace
        calls=[]
        def replace(path,target):
            calls.append(target)
            if len(calls)==1: raise PermissionError('Controlled Windows sharing violation')
            return original(path,target)
        with tempfile.TemporaryDirectory(prefix='retopo-progress-') as directory:
            folder=Path(directory)
            with patch.object(Path,'replace',replace),patch.object(cq.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
                cq._progress(folder,'Actual fitting stage')
            self.assertEqual(json.loads((folder/'progress.json').read_text())['stage'],'Actual fitting stage')
            self.assertGreaterEqual(len(calls),2)

    def test_persistent_progress_lock_cannot_abort_geometry(self):
        with tempfile.TemporaryDirectory(prefix='retopo-progress-') as directory:
            folder=Path(directory); old={'stage':'Earlier stage'}
            (folder/'progress.json').write_text(json.dumps(old))
            with patch.object(Path,'replace',side_effect=PermissionError('Controlled persistent status lock')),patch.object(cq.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
                cq._progress(folder,'Later fitting stage')
            self.assertEqual(json.loads((folder/'progress.json').read_text()),old)

    def test_invalid_quad_projection_is_a_recorded_rejection(self):
        source=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1]],dtype=float)
        triangles=np.array([[0,2,1],[0,1,3],[1,2,3],[2,0,3]])
        positions=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0]],dtype=float)
        result=cq.validate_surface(source,triangles,positions,np.array([[0,2,1,3]]),1800)
        self.assertFalse(result['passed'])
        self.assertFalse(result['checks']['validTriangulation'])
        self.assertIn('Self-crossing',result['reason'])


if __name__=='__main__': unittest.main()

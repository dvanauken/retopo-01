"""API admission retains model-specific density, including boundary requests."""
from pathlib import Path
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server


class TargetDensity(unittest.TestCase):
    def request(self, model, target):
        handler = server.Handler.__new__(server.Handler)
        handler.path = '/api/remesh'
        body = json.dumps(dict(meshId=model, target=target, guideMode=2, curves=[])).encode()
        handler.headers = {'Content-Type': 'application/json', 'Content-Length': str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler.respond = lambda data, status=200: (data, status)
        return handler.do_POST()

    def test_toilet_accepts_requested_density_without_clamping(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runs') as temp:
            root = Path(temp); (root/'runs').mkdir()
            with patch.object(server, 'ROOT', root), patch.dict(server.JOBS, {}, clear=True), patch.object(server.QUEUE, 'submit') as submit:
                for target in (150, 7200, 12000):
                    response, status = self.request('toilet', target)
                    self.assertEqual(status, 202)
                    settings = json.loads((root/'runs'/response['id']/'settings.json').read_text())
                    self.assertEqual(settings['target'], target)
                self.assertEqual(submit.call_count, 3)

    def test_bad_and_other_model_targets_do_not_start_workers(self):
        with patch.object(server.QUEUE, 'submit') as submit:
            for model, target in [('toilet', 12001), ('toilet', 149), ('toilet', True), ('toilet', 7200.5), ('hexagon', 7200), ('ellipsoid', 7200)]:
                with self.subTest(model=model, target=target):
                    response, status = self.request(model, target)
                    self.assertEqual(status, 400)
                    self.assertIn('Target', response['error'])
            submit.assert_not_called()


if __name__ == '__main__':
    unittest.main()

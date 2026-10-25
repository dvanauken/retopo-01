"""Progress/log I/O must not interrupt job observation or cancellation."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server


class JobIoFaults(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(server.JOBS, {}, clear=True))
        self.enterContext(patch.dict(server.REQUESTS, {}, clear=True))
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.job = dict(id='a' * 32, state='running', stage='Constructing mesh', directory=self.folder)
        server.JOBS[self.job['id']] = self.job

    def handler(self, path):
        handler = server.Handler.__new__(server.Handler)
        handler.path = path
        handler.respond = lambda data, status=200: (data, status)
        return handler

    def test_progress_sharing_violation_preserves_authoritative_status(self):
        handler = self.handler('/api/jobs/' + self.job['id'])
        with patch.object(server, 'read', side_effect=PermissionError('progress temporarily locked')):
            data, status = handler.do_GET()
        self.assertEqual(status, 200)
        self.assertEqual(data['state'], 'running')
        self.assertEqual(data['stage'], 'Constructing mesh')
        self.assertEqual(self.job['state'], 'running')

    def test_cancel_log_failure_still_terminates_real_process(self):
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.job['process'] = process
        try:
            with patch.object(server, 'write', side_effect=PermissionError('diagnostic file locked')):
                with server.LOCK:
                    result = server.cancel_job(self.job)
            process.wait(timeout=5)
            self.assertEqual(result['state'], 'cancelled')
            self.assertIsNotNone(process.returncode)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)

    def test_queued_cancel_log_failure_cannot_start_worker(self):
        self.job['state'] = 'queued'
        with patch.object(server, 'write', side_effect=PermissionError('diagnostic file locked')):
            with server.LOCK:
                result = server.cancel_job(self.job)
        with patch.object(server.subprocess, 'Popen') as spawn:
            server.execute(self.job)
        self.assertEqual(result['state'], 'cancelled')
        spawn.assert_not_called()

    def test_huge_integer_coordinate_returns_structured_validation_error(self):
        handler = self.handler('/api/remesh')
        body = json.dumps(dict(meshId='toilet', target=1800, curves=[[[10 ** 4000, 0, 0], [0, 0, 0]]])).encode()
        handler.headers = {'Content-Type': 'application/json', 'Content-Length': str(len(body))}
        handler.rfile = io.BytesIO(body)
        with patch.object(server.QUEUE, 'submit') as submit:
            data, status = handler.do_POST()
        self.assertEqual(status, 400)
        self.assertIn('finite XYZ', data['error'])
        submit.assert_not_called()


if __name__ == '__main__':
    unittest.main()

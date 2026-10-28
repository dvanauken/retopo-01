"""Deterministic startup/terminal-state races around the real execute function."""
from pathlib import Path
import json
import io
import sys
import threading
import unittest
from unittest.mock import patch, Mock
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server


class WorkerStartup(unittest.TestCase):
    def job(self):
        folder = ROOT/'runs'/uuid.uuid4().hex
        folder.mkdir()
        return dict(id=folder.name, state='queued', stage='Waiting for solver', directory=folder)

    def test_cancelled_queued_job_never_spawns(self):
        job = self.job(); job['state'] = 'cancelled'
        with patch.object(server.subprocess, 'Popen') as spawn:
            server.execute(job)
        spawn.assert_not_called()
        self.assertEqual(job['state'], 'cancelled')

    def test_startup_failure_is_reported(self):
        job = self.job()
        with patch.object(server.subprocess, 'Popen', side_effect=OSError('controlled startup failure')):
            server.execute(job)
        self.assertEqual(job['state'], 'failed')
        self.assertIn('controlled startup failure', job['error'])
        self.assertEqual(json.loads((job['directory']/'execution.json').read_text())['state'], 'failed')

    def test_cancellation_during_startup_failure_stays_cancelled(self):
        job = self.job(); entered, release = threading.Event(), threading.Event()
        def fail(*args, **kwargs):
            entered.set(); release.wait()
            raise OSError('controlled startup failure after cancellation')
        with patch.object(server.subprocess, 'Popen', side_effect=fail):
            thread = threading.Thread(target=server.execute, args=(job,))
            thread.start(); entered.wait()
            with server.LOCK:
                job.update(state='cancelled', stage='Cancelled')
            release.set(); thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(job['state'], 'cancelled')
        self.assertEqual(json.loads((job['directory']/'execution.json').read_text())['state'], 'cancelled')

    def test_worker_timeout_terminates_before_reporting_failure(self):
        job = self.job(); process = Mock()
        process.wait.side_effect = [server.subprocess.TimeoutExpired('owned worker', 600), -9]
        with patch.object(server.subprocess, 'Popen', return_value=process), patch.object(server, 'terminate_worker') as terminate:
            server.execute(job)
        terminate.assert_called_once_with(process)
        self.assertEqual(job['state'], 'failed')
        self.assertEqual(job['actualExitCode'], -9)
        self.assertIn('ten-minute limit', job['error'])

    def test_cancel_response_snapshots_under_the_job_lock(self):
        class LockedSnapshot(dict):
            def items(self):
                if not server.LOCK.locked():
                    raise AssertionError('Job enumeration can race worker field insertion')
                return super().items()
        job = LockedSnapshot(self.job()); job['state'] = 'cancelled'
        handler = server.Handler.__new__(server.Handler)
        handler.path = '/api/jobs/' + job['id'] + '/cancel'
        handler.headers = {'Content-Length':'2','Content-Type':'application/json'}; handler.rfile = io.BytesIO(b'{}')
        handler.respond = lambda data,status=200: (data,status)
        with patch.dict(server.JOBS, {job['id']:job}):
            response,status = handler.do_POST()
        self.assertEqual(status,200)
        self.assertEqual(response['state'],'cancelled')

    def test_model_budget_still_terminates_timed_out_worker(self):
        job=self.job();job['meshId']='feature-test';process=Mock()
        process.wait.side_effect=[server.subprocess.TimeoutExpired('owned worker',1500),-9]
        with patch.dict(server.MESHES,{'feature-test':dict(solverTimeoutSeconds=1500)}),patch.object(server.subprocess,'Popen',return_value=process),patch.object(server,'terminate_worker') as terminate:
            server.execute(job)
        self.assertEqual(process.wait.call_args_list[0].kwargs,{'timeout':1500})
        terminate.assert_called_once_with(process)
        self.assertEqual(job['state'],'failed')
        self.assertIn('25-minute limit',job['error'])


if __name__ == '__main__':
    unittest.main()

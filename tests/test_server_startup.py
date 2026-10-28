"""Real-process startup checks on isolated ports and copied server entrypoints."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import psutil

ROOT = Path(__file__).resolve().parents[1]


class Startup(unittest.TestCase):
    def setUp(self):
        # Spaces also exercise start.cmd's quoted working-directory change.
        self.folder = Path(tempfile.mkdtemp(prefix='startup test ', dir=ROOT/'runs'))
        self.processes = []
        self.servers = []
        self.pointer = ROOT/'runs/server.json'
        self.original_pointer = self.pointer.read_bytes() if self.pointer.exists() else None

    def tearDown(self):
        for process in self.servers:
            try:
                process.kill()
                process.wait(timeout=10)
            except psutil.NoSuchProcess:
                pass
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)
        current = self.pointer.read_bytes() if self.pointer.exists() else None
        self.assertEqual(current, self.original_pointer, 'User service pointer must remain untouched')
        # All deletion is confined to this test's resolved workspace directory.
        self.assertTrue(self.folder.resolve().is_relative_to((ROOT/'runs').resolve()))
        shutil.rmtree(self.folder)

    def checkout(self, name):
        folder = self.folder/name
        (folder/'assets').mkdir(parents=True)
        for file in ('server.py', 'process_ownership.py', 'job_progress.py', 'job_diagnostics.py', 'crease_angle.py', 'start.cmd'):
            shutil.copyfile(ROOT/file, folder/file)
        shutil.copyfile(ROOT/'assets/catalog.json', folder/'assets/catalog.json')
        return folder

    def free_port(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            return sock.getsockname()[1]

    def command(self, folder, port):
        return [sys.executable, '-X', 'utf8', str(folder/'server.py'), '--port', str(port)]

    def health(self, port):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f'http://127.0.0.1:{port}/api/health', timeout=1) as response:
            return json.load(response)

    def start(self, folder, port):
        process = subprocess.Popen(self.command(folder, port), cwd=folder,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.processes.append(process)
        for _ in range(100):
            self.assertIsNone(process.poll(), 'Fresh server exited before listening')
            try:
                self.health(port)
                return process
            except OSError:
                time.sleep(.05)
        self.fail('Server did not start')

    def duplicate(self, folder, port):
        return subprocess.run(self.command(folder, port), cwd=folder, capture_output=True,
                              text=True, timeout=10)

    def restart(self, folder, port, batch=False):
        pointer = folder/'runs/server.json'
        previous_pid = json.loads(pointer.read_text())['pid'] if pointer.exists() else None
        env = dict(os.environ)
        env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', '')
        command = ([os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c',
                    '.\\start.cmd', '--port', str(port)] if batch else
                   self.command(folder, port) + ['--restart', '--next-port'])
        with (folder/'startup.log').open('ab') as log:
            launcher = subprocess.Popen(command, cwd=folder, env=env, stdin=subprocess.DEVNULL,
                                        stdout=log, stderr=log,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.processes.append(launcher)
        for _ in range(200):
            if launcher.poll() is not None:
                self.fail((folder/'startup.log').read_text())
            try:
                record = json.loads(pointer.read_text())
                if record['pid'] != previous_pid:
                    server = psutil.Process(record['pid'])
                    if all(p.pid != server.pid for p in self.servers):
                        self.servers.append(server)
                    if self.health(record['port'])['ready']:
                        return server, record
            except (OSError, ValueError, psutil.NoSuchProcess):
                pass
            time.sleep(.05)
        self.fail('Restart did not complete: ' + (folder/'startup.log').read_text())

    def test_plain_python_repeat_preserves_original_server(self):
        folder = self.checkout('same checkout')
        port = self.free_port()
        (folder/'runs').mkdir()
        (folder/'runs/server.json').write_text('{"pid":-1,"port":1}')
        process = self.start(folder, port)
        pointer = (folder/'runs/server.json').read_bytes()
        self.assertEqual(json.loads(pointer)['pid'], process.pid)
        self.assertEqual(json.loads(pointer)['port'], port)
        result = self.duplicate(folder, port)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('already running', result.stdout)
        self.assertIn(f'http://localhost:{port}', result.stdout)
        self.assertNotIn('Press any key', result.stdout)
        self.assertNotIn('Traceback', result.stderr)
        self.assertIsNone(process.poll())
        self.assertTrue(self.health(port)['ready'])
        self.assertEqual((folder/'runs/server.json').read_bytes(), pointer)

    @unittest.skipUnless(os.name == 'nt', 'Windows batch launcher')
    def test_start_cmd_restarts_server_and_owned_worker(self):
        folder = self.checkout('batch restart')
        script = folder/'server.py'
        source = script.read_bytes()
        script.write_bytes(source.replace(
            b'protect_service_tree()\r\n',
            b'protect_service_tree()\r\n'
            b" child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'])\r\n"
            b" (ROOT/'worker-pid.txt').write_text(str(child.pid))\r\n"))
        # Support checkouts using LF as well as CRLF.
        if script.read_bytes() == source:
            script.write_bytes(source.replace(
                b'protect_service_tree()\n',
                b'protect_service_tree()\n'
                b" child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'])\n"
                b" (ROOT/'worker-pid.txt').write_text(str(child.pid))\n"))
        port = self.free_port()
        original = self.start(folder, port)
        worker = psutil.Process(int((folder/'worker-pid.txt').read_text()))
        self.servers.append(worker)
        replacement, record = self.restart(folder, port, batch=True)
        original.wait(timeout=10)
        worker.wait(timeout=10)
        self.assertNotEqual(original.pid, replacement.pid)
        self.assertEqual(record['port'], port)
        self.assertTrue(self.health(port)['ready'])
        self.assertIn('Stopping Retopo1', (folder/'startup.log').read_text())

    def test_busy_port_fallback_and_restarting_recorded_fallback(self):
        folder = self.checkout('fallback restart')
        with socket.socket() as foreign:
            foreign.bind(('127.0.0.1', 0))
            foreign.listen()
            port = foreign.getsockname()[1]
            first, record = self.restart(folder, port)
            self.assertNotEqual(record['port'], port)
            self.assertEqual(record['url'], f"http://127.0.0.1:{record['port']}")
            second, second_record = self.restart(folder, port)
            first.wait(timeout=10)
            self.assertNotEqual(first.pid, second.pid)
            self.assertEqual(second_record['port'], record['port'])
            # The unrelated listener remains intact across both launches.
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                pass

    def test_restart_does_not_stop_another_checkout(self):
        first, second = self.checkout('foreign checkout'), self.checkout('new checkout')
        port = self.free_port()
        original = self.start(first, port)
        _, record = self.restart(second, port)
        self.assertNotEqual(record['port'], port)
        self.assertIsNone(original.poll())
        self.assertTrue(self.health(port)['ready'])

    def test_restart_unhealthy_owned_server(self):
        folder = self.checkout('unhealthy restart')
        script = folder/'server.py'
        source = script.read_bytes()
        script.write_bytes(source.replace(b'dict(ready=True,engine=', b'dict(ready=False,engine='))
        port = self.free_port()
        original = self.start(folder, port)
        self.assertFalse(self.health(port)['ready'])
        script.write_bytes(source)
        _, record = self.restart(folder, port)
        original.wait(timeout=10)
        self.assertEqual(record['port'], port)

    def test_stale_pointer_cannot_stop_an_unrelated_process(self):
        folder = self.checkout('stale pointer')
        with socket.socket() as foreign:
            foreign.bind(('127.0.0.1', 0))
            foreign.listen()
            port = foreign.getsockname()[1]
            (folder/'runs').mkdir()
            (folder/'runs/server.json').write_text(json.dumps(dict(pid=os.getpid(), port=port)))
            _, record = self.restart(folder, port)
            self.assertNotEqual(record['port'], port)
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                pass

    def test_other_checkout_is_not_reused(self):
        first, second = self.checkout('first'), self.checkout('second')
        port = self.free_port()
        process = self.start(first, port)
        result = self.duplicate(second, port)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(f'Port {port} is already in use', result.stderr)
        self.assertIn('start.cmd --port', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertIsNone(process.poll())
        self.assertFalse((second/'runs/server.json').exists())

    def test_foreign_health_lookalike_is_not_reused(self):
        class Foreign(BaseHTTPRequestHandler):
            def do_GET(self):
                body = b'{"ready":true,"engine":"Local reference engine"}'
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Foreign)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_port
            result = self.duplicate(self.checkout('foreign conflict'), port)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(f'Port {port} is already in use', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertTrue(self.health(port)['ready'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_unhealthy_same_checkout_is_not_reported_as_ready(self):
        folder = self.checkout('unhealthy')
        script = folder/'server.py'
        script.write_bytes(script.read_bytes().replace(b'dict(ready=True,engine=', b'dict(ready=False,engine='))
        port = self.free_port()
        process = self.start(folder, port)
        result = self.duplicate(folder, port)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('unresponsive server', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertIsNone(process.poll())


if __name__ == '__main__':
    unittest.main(verbosity=2)

"""Observe actual WebGL draws and native viewport changes on the toilet."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from process_ownership import protect_service_tree

parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
args = parser.parse_args()
if not args.label.replace('-', '').isalnum():
    raise ValueError('Use a plain label')
protect_service_tree()
OUT = ROOT / 'tests/toilet-render-idle' / args.label
OUT.mkdir(parents=True, exist_ok=False)
(OUT / 'executed-test.py').write_bytes(Path(__file__).read_bytes())
files = ['app.js', 'server.py', 'assets/models/toilet.obj', 'tests/verify_toilet_render_idle.py']
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
hashes = {name: sha(ROOT / name) for name in files}
checks, errors = [], []
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
url = f'http://127.0.0.1:{port}'
pointer = ROOT / 'runs/server.json'
old_pointer = pointer.read_bytes() if pointer.exists() else None
log = (OUT / 'server.log').open('w', encoding='utf-8')
server = subprocess.Popen([sys.executable, '-X', 'utf8', 'server.py', '--port', str(port)], cwd=ROOT,
                          stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

def check(value, name, **detail):
    checks.append(dict(passed=bool(value), name=name, **detail))
    print(('PASS ' if value else 'FAIL ') + name, flush=True)

try:
    for _ in range(100):
        try:
            urllib.request.urlopen(url + '/api/health', timeout=1).close()
            break
        except OSError:
            time.sleep(.1)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport=dict(width=1700, height=1050), device_scale_factor=1)
        page.on('pageerror', lambda e: errors.append(str(e)))
        # Count genuine draw calls; delegate unchanged arguments to native WebGL.
        page.add_init_script('''window.observedWebGLDraws = 0;
          for (const Type of [WebGLRenderingContext, WebGL2RenderingContext]) {
            for (const name of ['drawArrays', 'drawElements', 'drawArraysInstanced', 'drawElementsInstanced']) {
              const original = Type.prototype[name]; if (!original) continue;
              Type.prototype[name] = function(...args) { window.observedWebGLDraws++; return original.apply(this, args); };
            }
          }''')
        page.goto(url, wait_until='networkidle')
        page.wait_for_function('window.retopoDemo?.getState().resultFaces > 0')
        page.locator('#meshSelect').select_option('toilet')
        page.wait_for_function('window.retopoDemo.getState().meshId === "toilet" && !document.getElementById("generateButton").disabled')
        page.locator('#topButton').click()
        source = json.load(urllib.request.urlopen(url + '/api/mesh/toilet'))
        curves = json.loads((ROOT / 'tests/toilet-paired-variants/sampling-and-density/short-small-perturbation/curves.json').read_text())['curves']
        packet = dict(coordinateFrame='source', sourceSha256=source['sourceSha256'], curves=curves)
        page.locator('#guideFile').set_input_files(dict(name='guides.json', mimeType='application/json', buffer=json.dumps(packet).encode()))
        page.wait_for_function('window.retopoDemo.getState().guides.length === 2')
        draws = lambda: page.evaluate('window.observedWebGLDraws')
        pixels = lambda: page.locator('#viewport').evaluate('(c) => c.toDataURL()')

        def settled():
            previous = draws()
            for _ in range(40):
                page.wait_for_timeout(100)
                current = draws()
                if current == previous:
                    return current
                previous = current
            raise AssertionError('Viewport did not stop drawing after damping')

        count = settled()
        page.wait_for_timeout(1500)
        check(count > 0 and draws() == count, 'Idle original toilet stops issuing WebGL draw calls', drawCalls=count)

        def change(action, name):
            before_count, before_pixels = draws(), pixels()
            action()
            page.wait_for_function('(n) => window.observedWebGLDraws > n', arg=before_count)
            settled()
            check(pixels() != before_pixels, name)

        change(lambda: page.locator('#wireToggle').uncheck(), 'Mesh-edge toggle repaints the actual viewport')
        change(lambda: page.locator('#wireToggle').check(), 'Mesh edges repaint when restored')
        change(lambda: page.locator('#guidesToggle').uncheck(), 'Hiding guides repaints the viewport')
        change(lambda: page.locator('#guidesToggle').check(), 'Showing guides repaints the viewport')
        change(lambda: page.locator('[data-view="overlay"]').click(), 'Overlay mode repaints')
        change(lambda: page.locator('[data-view="split"]').click(), 'Split mode repaints')
        change(lambda: page.locator('#themeButton').click(), 'Theme changes repaint materials and background')
        change(lambda: page.set_viewport_size(dict(width=1450, height=900)), 'Window resizing repaints and resizes the canvas')
        change(lambda: page.locator('[data-splitter="west"]').press('ArrowRight'), 'Navigator resizing repaints without a window resize')
        change(lambda: page.locator('[data-splitter="south"]').press('ArrowUp'), 'Dock resizing repaints without a window resize')
        change(lambda: page.locator('#toggle-ribbon').click(), 'Collapsing the ribbon repaints the resized viewport')
        change(lambda: page.locator('#toggle-ribbon').click(), 'Expanding the ribbon repaints the resized viewport')
        page.locator('#viewport').focus()
        box = page.locator('#viewport').bounding_box()
        x, y = box['x'] + box['width'] * .25, box['y'] + box['height'] * .5
        def orbit():
            page.keyboard.down('Space')
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x + 100, y + 45, steps=12)
            page.mouse.up()
            page.keyboard.up('Space')
        change(orbit, 'Native orbit repaints through damping')
        change(lambda: page.locator('#topButton').click(), 'Top command repaints after orbit settles')
        change(lambda: page.locator('#clearButton').click(), 'Clearing guides repaints the source')
        count = settled()
        page.wait_for_timeout(1500)
        check(draws() == count, 'Viewport returns to zero drawing after native interactions', drawCalls=count)
        page.screenshot(path=str(OUT / 'idle-toilet.png'))
        browser.close()
except Exception:
    errors.append(traceback.format_exc())
    print(errors[-1], flush=True)
finally:
    if server.poll() is None:
        server.kill()
    server.wait(timeout=15)
    log.close()
    if pointer.exists() and json.loads(pointer.read_text()).get('pid') == server.pid:
        if old_pointer is None:
            pointer.unlink()
        else:
            pointer.write_bytes(old_pointer)
    check(all(sha(ROOT / name) == digest for name, digest in hashes.items()), 'Implementation remains fixed during rendering checks')
    report = dict(complete=True, passed=not errors and all(c['passed'] for c in checks), checks=checks, errors=errors,
                  sourceHashes=hashes, scope='Actual WebGL draw-call observation and pixel changes on the original toilet with native controls. No solver response substitution. Idle checks are finite observations; editing and generation have separate suites.')
    (OUT / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
raise SystemExit(0 if report['passed'] else 1)

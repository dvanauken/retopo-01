"""Verify virgin import conservation and real browser part selection/export."""
import json
import sys
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
import numpy as np
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server
from mesh_parts import load_part

raw = json.loads((ROOT / 'assets/raw/toilet-skp/source-parts.json').read_text())
mesh = json.loads((ROOT / 'assets/models/toilet-skp.json').read_text())
assert len(mesh['faces']) == sum(len(p['faces']) for p in raw['parts']) == 25809
assert len(mesh['initialParts']) == 11
ids = []
for part in mesh['initialParts']:
    data, _ = load_part(part['partSource'])
    ids.extend(data['sourceFaceIds'])
    assert data['repair']['capFaces'] == 0
    actual = np.asarray(data['vertices'])[data['faces']]
    expected = np.asarray(mesh['vertices'])[np.asarray(mesh['faces'])[data['sourceFaceIds']]]
    assert np.array_equal(actual, expected)
assert sorted(ids) == list(range(len(mesh['faces'])))
http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
threading.Thread(target=http.serve_forever, daemon=True).start()
out = ROOT / 'runs/skp-parts-check'; out.mkdir(exist_ok=True)
errors = []
try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport=dict(width=1700, height=1100))
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(f'http://127.0.0.1:{http.server_port}', wait_until='networkidle')
        page.locator('#meshSelect').select_option('toilet-skp')
        page.wait_for_function('window.retopoDemo.getPartsState()?.parts.length === 11')
        assert page.locator('#generateButton').is_disabled()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(out / 'assembly.png'))
        for part in mesh['initialParts']:
            page.get_by_role('button', name=part['name'], exact=True).click()
            page.locator('#partsWork').click()
            page.wait_for_function('(id) => window.retopoDemo.getPartsState().active === id', arg=part['id'])
            assert page.locator('#generateButton').is_enabled()
        with page.expect_download() as download:
            page.locator('#partsExport').click()
        download.value.save_as(str(out / 'assembly.obj'))
        assert (out / 'assembly.obj').read_text().count('\no ') == 11
        assert not errors, errors
        browser.close()
finally:
    http.shutdown(); http.server_close()
print('PASS: 25,809 original triangles, 11 independently selectable/exported objects, no added caps or missing faces; browser has no errors.')

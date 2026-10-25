"""Check that no worker or Blender process remains for a completed matrix."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import psutil

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
args = parser.parse_args()
if not args.label.replace('-', '').isalnum():
    raise ValueError('Use a plain label')
folder = ROOT / 'tests/toilet-paired-variants' / args.label
matrix = json.loads((folder / 'result.json').read_text())
assert matrix['complete'] and not matrix['errors']
jobs = [case['job'] for case in matrix['cases']]
survivors = []
for process in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
    try:
        command = process.info['cmdline'] or []
        name = (process.info['name'] or '').lower()
        if not (name.startswith('python') or name == 'blender.exe'):
            continue
        matches = [job for job in jobs if any(job in str(arg) for arg in command)]
        if matches:
            survivors.append(dict(pid=process.pid, createdAt=process.info['create_time'], jobs=matches, command=command))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
report = dict(complete=True, passed=not survivors, checkedAt=datetime.now(timezone.utc).isoformat(), jobs=jobs, survivors=survivors,
              scope='After the real service matrix has shut down, no Python worker or Blender command still references any of its exact job IDs. Does not enumerate unrelated processes or prove universal leak freedom.')
(folder / 'process-cleanup.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
raise SystemExit(1 if survivors else 0)

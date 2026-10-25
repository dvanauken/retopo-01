"""Read-only CPU sample and post-run lifetime check for one real browser suite."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import psutil

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--after', action='store_true')
args = parser.parse_args()
if not args.label.replace('-', '').isalnum():
    raise ValueError('Use a plain label')
folder = ROOT / 'tests/toilet-fallback-browser' / args.label
path = folder / 'runtime-observation.json'
if args.after:
    original = json.loads(path.read_text())
    survivors = []
    for row in original['processes']:
        try:
            p = psutil.Process(row['pid'])
            if p.is_running() and p.create_time() == row['createdAt']:
                survivors.append(row)
        except psutil.NoSuchProcess:
            pass
    report = dict(complete=True, passed=not survivors, survivors=survivors,
                  observedProcesses=len(original['processes']), observedAt=datetime.now(timezone.utc).isoformat(),
                  scope='After the suite exits, every process in its recorded descendant tree is gone. Creation times prevent PID-reuse confusion. Processes born after the sample are outside this observation.')
    (folder / 'runtime-cleanup.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    raise SystemExit(1 if survivors else 0)

parents = []
for p in psutil.process_iter(['name', 'cmdline']):
    try:
        command = p.info['cmdline'] or []
        if p.info['name'].lower().startswith('python') and args.label in command and any(Path(a).name == 'verify_toilet_fallback_browser.py' for a in command):
            parents.append(p)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
if len(parents) != 1:
    raise RuntimeError('Expected exactly one matching live browser test')
processes = [parents[0], *parents[0].children(recursive=True)]
for p in processes:
    try:
        p.cpu_percent()
    except psutil.NoSuchProcess:
        pass
time.sleep(1)
rows = []
for p in processes:
    try:
        rows.append(dict(pid=p.pid, createdAt=p.create_time(), parentPid=p.ppid(), name=p.name(), command=p.cmdline(),
                         cpuPercent=p.cpu_percent(), rss=p.memory_info().rss))
    except psutil.NoSuchProcess:
        pass
with path.open('x') as output:
    output.write(json.dumps(dict(observedAt=datetime.now(timezone.utc).isoformat(), logicalCPUs=psutil.cpu_count(), processes=rows,
        scope='One-second sample of the exact test process and its descendants. CPU percentage is per logical CPU. Headless software rendering contends with fitting; this is not a general interactive timing benchmark.'), indent=2) + '\n')
print(json.dumps([dict(name=r['name'],cpuPercent=r['cpuPercent'],rss=r['rss']) for r in rows]))

"""Human-readable candidate outcomes, derived from the actual acceptance gates."""
from collections import Counter
import json
from pathlib import Path


LABELS = {'quality': 'quad shape/count', 'feature': 'source crease preservation',
          'surface': 'surface/boundary preservation', 'contacts': 'face intersections',
          'guides': 'guide fit'}


def outcome(row):
    if row.get('error'): return dict(checked={}, failures=[row['error']], measurements=[])
    checked = {key: value['passed'] for key in LABELS if isinstance(value := row.get(key), dict) and 'passed' in value}
    if 'guidesPassed' in row: checked['guides'] = row['guidesPassed']
    failures = []; measurements = []
    for key, passed in checked.items():
        if passed: continue
        value = row.get(key, {})
        if key == 'quality':
            reasons = value.get('failures', [])
            measurements.extend(dict(check=name, value=value.get(name), limit=value.get('limits', {}).get(name)) for name in value.get('limits', {}) if any(name in r for r in reasons))
        elif key == 'feature':
            reasons = value.get('failures', [])
            measurements.extend(dict(check=name, value=value.get('values', {}).get(name), limit=value.get('limits', {}).get(name)) for name in reasons)
        elif key == 'surface': reasons = [name for name, passed in value.get('checks', {}).items() if not passed]
        elif key == 'contacts':
            count = sum(len(value.get(name, [])) for name in ('nonAdjacentIntersectingFacePairs', 'adjacentIntersectingFacePairs'))
            reasons = [f'{count} intersecting face pairs']
        else: reasons = ['connected guide path exceeds its distance or angle limit']
        failures.append(LABELS[key] + (': ' + ', '.join(reasons) if reasons else ' failed'))
    return dict(checked=checked, failures=failures, measurements=measurements)


def candidate_message(row):
    label = f"Layout {row.get('attempt', 0) + 1}, candidate {row.get('iteration', 0) + 1}"
    result = outcome(row)
    faces = row.get('quality', {}).get('faces')
    if faces is not None: label += f' · {faces:,} quads'
    if row.get('passed'): return label + ' accepted; all checks passed.'
    return label + ' rejected: ' + ('; '.join(result['failures']) or 'No candidate passed all checks.')


def summarize(rows):
    candidates = [r for r in rows if 'quality' in r]
    rejected = [r for r in rows if not r.get('passed')]
    if not rejected: return dict(candidateCount=len(candidates), message='All recorded candidates passed.')
    best = min(rejected, key=lambda r: (len(outcome(r)['failures']) + 5 - len(outcome(r)['checked']), len(outcome(r)['failures']), -r.get('iteration', 0)))
    detail = outcome(best)
    counts = Counter(name for row in rejected for name, passed in outcome(row)['checked'].items() if not passed)
    passed = [LABELS[name] for name, value in detail['checked'].items() if value]
    failed = [LABELS[name] for name, value in detail['checked'].items() if not value]
    message = f"No accepted mesh after {len(candidates)} candidates across {len({r.get('attempt') for r in rows})} layouts."
    if failed: message += ' Best candidate failed ' + ', '.join(failed) + '.'
    elif best.get('error'): message += ' ' + best['error']
    if passed: message += ' Passed: ' + ', '.join(passed) + '.'
    return dict(candidateCount=len(candidates), message=message, bestCandidate=dict(attempt=best.get('attempt'), iteration=best.get('iteration'), **detail), failedCheckCounts=dict(counts))


def from_job(folder):
    try: return summarize(json.loads((Path(folder) / 'open-surface/history.json').read_text(encoding='utf-8')))
    except (OSError, ValueError): return None


def recovered_events(folder, cursor=0, limit=200):
    """Old runs lack timestamps for individual passes; mark those times unavailable."""
    try: rows = json.loads((Path(folder) / 'open-surface/history.json').read_text(encoding='utf-8'))
    except (OSError, ValueError): rows = []
    events = [dict(time=None, kind='candidate', level='info' if r.get('passed') else 'warning', message='Recovered diagnostics · ' + candidate_message(r), details=outcome(r)) for r in rows]
    result = events[cursor:cursor + limit]
    return dict(events=[dict(event, cursor=cursor + i + 1) for i, event in enumerate(result)], eventCursor=cursor + len(result), moreEvents=cursor + len(result) < len(events))

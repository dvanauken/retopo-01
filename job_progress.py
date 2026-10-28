"""Advisory, append-only worker events. Diagnostics must never decide acceptance."""
from pathlib import Path
import json
import time


def emit(job, message, *, level='info', kind='stage', details=None):
    event = dict(time=time.time(), message=str(message)[:8192], level=level, kind=kind)
    if details is not None: event['details'] = details
    try:
        with (Path(job) / 'events.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(event, allow_nan=False) + '\n')
    except (OSError, ValueError, TypeError) as error:
        print(f'Could not record progress: {error}', flush=True)


def read_events(job, cursor=0, limit=200):
    """Only consume complete records; a partial write is retried at the same cursor."""
    path = Path(job) / 'events.jsonl'; events = []
    try:
        with path.open('rb') as stream:
            if cursor > path.stat().st_size: cursor = 0
            stream.seek(cursor)
            while len(events) < limit:
                line = stream.readline(65537)
                if not line or not line.endswith(b'\n'): break
                cursor = stream.tell()
                try: event = json.loads(line)
                except (ValueError, UnicodeDecodeError): continue
                if isinstance(event, dict) and isinstance(event.get('message'), str):
                    events.append(dict(event, cursor=cursor))
            stream.seek(cursor)
            more = stream.readline(65537).endswith(b'\n')
    except OSError: more = False
    return dict(events=events, eventCursor=cursor, moreEvents=more)

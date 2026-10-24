"""Shared fail-closed promotion rules and immutable previous-file snapshots."""
import csv
import hashlib
import json
from pathlib import Path


def passed(result):
    """Require positive, nonempty measurements; aggregate true cannot hide failure."""
    expected={'EXP-0001':11,'EXP-0002':2,'EXP-0003':10,'EXP-0006':7}.get(result.get('experimentId'))
    if expected is not None and len(result.get('cases',result.get('runs',[])))!=expected:return False
    if 'cases' in result:
        return (result.get('passed') is True and bool(result['cases'])
                and all((row.get('passed',row.get('passTolerance')) is True
                         and row.get('passTolerance',True) is True) for row in result['cases']))
    if 'runs' in result:
        return (result.get('passed', True) is True and bool(result['runs'])
                and all(row.get('exitCode') == 0 for row in result['runs']))
    return False


def require_failed_startup(entry):
    """This historical finalizer is failure-only; reject success before any writes."""
    if (entry.get('passed') is not False or entry.get('pythonEntered') is not False
            or entry.get('identityWritten') is not False):
        raise ValueError('Failure-only finalizer rejects successful, partial, or ambiguous startup input; use a new experiment record.')


def archive(path):
    """Keep old bytes once by hash, alongside a small immutable provenance record."""
    path=Path(path)
    if not path.is_file(): return
    target=next((p for p in path.parents if p.name=='zbrush'),None)
    if target is None: raise ValueError('No zbrush target root for history')
    data=path.read_bytes();digest=hashlib.sha256(data).hexdigest()
    history=target/'evidence/history';history.mkdir(parents=True,exist_ok=True)
    dest=history/(digest+'.snapshot')
    if not dest.exists(): dest.write_bytes(data)
    record=history/(digest+'.json')
    if not record.exists(): record.write_text(json.dumps(dict(originalPath=path.relative_to(target).as_posix(),sha256=digest,snapshot=dest.name),indent=2)+'\n',encoding='utf-8')


def write_json(path,obj):
    archive(path)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def merge_csv(path,columns,rows,key):
    path=Path(path);old=[]
    if path.exists():
        with path.open(newline='',encoding='utf-8-sig') as f: old=list(csv.DictReader(f))
    archive(path);ids={r[key] for r in rows}
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
        writer.writerows([r for r in old if r[key] not in ids]+rows)


def claim_support(row,results):
    """Downgrade runtime-dependent claims on contradictory or absent support."""
    refs=row['experiment_refs'].split(';') if row['experiment_refs'] else []
    if refs and not all(passed(results.get(ref,{})) for ref in refs):
        row=dict(row,confidence='tentative',status='rejected',
                 notes='Current supporting experiment failed or lacks complete passing checks; historical versions are retained in evidence/history.')
    return row

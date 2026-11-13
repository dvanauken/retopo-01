"""Write engine/guided-quadriflow/development/corner-rows-verification.json from the retained evidence."""
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def case_rows(result):
    rows = []
    for case in result['cases']:
        row = dict(case=case['case'], passed=case['passed'], faces=case.get('faces'), seconds=round(case['observedSeconds'], 1),
                   job=Path(case['job']).name, outputSha256=case.get('outputSha256'))
        if case.get('cornerZones'):
            row['cornerZones'] = case['cornerZones']
        if case.get('result'):
            rows_report = case['result']['featureValidation'].get('rows') or {}
            row['creaseRows'] = dict(required=rows_report.get('required'), realized=rows_report.get('realized'), localFaces=bool(rows_report.get('localFaces')))
            guides = (case['result'].get('guideRows') or {}).get('guides') or []
            if guides:
                row['guideLoops'] = [dict(pathVertices=g.get('pathVertices'), turns=g.get('values', {}).get('turns'), passed=g['passed']) for g in guides]
        else:
            row['message'] = case['report'].get('message')
        rows.append(row)
    return rows


corners = read(HERE / 'corners-strict-extra-zbrush.json')
matrix = read(HERE / 'matrix-9/result.json')
matrix_serial = read(HERE / 'matrix-3/result.json')
before = read(ROOT / 'tests/registered-features/guide-native-1/matrix-4/result.json')
extra = read(HERE / 'extra-island6-10/result.json')
extra_serial = read(HERE / 'extra-island6-4/result.json')
extra3 = read(HERE / 'extra-island6-6/result.json')
matrix3 = read(HERE / 'matrix-5/result.json')
ui = read(HERE / 'ui-extra-200-guide-8/result.json')
ui_750 = read(HERE / 'ui-extra-750-guide-2/result.json')
ui_strict = read(HERE / 'ui-strict-200-guide-3/result.json')
assembly = read(HERE / 'ui-assembly-edges-2/result.json')
strict = read(HERE / 'strict-search-200/strict-search.json')
parity = read(HERE / 'engine-parity-19/parity.json')
manifest = read(ROOT / 'engine/guided-quadriflow/manifest.json')
previous = {Path(c['job']).name.split('-', 2)[2]: c['outputSha256'] for c in before['cases']}
record = dict(
    date='2026-11-10',
    scope="Open parts with 'Add faces where the shape needs them': the faces at admitted crease chains are sized so each chain carries an edge row "
          '(crease_rows.local_sizes, sent to the engine as face-size caps on its constrained edges), the band rule and the row check use those local '
          'faces, and corner zones (corner_zones) are enforced. At the strict count the corner zones are reported. Engineering stand-in for native '
          "ZRemesher's one-cell separation of constrained lines (0x28fe70); not native arithmetic.",
    spacing=corners['spacing'],
    case='Toilet island 6 (skp-6), request 200, keep creases at 30 degrees, guide tests/fixtures/island6-guide-483afe83.json',
    cornerZone=dict(definition=corners['zone'], measure='distance from each source vertex of the zone to the output surface, in requested faces',
                    meshes={title: dict(file=item['file'], sha256=sha(ROOT / item['file']), faces=item['faces'], quads=item['quads'], triangles=item['triangles'],
                                        fixedZone=item['fixedZone'],
                                        automaticZones=[{k: z[k] for k in ('sourceVertices', 'p95InFaces', 'maxInFaces', 'passed')} for z in item['automaticZones']['zones']],
                                        cornerCheckPassed=item['automaticZones']['passed'])
                            for title, item in corners['meshes'].items()},
                    picture='tests/extra-faces/corners-1/corners-strict-extra-zbrush.png'),
    extraFaces=dict(run=extra['runId'], codeStable=extra['codeStable'], cases=case_rows(extra), evidence='tests/extra-faces/corners-1/extra-island6-10'),
    ui=dict(boxChecked={k: ui['cases'][0].get(k) for k in ('job', 'passed', 'faces', 'extraFacesBox', 'allowExtraFaces', 'cornerZones', 'guideLoops', 'rows', 'errors', 'outputSha256')},
            boxUnchecked={k: ui_strict['cases'][0].get(k) for k in ('job', 'passed', 'faces', 'extraFacesBox', 'allowExtraFaces', 'cornerZones', 'guideLoops', 'rows', 'errors', 'outputSha256')},
            boxChecked750={k: ui_750['cases'][0].get(k) for k in ('job', 'passed', 'faces', 'extraFacesBox', 'allowExtraFaces', 'cornerZones', 'guideLoops', 'rows', 'errors', 'outputSha256')},
            codeStable=bool(ui['codeStable'] and ui_750['codeStable'] and ui_strict['codeStable']),
            assemblyMeshEdges=assembly,
            evidence=['tests/extra-faces/corners-1/ui-extra-200-guide-7', 'tests/extra-faces/corners-1/ui-extra-750-guide-2', 'tests/extra-faces/corners-1/ui-strict-200-guide-3', 'tests/extra-faces/corners-1/ui-assembly-edges-2']),
    strictCount=dict(matrix=dict(run=matrix['runId'], codeStable=matrix['codeStable'], passed=matrix['passedCases'], comparedWithRun=before['runId'],
                                 sameBytesAsBefore={c['case']: (c['outputSha256'] == previous[c['case']] if c['case'] in previous else 'new case') for c in matrix['cases']}, cases=case_rows(matrix),
                                 evidence='tests/extra-faces/corners-1/matrix-9'),
                     searchWithCornersEnforced={k: strict[k] for k in ('target', 'limits', 'scope', 'accepted', 'seconds', 'layoutsTried', 'candidatesChecked')} |
                     dict(bestWorstZoneP95InFaces=min(c['worstP95InFaces'] for c in strict['candidates']), candidates=strict['candidates'],
                          evidence='tests/extra-faces/corners-1/strict-search-200/strict-search.json')),
    speed=dict(rule='Rows layouts are processed three at a time in other processes and taken in plan order; every output is the same bytes as one at a time.', workers=3,
               sameBytes='Every output had the same bytes one layout at a time and three at a time (runs 39949fbf3d5a / 318e43ae6356 and b20cd86d42e8 / 5b311cff1e2b).',
               secondsOneAtATime={('extra faces: ' if run is extra_serial else 'strict: ') + c['case']: round(c['observedSeconds'], 1) for run in (extra_serial, matrix_serial) for c in run['cases']},
               secondsThreeAtATime={('extra faces: ' if run is extra3 else 'strict: ') + c['case']: round(c['observedSeconds'], 1) for run in (extra3, matrix3) for c in run['cases']},
               note='One run per number on a machine with about 15 % background load; timings moved by ten seconds and more between runs.'),
    unitTests=dict(total=256, passed=256, new=['tests/test_corner_zones.py (11)', 'tests/test_crease_rows.py (16 added)', 'tests/test_quad_connectivity.py (1 added)']),
    directionMeasure=dict(date='2026-11-13', change='crease_rows.measure_path compares a row edge with the stretch of chain between the nearest chain points of its two ends; the one-face chain chord against a single row edge charged a corner of the chain to a row lying on it', limitUnchanged='30 degrees', effect='island 6 at 200 with extra faces: 445 quads (was 466); every other verification output keeps its bytes', nativeReference='runs/native-rim-investigation/native-captures/baseline/island6-keep-creases-{1.5k,3k,7.2k}-high30a1'),
    engine=dict(build=manifest['build'], executableSha256=manifest['executableSha256'], sourceArchiveSha256=manifest['sourceArchiveSha256'], capabilities=manifest['capabilities'],
                previousBuild=manifest['previousBuild'], previousExecutableSha256=manifest['previousExecutableSha256'],
                buildRecord='ghidra-workbench/work/retopo-guided-layout/build-records/constrained-sizes-19', patch='tests/extra-faces/corners-1/engine-patch-19.py'),
    engineParity=dict(note='With no face size listed the build returns the same bytes as constrained-edges-18.', **parity),
    sourceHashes={name: sha(ROOT / name) for name in ('corner_zones.py', 'crease_rows.py', 'source_features.py', 'open_surface.py', 'registered_features.py', 'feature_refine.py',
                                                       'quad_connectivity.py', 'worker.py', 'job_diagnostics.py', 'app.js')},
    untilItWorks=dict(rule='Extra faces allowed: when no layout at the target face size has every row, the guide loop and the corners, the base faces are made smaller in steps (face count times 1.5, then 2.25) with the checks of the target; when the steps run out of time the rows of the strict count are used and the corners reported.',
                      steps=[1.0, 1.5, 2.25], deadlinesSeconds=[200, 250, 300], lastResortUntilSeconds=400,
                      island6At750WithGuide=dict(baseFaces=1125, faces=1848, seconds=152.3, secondsOneLayoutAtATime=230.4, job='registered-5b311cff1e2b-island6-750-guide')),
    highTargets=dict(note='Island 6 without a guide, scratch runs with three layout processes, 2026-11-11/12. Targets above about 750 are rejected in both modes; see GUIDED_LAYOUT.md, High targets.',
                     userJob='5a80a3ff627b4ceb95bf9534075a065c (7,200, extra faces): killed at the ten-minute limit while laying out all 64 seeds; fixed, now rejected at about 430 s',
                     results={'1500 unchecked': 'accepted since 2026-11-13: 1,557 quads (was rejected, 493 s; best candidate had all 20 rows and a boundary 0.119 h off against 0.1 h)', '1500 extra faces': 'accepted since 2026-11-13: 2,998 quads, 28 of 28 rows, corners enforced (was rejected, 446 s)', '3000 extra faces': 'rejected, 427 s',
                              '7200 unchecked': 'rejected, 426 s; 7 to 13 of 29 rows missing before fitting in all 46 layouts', '7200 extra faces': 'rejected, 431 s'}),
    limitations=['Targets of 3,000 and 7,200 are rejected on island 6 (parallel creases a fraction of a face apart each need a row; the engine has no separation step).','The steps live inside the 420 s solver budget; a part that needs a third step, or slower layouts, ends in the last resort with its corners reported as coarse. No case ends there with the final code.',
                 'Rows and the guide loop still come from screening seeds; the engine guarantees neither.',
                 'Long parallel creases (rim wall, back step) are still one band; native keeps both with thin quads that fail this application\'s shape limits.',
                 'A chain two local faces long is all end zone: only the one-local-face end limit applies to it.',
                 'Corner zones are measured from source vertices and follow the source tessellation. Their limits are this application\'s; ZBrush is 0.011 h over the 95th-percentile limit on one foot.',
                 'Only island 6 was run with extra faces. Closed parts ignore the option.'])
target = ROOT / 'engine/guided-quadriflow/development/corner-rows-verification.json'
target.write_bytes((json.dumps(record, indent=1, allow_nan=False) + '\n').encode('utf-8'))
print(target, len(record['strictCount']['matrix']['cases']), 'matrix cases; same bytes as before:', record['strictCount']['matrix']['sameBytesAsBefore'])

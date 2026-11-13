# Open-source port: native capture scripts

Copies of the tracer forks used to capture ZBrush's ZRemesher on open parts while porting the
recovered pipeline to open sources (see `HANDOFF.md` §4.01 and the workbench's
`targets/zbrush/understanding/guided/OPEN_SOURCE_PORT.md`).

They run from `runs/native-rim-investigation/native-captures/scripts/prep/` (the `runs/` folder is
not tracked), next to `configs/` and with their output under `native-captures/prep/<name>`:

| Script | Fork of (workbench `targets/zbrush/experiments/python/`) | Captures |
|---|---|---|
| `trace_native_prep.py` | `trace_native_crossing_cleanup.py` | preparation, guide embedding, cut, extraction, relaxation |
| `trace_native_features.py` | `trace_native_feature_metrics.py` | the above plus 260290 path metrics and admitted paths |
| `trace_native_cut_graph.py` | `trace_native_torus_cut_graph.py` | seeds, every call of the cut connector and cut stage, gauge, 284ef0 |
| `trace_native_algorithm.py` | unchanged helper, root path only | |
| `native_geometry_stage.py` | workbench stage script plus symmetry off and optional Keep Creases at CTolerance | |
| `native_geometry_stage_parameter.py` | the October parameter tracer's stage script, flat-source fix | |

Each launches its own ZBrush batch process and refuses to run while a ZBrush session is open.
